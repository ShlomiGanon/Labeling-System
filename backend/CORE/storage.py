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

import re

def build_source_row_from_dict(row_dict: dict, row_index: int) -> SourceRow:
    """
    Creates a SourceRow object by inspecting the content of every cell in a CSV line,
    ignoring column headers.

    - Finds the first cell that looks like an image URL.
    - Finds the longest remaining text cell that isn't the URL.
    - Tries to find an 'id' column, otherwise falls back to row_index.
    """
    row_id = str(row_index)
    
    # Try to find a dedicated ID column case-insensitively
    for k, v in row_dict.items():
        if k and str(k).lower().strip() in ("id", "identifier", "row_id", "index"):
            row_id = str(v).strip()
            break
            
    image_path = ""
    text_content = ""
    
    # Regex to identify image URLs or Google Drive links
    img_pattern = re.compile(
        r'^(https?://.*\.(?:png|jpg|jpeg|gif|webp|svg)(?:\?.*)?)$|'  # Standard image URLs
        r'^(https?://(?:drive\.google\.com|docs\.google\.com)/.*)$', # Google Drive/Docs links
        re.IGNORECASE
    )

    # 1. Find the Image URL
    for val in row_dict.values():
        str_val = str(val).strip()
        if not str_val:
            continue
            
        if img_pattern.search(str_val):
            image_path = str_val
            break # Stop at the first image found
            
    # 2. Find the Text Content (longest string that isn't the image URL)
    longest_text = ""
    for val in row_dict.values():
        str_val = str(val).strip()
        
        # Skip empty strings and the string we already identified as the image
        if not str_val or str_val == image_path:
            continue
            
        # We assume the longest remaining string is the actual text to label
        if len(str_val) > len(longest_text):
            longest_text = str_val
            
    text_content = longest_text

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

            # Remove identify_columns
            for idx, raw_row in enumerate(reader):
                row_obj = build_source_row_from_dict(raw_row, idx + 1)
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

# ---------------------------------------------------------------------------
# Remote / URL Storage
# ---------------------------------------------------------------------------

import urllib.request
import io

class RemoteStorage(BaseStorage):
    """
    Implementation of BaseStorage for remote files (S3 public links, Google Drive public links).
    """

    def load_source_csv(self, file_path: str) -> List[SourceRow]:
        """
        Downloads a remote CSV and parses it.
        
        Supports:
        - Direct links to CSVs.
        - Google Drive 'view' links (automatically converted to export links if possible).
        """
        url = file_path
        
        # --- Robust Google Drive Link Handling ---
        # 1. Google Sheets: .../spreadsheets/d/<ID>/...
        # 2. Uploaded File: .../file/d/<ID>/...
        if "drive.google.com" in url or "docs.google.com" in url:
            file_id = None
            if "/d/" in url:
                file_id = url.split("/d/")[1].split("/")[0]
            elif "id=" in url:
                file_id = url.split("id=")[1].split("&")[0]

            if file_id:
                if "/spreadsheets/" in url:
                    # It's a Google Sheet -> Use export
                    url = f"https://docs.google.com/spreadsheets/d/{file_id}/export?format=csv"
                else:
                    # It's a regular uploaded file -> Use direct download endpoint
                    url = f"https://docs.google.com/uc?export=download&id={file_id}"
        
        # We add a User-Agent to avoid some basic blocks from GDrive
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            content = response.read().decode("utf-8-sig")
            
            # Check if Google Drive returned an HTML sign-in page instead of a CSV
            content_lower = content.strip().lower()
            if content_lower.startswith('<!doctype html') or content_lower.startswith('<html'):
                raise ValueError("The provided URL requires authentication or is not a raw CSV file. Make sure the link is publicly accessible ('Anyone with the link').")

            csv_file = io.StringIO(content)
            reader = csv.DictReader(csv_file)
            
            if not reader.fieldnames: return []
            
            rows = []
            for idx, raw_row in enumerate(reader):
                row_obj = build_source_row_from_dict(raw_row, idx + 1)
                if row_obj: rows.append(row_obj)
            return rows


    def get_media_link(self, path: str) -> str:
        # For remote storage, we assume the paths in CSV are already URLs 
        # or relative to the same bucket. For now, return as is.
        return path

    def append_label(self, label_data: dict, master_file_path: str) -> bool:
        # Saving results back to remote storage (S3/GDrive) typically requires 
        # API writes. For simplicity, we keep results in a local CSV.
        # This can be extended to upload the master file back to S3 after каждой saving.
        local = LocalStorage()
        return local.append_label(label_data, master_file_path)

# NOTE: For full S3/GDrive integration (private files, writing back), 
# libraries like boto3 and google-api-python-client would be required.
