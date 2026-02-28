# Flask setup and engine registry.

import os
import sys
import logging
import threading
import time
from flask import Flask, jsonify, request

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("LabelingSystem")

# Base paths used across the backend.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BACKEND_DIR = os.path.join(BASE_DIR, "backend")
CORE_DIR = os.path.dirname(os.path.abspath(__file__))

# Make local backend modules importable.
if CORE_DIR not in sys.path:
    sys.path.insert(0, CORE_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# Frontend flag for image loading behavior.
SHOW_IMAGE_LOADING_BAR = True

from labeling_engine import LabelingEngine
from storage import LocalStorage, RemoteStorage

app = Flask(__name__, static_folder="../../frontend/dist", static_url_path="")
app.secret_key = "labeling-system-secret-key-change-in-production"

PROJECTS_FILE = os.path.join(BASE_DIR, "projects.json")

# Active engines live in memory by project id.
_engines: dict = {}


# Build a per-source output file name for multi-source projects.
def _derive_source_master(project_master: str, source_path: str) -> str:
    master_dir = os.path.dirname(project_master)
    master_stem = os.path.splitext(os.path.basename(project_master))[0]
    source_stem = os.path.splitext(os.path.basename(source_path))[0]
    return os.path.join(master_dir, f"{master_stem}__{source_stem}.csv")


def get_engine(project: dict) -> LabelingEngine:
    pid = project["id"]
    if pid not in _engines:
        # Support both the new list field and the old single-source field.
        raw_sources = project.get("csv_sources") or (
            [project["source_csv"]] if project.get("source_csv") else []
        )

        storage = LocalStorage()
        master_path = os.path.join(BASE_DIR, project["master_csv"])
        engine = LabelingEngine(storage, master_path)
        engine.init_error = None
        engine.source_errors = {}

        # Load all project sources up front.
        multi_source = len(raw_sources) > 1
        for source_path in raw_sources:
            try:
                is_remote_source = source_path.startswith("http://") or source_path.startswith("https://")
                source_storage = RemoteStorage() if is_remote_source else LocalStorage()
                if is_remote_source:
                    per_master = _derive_source_master(master_path, source_path) if multi_source else None
                    engine.load_source(source_path, master_path=per_master, storage=source_storage)
                else:
                    # Local sources are stored as project-relative paths.
                    full_source_path = os.path.join(BASE_DIR, source_path)
                    if os.path.isfile(full_source_path):
                        per_master = _derive_source_master(master_path, full_source_path) if multi_source else None
                        engine.load_source(full_source_path, master_path=per_master, storage=source_storage)
                    else:
                        msg = f"Source CSV not found at: {full_source_path}"
                        logger.warning(msg)
                        engine.source_errors[source_path] = msg
            except Exception as e:
                msg = str(e)
                logger.error(f"Error loading source '{source_path}' for project {pid}: {msg}")
                engine.source_errors[source_path] = msg

        if engine.source_errors:
            engine.init_error = "; ".join(engine.source_errors.values())

        _engines[pid] = engine

    return _engines[pid]


# Refresh remote projects in the background.
def start_refresher():
    def refresh_loop():
        import json

        while True:
            time.sleep(60)

            try:
                if not os.path.exists(PROJECTS_FILE):
                    continue

                from CORE.persistence import load_projects

                projects_data = load_projects(PROJECTS_FILE)
                current_engine_ids = list(_engines.keys())
                for pid in current_engine_ids:
                    engine = _engines.get(pid)
                    if not engine:
                        continue

                    if isinstance(engine._storage, RemoteStorage):
                        project = next((p for p in projects_data if p["id"] == pid), None)
                        if project:
                            engine.load_source(project["source_csv"])
            except Exception as e:
                logger.error(f"Background refresher error: {e}")

    thread = threading.Thread(target=refresh_loop, daemon=True)
    thread.start()


start_refresher()


# Allow the local frontend to call the backend with cookies.
@app.after_request
def add_cors_headers(response):
    origin = request.headers.get("Origin", "")

    if origin in ("http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:5000"):
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"

    return response


# Return JSON errors for API calls and plain HTML for everything else.
@app.errorhandler(Exception)
def handle_exception(e):
    import traceback

    if request.path.startswith("/api/"):
        logger.error(f"API Error at {request.path}: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            "error": "Internal Server Error",
            "message": str(e),
            "traceback": traceback.format_exc().splitlines()
        }), 500

    return f"<h1>Internal Server Error</h1><pre>{str(e)}</pre>", 500
