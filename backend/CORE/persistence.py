# persistence.py
# --------------
# Handles the persistence of project configurations to/from the local filesystem.

import json
import os
import logging

# Initializes a named logger for the labeling system's persistence layer.
# Returns a Logger instance.
logger = logging.getLogger("LabelingSystem")

# Reads the project configuration file and retrieves the list of active projects.
# It handles missing files and potential JSON parsing errors gracefully.
# Returns a list of project dictionaries, or an empty list if loading fails.
def load_projects(projects_file: str) -> list:
    # Checks if the specified projects file exists on the local filesystem.
    # Returns True if it exists, False otherwise.
    if not os.path.exists(projects_file):
        # Returns an empty list if no configuration file is found.
        # Returns a list.
        return []
        
    try:
        # Opens the projects configuration file for reading with UTF-8 encoding.
        # Returns a file handle.
        with open(projects_file, encoding="utf-8") as f:
            # Parses the JSON file content into a Python dictionary.
            # Returns a dictionary representing the projects data.
            data = json.load(f)
            # Retrieves the 'projects' list from the parsed data dictionary.
            # Returns a list of dictionaries.
            return data.get("projects", [])
    except Exception as e:
        # Logs an error message if the project loading operation fails due to syntax or access issues.
        # Returns None.
        logger.error(f"Error loading projects from {projects_file}: {e}")
        return []

# Persists the current list of projects to a JSON file on disk.
# It ensures that data is stored with non-ASCII characters preserved and readable indentation.
# Returns None.
def save_projects(projects_file: str, projects: list) -> None:
    try:
        # Opens or creates the projects configuration file for writing.
        # Returns a file handle.
        with open(projects_file, "w", encoding="utf-8") as f:
            # Serializes the projects list into a JSON formatted string and writes it to the file.
            # Returns None.
            json.dump({"projects": projects}, f, ensure_ascii=False, indent=2)
    except Exception as e:
        # Logs an error message if the project saving operation fails.
        # Returns None.
        logger.error(f"Error saving projects to {projects_file}: {e}")
