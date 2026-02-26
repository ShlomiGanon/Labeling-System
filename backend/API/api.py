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
from CORE.persistence import load_projects, save_projects
import CORE.workflows as workflows
from CORE.storage import LocalStorage
from CORE.models import WorkflowType, EntityType, Sentiment, ImageTextRelationship, CustomLabel

# Create a Blueprint to modularize our routes
api_bp = Blueprint('api', __name__)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Internal Helpers
# ---------------------------------------------------------------------------


# Retrieves the username of the currently logged-in user from the active session.
# Returns the username string if it exists, otherwise returns None.
def current_user() -> str | None:
    # Accesses the session dictionary to look up the 'user_name' key.
    # Returns the value associated with the key or None.
    return session.get("user_name")


# Validates that a user is logged in before allowing access to protected API endpoints.
# This serves as a security gate for the application's core functionality.
# Returns a Flask JSON error response with status 401 if not logged in, otherwise returns None.
def require_login():
    # Checks the session for an active username.
    # Returns the username string or None.
    if not current_user():
        # Generates a standard JSON error message for unauthorized access.
        # Returns a Flask response object.
        return jsonify({"error": "Unauthorized. Please log in."}), 401
    return None

# Serves the compiled React frontend application from the static distribution folder.
# It acts as a fallback handler, directing non-API requests to the SPA's entry point.
# Returns a static file or the index.html content as a Flask response.
@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_react(path):
    # Checks if the requested path is intended for the API rather than the frontend.
    # Returns True if it starts with 'api/', False otherwise.
    if path.startswith("api/"):
        # Logs a warning about an invalid attempt to access a non-existent API route.
        # Returns None.
        logger.warning(f"API Route not found: {path}")
        # Returns a JSON error indicating the resource was not found.
        # Returns a Flask response object.
        return jsonify({"error": "Route not found"}), 404

    # Constructs the absolute path to the frontend's distribution directory.
    # Returns a path string.
    dist_dir = os.path.join(app.root_path, "..", "..", "frontend", "dist")
    # Joins the distribution directory with the specific requested path.
    # Returns a full file path string.
    full_path = os.path.join(dist_dir, path)
    
    # Determines if the requested file exists on the server's disk.
    # Returns True if the path exists, False otherwise.
    if path and os.path.exists(full_path):
        # Sends a specific static file (like CSS or JS) from the disk to the browser.
        # Returns a Flask response object.
        return send_from_directory(dist_dir, path)
    # Serves the main index.html file to let React handle the internal routing.
    # Returns a Flask response object.
    return send_from_directory(dist_dir, "index.html")

# Responds to HTTP OPTIONS requests used for CORS pre-flight checks.
# It confirms to the browser that cross-origin communication is permitted for the requested route.
# Returns an empty string and a 204 No Content status code.
@api_bp.route("/<path:path>", methods=["OPTIONS"])
def options_handler(path):
    return "", 204

# Authenticates a user by storing their provided username in the server session.
# This simple login mechanism establishes the identity for subsequent labeling activities.
# Returns a JSON response containing the confirmed username.
@api_bp.route("/login", methods=["POST"])
def login():
    # Extracts the JSON payload from the incoming request.
    # Returns a dictionary.
    data      = request.get_json(force=True)
    # Retrieves and cleans the 'user_name' field from the input data.
    # Returns a stripped string.
    user_name = (data.get("user_name") or "").strip()

    if not user_name:
        # Returns an error if the username provided is empty or whitespace.
        # Returns a Flask response object.
        return jsonify({"error": "Empty username."}), 400

    # Stores the validated username in the persistent session cookie.
    # Returns None.
    session["user_name"] = user_name
    # Confirms the successful login by returning the username.
    # Returns a Flask response object.
    return jsonify({"user_name": user_name})


# Logs out the current user, clearing their session and releasing any checked-out labeling tasks.
# This ensures that rows being worked on are returned to the queue if the user leaves.
# Returns a JSON response indicating whether a row was released.
@api_bp.route("/logout", methods=["POST"])
def logout():
    # Retrieves the identity of the user initiating the logout.
    # Returns a username string or None.
    user     = current_user()
    released = False

    if user:
        # Dynamically imports the active engines dictionary to avoid potential circular dependencies.
        # Returns a dictionary of LabelingEngine instances.
        from CORE.server import _engines
        for engine in _engines.values():
            # Attempts to release any row currently locked by the logging-out user.
            # Returns True if a row was released, False otherwise.
            if engine.release_row(user):
                released = True

    # Wipes all data from the current user's session.
    # Returns None.
    session.clear()
    # Confirms completion of logout and informs if any task was recycled.
    # Returns a Flask response object.
    return jsonify({"released": released})


