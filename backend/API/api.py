"""
api.py
------
API Blueprint definitions for the Labeling System.
This file handles the translation of HTTP requests into backend logic.
"""

import json
import os
import uuid
import logging
from flask import Blueprint, jsonify, request, session, send_from_directory

# Local imports from our structured backend
from CORE.server import app, PROJECTS_FILE, get_engine
import CORE.workflows as workflows
from CORE.storage import LocalStorage
from CORE.models import WorkflowType, EntityType, Sentiment, ImageTextRelationship

# Create a Blueprint to modularize our routes
api_bp = Blueprint('api', __name__)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Internal Helpers
# ---------------------------------------------------------------------------

def load_projects() -> list:
    """
    Reads the projects.json configuration file.
    
    Returns:
        list: A list of all project metadata dictionaries.
    """
    if not os.path.exists(PROJECTS_FILE):
        return []
    with open(PROJECTS_FILE, encoding="utf-8") as f:
        return json.load(f).get("projects", [])


def save_projects(projects: list) -> None:
    """
    Persists the project list to disk.
    
    Args:
        projects (list): The list of project objects to save.
    """
    with open(PROJECTS_FILE, "w", encoding="utf-8") as f:
        json.dump({"projects": projects}, f, ensure_ascii=False, indent=2)


def current_user() -> str | None:
    """
    Retrieves the logged-in user's identity from the Flask session.
    
    Returns:
        str | None: The username if logged in, else None.
    """
    return session.get("user_name")


def require_login():
    """
    Middleware-like check to ensure a user is authenticated before accessing API.
    
    Returns:
        tuple | None: A tuple of (JSON response, status code) if unauthorized, else None.
    """
    if not current_user():
        return jsonify({"error": "Unauthorized. Please log in."}), 401
    return None

# ---------------------------------------------------------------------------
# Frontend Serving
# ---------------------------------------------------------------------------

@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_react(path):
    """
    Serves the React frontend (dist folder). 
    Matches all routes that don't start with /api/.
    
    Args:
        path (str): The requested file path.
        
    Returns:
        Response: The requested static file or index.html.
    """
    if path.startswith("api/"):
        logger.warning(f"API Route not found: {path}")
        return jsonify({"error": "Route not found"}), 404

    # The dist folder is located relative to the server script
    dist_dir = os.path.join(app.root_path, "..", "..", "frontend", "dist")
    full_path = os.path.join(dist_dir, path)
    
    if path and os.path.exists(full_path):
        return send_from_directory(dist_dir, path)
    return send_from_directory(dist_dir, "index.html")

@api_bp.route("/<path:path>", methods=["OPTIONS"])
def options_handler(path):
    """
    Handles CORS pre-flight requests from modern browsers.
    """
    return "", 204

# ---------------------------------------------------------------------------
# Authentication Endpoints
# ---------------------------------------------------------------------------

@api_bp.route("/login", methods=["POST"])
def login():
    """
    Sets a username in the server session.
    
    Returns:
        JSON: The username that was set.
    """
    data      = request.get_json(force=True)
    user_name = (data.get("user_name") or "").strip()

    if not user_name:
        return jsonify({"error": "Empty username."}), 400

    session["user_name"] = user_name
    return jsonify({"user_name": user_name})


@api_bp.route("/logout", methods=["POST"])
def logout():
    """
    Clears the user session and releases any row they were working on.
    
    Returns:
        JSON: Whether any row was released back to the queue.
    """
    user     = current_user()
    released = False

    if user:
        from CORE.server import _engines
        for engine in _engines.values():
            if engine.release_row(user):
                released = True

    session.clear()
    return jsonify({"released": released})


@api_bp.route("/me", methods=["GET"])
def me():
    """
    Check current authentication status.
    """
    return jsonify({"user_name": current_user()})


# ---------------------------------------------------------------------------
# Project Management Endpoints
# ---------------------------------------------------------------------------

@api_bp.route("/projects", methods=["GET"])
def list_projects():
    """
    Returns a summary of all available labeling projects.
    
    Returns:
        JSON: List of project summaries including progress.
    """
    auth_check = require_login()
    if auth_check: return auth_check

    projects = load_projects()
    result = []
    
    for p in projects:
        try:
            engine = get_engine(p)
            result.append({
                "id": p["id"],
                "name": p["name"],
                "owner": p["owner"],
                "workflow_type": p["workflow_type"],
                "rows_remaining": engine.get_queue_size(),
                "is_finished": engine.is_finished()
            })
        except Exception as e:
            logger.error(f"Failed to load project '{p['name']}': {e}")
            result.append({
                "id": p["id"], "name": p["name"], "error": "Disk error"
            })
            
    return jsonify({"projects": result})


