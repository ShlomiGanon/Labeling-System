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
from werkzeug.utils import secure_filename

# Local imports from our structured backend
from CORE.server import app, PROJECTS_FILE, get_engine
import CORE.workflows as workflows
from CORE.storage import LocalStorage
from CORE.models import WorkflowType, EntityType, Sentiment, ImageTextRelationship, CustomLabel

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


# ---------------------------------------------------------------------------
# CSV Upload
# ---------------------------------------------------------------------------

@api_bp.route("/upload-csv", methods=["POST"])
def upload_csv():
    """
    Accepts a CSV file upload from the frontend and saves it to backend/data/.

    Returns:
        JSON: { "path": "backend/data/<filename>" } on success.
    """
    auth_check = require_login()
    if auth_check: return auth_check

    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400

    f = request.files['file']
    if not f or not f.filename:
        return jsonify({"error": "Empty filename"}), 400
    if not f.filename.lower().endswith('.csv'):
        return jsonify({"error": "Only CSV files are supported"}), 400

    safe_name = secure_filename(f.filename)
    save_dir  = os.path.join("backend", "data")
    os.makedirs(save_dir, exist_ok=True)
    save_path = os.path.join(save_dir, safe_name)
    f.save(save_path)

    return jsonify({"path": save_path.replace("\\", "/")}), 200


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
    source_csv = (data.get("source_csv") or "").strip()
    custom_schema = data.get("custom_schema")  # Will be None for preset workflows

    if not name or not source_csv:
        return jsonify({"error": "Name and source path are required."}), 400

    # Determine workflow type:
    # If a custom_schema is provided, use CUSTOM type.
    # Otherwise, parse the preset type (A, B, C).
    if custom_schema:
        workflow_type = WorkflowType.CUSTOM
    else:
        try:
            wtype_str = (data.get("workflow_type") or "").strip().upper()
            workflow_type = WorkflowType(wtype_str)
        except ValueError:
            return jsonify({"error": "Invalid workflow_type. Must be A, B, C, or provide a custom_schema."}), 400

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

    # Persist the full custom schema so the frontend can render it correctly.
    if custom_schema:
        project["custom_schema"] = custom_schema

    projects = load_projects()
    projects.append(project)
    save_projects(projects)

    # Pre-warm the engine
    get_engine(project)

    return jsonify(project), 201


@api_bp.route("/projects/<project_id>", methods=["DELETE"])
def delete_project(project_id):
    """
    Deletes a labeling project.
    
    Query params:
        delete_files (str): 'true' to also delete source and master CSV files from disk.

    Returns:
        JSON: { "deleted": <project_id> }
    """
    auth_check = require_login()
    if auth_check: return auth_check

    projects  = load_projects()
    project   = next((p for p in projects if p["id"] == project_id), None)

    if not project:
        return jsonify({"error": "Project not found"}), 404

    delete_files = request.args.get("delete_files", "false").lower() == "true"

    if delete_files:
        for csv_key in ("source_csv", "master_csv"):
            path = project.get(csv_key, "")
            if path and os.path.isfile(path):
                try:
                    os.remove(path)
                    logger.info(f"Deleted file: {path}")
                except Exception as e:
                    logger.warning(f"Could not delete {path}: {e}")

    # Remove project from list and persist
    updated = [p for p in projects if p["id"] != project_id]
    save_projects(updated)

    return jsonify({"deleted": project_id}), 200


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


@api_bp.route("/projects/<project_id>/config", methods=["GET"])
def get_project_config(project_id: str):
    """
    Returns the UI schema/configuration for the project's workflow.
    """
    auth_check = require_login()
    if auth_check: return auth_check

    projects = load_projects()
    project  = next((p for p in projects if p["id"] == project_id), None)
    if not project:
        return jsonify({"error": "Project not found"}), 404

    from CORE.models import WORKFLOW_SCHEMAS, WorkflowType
    wtype = WorkflowType(project["workflow_type"])

    # If the project was built with the custom workflow builder,
    # return the stored schema directly (it's already in the correct frontend format).
    if wtype == WorkflowType.CUSTOM:
        custom_schema = project.get("custom_schema")
        if not custom_schema:
            return jsonify({"error": "Custom schema not found in project"}), 404
        # Add workflow_type to the response so the frontend knows it's custom
        return jsonify({"workflow_type": "CUSTOM", **custom_schema})

    # For preset workflows (A, B, C), use the predefined schemas
    schema = WORKFLOW_SCHEMAS.get(wtype)
    if not schema:
        return jsonify({"error": "Schema not found"}), 404

    return jsonify(schema.to_dict())


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
            rel = ImageTextRelationship(data.get("relationship", ""))
            success = workflows.process_image_text_relationship(engine, user, row_id, rel)

        elif wtype == WorkflowType.ENTITY_SENTIMENT:
            etype = EntityType(data.get("entity_type", ""))
            sent  = Sentiment(data.get("sentiment", ""))
            workflows.process_entity_identification(user, row_id, data.get("entity_name", ""), etype)
            workflows.process_topic_assignment(user, row_id, data.get("topic", ""))
            success = workflows.process_entity_sentiment(engine, user, row_id, sent)

        elif wtype == WorkflowType.GOLDEN_CAPTION:
            success = workflows.process_caption(engine, user, row_id, data.get("caption", ""))

        elif wtype == WorkflowType.CUSTOM:
            # For custom workflows, pass ALL submitted fields directly.
            # We exclude known metadata keys and let everything else through.
            excluded = {"row_id"}
            custom_fields = {k: v for k, v in data.items() if k not in excluded}

            # Build a mapping from field ID → field label using the stored custom_schema.
            # This ensures CSV column headers show the human-readable field name
            # (e.g. "בחר ישות") instead of the generated ID (e.g. "field_17720282...").
            id_to_label = {}
            custom_schema = project.get("custom_schema", {})
            for step in custom_schema.get("steps", []):
                for field in step.get("fields", []):
                    fid   = field.get("id", "")
                    label = field.get("label", "").strip()
                    if fid and label:
                        id_to_label[fid] = label

            # Rename keys: if the key is a known field ID, replace it with the label.
            # If two fields share the same label, append a numeric suffix to avoid collision.
            seen_labels = {}
            renamed_fields = {}
            for k, v in custom_fields.items():
                col_name = id_to_label.get(k, k)  # fall back to ID if no label found
                if col_name in seen_labels:
                    seen_labels[col_name] += 1
                    col_name = f"{col_name}_{seen_labels[col_name]}"
                else:
                    seen_labels[col_name] = 1
                renamed_fields[col_name] = v

            success = workflows.process_custom_workflow(engine, user, row_id, renamed_fields)

        else:
            return jsonify({"error": "Unknown workflow"}), 400

    except (ValueError, KeyError) as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({
        "success":        success,
        "rows_remaining": engine.get_queue_size(),
        "is_finished":    engine.is_finished(),
    })
