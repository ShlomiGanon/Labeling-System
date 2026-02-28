# server.py
# ---------
# Flask application initialization and engine management.

import os
import sys
import logging
import threading
import time
from flask import Flask, jsonify, request

# Configure logging to provide visibility into server operations.
# Returns None.
logging.basicConfig(level=logging.INFO)
# Creates a logger instance for the labeling system.
# Returns a Logger object.
logger = logging.getLogger("LabelingSystem")

# Base directory setup to help resolve file paths correctly.
# Returns an absolute path string.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# Returns a path string.
BACKEND_DIR = os.path.join(BASE_DIR, "backend")
# Returns a path string.
CORE_DIR = os.path.dirname(os.path.abspath(__file__))

# Ensure the core and backend directories are in the system path for imports.
if CORE_DIR not in sys.path:
    # Inserts core directory at the start of sys.path.
    # Returns None.
    sys.path.insert(0, CORE_DIR)
if BACKEND_DIR not in sys.path:
    # Inserts backend directory at the start of sys.path.
    # Returns None.
    sys.path.insert(0, BACKEND_DIR)

# Configuration for Image Loading Bar in Frontend.
SHOW_IMAGE_LOADING_BAR = True

from labeling_engine import LabelingEngine
from storage import LocalStorage, RemoteStorage

# --- App Initialization ---

# We point the static folder to the compiled React frontend.
# Returns a Flask application object.
app = Flask(__name__, static_folder="../../frontend/dist", static_url_path="")
# Sets a secret key for session management.
# Returns None.
_secret = os.environ.get("SECRET_KEY", "")
if not _secret:
    raise RuntimeError(
        "SECRET_KEY environment variable is not set. "
        "Copy backend/.env.example to backend/.env and set a strong secret key."
    )
app.secret_key = _secret

# Defines the location of the projects configuration file.
PROJECTS_FILE = os.path.join(BASE_DIR, "projects.json")

# In-memory session-like storage for active labeling engines.
_engines: dict = {}

# This function manages the lifecycle of LabelingEngine instances for each project.
# It checks if an engine already exists for the project ID; if not, it handles storage initialization,
# determines whether the source is local or remote, and pre-loads the data.
# It returns the LabelingEngine instance associated with the project.
def _derive_source_master(project_master: str, source_path: str) -> str:
    """
    For multi-source projects, derive a dedicated output file for one source CSV.
    Example: master_myproject.csv + source_batch2.csv → master_myproject__batch2.csv
    """
    master_dir  = os.path.dirname(project_master)
    master_stem = os.path.splitext(os.path.basename(project_master))[0]
    source_stem = os.path.splitext(os.path.basename(source_path))[0]
    return os.path.join(master_dir, f"{master_stem}__{source_stem}.csv")


def get_engine(project: dict) -> LabelingEngine:
    # Extracts the project ID from the project dictionary.
    # Returns a string.
    pid = project["id"]
    if pid not in _engines:
        # Support csv_sources (array, new) with fallback to source_csv (string, legacy).
        raw_sources = project.get("csv_sources") or (
            [project["source_csv"]] if project.get("source_csv") else []
        )

        # Determine storage type from the first source path.
        first_source = raw_sources[0] if raw_sources else ""
        is_remote = first_source.startswith("http") or "drive.google.com" in first_source

        storage = RemoteStorage() if is_remote else LocalStorage()
        master_path = os.path.join(BASE_DIR, project["master_csv"])
        engine = LabelingEngine(storage, master_path)
        engine.init_error = None

        # Pre-load all source files into the engine queue.
        # For multi-source projects each source gets its own output file so annotations
        # are kept separate. Single-source projects use master_path directly (backward compat).
        multi_source = len(raw_sources) > 1
        try:
            for source_path in raw_sources:
                if is_remote:
                    per_master = _derive_source_master(master_path, source_path) if multi_source else None
                    engine.load_source(source_path, master_path=per_master)
                else:
                    full_source_path = os.path.join(BASE_DIR, source_path)
                    if os.path.isfile(full_source_path):
                        per_master = _derive_source_master(master_path, full_source_path) if multi_source else None
                        engine.load_source(full_source_path, master_path=per_master)
                    else:
                        msg = f"Source CSV not found at: {full_source_path}"
                        logger.warning(msg)
                        engine.init_error = msg
        except Exception as e:
            logger.error(f"Error loading source data for project {pid}: {e}")
            engine.init_error = str(e)

        # Stores the initialized engine in the global registry.
        # Returns None.
        _engines[pid] = engine
    
    # Returns the requested engine instance from the registry.
    return _engines[pid]