@api_bp.route("/projects", methods=["POST"])
def create_project():
    """
    Defines a new labeling project.
    
    Expects:
        JSON: { name, workflow_type ('A'|'B'|'C'), source_csv }
        
    Returns:
        JSON: The newly created project object.
    """
    auth_check = require_login()
    if auth_check: return auth_check

    data = request.get_json(force=True)
    name = (data.get("name") or "").strip()
    
    # Map the string input to our WorkflowType Enum
    try:
        wtype_str = (data.get("workflow_type") or "").strip().upper()
        workflow_type = WorkflowType(wtype_str)
    except ValueError:
        return jsonify({"error": "Invalid workflow_type. Must be A, B, or C."}), 400

    source_csv = (data.get("source_csv") or "").strip()

    if not name or not source_csv:
        return jsonify({"error": "Name and source path are required."}), 400

    # Sanitize name for file path usage
    safe_name  = name.replace(" ", "_").lower()
    master_csv = f"backend/data/master_{safe_name}.csv"

    project = {
        "id":            str(uuid.uuid4()),
        "name":          name,
        "owner":         current_user(),
        "workflow_type": workflow_type.value,
        "source_csv":    source_csv,
        "master_csv":    master_csv,
    }

    projects = load_projects()
    projects.append(project)
    save_projects(projects)

    # Pre-warm the engine
    get_engine(project)

    return jsonify(project), 201


# ---------------------------------------------------------------------------
# Task Execution Endpoints
# ---------------------------------------------------------------------------

@api_bp.route("/projects/<project_id>/task", methods=["GET"])
def get_task(project_id: str):
    """
    Fetches the next row for a user to label.
    
    Returns:
        JSON: Row metadata and workflow context.
    """
    auth_check = require_login()
    if auth_check: return auth_check

    projects = load_projects()
    project  = next((p for p in projects if p["id"] == project_id), None)
    if not project:
        return jsonify({"error": "Project not found"}), 404

    engine = get_engine(project)
    row    = engine.get_next_row(current_user())

    if row is None:
        return jsonify({"finished": True})

    image_link = LocalStorage().get_media_link(row.image_path) if row.has_image() else ""

    return jsonify({
        "row_id":        row.row_id,
        "image_path":    image_link,
        "text_content":  row.text_content,
        "workflow_type": project["workflow_type"],
        "has_image":     row.has_image(),
        "has_text":      row.has_text(),
    })


@api_bp.route("/projects/<project_id>/submit", methods=["POST"])
def submit_task(project_id: str):
    """
    Saves work for a single task row.
    
    Returns:
        JSON: Success status and queue progress.
    """
    auth_check = require_login()
    if auth_check: return auth_check

    projects = load_projects()
    project  = next((p for p in projects if p["id"] == project_id), None)
    if not project:
        return jsonify({"error": "Project not found"}), 404

    data   = request.get_json(force=True)
    engine = get_engine(project)
    user   = current_user()
    row_id = str(data.get("row_id", ""))
    
    wtype  = WorkflowType(project["workflow_type"])

    try:
        # Route to appropriate workflow handler based on project type
        if wtype == WorkflowType.IMAGE_TEXT_RELATIONSHIP:
            # Step 1: Convert string to Enum
            rel = ImageTextRelationship(data.get("relationship", ""))
            success = workflows.process_image_text_relationship(engine, user, row_id, rel)

        elif wtype == WorkflowType.ENTITY_SENTIMENT:
            # Workflow B sends all data at once in the frontend implementation
            etype = EntityType(data.get("entity_type", ""))
            sent  = Sentiment(data.get("sentiment", ""))
            
            workflows.process_entity_identification(user, row_id, data.get("entity_name", ""), etype)
            workflows.process_topic_assignment(user, row_id, data.get("topic", ""))
            success = workflows.process_entity_sentiment(engine, user, row_id, sent)

        elif wtype == WorkflowType.GOLDEN_CAPTION:
            success = workflows.process_caption(engine, user, row_id, data.get("caption", ""))

        else:
            return jsonify({"error": "Unknown workflow"}), 400

    except (ValueError, KeyError) as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({
        "success":        success,
        "rows_remaining": engine.get_queue_size(),
        "is_finished":    engine.is_finished(),
    })
