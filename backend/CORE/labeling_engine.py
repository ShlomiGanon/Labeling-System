# Core queue and submit logic for labeling tasks.

import os
import csv
import threading
import logging
from collections import deque
from typing import Optional, List, Dict

from models import SourceRow
from storage import BaseStorage


class LabelingEngine:
    def __init__(self, storage: BaseStorage, master_file_path: str):
        self._logger = logging.getLogger("LabelingSystem")
        self._storage = storage
        self._master_file_path = master_file_path
        self._source_storages: Dict[str, BaseStorage] = {}
        self._row_queue: deque = deque()
        self._active_rows: Dict[str, SourceRow] = {}
        # Keep finished ids out of the queue when sources are reloaded.
        self._processed_ids: set = set()
        # Each source can write to a different output file.
        self._source_to_master: Dict[str, str] = {}
        self._load_processed_ids()
        self._lock = threading.Lock()

    # Read existing outputs so we do not assign the same row twice.
    def _load_processed_ids(self, current_master: str = None):
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

    # Load one source and add only rows that are still available.
    def load_source(self, csv_file_path: str, master_path: str = None, storage: BaseStorage = None) -> int:
        with self._lock:
            loader = storage or self._storage
            effective_master = master_path or self._master_file_path
            self._load_processed_ids(current_master=effective_master)
            self._source_to_master[csv_file_path] = effective_master
            self._source_storages[csv_file_path] = loader

            new_rows = loader.load_source_csv(csv_file_path)
            current_queued_ids = {row.row_id for row in self._row_queue}
            current_active_ids = {row.row_id for row in self._active_rows.values()}

            added_count = 0
            for row in new_rows:
                rid_str = str(row.row_id)
                if (
                    rid_str not in self._processed_ids
                    and rid_str not in current_queued_ids
                    and rid_str not in current_active_ids
                ):
                    # Keep the source path so submit_label knows where to save.
                    row.source_csv = csv_file_path
                    self._row_queue.append(row)
                    added_count += 1

            if added_count > 0:
                self._logger.info(f"Added {added_count} NEW rows from {csv_file_path}")
            return added_count

    # Load many sources into the same queue.
    def load_sources(
        self,
        csv_file_paths: List[str],
        master_paths: List[str] = None,
        storages: List[BaseStorage] = None,
    ) -> int:
        total = 0
        for i, path in enumerate(csv_file_paths):
            master = master_paths[i] if master_paths and i < len(master_paths) else None
            storage = storages[i] if storages and i < len(storages) else None
            total += self.load_source(path, master_path=master, storage=storage)
        return total

    # A user keeps the same row until they submit or release it.
    def get_next_row(self, user_name: str) -> Optional[SourceRow]:
        with self._lock:
            if user_name in self._active_rows:
                return self._active_rows[user_name]

            if not self._row_queue:
                return None

            next_row = self._row_queue.popleft()
            self._active_rows[user_name] = next_row
            return next_row

    # Save the label for the row currently assigned to this user.
    def submit_label(self, user_name: str, label) -> bool:
        with self._lock:
            if user_name not in self._active_rows:
                raise ValueError(f"System Error: User '{user_name}' has no row checked out.")

            active_row = self._active_rows[user_name]
            if str(label.row_id) != str(active_row.row_id):
                raise ValueError(f"ID Mismatch: User assigned {active_row.row_id}, but submitted {label.row_id}")

            label_dict = label.to_dict()
            # Save to the output file that belongs to this source.
            target_master = self._source_to_master.get(active_row.source_csv) or self._master_file_path
            target_storage = self._source_storages.get(active_row.source_csv, self._storage)
            success = target_storage.append_label(label_dict, target_master)

            if success:
                self._processed_ids.add(str(active_row.row_id))
                del self._active_rows[user_name]
                self._logger.info(
                    f"Row {active_row.row_id} tagged by {user_name} "
                    f"and saved to {os.path.basename(target_master)}"
                )
            return success

    # Put the active row back in front of the queue.
    def release_row(self, user_name: str) -> bool:
        with self._lock:
            if user_name not in self._active_rows:
                return False

            released_row = self._active_rows.pop(user_name)
            self._row_queue.appendleft(released_row)
            self._logger.info(f"Row {released_row.row_id} recycled into queue (User: {user_name})")
            return True

    def get_queue_size(self) -> int:
        return len(self._row_queue)

    def get_active_tasks_count(self) -> int:
        return len(self._active_rows)

    def is_finished(self) -> bool:
        return len(self._row_queue) == 0 and len(self._active_rows) == 0
