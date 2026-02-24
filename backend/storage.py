"""
storage.py
----------
This file handles how data is read from and saved to files.

What this file does:
1. Defines a 'BaseStorage' plan that all storage types must follow.
2. Implements 'LocalStorage' (for files on your own computer).
3. Includes helpers to automatically figure out which CSV column is for images and which is for text.
"""

import csv
import os
import logging
from abc import ABC, abstractmethod
from typing import Optional
from models import SourceRow

# ---------------------------------------------------------------------------
# Storage Base Class
# ---------------------------------------------------------------------------

class BaseStorage(ABC):
    """
    This is a blueprint for any storage system (Local, S3, Google Drive, etc.).
    """

    @abstractmethod
    def load_source_csv(self, file_path: str) -> list:
        """How to read a CSV file into a list of rows."""
        pass

    @abstractmethod
    def get_media_link(self, path: str) -> str:
        """How to get a link to an image file."""
        pass

    @abstractmethod
    def append_label(self, label_data: dict, master_path: str) -> bool:
        """How to save a finished label to the results file."""
        pass


# ---------------------------------------------------------------------------
# CSV Helpers
# ---------------------------------------------------------------------------

def identify_columns(fieldnames: list):
    """
    Search through the column names of a CSV and try to guess which one is:
    - The ID
    - The Image URL/Path
    - The Text content
    """
    id_col, image_col, text_col = None, None, None
    fields = [f.lower().strip() for f in fieldnames]
    
    # Try common names for ID
    for idx, f in enumerate(fields):
        if f in ("id", "identifier", "row_id", "index"):
            id_col = fieldnames[idx]
            break
            
    # Try common names for images and text
    for idx, f in enumerate(fields):
        if f in ("image_url", "image_path", "image", "url" , "img"):
            image_col = fieldnames[idx]
        if f in ("text", "text_content", "content", "caption", "description"):
            text_col = fieldnames[idx]

    # If we still can't find them, default to the first columns
    if not image_col and len(fieldnames) > 0:
        image_col = fieldnames[min(1, len(fieldnames)-1)]
    if not text_col and len(fieldnames) > 0:
        text_col = fieldnames[0]
        
    return id_col, image_col, text_col

def build_source_row_from_dict(row_dict: dict, row_index: int, id_col=None, image_col=None, text_col=None) -> SourceRow:
    """
    Create a 'SourceRow' object from a single CSV line.
    """
    # Get ID or use the row number
    row_id = str(row_dict.get(id_col, "")).strip() if id_col else str(row_index)
    
    # Get image and text
    image_path = str(row_dict.get(image_col, "")).strip() if image_col else ""
    text_content = str(row_dict.get(text_col, "")).strip() if text_col else ""

    return SourceRow(row_id=row_id, image_path=image_path, text_content=text_content)


# ---------------------------------------------------------------------------
# Local Filesystem Storage
# ---------------------------------------------------------------------------

class LocalStorage(BaseStorage):
    """
    Handles files stored on your local computer.
    """

    def load_source_csv(self, file_path: str) -> list:
        """Read a local CSV file."""
        logger = logging.getLogger("LabelingSystem")
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        rows = []
        with open(file_path, mode="r", encoding="utf-8-sig", newline="") as csv_file:
            reader = csv.DictReader(csv_file)
            
            if not reader.fieldnames: return []

            # Figure out column names
            id_col, img_col, txt_col = identify_columns(reader.fieldnames)

            for idx, raw_row in enumerate(reader):
                row_obj = build_source_row_from_dict(raw_row, idx + 1, id_col, img_col, txt_col)
                if row_obj: rows.append(row_obj)

        return rows

    def get_media_link(self, path: str) -> str:
        """Return the absolute path to an image."""
        if path.startswith("http://") or path.startswith("https://"):
            return path
        return os.path.abspath(path)

    def append_label(self, label_data: dict, master_file_path: str) -> bool:
        """Add a new line of finished labeling work to the results CSV."""
        try:
            fieldnames = list(label_data.keys())
            file_exists = os.path.isfile(master_file_path)

            # Open file in 'append' mode
            with open(master_file_path, mode="a", encoding="utf-8", newline="") as csv_file:
                writer = csv.DictWriter(csv_file, fieldnames=fieldnames)

                # Write header only if file is new
                if not file_exists:
                    writer.writeheader()

                writer.writerow(label_data)
            return True

        except Exception as error:
            print(f"Error saving label: {error}")
            return False

# NOTE: S3Storage and GDriveStorage were removed to keep the code clean.
# They can be added back if cloud storage is needed in the future.
