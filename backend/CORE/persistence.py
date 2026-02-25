"""
persistence.py
--------------
Handles the persistence of project configurations.
"""

import json
import os
import logging

logger = logging.getLogger("LabelingSystem")

def load_projects(projects_file: str) -> list:
    """
    Reads the projects configuration file.
    """
    if not os.path.exists(projects_file):
        return []
    try:
        with open(projects_file, encoding="utf-8") as f:
            data = json.load(f)
            return data.get("projects", [])
    except Exception as e:
        logger.error(f"Error loading projects from {projects_file}: {e}")
        return []

def save_projects(projects_file: str, projects: list) -> None:
    """
    Persists the project list to disk.
    """
    try:
        with open(projects_file, "w", encoding="utf-8") as f:
            json.dump({"projects": projects}, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Error saving projects to {projects_file}: {e}")
