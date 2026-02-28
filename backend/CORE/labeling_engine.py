# labeling_engine.py
# ------------------
# This module coordinates the core labeling logic, ensuring that rows are distributed
# uniquely and completed work is recorded systematically.

import os
import csv
import threading
import logging
from collections import deque
from typing import Optional, List, Dict

from models import SourceRow
from storage import BaseStorage

# Main engine that manages the lifecycle of a labeling project.
# It tracks remaining tasks and ensures thread-safe data access.
class LabelingEngine:

    # Initializes a LabelingEngine instance for a specific results file and storage.
    # It sets up a FIFO queue for rows, a dictionary for active rows, and a set for processed IDs.
    # It does not return anything.
    def __init__(self, storage: BaseStorage, master_file_path: str):
        # Initializes a named logger for the labeling system.
        # Returns a Logger instance.
        self._logger = logging.getLogger("LabelingSystem")
        self._storage = storage
        self._master_file_path = master_file_path
        self._source_storages: Dict[str, BaseStorage] = {}

        # Initializes a deque for the row queue to manage tasks in a first-in-first-out manner.
        # Returns an empty deque.
        self._row_queue: deque = deque()

        # Tracks rows currently being processed by labelers.
        # Format: { "username": SourceRow_object }
        self._active_rows: Dict[str, SourceRow] = {}

        # REASONING: Track completed IDs to prevent double labeling during incremental updates.
        self._processed_ids: set = set()

        # Maps each source CSV path to its designated output (master) file.
        # Used to route annotations to the correct file when multiple sources are loaded.
        self._source_to_master: Dict[str, str] = {}

        # Scans the master results file to populate the set of already completed row IDs.
        # Returns None.
        self._load_processed_ids()

        # Creates a Reentrant Lock to ensure thread-safe operations on the engine's state.
        # Returns a Lock object.
        self._lock = threading.Lock()

    # Scans all known master files (project-level and per-source) to build the set of
    # already-completed row IDs. Accepts an optional extra path for a master not yet registered.
    # It does not return anything.
    def _load_processed_ids(self, current_master: str = None):
        # Collect every master file path we know about.
        paths_to_scan = {self._master_file_path}
        paths_to_scan.update(self._source_to_master.values())
        if current_master:
            paths_to_scan.add(current_master)

        for path in paths_to_scan:
            if not os.path.exists(path):
                continue
            try:
                with open(path, mode="r", encoding="utf-8-sig") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        rid = row.get("row_id")
                        if rid:
                            self._processed_ids.add(str(rid))
            except Exception as e:
                self._logger.error(f"Error loading processed IDs from {path}: {e}")

    # Updates the engine's task queue with rows from a source CSV file.
    # master_path: optional per-source output file; falls back to the project-level master.
    # Each loaded row is tagged with csv_file_path as its origin for annotation routing.
    # Returns the integer count of new rows added to the queue.
    def load_source(self, csv_file_path: str, master_path: str = None, storage: BaseStorage = None) -> int:
        with self._lock:
            loader = storage or self._storage
            # Resolve the output file for this source.
            effective_master = master_path or self._master_file_path
            # Scan all known masters (including this one) before filtering.
            self._load_processed_ids(current_master=effective_master)
            # Register source → master so submit_label can route correctly.
            self._source_to_master[csv_file_path] = effective_master
            self._source_storages[csv_file_path] = loader

            new_rows = loader.load_source_csv(csv_file_path)

            current_queued_ids = {row.row_id for row in self._row_queue}
            current_active_ids = {row.row_id for row in self._active_rows.values()}

            added_count = 0
            for row in new_rows:
                rid_str = str(row.row_id)
                if (rid_str not in self._processed_ids and
                        rid_str not in current_queued_ids and
                        rid_str not in current_active_ids):
                    row.source_csv = csv_file_path  # Tag row with its origin
                    self._row_queue.append(row)
                    added_count += 1

            if added_count > 0:
                self._logger.info(f"Added {added_count} NEW rows from {csv_file_path}")
            return added_count

    # Loads rows from multiple source CSVs and merges them into the queue.
    # master_paths: optional list of per-source output files, aligned by index with csv_file_paths.
    # Returns the total count of new rows added across all files.
    def load_sources(self, csv_file_paths: List[str], master_paths: List[str] = None, storages: List[BaseStorage] = None) -> int:
        total = 0
        for i, path in enumerate(csv_file_paths):
            master = master_paths[i] if master_paths and i < len(master_paths) else None
            storage = storages[i] if storages and i < len(storages) else None
            total += self.load_source(path, master_path=master, storage=storage)
        return total

    # Assigns the next available task from the queue to a specific user.
    # If the user is already working on a row, it returns that specific row to ensure idempotency.
    # Returns a SourceRow object if a task is available, otherwise returns None.
    def get_next_row(self, user_name: str) -> Optional[SourceRow]:
        # Protects the queue access and user assignment with a thread lock.
        with self._lock:
            # Check if this user is already midway through a task.
            if user_name in self._active_rows:
                # Returns the original row assigned to the user.
                return self._active_rows[user_name]

            # If the queue is dry, there's no more work to do.
            if not self._row_queue:
                # Returns None to indicate that the queue is empty.
                return None

            # Removes and returns the row at the front of the queue.
            # Returns a SourceRow object.
            next_row = self._row_queue.popleft()
            # Map the row to the user so we know who is working on it.
            # Returns None.
            self._active_rows[user_name] = next_row
            return next_row

    # Finalizes a labeling task by saving the user's input to the master results file.
    # It validates the submission against the assigned row and clears the user's active status.
    # Returns True if the label was successfully persisted, False otherwise.
    def submit_label(self, user_name: str, label) -> bool:
        # Prevents concurrent modifications to the results tracking state.
        with self._lock:
            # Ensure the state hasn't been corrupted or the session timed out.
            if user_name not in self._active_rows:
                # Raises an error if the user attempts to submit without an active task.
                # Returns a ValueError.
                raise ValueError(f"System Error: User '{user_name}' has no row checked out.")

            # Retrieves the row metadata currently assigned to the user.
            active_row = self._active_rows[user_name]

            # Integrity Check: The user must be submitting for the row they were actually assigned.
            if str(label.row_id) != str(active_row.row_id):
                # Raises an error if the submitted ID does not match the assigned ID.
                # Returns a ValueError.
                raise ValueError(f"ID Mismatch: User assigned {active_row.row_id}, but submitted {label.row_id}")

            label_dict = label.to_dict()

            # Route to the per-source master if registered; fall back to the project master
            # for single-CSV projects and backward-compat cases where source_csv is unset.
            target_master = (
                self._source_to_master.get(active_row.source_csv)
                or self._master_file_path
            )
            target_storage = self._source_storages.get(active_row.source_csv, self._storage)
            success = target_storage.append_label(label_dict, target_master)

            if success:
                self._processed_ids.add(str(active_row.row_id))
                del self._active_rows[user_name]
                self._logger.info(
                    f"Row {active_row.row_id} tagged by {user_name} "
                    f"and saved to {os.path.basename(target_master)}"
                )
            
            # Returns whether the data was successfully written to the storage backend.
            return success

    # Cancels an active labeling task and returns the row to the front of the queue.
    # This ensures that no tasks are lost if a user disconnects or leaves unexpectedly.
    # Returns True if a row was found and successfully released, False otherwise.
    def release_row(self, user_name: str) -> bool:
        # Uses the Reentrant Lock to update the user's status safely.
        with self._lock:
            # Verifies if the user actually has an active assignment to release.
            if user_name not in self._active_rows:
                return False 

            # Retrieves and removes the row currently assigned to the user.
            # Returns a SourceRow object.
            released_row = self._active_rows.pop(user_name)
            # Places the released row back at the very front of the queue.
            # Returns None.
            self._row_queue.appendleft(released_row)
            # Logs the recycling of the task row back into the available pool.
            # Returns None.
            self._logger.info(f"Row {released_row.row_id} recycled into queue (User: {user_name})")
            return True

    # Reports the total number of tasks currently waiting in the processing queue.
    # Returns the integer count of queued rows.
    def get_queue_size(self) -> int:
        # Returns the number of items stored in the task deque.
        return len(self._row_queue)

    # Reports the number of tasks currently being worked on by all active users.
    # Returns the integer count of entries in the active rows dictionary.
    def get_active_tasks_count(self) -> int:
        # Returns the number of active assignments.
        return len(self._active_rows)

    # Evaluates whether the labeling project has been completed in full.
    # It checks if both the queue is empty and no users have active tasks.
    # Returns True if no work remains, False otherwise.
    def is_finished(self) -> bool:
        # Returns True if both the queue is empty AND no users have active rows.
        return len(self._row_queue) == 0 and len(self._active_rows) == 0
