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
from storage import LocalStorage

# --- App Initialization ---

# We point the static folder to the compiled React frontend.
app = Flask(__name__, static_folder="../../frontend/dist", static_url_path="")
app.secret_key = "labeling-system-secret-key-change-in-production"

PROJECTS_FILE = os.path.join(BASE_DIR, "projects.json")

# In-memory session-like storage for active labeling engines.
# This prevents reloading CSVs from disk on every single request.
_engines: dict = {}

def get_engine(project: dict) -> LabelingEngine:
    """
    Retrieves an existing LabelingEngine or creates a new one if it doesn't exist.
    
    Args:
        project (dict): Dictionary containing project metadata (id, paths, etc.).
        
    Returns:
        LabelingEngine: The active engine instance for this project.
    """
    pid = project["id"]
    if pid not in _engines:
        # Create a new engine instance for this specific project.
        storage = LocalStorage()
        master_path = os.path.join(BASE_DIR, project["master_csv"])
        engine = LabelingEngine(storage, master_path)

        # Pre-load the source data into the engine's queue.
        source_path = os.path.join(BASE_DIR, project["source_csv"])
        if os.path.exists(source_path):
            engine.load_source(source_path)
        else:
            logger.warning(f"Source CSV not found at: {source_path}")

        _engines[pid] = engine
    return _engines[pid]

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