# Retrieves basic information about the currently authenticated session.
# This is used by the frontend to verify if the user needs to log in again.
# Returns a JSON response containing the current username.
@api_bp.route("/me", methods=["GET"])
def me():
    # Fetches the username from the session helper.
    # Returns a username string or None.
    return jsonify({"user_name": current_user()})


# ---------------------------------------------------------------------------
# Project Management Endpoints
# ---------------------------------------------------------------------------

# Compiles and returns a comprehensive list of all projects and their current status.
# It merges static project metadata with dynamic progress data from each labeling engine.
# Returns a JSON list of project summaries.
@api_bp.route("/projects", methods=["GET"])
def list_projects():
    # Verifies if the requester is an authenticated user.
    # Returns a Flask response object or None.
    auth_check = require_login()
    if auth_check: return auth_check

    # Loads the full list of projects defined in the configuration file.
    # Returns a list of dictionaries.
    projects = load_projects(PROJECTS_FILE)
    result = []
    
    for p in projects:
        try:
            # Retrieves or initializes the labeling engine for the specific project.
            # Returns a LabelingEngine instance.
            engine = get_engine(p)
            # Creates a shallow copy of the project dictionary to avoid mutating the original.
            # Returns a modified dictionary copy.
            proj_summary = p.copy()
            # Injects dynamic progress metrics (remaining rows and completion status).
            # Returns None (modifies proj_summary in-place).
            proj_summary.update({
                "rows_remaining": engine.get_queue_size(),
                "is_finished": engine.is_finished()
            })
            
            # Checks if the engine encountered an error during its own initialization.
            # Returns the error string or None.
            if getattr(engine, "init_error", None):
                proj_summary["init_error"] = engine.init_error
                
            result.append(proj_summary)
        except Exception as e:
            # Logs a failure to load an engine for a specific project.
            # Returns None.
            logger.error(f"Failed to load project '{p['name']}': {e}")
            result.append({
                "id": p["id"], 
                "name": p["name"], 
                "error": "Engine initialization failed"
            })
            
    # Returns the compiled project list as a JSON response.
    # Returns a Flask response object.
    return jsonify({"projects": result})


# Processes an uploaded CSV file, validating its format and saving it to the local storage directory.
# This serves as the primary way to ingest new raw data into the labeling system.
# Returns a JSON response containing the relative path to the saved file.
@api_bp.route("/upload-csv", methods=["POST"])
def upload_csv():
    # Ensures the user has permissions to upload files.
    # Returns a Flask response or None.
    auth_check = require_login()
    if auth_check: return auth_check

    # Checks if the request contains an attached file part.
    # Returns True or False.
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400

    f = request.files['file']
    # Verifies that a valid filename was provided.
    # Returns True if missing/empty.
    if not f or not f.filename:
        return jsonify({"error": "Empty filename"}), 400
    # Restricts uploads to the CSV file format.
    # Returns True if the extension is not .csv.
    if not f.filename.lower().endswith('.csv'):
        return jsonify({"error": "Only CSV files are supported"}), 400

    # Sanity-checks the filename to prevent path injection attacks.
    # Returns a safe filename string.
    safe_name = secure_filename(f.filename)
    # Defines the target directory for data storage within the backend.
    # Returns a path string.
    save_dir  = os.path.join("backend", "data")
    # Ensures the storage directory exists on the disk.
    # Returns None.
    os.makedirs(save_dir, exist_ok=True)
    # Constructs the full destination path for the uploaded file.
    # Returns a path string.
    save_path = os.path.join(save_dir, safe_name)
    # Writes the file content from the request to the specified disk location.
    # Returns None.
    f.save(save_path)

    # Returns the normalized path for future reference in project creation.
    # Returns a Flask response object.
    return jsonify({"path": save_path.replace("\\", "/")}), 200


