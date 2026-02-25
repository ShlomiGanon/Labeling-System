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

    def __init__(self, storage: BaseStorage, master_file_path: str):
        """
        Initializes a LabelingEngine for a specific results file.

        Args:
            storage (BaseStorage): The storage provider used to load/save data.
            master_file_path (str): The absolute path to the results CSV file.
        """
        self._logger = logging.getLogger("LabelingSystem")
        self._storage = storage
        self._master_file_path = master_file_path

        # A First-In-First-Out (FIFO) queue for rows awaiting labeling.
        self._row_queue: deque = deque()

        # Tracks rows currently being processed by labelers.
        # Format: { "username": SourceRow_object }
        self._active_rows: Dict[str, SourceRow] = {}

        # REASONING: Track completed IDs to prevent double labeling during incremental updates.
        self._processed_ids: set = set()
        self._load_processed_ids()

        # REASONING: A global lock is used to prevent "Double Popping".
        self._lock = threading.Lock()

    def _load_processed_ids(self):
        """
        Reads the master results file to identify which rows are already completed.
        """
        if not os.path.exists(self._master_file_path):
            return

        try:
            with open(self._master_file_path, mode="r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    rid = row.get("row_id")
                    if rid:
                        self._processed_ids.add(str(rid))
        except Exception as e:
            self._logger.error(f"Error loading processed IDs from {self._master_file_path}: {e}")

    def load_source(self, csv_file_path: str) -> int:
        """
        Populate or update the engine's internal queue with data from a source CSV.
        Only adds rows that aren't already processed, active, or in the queue.

        Args:
            csv_file_path (str): Path to the CSV with image/text data.

        Returns:
            int: Number of NEW rows successfully added to the queue.
        """
        with self._lock:
            # Refresh processed IDs just in case the file was modified externally
            self._load_processed_ids()
            
            new_rows = self._storage.load_source_csv(csv_file_path)
            
            # Identify what's already in the queue or active
            current_queued_ids = {row.row_id for row in self._row_queue}
            current_active_ids = {row.row_id for row in self._active_rows.values()}
            
            added_count = 0
            for row in new_rows:
                if (row.row_id not in self._processed_ids and 
                    row.row_id not in current_queued_ids and 
                    row.row_id not in current_active_ids):
                    self._row_queue.append(row)
                    added_count += 1
            
            if added_count > 0:
                self._logger.info(f"Added {added_count} NEW rows from {csv_file_path}")
            return added_count

    def get_next_row(self, user_name: str) -> Optional[SourceRow]:
        """
        Assigns a new row to a user. If the user already has an active row, 
        returns the existing one (Idempotent assignment).

        Args:
            user_name (str): The name/ID of the current labeler.

        Returns:
            Optional[SourceRow]: The assigned row data, or None if the queue is empty.
        """
        with self._lock:
            # Check if this user is already midway through a task.
            if user_name in self._active_rows:
                return self._active_rows[user_name]

            # If the queue is dry, there's no more work to do.
            if not self._row_queue:
                return None

            # Atomically pull the oldest row from the queue.
            next_row = self._row_queue.popleft()
            # Map the row to the user so we know who is working on it.
            self._active_rows[user_name] = next_row
            return next_row

    def submit_label(self, user_name: str, label) -> bool:
        """
        Records the completed work and marks the user as available for a new row.

        Args:
            user_name (str): The labeler's identity.
            label (LabelObject): Any object from models.py that has a to_dict() method.

        Returns:
            bool: True if storage was successful.
        """
        with self._lock:
            # Ensure the state hasn't been corrupted or the session timed out.
            if user_name not in self._active_rows:
                raise ValueError(f"System Error: User '{user_name}' has no row checked out.")

            active_row = self._active_rows[user_name]

            # Integrity Check: The user must be submitting for the row they were actually assigned.
            if str(label.row_id) != str(active_row.row_id):
                raise ValueError(f"ID Mismatch: User assigned {active_row.row_id}, but submitted {label.row_id}")

            # Persist to disk via our storage implementation.
            label_dict = label.to_dict()
            success = self._storage.append_label(label_dict, self._master_file_path)

            if success:
                # Update processed IDs so we don't reload this row if the source CSV still has it
                self._processed_ids.add(str(active_row.row_id))
                # Cleanup internal state once the data is safely on disk.
                del self._active_rows[user_name]
                self._logger.info(f"Row {active_row.row_id} tagged by {user_name} and saved.")
            
            return success

    def release_row(self, user_name: str) -> bool:
        """
        Returns a row to the queue if the user leaves the session without submitting.
        Prevents tasks from being "lost" if a user closes their browser.

        Args:
            user_name (str): The labeler who is leaving.

        Returns:
            bool: True if a row was found and released.
        """
        with self._lock:
            if user_name not in self._active_rows:
                return False 

            # Remove from 'active' and put back into the 'to-do' list.
            released_row = self._active_rows.pop(user_name)
            # REASONING: We use appendleft() so the released row stays at the front
            # of the line for the next person who asks for a task.
            self._row_queue.appendleft(released_row)
            self._logger.info(f"Row {released_row.row_id} recycled into queue (User: {user_name})")
            return True

    def get_queue_size(self) -> int:
        """
        Returns the number of rows yet to be assigned.
        """
        return len(self._row_queue)

    def get_active_tasks_count(self) -> int:
        """
        Returns the number of rows currently assigned to labelers and in progress.

        Returns:
            int: The current number of rows in the _active_rows dictionary.
        """
        return len(self._active_rows)

    def is_finished(self) -> bool:
        """
        Determines if there is absolutely no work remaining (nothing in the queue
        and no tasks currently active with labelers).

        Returns:
            bool: True if all tasks are completed or no tasks were loaded, False otherwise.
        """
        return len(self._row_queue) == 0 and len(self._active_rows) == 0
