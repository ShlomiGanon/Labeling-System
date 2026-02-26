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

# Configuration for Image Loading Bar in Frontend
SHOW_IMAGE_LOADING_BAR = True

from labeling_engine import LabelingEngine
from storage import LocalStorage, RemoteStorage

# --- App Initialization ---

# We point the static folder to the compiled React frontend.
app = Flask(__name__, static_folder="../../frontend/dist", static_url_path="")
app.secret_key = "labeling-system-secret-key-change-in-production"

PROJECTS_FILE = os.path.join(BASE_DIR, "projects.json")

# In-memory session-like storage for active labeling engines.
_engines: dict = {}

# This function manages the lifecycle of LabelingEngine instances for each project.
# It checks if an engine already exists for the project ID; if not, it handles storage initialization,
# determines whether the source is local or remote, and pre-loads the data.
# It returns the LabelingEngine instance associated with the project.
def get_engine(project: dict) -> LabelingEngine:
    pid = project["id"]
    if pid not in _engines:
        source_path = project["source_csv"]
        # Checks if the source path is a URL or a Google Drive link to decide on the storage type.
        # Returns True if it's remote, False otherwise.
        is_remote = source_path.startswith("http") or "drive.google.com" in source_path
        
        # Initializes the appropriate storage backend (Remote or Local).
        # Returns an instance of RemoteStorage or LocalStorage.
        storage = RemoteStorage() if is_remote else LocalStorage()
        # Constructs the full file path for the master CSV file.
        # Returns the absolute path as a string.
        master_path = os.path.join(BASE_DIR, project["master_csv"])
        # Creates a new instance of the LabelingEngine with the specified storage and master file.
        # Returns a LabelingEngine object.
        engine = LabelingEngine(storage, master_path)
        engine.init_error = None

        # Pre-load the source data
        try:
            if is_remote:
                # Triggers the engine to fetch and load data from a remote CSV source.
                # Returns None or raises an exception if loading fails.
                engine.load_source(source_path)
            else:
                # Constructs the full file path for the local source CSV.
                # Returns the absolute path as a string.
                full_source_path = os.path.join(BASE_DIR, source_path)
                # Verifies if the source CSV file exists on the local filesystem.
                # Returns True if it exists, False otherwise.
                if os.path.exists(full_source_path):
                    # Loads the local CSV data into the engine.
                    # Returns None or raises an exception.
                    engine.load_source(full_source_path)
                else:
                    msg = f"Source CSV not found at: {full_source_path}"
                    # Logs a warning if the file is missing.
                    # Returns None.
                    logger.warning(msg)
                    engine.init_error = msg
        except Exception as e:
            # Logs any major errors encountered during engine initialization.
            # Returns None.
            logger.error(f"Error loading source data for project {pid}: {e}")
            # Converts the exception to a string for error reporting.
            # Returns the error message.
            engine.init_error = str(e)

        _engines[pid] = engine
    return _engines[pid]

# ---------------------------------------------------------------------------
# Background Refresher (Polling for remote changes)
# ---------------------------------------------------------------------------

import threading
import time

# Initializes and launches a background daemon thread that periodically refreshes project data.
# This prevents blocking the main server thread while waiting for I/O.
# It does not return anything.
def start_refresher():
    # Defines a nested loop that runs indefinitely to refresh remote storage sources.
    # It checks for updates in the projects.json file and reloads the engine data.
    # It does not return anything.
    def refresh_loop():
        import json
        while True:
            # Suspends execution of the current thread for 60 seconds.
            # Returns None.
            time.sleep(60) 
            
            try:
                # Checks if the projects configuration file exists on disk.
                # Returns True if it exists, False otherwise.
                if not os.path.exists(PROJECTS_FILE):
                    continue
                    
                # Opens the projects.json file for reading.
                # Returns a file object.
                with open(PROJECTS_FILE, encoding="utf-8") as f:
                    # Parses the JSON file content into a Python dictionary.
                    # Returns a dictionary representing the projects.
                    projects_data = json.load(f).get("projects", [])
                
                # Creates a list of all current active engine IDs to iterate over safely.
                # Returns a list of project IDs.
                current_engine_ids = list(_engines.keys())
                for pid in current_engine_ids:
                    # Retrieves the engine object for a given project ID.
                    # Returns a LabelingEngine instance or None.
                    engine = _engines.get(pid)
                    if not engine: continue
                    
                    # Checks if the engine's storage is of type RemoteStorage.
                    # Returns True or False.
                    if isinstance(engine._storage, RemoteStorage):
                        # Safely imports the load_projects function.
                        from CORE.persistence import load_projects
                        # Loads the current project configuration from the filesystem.
                        # Returns a list of project dictionaries.
                        projects_data = load_projects(PROJECTS_FILE)
                        # Finds the specific project configuration matching the current engine.
                        # Returns a project dictionary or None.
                        project = next((p for p in projects_data if p["id"] == pid), None)
                        if project:
                            # Commands the engine to reload its remote source data.
                            # Returns None.
                            engine.load_source(project["source_csv"])
            except Exception as e:
                # Retrieves the project's named logger for error reporting.
                # Returns a Logger instance.
                logging.getLogger("LabelingSystem").error(f"Background refresher error: {e}")

    # Initializes a new Thread object targeting the refresh loop as a background daemon.
    # Returns a Thread object.
    thread = threading.Thread(target=refresh_loop, daemon=True)
    # Starts the newly created thread.
    # Returns None.
    thread.start()

# Start the refresher as soon as the module is loaded
start_refresher()

# Adds Cross-Origin Resource Sharing (CORS) headers to outgoing Flask responses.
# This is necessary for development environments where the frontend and backend run on different ports.
# Returns the Flask response object with the added headers.
@app.after_request
def add_cors_headers(response):
    # Retrieves the 'Origin' header from the incoming request.
    # Returns a string representing the requester's origin.
    origin = request.headers.get("Origin", "")
    # Allow localhost development ports.
    if origin in ("http://localhost:5173", "http://127.0.0.1:5173"):
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
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
    
    return f"<h1>Internal Server Error</h1><pre>{str(e)}</pre>", 500
