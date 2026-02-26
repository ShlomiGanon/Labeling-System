"""
labeling_engine.py
------------------
This module coordinates the core labeling logic, ensuring that rows are distributed
uniquely and completed work is recorded systematically.
"""

import os
import csv
import threading
import logging
from collections import deque
from typing import Optional, List, Dict

from models import SourceRow
from storage import BaseStorage

class LabelingEngine:
    """
    Main engine that manages the lifecycle of a labeling project.
    It tracks remaining tasks and ensures thread-safe data access.
    """

    # Initializes a LabelingEngine instance for a specific results file and storage.
    # It sets up a FIFO queue for rows, a dictionary for active rows, and a set for processed IDs.
    # It does not return anything.
    def __init__(self, storage: BaseStorage, master_file_path: str):
        # Initializes a named logger for the labeling system.
        # Returns a Logger instance.
        self._logger = logging.getLogger("LabelingSystem")
        self._storage = storage
        self._master_file_path = master_file_path

        # Initializes a deque for the row queue to manage tasks in a first-in-first-out manner.
        # Returns an empty deque.
        self._row_queue: deque = deque()

        # Tracks rows currently being processed by labelers.
        # Format: { "username": SourceRow_object }
        self._active_rows: Dict[str, SourceRow] = {}

        # REASONING: Track completed IDs to prevent double labeling during incremental updates.
        self._processed_ids: set = set()
        # Scans the master results file to populate the set of already completed row IDs.
        # Returns None.
        self._load_processed_ids()

        # Creates a Reentrant Lock to ensure thread-safe operations on the engine's state.
        # Returns a Lock object.
        self._lock = threading.Lock()

    # Reads the master results CSV file to identify and record which rows have already been completed.
    # This prevents duplicating work when identical source data is reloaded.
    # It does not return anything.
    def _load_processed_ids(self):
        # Verifies if the master results file actually exists on the filesystem.
        # Returns True if it exists, False otherwise.
        if not os.path.exists(self._master_file_path):
            return

        try:
            # Opens the master results file for reading with UTF-8 encoding.
            # Returns a file object.
            with open(self._master_file_path, mode="r", encoding="utf-8-sig") as f:
                # Initializes a CSV dictionary reader to parse the file rows.
                # Returns a DictReader object.
                reader = csv.DictReader(f)
                for row in reader:
                    # Retrieves the unique identifier for the current row.
                    # Returns the row ID as a string or None.
                    rid = row.get("row_id")
                    if rid:
                        # Adds the row ID to the set of processed IDs to track completion.
                        # Returns None.
                        self._processed_ids.add(str(rid))
        except Exception as e:
            # Logs an error message if the file reading or parsing fails.
            # Returns None.
            self._logger.error(f"Error loading processed IDs from {self._master_file_path}: {e}")

    # Updates the engine's task queue with new rows from a source CSV file.
    # It filters out rows that are either already processed, currently active, or already in the queue.
    # Returns the integer count of new rows successfully added to the queue.
    def load_source(self, csv_file_path: str) -> int:
        with self._lock:
            # Refreshes the internal list of completed row IDs to ensure synchronization with the filesystem.
            # Returns None.
            self._load_processed_ids()
            
            # Delegates the loading of the source CSV data to the configured storage provider.
            # Returns a list of SourceRow objects.
            new_rows = self._storage.load_source_csv(csv_file_path)
            
            # Collects the IDs of all rows currently waiting in the queue for comparison.
            # Returns a set of row IDs.
            current_queued_ids = {row.row_id for row in self._row_queue}
            # Collects the IDs of all rows currently being processed by users.
            # Returns a set of row IDs.
            current_active_ids = {row.row_id for row in self._active_rows.values()}
            
            added_count = 0
            for row in new_rows:
                if (row.row_id not in self._processed_ids and 
                    row.row_id not in current_queued_ids and 
                    row.row_id not in current_active_ids):
                    # Inserts the new row into the back of the task queue.
                    # Returns None.
                    self._row_queue.append(row)
                    added_count += 1
            
            if added_count > 0:
                # Logs the number of newly added rows for auditing purposes.
                # Returns None.
                self._logger.info(f"Added {added_count} NEW rows from {csv_file_path}")
            return added_count

    # Assigns the next available task from the queue to a specific user.
    # If the user is already working on a row, it returns that specific row to ensure idempotency.
    # Returns a SourceRow object if a task is available, otherwise returns None.
    def get_next_row(self, user_name: str) -> Optional[SourceRow]:
        with self._lock:
            # Check if this user is already midway through a task.
            if user_name in self._active_rows:
                return self._active_rows[user_name]

            # If the queue is dry, there's no more work to do.
            if not self._row_queue:
                return None

            # Removes and returns the row at the front of the queue.
            # Returns a SourceRow object.
            next_row = self._row_queue.popleft()
            # Map the row to the user so we know who is working on it.
            self._active_rows[user_name] = next_row
            return next_row

    # Finalizes a labeling task by saving the user's input to the master results file.
    # It validates the submission against the assigned row and clears the user's active status.
    # Returns True if the label was successfully persisted, False otherwise.
    def submit_label(self, user_name: str, label) -> bool:
        with self._lock:
            # Ensure the state hasn't been corrupted or the session timed out.
            if user_name not in self._active_rows:
                # Raises an error if the user attempts to submit without an active task.
                # Returns a ValueError.
                raise ValueError(f"System Error: User '{user_name}' has no row checked out.")

            active_row = self._active_rows[user_name]

            # Integrity Check: The user must be submitting for the row they were actually assigned.
            if str(label.row_id) != str(active_row.row_id):
                # Raises an error if the submitted ID does not match the assigned ID.
                # Returns a ValueError.
                raise ValueError(f"ID Mismatch: User assigned {active_row.row_id}, but submitted {label.row_id}")

            # Converts the label object into a standard dictionary format for CSV storage.
            # Returns a dictionary.
            label_dict = label.to_dict()
            # Persists the label dictionary to the master results CSV file.
            # Returns True if successful, False otherwise.
            success = self._storage.append_label(label_dict, self._master_file_path)

            if success:
                # Marks the row ID as processed in the internal cache to avoid re-loading.
                # Returns None.
                self._processed_ids.add(str(active_row.row_id))
                # Removes the user from the tracking of active tasks.
                # Returns None.
                del self._active_rows[user_name]
                # Logs a confirmation of the saved labeling action.
                # Returns None.
                self._logger.info(f"Row {active_row.row_id} tagged by {user_name} and saved.")
            
            return success

    # Cancels an active labeling task and returns the row to the front of the queue.
    # This ensures that no tasks are lost if a user disconnects or leaves unexpectedly.
    # Returns True if a row was found and successfully released, False otherwise.
    def release_row(self, user_name: str) -> bool:
        with self._lock:
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
        return len(self._row_queue)

    # Reports the number of tasks currently being worked on by all active users.
    # Returns the integer count of entries in the active rows dictionary.
    def get_active_tasks_count(self) -> int:
        return len(self._active_rows)

    # Evaluates whether the labeling project has been completed in full.
    # It checks if both the queue is empty and no users have active tasks.
    # Returns True if no work remains, False otherwise.
    def is_finished(self) -> bool:
        return len(self._row_queue) == 0 and len(self._active_rows) == 0
