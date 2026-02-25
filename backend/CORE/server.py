"""
server.py
---------
Flask application initialization and engine management.
Located in backend/SERVER/server.py
"""

import os
import sys
import logging
from flask import Flask, jsonify, request

# Configure logging to provide visibility into server operations.
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Base directory setup to help resolve file paths correctly.
# We are currently in backend/CORE/, so we go up two levels for the project root.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BACKEND_DIR = os.path.join(BASE_DIR, "backend")
CORE_DIR = os.path.dirname(os.path.abspath(__file__))

# Ensure the core and backend directories are in the system path for imports.
if CORE_DIR not in sys.path:
    sys.path.insert(0, CORE_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from labeling_engine import LabelingEngine
from storage import LocalStorage, RemoteStorage

# --- App Initialization ---

# We point the static folder to the compiled React frontend.
app = Flask(__name__, static_folder="../../frontend/dist", static_url_path="")
app.secret_key = "labeling-system-secret-key-change-in-production"

PROJECTS_FILE = os.path.join(BASE_DIR, "projects.json")

# In-memory session-like storage for active labeling engines.
_engines: dict = {}

def get_engine(project: dict) -> LabelingEngine:
    """
    Retrieves an existing LabelingEngine or creates a new one if it doesn't exist.
    """
    pid = project["id"]
    if pid not in _engines:
        # Determine based on path if it's local or remote
        source_path = project["source_csv"]
        is_remote = source_path.startswith("http") or "drive.google.com" in source_path
        
        storage = RemoteStorage() if is_remote else LocalStorage()
        master_path = os.path.join(BASE_DIR, project["master_csv"])
        engine = LabelingEngine(storage, master_path)
        engine.init_error = None

        # Pre-load the source data
        try:
            if is_remote:
                engine.load_source(source_path)
            else:
                full_source_path = os.path.join(BASE_DIR, source_path)
                if os.path.exists(full_source_path):
                    engine.load_source(full_source_path)
                else:
                    msg = f"Source CSV not found at: {full_source_path}"
                    logger.warning(msg)
                    engine.init_error = msg
        except Exception as e:
            logger.error(f"Error loading source data for project {pid}: {e}")
            engine.init_error = str(e)

        _engines[pid] = engine
    return _engines[pid]

# ---------------------------------------------------------------------------
# Background Refresher (Polling for remote changes)
# ---------------------------------------------------------------------------

import threading
import time

def start_refresher():
    """
    Starts a background thread that periodically polls remote CSV files for new rows.
    """
    def refresh_loop():
        import json
        while True:
            # Check every 60 seconds.
            time.sleep(60) 
            
            try:
                # Load projects directly to avoid circular imports with API.api
                if not os.path.exists(PROJECTS_FILE):
                    continue
                    
                with open(PROJECTS_FILE, encoding="utf-8") as f:
                    projects_data = json.load(f).get("projects", [])
                
                current_engine_ids = list(_engines.keys())
                for pid in current_engine_ids:
                    engine = _engines.get(pid)
                    if not engine: continue
                    
                    if isinstance(engine._storage, RemoteStorage):
                        # Find matching project config
                        from CORE.persistence import load_projects
                        projects_data = load_projects(PROJECTS_FILE)
                        project = next((p for p in projects_data if p["id"] == pid), None)
                        if project:
                            engine.load_source(project["source_csv"])
            except Exception as e:
                logging.getLogger("LabelingSystem").error(f"Background refresher error: {e}")

    thread = threading.Thread(target=refresh_loop, daemon=True)
    thread.start()

# Start the refresher as soon as the module is loaded
start_refresher()

@app.after_request
def add_cors_headers(response):
    """
    Injects CORS headers to allow the React development server to communicate with this API.
    
    Args:
        response (flask.Response): The outgoing response object.
        
    Returns:
        flask.Response: The response with added security/access headers.
    """
    origin = request.headers.get("Origin", "")
    # Allow localhost development ports.
    if origin in ("http://localhost:5173", "http://127.0.0.1:5173"):
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response

@app.errorhandler(Exception)
def handle_exception(e):
    """
    Global catch-all for any unhandled exceptions in the API.
    Returns a JSON error instead of an HTML crash page.
    
    Args:
        e (Exception): The exception that was raised.
        
    Returns:
        tuple: JSON error message and the 500 status code.
    """
    import traceback
    if request.path.startswith("/api/"):
        logger.error(f"API Error at {request.path}: {str(e)}")
        # Log the full stack trace for debugging purposes.
        logger.error(traceback.format_exc())
        
        return jsonify({
            "error": "Internal Server Error",
            "message": str(e),
            "traceback": traceback.format_exc().splitlines()
        }), 500
    
    return f"<h1>Internal Server Error</h1><pre>{str(e)}</pre>", 500