# Registers a new labeling project with a specific workflow and data source.
# It handles both predefined (A, B, C) and custom modular workflows.
# Returns a JSON representation of the newly created project.
@api_bp.route("/projects", methods=["POST"])
def create_project():
    # Validates user session before allowing project creation.
    # Returns a Flask response or None.
    auth_check = require_login()
    if auth_check: return auth_check

    # Parses the project parameters from the POST body.
    # Returns a dictionary.
    data = request.get_json(force=True)
    # Extracts and cleans the project name.
    # Returns a string.
    name = (data.get("name") or "").strip()
    # Retrieves optional custom UI schema.
    # Returns a dictionary or None.
    custom_schema = data.get("custom_schema")

    # Accept csv_sources (array, new) or source_csv (string, legacy) — normalize to a list.
    csv_sources = data.get("csv_sources")
    if csv_sources is not None:
        csv_sources = [p.strip() for p in csv_sources if isinstance(p, str) and p.strip()]
    else:
        legacy = (data.get("source_csv") or "").strip()
        csv_sources = [legacy] if legacy else []

    if not name:
        return jsonify({"error": "Project name is required."}), 400
    if not csv_sources:
        return jsonify({"error": "At least one source CSV is required (csv_sources or source_csv)."}), 400

    # Decides the workflow strategy based on the input schema.
    if custom_schema:
        workflow_type = WorkflowType.CUSTOM
    else:
        try:
            # Maps the string identifier (A/B/C) to a typed WorkflowType enum.
            # Returns a WorkflowType instance.
            wtype_str = (data.get("workflow_type") or "").strip().upper()
            workflow_type = WorkflowType(wtype_str)
        except ValueError:
            return jsonify({"error": "Invalid workflow_type. Must be A, B, C, or provide a custom_schema."}), 400

    # Normalizes the project name for use in filesystem paths.
    # Returns a slugified string.
    safe_name  = name.replace(" ", "_").lower()
    # Generates a predictable results file path for the project.
    # Returns a path string.
    master_csv = f"backend/data/master_{safe_name}.csv"

    # Constructs the core project configuration object.
    # Returns a dictionary.
    project = {
        "id":            str(uuid.uuid4()),
        "name":          name,
        "owner":         current_user(),
        "workflow_type": workflow_type.value,
        "csv_sources":   csv_sources,
        "master_csv":    master_csv,
    }

    if custom_schema:
        # Attaches the custom UI blueprint to the project if applicable.
        # Returns None.
        project["custom_schema"] = custom_schema

    # Appends the new project to the global configuration list.
    # Returns a list of dictionaries.
    projects = load_projects(PROJECTS_FILE)
    projects.append(project)
    # Persists the updated project list to the disk.
    # Returns None.
    save_projects(PROJECTS_FILE, projects)

    # Triggers the engine initialization immediately to check for data errors.
    # Returns a LabelingEngine instance.
    get_engine(project)

    # Returns the finalized project metadata to the frontend.
    # Returns a Flask response object.
    return jsonify(project), 201


