"""
labeling_engine.py
------------------
This is the heart of the system. It manages which user gets which row to label.

What this file does:
1. Loads data from CSV files.
2. Gives out rows to users one by one (so two people don't work on the same row).
3. Saves the finished labels.
4. Handles users logging out by putting their unfinished tasks back in the queue.
"""

import threading
import logging
from collections import deque
from typing import Optional

from models import SourceRow
from storage import BaseStorage

class LabelingEngine:
    """
    The engine that manages the labeling process.
    """

    def __init__(self, storage: BaseStorage, master_file_path: str):
        self._logger = logging.getLogger("LabelingSystem")
        self._storage = storage
        self._master_file_path = master_file_path

        # A queue of rows that still need to be labeled
        self._row_queue: deque = deque()

        # Tracks which user is currently working on which row
        # Example: { "Alice": row_object }
        self._active_rows: dict = {}

        # A 'Lock' ensures that if two users ask for a row at the same time, 
        # the computer only gives one row to each person correctly.
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Loading Data
    # ------------------------------------------------------------------

    def load_source(self, csv_file_path: str) -> int:
        """
        Load rows from a CSV file into our queue.
        Returns the number of rows loaded.
        """
        rows = self._storage.load_source_csv(csv_file_path)
        self._row_queue = deque(rows)
        self._logger.info(f"Loaded {len(rows)} rows from {csv_file_path}")
        return len(rows)

    # ------------------------------------------------------------------
    # Giving Rows to Users
    # ------------------------------------------------------------------

    def get_next_row(self, user_name: str) -> Optional[SourceRow]:
        """
        Give a unique row to a user. 
        If they are already working on a row, give them that same row again.
        """
        with self._lock:
            # Check if user already has a row they didn't finish
            if user_name in self._active_rows:
                return self._active_rows[user_name]

            # If no more rows are left, return None
            if not self._row_queue:
                return None

            # Get the next row from the queue and assign it to the user
            next_row = self._row_queue.popleft()
            self._active_rows[user_name] = next_row
            return next_row

    # ------------------------------------------------------------------
    # Saving Finished Labels
    # ------------------------------------------------------------------

    def submit_label(self, user_name: str, label) -> bool:
        """
        Save a user's finished work and mark them as ready for a new task.
        """
        with self._lock:
            # Make sure the user actually has a task assigned
            if user_name not in self._active_rows:
                raise ValueError(f"User '{user_name}' has no active row.")

            active_row = self._active_rows[user_name]

            # Ensure they are submitting for the correct row
            if label.row_id != active_row.row_id:
                raise ValueError("Row ID mismatch!")

            # Convert the label data to a dictionary and save it to the CSV file
            label_dict = label.to_dict()
            success = self._storage.append_label(label_dict, self._master_file_path)

            if success:
                # Remove the row from 'active' because it's now finished
                del self._active_rows[user_name]
                self._logger.info(f"Saved label for row {active_row.row_id} by {user_name}")
            
            return success

    def release_row(self, user_name: str) -> bool:
        """
        If a user leaves without finishing, put their row back at the front of the line.
        """
        with self._lock:
            if user_name not in self._active_rows:
                return False 

            released_row = self._active_rows.pop(user_name)
            # Put it back at the FRONT so it's the next one someone else gets
            self._row_queue.appendleft(released_row)
            self._logger.info(f"Row {released_row.row_id} returned to queue by {user_name}")
            return True

    # ------------------------------------------------------------------
    # Status Helpers
    # ------------------------------------------------------------------

    def get_queue_size(self) -> int:
        """How many rows are still waiting?"""
        return len(self._row_queue)

    def is_finished(self) -> bool:
        """Are all rows finished?"""
        return len(self._row_queue) == 0 and len(self._active_rows) == 0