# Starts a background daemon thread that periodically refreshes data for projects using remote storage.
# This ensures that any new rows added to Google Sheets are automatically picked up by the system.
# Returns None.
def start_refresher():
    # Defines the internal loop logic for the background thread.
    # Returns None.
    def refresh_loop():
        # Imports json inside the function to avoid circular dependencies if any.
        import json
        while True:
            # Pauses the loop for 60 seconds between refresh cycles.
            # Returns None.
            time.sleep(60) 
            
            try:
                # Skips the cycle if the main projects configuration file is missing.
                # Returns True/False.
                if not os.path.exists(PROJECTS_FILE):
                    continue
                
                # Loads the latest project metadata from the disk.
                # Returns a dictionary.
                from CORE.persistence import load_projects
                projects_data = load_projects(PROJECTS_FILE)
                
                # Iterates through all currently active labeling engines.
                # Returns a list of project IDs.
                current_engine_ids = list(_engines.keys())
                for pid in current_engine_ids:
                    # Retrieves the engine instance from memory.
                    # Returns a LabelingEngine or None.
                    engine = _engines.get(pid)
                    if not engine: continue
                    
                    # Target only engines using remote storage for periodic updates.
                    # Returns True if storage is remote.
                    if isinstance(engine._storage, RemoteStorage):
                        # Finds the specific project configuration for the active engine.
                        # Returns a project dictionary or None.
                        project = next((p for p in projects_data if p["id"] == pid), None)
                        if project:
                            # Re-loads the remote source CSV to pick up newly added rows.
                            # Returns an integer (count of new rows).
                            engine.load_source(project["source_csv"])
            except Exception as e:
                # Logs errors in the background worker to prevent system-wide crashes.
                # Returns None.
                logger.error(f"Background refresher error: {e}")

    # Creates a background thread to handle the refresh logic asynchronously.
    # Returns a Thread object.
    thread = threading.Thread(target=refresh_loop, daemon=True)
    # Starts the actual execution of the background thread.
    # Returns None.
    thread.start()


# Starts the refresher as soon as the module is loaded.
# Returns None.
start_refresher()


# Adds Cross-Origin Resource Sharing (CORS) headers to outgoing Flask responses.
# This is necessary for development environments where the frontend and backend run on different ports.
# Returns the Flask response object with the added headers.
@app.after_request
def add_cors_headers(response):
    # Retrieves the 'Origin' header from the incoming request.
    # Returns a string representing the requester's origin or an empty string.
    origin = request.headers.get("Origin", "")
    
    # Validates if the request comes from the trusted local development environment.
    # Returns True if it's localhost.
    _allowed = {
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5000",
    }
    extra = os.environ.get("ALLOWED_ORIGIN", "").strip()
    if extra:
        _allowed.add(extra)

    if origin in _allowed:
        # Explicitly allows the specified origin to access backend resources.
        # Returns None.
        response.headers["Access-Control-Allow-Origin"] = origin
        # Enables the transmission of cookies and authorization headers across origins.
        # Returns None.
        response.headers["Access-Control-Allow-Credentials"] = "true"
        # Lists the allowed HTTP headers for pre-flight requests from the browser.
        # Returns None.
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With"
        # Lists the HTTP methods permitted for the given origin.
        # Returns None.
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    
    # Returns the modified response object back to the client.
    return response


# Acts as a global error handler for all unhandled exceptions within the Flask application.
# It formats the error as a JSON response for API requests or as a simple HTML message for others.
# Returns a Flask response (JSON or string) and an HTTP status code 500.
@app.errorhandler(Exception)
def handle_exception(e):
    import traceback
    # Checks if the current request path is an API endpoint.
    # Returns True if it starts with '/api/', False otherwise.
    if request.path.startswith("/api/"):
        # Logs the error details specifically for the API endpoint.
        # Returns None.
        logger.error(f"API Error at {request.path}: {str(e)}")
        # Generates a formatted string of the current stack trace for debugging.
        # Returns a string.
        logger.error(traceback.format_exc())
        
        # Creates a JSON response containing the error message and traceback details.
        # Returns a Flask response object.
        return jsonify({
            "error": "Internal Server Error",
            "message": str(e),
            "traceback": traceback.format_exc().splitlines()
        }), 500
    
    # Provides a default HTML error page for non-API requests.
    # Returns a string.
    return f"<h1>Internal Server Error</h1><pre>{str(e)}</pre>", 500