# Updates the metadata and configuration of an existing labeling project.
# If the source data file is changed, it invalidates the current engine's cache to ensure new data is loaded.
# Returns the updated project dictionary.
@api_bp.route("/projects/<project_id>", methods=["PUT"])
def update_project(project_id):
    # Verifies user authentication before allowing modifications.
    # Returns a Flask response or None.
    auth_check = require_login()
    if auth_check: return auth_check

    # Extracts the updated project fields from the request body.
    # Returns a dictionary.
    data = request.get_json(force=True)
    # Retrieves the current list of all projects.
    # Returns a list of dictionaries.
    projects = load_projects(PROJECTS_FILE)
    
    # Locates the index of the target project within the global list.
    # Returns an integer index or -1 if not found.
    idx = next((i for i, p in enumerate(projects) if p["id"] == project_id), -1)
    if idx == -1:
        return jsonify({"error": "Project not found"}), 404

    project = projects[idx]
    
    # Update fields
    if "name" in data: 
        project["name"] = data["name"].strip()
    if "owner" in data: 
        project["owner"] = data["owner"].strip()
    if "workflow_type" in data:
        project["workflow_type"] = data["workflow_type"]
    
    if "custom_schema" in data:
        project["custom_schema"] = data["custom_schema"]
    elif "workflow_type" in data and data["workflow_type"] != "CUSTOM":
        # Removes the custom schema if the project is being reverted to a preset workflow.
        # Returns None.
        project.pop("custom_schema", None)
    
    source_changed = False
    if "csv_sources" in data:
        new_sources = [p.strip() for p in data["csv_sources"] if isinstance(p, str) and p.strip()]
        if new_sources != project.get("csv_sources"):
            project["csv_sources"] = new_sources
            project.pop("source_csv", None)  # Remove legacy field if present
            source_changed = True
    elif "source_csv" in data:
        new_source = data["source_csv"].strip()
        old_sources = project.get("csv_sources") or (
            [project["source_csv"]] if project.get("source_csv") else []
        )
        if [new_source] != old_sources:
            project["csv_sources"] = [new_source]
            project.pop("source_csv", None)
            source_changed = True
            
    # Persists the modified project list back to the configuration file.
    # Returns None.
    save_projects(PROJECTS_FILE, projects)

    # Identifies if a source change requires a reset of the labeling engine.
    if source_changed:
        # Accesses the global registry of active labeling engines.
        # Returns a dictionary.
        from CORE.server import _engines
        if project_id in _engines:
            # Removes the stale engine instance from memory.
            # Returns None.
            del _engines[project_id]
            # Logs the invalidation of the engine for audit purposes.
            # Returns None.
            logger.info(f"Invalidated engine cache for project {project_id} due to source change.")

    return jsonify(project), 200


# Permanently removes a labeling project from the system and optionally cleans up its data files.
# It handles the deletion of both the configuration entry and the physical CSV results/source files.
# Returns a JSON confirmation of the deleted project ID.
@api_bp.route("/projects/<project_id>", methods=["DELETE"])
def delete_project(project_id):
    # Ensures the user is authorized to perform destructive operations.
    # Returns a Flask response or None.
    auth_check = require_login()
    if auth_check: return auth_check

    # Loads projects to find the one targeted for deletion.
    # Returns a list of dictionaries.
    projects  = load_projects(PROJECTS_FILE)
    # Finds the specific project metadata by ID.
    # Returns a project dictionary or None.
    project   = next((p for p in projects if p["id"] == project_id), None)

    if not project:
        return jsonify({"error": "Project not found"}), 404

    # Checks the query parameters to decide if physical files should be wiped from the disk.
    # Returns True if 'delete_files' is set to 'true'.
    delete_files = request.args.get("delete_files", "false").lower() == "true"

    if delete_files:
        # Collect source files: prefer csv_sources (array, new), fall back to source_csv (legacy).
        source_paths = project.get("csv_sources") or (
            [project["source_csv"]] if project.get("source_csv") else []
        )
        for path in source_paths + [project.get("master_csv", "")]:
            if path and os.path.isfile(path):
                try:
                    os.remove(path)
                    logger.info(f"Deleted file: {path}")
                except Exception as e:
                    logger.warning(f"Could not delete {path}: {e}")

    # Creates a new projects list excluding the one being deleted.
    # Returns a filtered list.
    updated = [p for p in projects if p["id"] != project_id]
    # Saves the reduced project list to the configuration file.
    # Returns None.
    save_projects(PROJECTS_FILE, updated)

    return jsonify({"deleted": project_id}), 200


# ---------------------------------------------------------------------------
# Task Execution Endpoints
# ---------------------------------------------------------------------------

