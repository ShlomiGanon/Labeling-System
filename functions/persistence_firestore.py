# persistence_firestore.py
# ------------------------
# Firestore-backed replacement for backend/CORE/persistence.py.
#
# Original (persistence.py)      →  This file
# ─────────────────────────────────────────────────────────────
# load_projects(projects_file)   →  load_projects()
# save_projects(file, projects)  →  save_projects(projects)   ← migration helper only
#                                   get_project(id)           ← new: single-doc read
#                                   create_project(project)   ← new: create one doc
#                                   update_project(id, data)  ← new: partial update
#                                   delete_project(id)        ← new: delete one doc
#
# Firestore schema
# ─────────────────────────────────────────────────────────────
# Collection : projects
# Document ID: project["id"]  (same UUID that was used as the key in projects.json)
# Fields     : all existing project dict fields are stored as-is
#
#   projects/{projectId}
#     ├── id                : str
#     ├── name              : str
#     ├── owner             : str
#     ├── workflow_type     : str  ("A" | "B" | "C" | "CUSTOM")
#     ├── csv_sources       : list[str]
#     ├── master_csv        : str
#     ├── is_finished       : bool
#     ├── custom_schema     : dict  (optional, CUSTOM workflows only)
#     └── source_labels     : dict  (optional)

import logging
from typing import Optional

import firebase_admin
from firebase_admin import firestore

logger = logging.getLogger("LabelingSystem")

PROJECTS_COLLECTION = "projects"


# ── Firebase initialisation ──────────────────────────────────────────────────

def _get_db():
    """
    Return a Firestore client.
    Initialises the Firebase Admin SDK on first call using Application Default
    Credentials (automatically available inside Cloud Functions).
    Safe to call multiple times.
    """
    try:
        firebase_admin.get_app()
    except ValueError:
        # No app initialised yet — start with ADC (works in Cloud Functions
        # and locally when GOOGLE_APPLICATION_CREDENTIALS is set).
        firebase_admin.initialize_app()
    return firestore.client()


# ── Read operations ──────────────────────────────────────────────────────────

def load_projects() -> list:
    """
    Return every project as a list of dicts.
    Drop-in replacement for persistence.load_projects(projects_file).
    Returns [] on any error (mirrors original behaviour).
    """
    try:
        db = _get_db()
        docs = db.collection(PROJECTS_COLLECTION).stream()
        return [doc.to_dict() for doc in docs]
    except Exception as e:
        logger.error(f"Error loading projects from Firestore: {e}")
        return []


def get_project(project_id: str) -> Optional[dict]:
    """
    Return a single project dict by its ID, or None if it does not exist.
    No equivalent in the original persistence.py (load_projects fetched all).
    """
    try:
        db = _get_db()
        doc = db.collection(PROJECTS_COLLECTION).document(project_id).get()
        return doc.to_dict() if doc.exists else None
    except Exception as e:
        logger.error(f"Error getting project '{project_id}' from Firestore: {e}")
        return None


# ── Write operations ─────────────────────────────────────────────────────────

def create_project(project: dict) -> bool:
    """
    Write a new project document to Firestore.
    Uses project['id'] as the Firestore document ID.
    Returns True on success, False on failure.
    """
    try:
        db = _get_db()
        project_id = project["id"]
        db.collection(PROJECTS_COLLECTION).document(project_id).set(project)
        logger.info(f"Project '{project_id}' created in Firestore.")
        return True
    except Exception as e:
        logger.error(f"Error creating project in Firestore: {e}")
        return False


def update_project(project_id: str, data: dict) -> bool:
    """
    Partially update an existing project document.
    Only the keys present in `data` are overwritten — other fields are untouched.
    Returns True on success, False on failure.
    """
    try:
        db = _get_db()
        db.collection(PROJECTS_COLLECTION).document(project_id).update(data)
        logger.info(f"Project '{project_id}' updated in Firestore.")
        return True
    except Exception as e:
        logger.error(f"Error updating project '{project_id}' in Firestore: {e}")
        return False


def delete_project(project_id: str) -> bool:
    """
    Delete a project document from Firestore.
    Returns True on success, False on failure.
    """
    try:
        db = _get_db()
        db.collection(PROJECTS_COLLECTION).document(project_id).delete()
        logger.info(f"Project '{project_id}' deleted from Firestore.")
        return True
    except Exception as e:
        logger.error(f"Error deleting project '{project_id}' from Firestore: {e}")
        return False


# ── Migration helper ─────────────────────────────────────────────────────────

def save_projects(projects: list) -> bool:
    """
    Batch-write a full projects list to Firestore in a single commit.

    This mirrors save_projects(projects_file, projects) from persistence.py and
    is intended for the one-time migration from projects.json → Firestore.

    For live production use, prefer the granular helpers above
    (create_project / update_project / delete_project) to avoid overwriting
    concurrent changes.

    Returns True if all writes succeeded, False if any failed.
    """
    try:
        db = _get_db()
        batch = db.batch()
        for project in projects:
            ref = db.collection(PROJECTS_COLLECTION).document(project["id"])
            batch.set(ref, project)
        batch.commit()
        logger.info(f"Batch-saved {len(projects)} projects to Firestore.")
        return True
    except Exception as e:
        logger.error(f"Error batch-saving projects to Firestore: {e}")
        return False
