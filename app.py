"""
app.py
------
Flask API server - This file connects the React frontend to the Python backend.

What this file does:
1. Handles web requests (Login, Projects, Tasks).
2. Manages user sessions.
3. Serves the frontend files.
"""

import json
import os
import sys
import uuid
import logging
import traceback
from flask import Flask, jsonify, request, session, send_from_directory

# Configure logging to see what's happening
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Path Configuration
# ---------------------------------------------------------------------------
BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(BASE_DIR, "backend")
DATA_DIR    = os.path.join(BACKEND_DIR, "data")

# Add the backend folder to Python's path so we can import files from it
sys.path.insert(0, BACKEND_DIR)

from labeling_engine import LabelingEngine   # noqa: E402
from storage import LocalStorage             # noqa: E402
import workflows                             # noqa: E402

# ---------------------------------------------------------------------------
# Flask App Setup
# ---------------------------------------------------------------------------
app = Flask(__name__, static_folder="frontend/dist", static_url_path="")
app.secret_key = "labeling-system-secret-key-change-in-production"

PROJECTS_FILE = os.path.join(BASE_DIR, "projects.json")

# This dictionary stores active labeling engines for each project
_engines: dict = {}

# ---------------------------------------------------------------------------
# Security & Headers
# ---------------------------------------------------------------------------
@app.after_request
def add_cors_headers(response):
    """
    Allow the React development server (port 5173) to talk to this API.
    In production, this isn't needed because they run on the same port.
    """
    origin = request.headers.get("Origin", "")
    if origin in ("http://localhost:5173", "http://127.0.0.1:5173"):
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response


@app.route("/api/<path:path>", methods=["OPTIONS"])
def options_handler(path):
    """Handle special 'pre-flight' requests from browsers."""
    return "", 204

# ---------------------------------------------------------------------------
# Error Handling
# ---------------------------------------------------------------------------

@app.errorhandler(Exception)
def handle_exception(e):
    """
    If something goes wrong, return a clear error message in JSON format.
    """
    if request.path.startswith("/api/"):
        logger.error(f"API Error at {request.path}: {str(e)}")
        logger.error(traceback.format_exc())
        
        return jsonify({
            "error": "Internal Server Error",
            "message": str(e),
            "traceback": traceback.format_exc().splitlines()
        }), 500
    
    return f"<h1>Internal Server Error</h1><pre>{str(e)}</pre>", 500

# ---------------------------------------------------------------------------
# Serve the Frontend
# ---------------------------------------------------------------------------

@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_react(path):
    """
    This route serves the React app files.
    If a specific file exists, it sends it. Otherwise, it sends index.html.
    """
    # Safety check: if an API request reaches here, it's a 404
    if path.startswith("api/"):
        logger.warning(f"API Route not found: {path}")
        return jsonify({"error": "API route not found"}), 404

    dist_dir = os.path.join(app.root_path, "frontend", "dist")
    full_path = os.path.join(dist_dir, path)
    if path and os.path.exists(full_path):
        return send_from_directory(dist_dir, path)
    return send_from_directory(dist_dir, "index.html")


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------

def load_projects() -> list:
    """Load the list of projects from the projects.json file."""
    if not os.path.exists(PROJECTS_FILE):
        return []
    with open(PROJECTS_FILE, encoding="utf-8") as f:
        return json.load(f).get("projects", [])


def save_projects(projects: list) -> None:
    """Save the list of projects back to the projects.json file."""
    with open(PROJECTS_FILE, "w", encoding="utf-8") as f:
        json.dump({"projects": projects}, f, ensure_ascii=False, indent=2)


def get_engine(project: dict) -> LabelingEngine:
    """
    Get or create a LabelingEngine for a specific project.
    We keep engines in memory so they remember their state.
    """
    pid = project["id"]
    if pid not in _engines:
        storage     = LocalStorage()
        master_path = os.path.join(BASE_DIR, project["master_csv"])
        engine      = LabelingEngine(storage, master_path)

        source_path = os.path.join(BASE_DIR, project["source_csv"])
        if os.path.exists(source_path):
            engine.load_source(source_path)
        else:
            logger.warning(f"Source CSV not found: {source_path}")

        _engines[pid] = engine
    return _engines[pid]


def current_user() -> str | None:
    """Get the name of the user who is currently logged in."""
    return session.get("user_name")


def require_login():
    """Check if a user is logged in. If not, return an error."""
    if not current_user():
        return jsonify({"error": "Not authenticated. Please log in first."}), 401
    return None


# ---------------------------------------------------------------------------
# Authentication API
# ---------------------------------------------------------------------------

@app.route("/api/login", methods=["POST"])
def login():
    """
    Log a user in by saving their name in the session.
    Expects: { "user_name": "Alice" }
    """
    data      = request.get_json(force=True)
    user_name = (data.get("user_name") or "").strip()

    if not user_name:
        return jsonify({"error": "Username cannot be empty."}), 400

    session["user_name"] = user_name
    return jsonify({"user_name": user_name})


@app.route("/api/logout", methods=["POST"])
def logout():
    """
    Log the user out and clear their session.
    It also releases any tasks they were working on so others can take them.
    """
    user     = current_user()
    released = False

    if user:
        # Release this user's active row in every loaded engine
        for engine in _engines.values():
            if engine.release_row(user):
                released = True

    session.clear()
    return jsonify({"released": released})


