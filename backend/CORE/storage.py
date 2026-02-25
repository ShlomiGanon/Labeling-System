"""
storage.py
----------
Handles the persistence layer of the system.
Abstracts the way rows are loaded from source files and labels are saved.
"""

import os
import csv
import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Tuple

from models import SourceRow

# ---------------------------------------------------------------------------
# Storage Base Class
# ---------------------------------------------------------------------------

class BaseStorage(ABC):
    """
    Abstract Base Class (blueprint) for any storage system (Local, S3, Google Drive, etc.).
    Ensures that different storage backends provide a consistent interface.
    """

    @abstractmethod
    def load_source_csv(self, file_path: str) -> List[SourceRow]:
        """
        Reads a CSV file and converts its contents into a list of SourceRow objects.

        Args:
            file_path (str): Path to the source file.

        Returns:
            List[SourceRow]: A list of rows ready for labeling.
        """
        pass

    @abstractmethod
    def get_media_link(self, path: str) -> str:
        """
        Converts a relative file path or internal ID into a displayable URL or absolute path.

        Args:
            path (str): The raw path from the CSV.

        Returns:
            str: A link that the frontend or browser can use to display the media.
        """
        pass

    @abstractmethod
    def append_label(self, label_data: dict, master_path: str) -> bool:
        """
        Appends a completed labeling result to the master results file.

        Args:
            label_data (dict): The data dictionary to save.
            master_path (str): Path to the results file.

        Returns:
            bool: True if saving was successful.
        """
        pass


# ---------------------------------------------------------------------------
# CSV Helpers
# ---------------------------------------------------------------------------

def identify_columns(fieldnames: List[str]) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Analyzes CSV column headers to guess which columns contain the ID, Image, and Text.
    This makes the system flexible with different CSV structures.

    Args:
        fieldnames (List[str]): The header names found in the CSV.

    Returns:
        Tuple[str, str, str]: (ID column name, Image column name, Text column name). 
                              Some might be None if not found.
    """
    id_col, image_col, text_col = None, None, None
    fields = [f.lower().strip() for f in fieldnames]
    
    # Heuristic for ID: look for 'id', 'identifier', etc.
    for idx, f in enumerate(fields):
        if f in ("id", "identifier", "row_id", "index"):
            id_col = fieldnames[idx]
            break
            
    # Heuristic for Images and Text: check for common descriptive keywords.
    for idx, f in enumerate(fields):
        if f in ("image_url", "image_path", "image", "url" , "img"):
            image_col = fieldnames[idx]
        if f in ("text", "text_content", "content", "caption", "description"):
            text_col = fieldnames[idx]

    # Fallback Mechanism:
    # If image/text columns aren't found by name, we make a best-effort guess by index.
    if not image_col and len(fieldnames) > 0:
        image_col = fieldnames[min(1, len(fieldnames)-1)]
    if not text_col and len(fieldnames) > 0:
        text_col = fieldnames[0]
        
    return id_col, image_col, text_col

def build_source_row_from_dict(row_dict: dict, row_index: int, id_col=None, image_col=None, text_col=None) -> SourceRow:
    """
    Creates a SourceRow object from a dictionary representing a CSV line.

    Args:
        row_dict (dict): The raw data from one CSV line.
        row_index (int): The 1-based index of the row in the file (used as fallback ID).
        id_col (str): The identified ID column name.
        image_col (str): The identified Image column name.
        text_col (str): The identified Text column name.

    Returns:
        SourceRow: The structured data object.
    """
    # Prefer assigned ID, otherwise use the line number.
    row_id = str(row_dict.get(id_col, "")).strip() if id_col else str(row_index)
    
    # Extract data using the identified column mappings.
    image_path = str(row_dict.get(image_col, "")).strip() if image_col else ""
    text_content = str(row_dict.get(text_col, "")).strip() if text_col else ""

    return SourceRow(row_id=row_id, image_path=image_path, text_content=text_content)


# ---------------------------------------------------------------------------
# Local Filesystem Storage
# ---------------------------------------------------------------------------

class LocalStorage(BaseStorage):
    """
    Implementation of BaseStorage for local file systems.
    Handles CSV files on the local disk and maps images to absolute local paths.
    """

    def load_source_csv(self, file_path: str) -> List[SourceRow]:
        """
        Reads a local CSV file and parses it into SourceRow objects.

        Args:
            file_path (str): Local path to the CSV.

        Returns:
            List[SourceRow]: Parsed data rows.
        """
        logger = logging.getLogger("LabelingSystem")
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        rows = []
        # Using utf-8-sig to handle files with Byte Order Mark (BOM) properly.
        with open(file_path, mode="r", encoding="utf-8-sig", newline="") as csv_file:
            reader = csv.DictReader(csv_file)
            
            if not reader.fieldnames: return []

            # Map the CSV headers once for the entire file.
            id_col, img_col, txt_col = identify_columns(reader.fieldnames)

            for idx, raw_row in enumerate(reader):
                row_obj = build_source_row_from_dict(raw_row, idx + 1, id_col, img_col, txt_col)
                if row_obj: rows.append(row_obj)

        return rows

    def get_media_link(self, path: str) -> str:
        """
        Resolves a local image path.
        If the path is already a URL, it's returned as-is.
        Otherwise, an absolute filesystem path is generated.

        Args:
            path (str): Relative or absolute path from the CSV.

        Returns:
            str: The resolved path/URL.
        """
        if path.startswith("http://") or path.startswith("https://"):
            return path
        return os.path.abspath(path)

    def append_label(self, label_data: dict, master_file_path: str) -> bool:
        """
        Appends label data to a local CSV file.
        Automatically handles creating the file and writing headers if it doesn't exist yet.

        Args:
            label_data (dict): Data to be appended.
            master_file_path (str): Path to the results CSV.

        Returns:
            bool: True if write was successful.
        """
        try:
            fieldnames = list(label_data.keys())
            file_exists = os.path.isfile(master_file_path)

            # Open file in 'append' mode ('a').
            with open(master_file_path, mode="a", encoding="utf-8-sig", newline="") as csv_file:
                writer = csv.DictWriter(csv_file, fieldnames=fieldnames)

                # Write header only on the very first entry.
                if not file_exists:
                    writer.writeheader()

                writer.writerow(label_data)
            return True

        except Exception as error:
            # We use print here as a simple backup, but normally would log this.
            print(f"Error saving label: {error}")
            return False

# NOTE: S3Storage and GDriveStorage were removed to keep the code clean.
# They can be added back if cloud storage is needed in the future.
