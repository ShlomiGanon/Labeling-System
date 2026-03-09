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

# Analyzes CSV column headers to guess which columns contain the ID, Image, and Text data.
# This makes the system flexible with different CSV structures.
# Returns a tuple containing the guessed (ID column name, Image column name, Text column name).
def identify_columns(fieldnames: List[str]) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    id_col, image_col, text_col = None, None, None
    # Normalizes field names by converting to lowercase and stripping whitespace for consistent comparison.
    # Returns a list of cleaned field names.
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
        # Defaults to the second column for images if no name match is found.
        # Returns the header name.
        image_col = fieldnames[min(1, len(fieldnames)-1)]
    if not text_col and len(fieldnames) > 0:
        # Defaults to the first column for text if no name match is found.
        # Returns the header name.
        text_col = fieldnames[0]
        
    return id_col, image_col, text_col

import re

# Creates a SourceRow object by inspecting the content of every cell in a CSV line.
# It uses heuristics and regex to identify image URLs and the primary text content.
# Returns a SourceRow object containing the extracted data.
def build_source_row_from_dict(row_dict: dict, row_index: int) -> SourceRow:
    row_id = str(row_index)
    
    # Try to find a dedicated ID column case-insensitively
    for k, v in row_dict.items():
        if k and str(k).lower().strip() in ("id", "identifier", "row_id", "index"):
            # Extracts the value from a column identified as the unique identifier.
            # Returns a string.
            row_id = str(v).strip()
            break
            
    image_path = ""
    text_content = ""
    
    # Compiles a regular expression pattern to identify image URLs or Google Drive links.
    # Returns a Regex object.
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
            
        # Checks if the cell value matches the predefined image URL pattern.
        # Returns a Match object or None.
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
            
        # Selects the longest remaining string as the textual content to be labeled.
        # Returns None (updates the longest_text variable).
        if len(str_val) > len(longest_text):
            longest_text = str_val
            
    text_content = longest_text

    # Returns a newly constructed SourceRow data object.
    return SourceRow(row_id=row_id, image_path=image_path, text_content=text_content)


# ---------------------------------------------------------------------------
# Local Filesystem Storage
# ---------------------------------------------------------------------------