@app.route("/api/me", methods=["GET"])
def me():
    """Return the name of the current logged-in user."""
    return jsonify({"user_name": current_user()})


# ---------------------------------------------------------------------------
# Projects API
# ---------------------------------------------------------------------------

@app.route("/api/projects", methods=["GET"])
def list_projects():
    """Return a list of all projects and their current status."""
    auth_error = require_login()
    if auth_error: return auth_error

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
            # If one project fails (e.g. missing CSV), don't crash the whole list.
            # Just mark it as inaccessible.
            logger.error(f"Error loading project '{p['name']}': {e}")
            result.append({
                "id": p["id"],
                "name": p["name"],
                "owner": p["owner"],
                "workflow_type": p["workflow_type"],
                "rows_remaining": 0,
                "is_finished": False,
                "error": "Error loading project files"
            })
            
    return jsonify({"projects": result})


@app.route("/api/projects", methods=["POST"])
def create_project():
    """
    Create a new labeling project.
    Expects: { "name": "Project Name", "workflow_type": "A", "source_csv": "path/to/data.csv" }
    """
    auth_error = require_login()
    if auth_error: return auth_error

    data          = request.get_json(force=True)
    name          = (data.get("name") or "").strip()
    workflow_type = (data.get("workflow_type") or "").strip().upper()
    source_csv    = (data.get("source_csv") or "").strip()

    # Validate required fields
    if not name:
        return jsonify({"error": "Project name is required."}), 400
    if workflow_type not in ("A", "B", "C"):
        return jsonify({"error": "workflow_type must be A, B, or C."}), 400
    if not source_csv:
        return jsonify({"error": "source_csv path is required."}), 400

    # Auto-generate the master labels path inside backend/data/
    safe_name  = name.replace(" ", "_").lower()
    master_csv = f"backend/data/master_{safe_name}.csv"

    project = {
        "id":            str(uuid.uuid4()),
        "name":          name,
        "owner":         current_user(),
        "workflow_type": workflow_type,
        "source_csv":    source_csv,
        "master_csv":    master_csv,
    }

    projects = load_projects()
    projects.append(project)
    save_projects(projects)

    # Pre-load the engine so queue stats are available immediately
    get_engine(project)

    return jsonify(project), 201


# ---------------------------------------------------------------------------
# Tasks API
# ---------------------------------------------------------------------------

@app.route("/api/projects/<project_id>/task", methods=["GET"])
def get_task(project_id: str):
    """
    Fetch the next available task for the user in a project.
    """
    auth_error = require_login()
    if auth_error: return auth_error

    projects = load_projects()
    project  = next((p for p in projects if p["id"] == project_id), None)
    if not project:
        return jsonify({"error": "Project not found."}), 404

    engine = get_engine(project)
    row    = engine.get_next_row(current_user())

    if row is None:
        return jsonify({"finished": True})

    # Resolve the image path to a displayable URL via the storage provider
    image_link = LocalStorage().get_media_link(row.image_path) if row.has_image() else ""

    return jsonify({
        "row_id":        row.row_id,
        "image_path":    image_link,
        "text_content":  row.text_content,
        "workflow_type": project["workflow_type"],
        "has_image":     row.has_image(),
        "has_text":      row.has_text(),
    })


@app.route("/api/projects/<project_id>/submit", methods=["POST"])
def submit_task(project_id: str):
    """
    Save the user's answers for a task.
    The format of the answer depends on the workflow type (A, B, or C).
    """
    auth_error = require_login()
    if auth_error: return auth_error

    projects = load_projects()
    project  = next((p for p in projects if p["id"] == project_id), None)
    if not project:
        return jsonify({"error": "Project not found."}), 404

    data          = request.get_json(force=True)
    engine        = get_engine(project)
    user          = current_user()
    row_id        = str(data.get("row_id", ""))
    workflow_type = project["workflow_type"]

    try:
        # Route to the correct processing logic based on project type
        if workflow_type == "A":
            success = workflows.process_image_text_relationship(
                engine, user, row_id, data.get("relationship", "")
            )

        elif workflow_type == "B":
            # All three steps are sent in a single form submission
            workflows.process_entity_identification(
                user, row_id,
                data.get("entity_name", ""),
                data.get("entity_type", ""),
            )
            workflows.process_topic_assignment(user, row_id, data.get("topic", ""))
            success = workflows.process_entity_sentiment(
                engine, user, row_id, data.get("sentiment", "")
            )

        elif workflow_type == "C":
            success = workflows.process_caption(
                engine, user, row_id, data.get("caption", "")
            )

        else:
            return jsonify({"error": f"Unsupported workflow type: {workflow_type}"}), 400

    except (ValueError, KeyError) as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({
        "success":        success,
        "rows_remaining": engine.get_queue_size(),
        "is_finished":    engine.is_finished(),
    })


# ---------------------------------------------------------------------------
# Server Kickoff
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("-" * 50)
    print("Labeling System Backend is starting...")
    print("URL: http://localhost:5000")
    print("-" * 50)
    app.run(debug=True, host="0.0.0.0", port=5000)