# Fetches the next available data row for the current user to perform a labeling task.
# It automatically provides the correct media links and workflow context required by the frontend.
# Returns a JSON object with the row data or a finished status.
@api_bp.route("/projects/<project_id>/task", methods=["GET"])
def get_task(project_id: str):
    # Verifies that a user is logged in before serving task data.
    # Returns a Flask response or None.
    auth_check = require_login()
    if auth_check: return auth_check

    # Loads the project metadata to identify the specific labeling configuration.
    # Returns a list of dictionaries.
    projects = load_projects(PROJECTS_FILE)
    # Finds the target project by its unique identifier.
    # Returns a dictionary or None.
    project  = next((p for p in projects if p["id"] == project_id), None)
    if not project:
        return jsonify({"error": "Project not found"}), 404

    # Accesses the singleton engine instance for the project.
    # Returns a LabelingEngine object.
    engine = get_engine(project)
    
    # Reports any critical data loading errors encountered during engine startup.
    # Returns an error string or None.
    if getattr(engine, "init_error", None):
        return jsonify({"error": f"Data Loading Error: {engine.init_error}"}), 500

    # Requests the next unassigned row from the engine's internal queue.
    # Returns a SourceRow object or None.
    row = engine.get_next_row(current_user())

    if row is None:
        # Returns a specialized signal indicating that all data for this project has been processed.
        # Returns a JSON response.
        return jsonify({"finished": True})

    # Resolves the image path into a fully qualified URL for frontend display.
    # Returns a URL string or an empty string.
    image_link = LocalStorage().get_media_link(row.image_path) if row.has_image() else ""

    # Checks the global application state for UI preferences.
    # Returns a boolean value.
    from CORE.server import SHOW_IMAGE_LOADING_BAR

    # Packs the row data into a JSON response for the frontend UI.
    # Returns a Flask response object.
    return jsonify({
        "row_id":        row.row_id,
        "image_path":    image_link,
        "text_content":  row.text_content,
        "workflow_type": project["workflow_type"],
        "has_image":     row.has_image(),
        "has_text":      row.has_text(),
        "source_csv":    row.source_csv,
        "use_image_loading_bar": SHOW_IMAGE_LOADING_BAR,
    })


# Retrieves the UI configuration schema that defines the form fields for a specific project.
# This allows the frontend to dynamically render the correct questions for any workflow type.
# Returns a JSON schema definition for the workflow.
@api_bp.route("/projects/<project_id>/config", methods=["GET"])
def get_project_config(project_id: str):
    # Ensures security by blocking unauthenticated configuration requests.
    # Returns a Flask response or None.
    auth_check = require_login()
    if auth_check: return auth_check

    # Loads project definitions to determine which schema to provide.
    # Returns a list of dictionaries.
    projects = load_projects(PROJECTS_FILE)
    # Finds the requested project in the database.
    # Returns a single project dictionary or None.
    project  = next((p for p in projects if p["id"] == project_id), None)
    if not project:
        return jsonify({"error": "Project not found"}), 404

    # Imports schema definitions and type enums for resolution.
    from CORE.models import WORKFLOW_SCHEMAS, WorkflowType
    # Casts the stored workflow string back into a typed enum for comparison.
    # Returns a WorkflowType enum member.
    wtype = WorkflowType(project["workflow_type"])

    # Returns the user-defined JSON schema directly if the project is a modular 'Custom' type.
    if wtype == WorkflowType.CUSTOM:
        # Retrieves the baked-in UI blueprint from the project record.
        # Returns a dictionary or None.
        custom_schema = project.get("custom_schema")
        if not custom_schema:
            return jsonify({"error": "Custom schema not found in project"}), 404
        # Merges the schema with the type identifier for frontend routing.
        # Returns a Flask response object.
        return jsonify({"workflow_type": "CUSTOM", **custom_schema})

    # Retrieves the hardcoded schema object for standard preset workflows (A, B, or C).
    # Returns a WorkflowSchema object.
    schema = WORKFLOW_SCHEMAS.get(wtype)
    if not schema:
        return jsonify({"error": "Schema not found"}), 404

    # Serializes the schema object into a dictionary format compatible with React.
    # Returns a Flask response object.
    return jsonify(schema.to_dict())