class LocalStorage(BaseStorage):
    # Implementation of BaseStorage for local file systems.
    # Handles CSV files on the local disk and maps images to absolute local paths.

    # Implementation of BaseStorage for local file systems.
    # Reads a local CSV file and parses it into SourceRow objects.
    # Returns a list of SourceRow objects containing the parsed data.
    def load_source_csv(self, file_path: str) -> List[SourceRow]:
        # Retrieves the named logger for the labeling system.
        # Returns a Logger instance.
        logger = logging.getLogger("LabelingSystem")
        # Verifies if the source file exists on the local disk.
        # Returns True if it exists, False otherwise.
        if not os.path.exists(file_path):
            # Raises an error if the specified file path is invalid.
            # Returns a FileNotFoundError.
            raise FileNotFoundError(f"File not found: {file_path}")

        rows = []
        # Opens the local CSV file with UTF-8 encoding and BOM handling.
        # Returns a file object.
        with open(file_path, mode="r", encoding="utf-8-sig", newline="") as csv_file:
            # Initializes a CSV dictionary reader to iterate through the rows.
            # Returns a DictReader instance.
            reader = csv.DictReader(csv_file)
            
            if not reader.fieldnames: return []

            # Remove identify_columns
            for idx, raw_row in enumerate(reader):
                # Converts a raw dictionary row into a structured SourceRow object.
                # Returns a SourceRow object.
                row_obj = build_source_row_from_dict(raw_row, idx + 1)
                if row_obj: 
                    # Appends the structured row to the results list.
                    # Returns None.
                    rows.append(row_obj)

        return rows

    # Resolves a local metadata path or URL into a fully usable link for the frontend.
    # If the path is already a URL, it is returned as is; otherwise, it's converted to an absolute path.
    # Returns a string representing the absolute path or URL.
    def get_media_link(self, path: str) -> str:
        # Checks if the path starts with standard web protocols.
        # Returns True if it is a URL, False otherwise.
        if path.startswith("http://") or path.startswith("https://"):
            return path
        # Converts a relative filesystem path into a globally unique absolute path.
        # Returns an absolute path string.
        return os.path.abspath(path)

    # Appends a single labeling result to a local CSV file, managing headers dynamically.
    # It automatically detects and adds new columns if the labeling schema has evolved.
    # Returns True if the save was successful, False otherwise.
    def append_label(self, label_data: dict, master_file_path: str) -> bool:
        try:
            # Checks if the master results file already exists on disk.
            # Returns True if it exists, False otherwise.
            file_exists = os.path.isfile(master_file_path)

            if file_exists:
                # Opens to dynamically check if we have new columns to add
                with open(master_file_path, mode="r", encoding="utf-8-sig", newline="") as csv_file:
                    # Reads existing headers to detect if the new data contains additional fields.
                    # Returns a DictReader instance.
                    reader = csv.DictReader(csv_file)
                    existing_headers = reader.fieldnames or []
                    # Converts the remaining file content into a list of dictionaries.
                    # Returns a list of dictionaries.
                    existing_rows = list(reader)

                new_keys = [k for k in label_data.keys() if k not in existing_headers]

                if new_keys:
                    # Merges existing headers with newly discovered data keys.
                    # Returns a list of strings.
                    all_headers = existing_headers + new_keys
                    
                    # Best-effort recovery: 
                    # If the file already had rows with extra values (answers without headers),
                    # DictReader puts them in the `None` key as a list.
                    clean_rows = []
                    for row in existing_rows:
                        # Retrieves and removes values that were orphaned without a header.
                        # Returns a list of orphaned values.
                        extra_vals = row.pop(None, [])
                        for i, val in enumerate(extra_vals):
                            if i < len(new_keys):
                                row[new_keys[i]] = val
                        clean_rows.append(row)

                    with open(master_file_path, mode="w", encoding="utf-8-sig", newline="") as csv_file:
                        # Initializes a CSV writer configured for the updated full header set.
                        # Returns a DictWriter instance.
                        writer = csv.DictWriter(csv_file, fieldnames=all_headers, extrasaction='ignore')
                        # Writes the updated column header row to the top of the file.
                        # Returns None.
                        writer.writeheader()
                        # Re-writes all historical rows into the newly formatted file.
                        # Returns None.
                        writer.writerows(clean_rows)
                        # Appends the latest labeling result at the end of the updated file.
                        # Returns None.
                        writer.writerow(label_data)
                    return True
                else:
                    # Append as usual, ensuring column order matches existing headers
                    with open(master_file_path, mode="a", encoding="utf-8-sig", newline="") as csv_file:
                        # Initializes an append-only CSV writer using the existing header order.
                        # Returns a DictWriter instance.
                        writer = csv.DictWriter(csv_file, fieldnames=existing_headers, extrasaction='ignore')
                        # Writes the new labeling result to the end of the file.
                        # Returns None.
                        writer.writerow(label_data)
                    return True
            else:
                # Extracts all keys from the label data to serve as initial headers for a new file.
                # Returns a list of strings.
                fieldnames = list(label_data.keys())
                with open(master_file_path, mode="w", encoding="utf-8-sig", newline="") as csv_file:
                    # Creates a new CSV file with the required headers and the first data row.
                    # Returns a DictWriter instance.
                    writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
                    # Writes the initial header row for the new results file.
                    # Returns None.
                    writer.writeheader()
                    # Writes the first labeling result into the new file.
                    # Returns None.
                    writer.writerow(label_data)
                return True

        except Exception as error:
            # Retrieves the system logger to record the write failure.
            # Returns a Logger instance.
            logger = logging.getLogger("LabelingSystem")
            # Logs a specified error occurred during storage persistence.
            # Returns None.
            logger.error(f"Error saving label: {error}")
            return False

# ---------------------------------------------------------------------------
# Remote / URL Storage
# ---------------------------------------------------------------------------

import urllib.request
import io

class RemoteStorage(BaseStorage):
    # Implementation of BaseStorage for remote files (S3 public links, Google Drive public links).

    # Implementation of BaseStorage for remote files such as Google Drive or standard URLs.
    # Downloads the remote file, processes Google-specific link formats, and parses the CSV content.
    # Returns a list of SourceRow objects containing the downloaded data.
    def load_source_csv(self, file_path: str) -> List[SourceRow]:
        url = file_path
        
        # --- Robust Google Drive Link Handling ---
        # 1. Google Sheets: .../spreadsheets/d/<ID>/...
        # 2. Uploaded File: .../file/d/<ID>/...
        if "drive.google.com" in url or "docs.google.com" in url:
            file_id = None
            # Efficiently extracts the unique Google file ID from various link structures.
            # Returns a string or None.
            if "/d/" in url:
                file_id = url.split("/d/")[1].split("/")[0]
            elif "id=" in url:
                file_id = url.split("id=")[1].split("&")[0]

            if file_id:
                if "/spreadsheets/" in url:
                    # Preserve the sheet tab (gid) so the correct tab is exported.
                    gid_match = re.search(r'[?&#]gid=(\d+)', file_path)
                    gid_param = f"&gid={gid_match.group(1)}" if gid_match else ""
                    url = f"https://docs.google.com/spreadsheets/d/{file_id}/export?format=csv{gid_param}"
                else:
                    # Reconstructs the URL to point to the direct download endpoint for uploaded files.
                    # Returns a modified URL string.
                    url = f"https://docs.google.com/uc?export=download&id={file_id}"
        
        # Prepares a network request with a spoofed User-Agent to bypass basic scrapers locks.
        # Returns a Request object.
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        # Connects to the remote URL and retrieves the file content.
        # Returns a HTTPResponse object.
        with urllib.request.urlopen(req) as response:
            # Reads the response body and decodes it using UTF-8 with BOM awareness.
            # Returns a string.
            content = response.read().decode("utf-8-sig")
            
            # Check if Google Drive returned an HTML sign-in page instead of a CSV
            content_lower = content.strip().lower()
            if content_lower.startswith('<!doctype html') or content_lower.startswith('<html'):
                # Validates that the response is actual CSV data rather than a login or error page.
                # Returns a ValueError.
                raise ValueError("The provided URL requires authentication or is not a raw CSV file. Make sure the link is publicly accessible ('Anyone with the link').")

            # Wraps the raw string content into a file-like stream for CSV parsing.
            # Returns a StringIO instance.
            csv_file = io.StringIO(content)
            # Initializes the dictionary reader for the remote stream.
            # Returns a DictReader instance.
            reader = csv.DictReader(csv_file)
            
            if not reader.fieldnames: return []
            
            rows = []
            for idx, raw_row in enumerate(reader):
                # Parses each dictionary row from the remote stream into a structural object.
                # Returns a SourceRow object.
                row_obj = build_source_row_from_dict(raw_row, idx + 1)
                if row_obj: 
                    # Appends the parsed object to the cumulative results.
                    # Returns None.
                    rows.append(row_obj)
            return rows


    # Resolves a remote metadata path by returning it as-is, assuming it's already a valid URL.
    # Returns a string representing the URL.
    def get_media_link(self, path: str) -> str:
        # For remote storage, we assume the paths in CSV are already URLs 
        # or relative to the same bucket. For now, return as is.
        return path

    # Proxies the label fulfillment request to the LocalStorage provider.
    # This ensures that even for remote projects, the results are stored on the local server filesystem.
    # Returns True if the append was successful, False otherwise.
    def append_label(self, label_data: dict, master_file_path: str) -> bool:
        # Saving results back to remote storage (S3/GDrive) typically requires 
        # API writes. For simplicity, we keep results in a local CSV.
        # This can be extended to upload the master file back to S3 after каждой saving.
        
        # Initializes a local storage instance to handle the physical file write operation.
        # Returns a LocalStorage object.
        local = LocalStorage()
        # Delegates the append operation to the local filesystem handler.
        # Returns a boolean.
        return local.append_label(label_data, master_file_path)

# NOTE: For full S3/GDrive integration (private files, writing back), 
# libraries like boto3 and google-api-python-client would be required.