# Processes and persists user-submitted labels for a specific data row.
# It dispatches the submission to the appropriate workflow handler based on project type.
# Returns a JSON confirmation with current project progress stats.
@api_bp.route("/projects/<project_id>/submit", methods=["POST"])
def submit_task(project_id: str):
    # Validates that the session is still active before accepting data.
    # Returns a Flask response or None.
    auth_check = require_login()
    if auth_check: return auth_check

    # Loads the project context to ensure the submission matches the project's requirements.
    # Returns a list of dictionaries.
    projects = load_projects(PROJECTS_FILE)
    # Matches the project ID to find the active configuration.
    # Returns a dictionary or None.
    project  = next((p for p in projects if p["id"] == project_id), None)
    if not project:
        return jsonify({"error": "Project not found"}), 404

    # Parses the submitted label data from the request JSON.
    # Returns a dictionary.
    data   = request.get_json(force=True)
    # Retrieves the active engine dedicated to this project.
    # Returns a LabelingEngine instance.
    engine = get_engine(project)
    # Identifies the logged-in labeler.
    # Returns a string.
    user   = current_user()
    # Identifies exactly which row is being submitted.
    # Returns a string.
    row_id = str(data.get("row_id", ""))
    
    # Determines the processing path based on the project's workflow type.
    # Returns a WorkflowType instance.
    wtype  = WorkflowType(project["workflow_type"])

    try:
        # Routes the submission to the specific handler for Image-Text Relationships.
        if wtype == WorkflowType.IMAGE_TEXT_RELATIONSHIP:
            # Converts the raw text input into a typed relationship enum.
            # Returns an ImageTextRelationship member.
            rel = ImageTextRelationship(data.get("relationship", ""))
            # Passes the validated label to the workflow coordinator for processing.
            # Returns a boolean success status.
            success = workflows.process_image_text_relationship(engine, user, row_id, rel)

        # Handles the multi-step Entity and Sentiment workflow submission.
        elif wtype == WorkflowType.ENTITY_SENTIMENT:
            # Casts raw inputs into their respective backend type enums.
            # Returns EntityType and Sentiment enum members.
            etype = EntityType(data.get("entity_type", ""))
            sent  = Sentiment(data.get("sentiment", ""))
            # Progresses the internal state machine for the current labeling session.
            # Returns EntitySentimentLabel objects (intermediate state).
            workflows.process_entity_identification(user, row_id, data.get("entity_name", ""), etype)
            workflows.process_topic_assignment(user, row_id, data.get("topic", ""))
            # Finalizes the sequence and persists the multi-field result.
            # Returns a boolean success status.
            success = workflows.process_entity_sentiment(engine, user, row_id, sent)

        # Processes simple text caption submissions.
        elif wtype == WorkflowType.GOLDEN_CAPTION:
            # Calls the caption-specific workflow handler.
            # Returns a boolean success status.
            success = workflows.process_caption(engine, user, row_id, data.get("caption", ""))

        # Handles highly flexible user-defined schemas by mapping IDs to human-readable labels.
        elif wtype == WorkflowType.CUSTOM:
            # Filters out internal metadata to isolate the actual answers.
            # Returns a dictionary of user answers.
            excluded = {"row_id"}
            custom_fields = {k: v for k, v in data.items() if k not in excluded}

            # Builds a translation dictionary to convert opaque field IDs into readable CSV headers.
            # Returns a dictionary mapping IDs to labels.
            id_to_label = {}
            # Retrieves the blueprint for the custom project.
            # Returns a dictionary.
            custom_schema = project.get("custom_schema", {})
            for step in custom_schema.get("steps", []):
                for field in step.get("fields", []):
                    # Extracts the ID and Label for every input component in the workflow.
                    # Returns strings.
                    fid   = field.get("id", "")
                    label = field.get("label", "").strip()
                    if fid and label:
                        id_to_label[fid] = label

            # Iterates through submissions and renames keys for the final CSV export.
            seen_labels = {}
            renamed_fields = {}
            for k, v in custom_fields.items():
                # Looks up the human-readable name or keeps the ID as a fallback.
                # Returns a string.
                col_name = id_to_label.get(k, k)
                if col_name in seen_labels:
                    # Handles naming collisions if multiple fields use the same label.
                    # Returns a string.
                    seen_labels[col_name] += 1
                    col_name = f"{col_name}_{seen_labels[col_name]}"
                else:
                    # Tracks occurrences to manage unique column headers.
                    # Returns None.
                    seen_labels[col_name] = 1
                renamed_fields[col_name] = v

            # Hands off the dynamically structured data to the generic custom handler.
            # Returns a boolean success status.
            success = workflows.process_custom_workflow(engine, user, row_id, renamed_fields)

        else:
            return jsonify({"error": "Unknown workflow"}), 400

    except (ValueError, KeyError) as e:
        # Returns a user-friendly error message if data validation or processing failed.
        # Returns a Flask response object.
        return jsonify({"error": str(e)}), 400

    # Returns the updated state of the labeling project after the submission.
    # Returns a Flask response object.
    return jsonify({
        "success":        success,
        "rows_remaining": engine.get_queue_size(),
        "is_finished":    engine.is_finished(),
    })
