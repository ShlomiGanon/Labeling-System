# main.py
# -------
# Firebase Cloud Functions entry point.
# All routes from backend/API/api.py are represented here.
#
# Migration status
# ─────────────────────────────────────────────────────────────
# [x] POST   /api/login              → login()
# [x] POST   /api/logout             → logout()
# [x] GET    /api/me                 → me()
# [x] GET    /api/projects           → projects()  method=GET
# [x] POST   /api/projects           → projects()  method=POST
# [x] PUT    /api/projects/<id>      → projects()  method=PUT,    path=/<id>
# [x] DELETE /api/projects/<id>      → projects()  method=DELETE, path=/<id>
# [x] GET    /api/projects/<id>/task → tasks()      path=/<id>    [Phase 4 TODO]
# [x] GET    /api/projects/<id>/config → config()   path=/<id>
# [x] POST   /api/projects/<id>/submit → submit()   path=/<id>    [Phase 4 TODO]
# [x] GET    /api/manager/dashboard  → dashboard()
# [x] GET    /api/manager/download/<id> → download() path=/<id>   [Phase 3 TODO]
# [x] POST   /api/upload-csv         → upload_csv()               [Phase 3 TODO]
#
# ─────────────────────────────────────────────────────────────
# Auth note
# ─────────────────────────────────────────────────────────────
# Flask used plain username strings stored in session["user_name"].
# Cloud Functions use Firebase UID decoded from Authorization: Bearer <token>.
#
# Username is stored in Firestore at:  users/{uid}.username
#
# Impact on "owner" field in projects:
#   Old system  → owner = "username" (plain string, e.g. "ofek")
#   New system  → owner = Firebase UID (opaque, e.g. "abc123xyz...")
# The migration script must map old usernames → UIDs when copying projects.
#
# ─────────────────────────────────────────────────────────────
# Phase 3 TODOs (Firebase Storage):
#   - upload_csv: store uploaded files in Firebase Storage
#   - download:   serve CSV built from Firestore labels collection
#
# Phase 4 TODOs (Firestore queue engine):
#   - tasks:      claim a row from queue_rows collection via runTransaction
#   - submit:     write label to labels collection, update queue_rows status
#   - logout:     release locked queue_rows for this UID
#   - dashboard:  compute rows_remaining/completed from labels + queue_rows

import json
import logging
import uuid

from firebase_admin import auth as firebase_auth
from firebase_admin import firestore as fb_firestore
from firebase_admin import initialize_app
from firebase_functions import https_fn

from persistence_firestore import (
    create_project as fs_save_project,   # .set() — used for create and full-replace update
    delete_project as fs_delete_project,
    get_project,
    load_projects,
)

logger = logging.getLogger("LabelingSystem")

initialize_app()

# ── Workflow schemas ─────────────────────────────────────────────────────────
# Inlined from backend/CORE/models.py — kept in sync manually.
# The frontend's translations.js already has EN translations for these labels.

_WORKFLOW_SCHEMAS = {
    "A": {
        "workflow_type": "A",
        "steps": [{
            "title": "בדיקת קשר תמונה-טקסט",
            "fields": [{
                "id": "relationship",
                "label": "מה סוג הקשר בין התמונה לטקסט?",
                "component": "button_group",
                "placeholder": "",
                "options": ["Independent", "Context-Dependent", "Noise"],
            }],
        }],
    },
    "B": {
        "workflow_type": "B",
        "steps": [
            {
                "title": "צעד 1: זיהוי ישות",
                "fields": [
                    {
                        "id": "entity_name",
                        "label": "שם הישות:",
                        "component": "input_text",
                        "placeholder": "הכנס שם ישות...",
                        "options": [],
                    },
                    {
                        "id": "entity_type",
                        "label": "סוג הישות:",
                        "component": "select",
                        "placeholder": "",
                        "options": ["Person", "Org", "Place"],
                    },
                ],
            },
            {
                "title": "צעד 2: נושא",
                "fields": [{
                    "id": "topic",
                    "label": "מה הנושא העיקרי?",
                    "component": "input_text",
                    "placeholder": "כתוב את הנושא...",
                    "options": [],
                }],
            },
            {
                "title": "צעד 3: סנטימנט",
                "fields": [{
                    "id": "sentiment",
                    "label": "מה הסנטימנט?",
                    "component": "button_group",
                    "placeholder": "",
                    "options": ["Good", "Bad", "Trust", "Fear", "Anger"],
                }],
            },
        ],
    },
    "C": {
        "workflow_type": "C",
        "steps": [{
            "title": "תיאור תמונה (Golden Caption)",
            "fields": [{
                "id": "caption",
                "label": "תאר את התמונה בצורה מפורטת:",
                "component": "textarea",
                "placeholder": "הכנס תיאור כאן...",
                "options": [],
            }],
        }],
    },
}

# ── Shared helpers ───────────────────────────────────────────────────────────

def _get_db():
    """Return a Firestore client. App is already initialised above."""
    return fb_firestore.client()


def _json(data: dict, status: int = 200) -> https_fn.Response:
    """Build a JSON response with correct Content-Type and CORS headers."""
    return https_fn.Response(
        json.dumps(data, ensure_ascii=False),
        status=status,
        mimetype="application/json",
        headers=_cors_headers(),
    )


def _cors_headers() -> dict:
    return {
        "Access-Control-Allow-Origin":  "*",
        "Access-Control-Allow-Headers": "Content-Type, Authorization",
        "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
    }


def _require_auth(req: https_fn.Request):
    """
    Verify the Firebase ID token from Authorization: Bearer <token>.
    Returns (uid, None) on success.
    Returns (None, error_response) on failure — caller must return immediately.
    """
    auth_header = req.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None, _json({"error": "Unauthorized. No token provided."}, 401)
    token = auth_header.split("Bearer ", 1)[1].strip()
    try:
        decoded = firebase_auth.verify_id_token(token)
        return decoded["uid"], None
    except Exception:
        return None, _json({"error": "Unauthorized. Invalid or expired token."}, 401)


def _get_uid_or_none(req: https_fn.Request):
    """
    Try to decode the Firebase token silently.
    Returns the UID string on success, or None on any failure.
    Used by the /me endpoint which must not return 401 when called unauthenticated.
    """
    auth_header = req.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header.split("Bearer ", 1)[1].strip()
    try:
        return firebase_auth.verify_id_token(token)["uid"]
    except Exception:
        return None


def _extract_project_id(req: https_fn.Request):
    """
    Extract a project UUID from req.path.
    Cloud Function URL: .../function_name/{uuid}
    req.path will be    "/{uuid}"  or  "/"  or  ""
    Returns the UUID string, or None if the path is root / empty.
    """
    segment = req.path.strip("/")
    return segment if segment else None


def _preflight(req: https_fn.Request):
    """Return a CORS preflight response if this is an OPTIONS request."""
    if req.method == "OPTIONS":
        return https_fn.Response("", status=204, headers=_cors_headers())
    return None


# ── POST /api/login ──────────────────────────────────────────────────────────

@https_fn.on_request()
def login(req: https_fn.Request) -> https_fn.Response:
    """
    Register or update the display username for a Firebase-authenticated user.

    Body: { user_name: "ofek" }

    Stores the username in Firestore at users/{uid}.username so it can be
    retrieved by the /me endpoint and displayed in the UI.

    Flask equivalent: login() in api.py  (session["user_name"] = user_name)
    """
    if p := _preflight(req): return p

    uid, err = _require_auth(req)
    if err:
        return err

    data      = req.get_json(force=True) or {}
    user_name = (data.get("user_name") or "").strip()

    if not user_name:
        return _json({"error": "Empty username."}, 400)

    db = _get_db()
    db.collection("users").document(uid).set(
        {"username": user_name, "uid": uid},
        merge=True,   # preserve any other fields on the document
    )

    logger.info(f"User '{user_name}' (uid={uid}) logged in.")
    return _json({"user_name": user_name})


# ── POST /api/logout ─────────────────────────────────────────────────────────

@https_fn.on_request()
def logout(req: https_fn.Request) -> https_fn.Response:
    """
    Log out the current user.

    Cloud Functions are stateless — there is no server-side session to clear.
    The client must call firebase.auth().signOut() after this endpoint.

    TODO (Phase 4): release any queue_rows documents where locked_by == uid
    so the row returns to "available" status for other labelers.

    Flask equivalent: logout() in api.py  (session.clear() + engine.release_row())
    """
    if p := _preflight(req): return p

    uid, err = _require_auth(req)
    if err:
        return err

    # TODO (Phase 4): query queue_rows where locked_by == uid, set status = "available"
    released = False

    logger.info(f"User uid={uid} logged out. Queue release pending Phase 4.")
    return _json({"released": released})


# ── GET /api/me ──────────────────────────────────────────────────────────────

@https_fn.on_request()
def me(req: https_fn.Request) -> https_fn.Response:
    """
    Return the display username for the currently authenticated user.
    Returns { user_name: null } (not 401) if no valid token is present —
    this mirrors the Flask behaviour where /api/me is public.

    Flask equivalent: me() in api.py  (return session.get("user_name"))
    """
    if p := _preflight(req): return p

    uid = _get_uid_or_none(req)
    if not uid:
        return _json({"user_name": None})

    db  = _get_db()
    doc = db.collection("users").document(uid).get()
    user_name = doc.to_dict().get("username") if doc.exists else None

    return _json({"user_name": user_name})


# ── /api/projects — all four CRUD routes ─────────────────────────────────────

@https_fn.on_request()
def projects(req: https_fn.Request) -> https_fn.Response:
    """
    Project CRUD — all four methods in one function.

    GET    /projects        → list all projects
    POST   /projects        → create a new project
    PUT    /projects/{id}   → update an existing project
    DELETE /projects/{id}   → delete a project
    """
    if p := _preflight(req): return p

    project_id = _extract_project_id(req)

    if req.method == "GET"    and not project_id: return _list_projects(req)
    if req.method == "POST"   and not project_id: return _create_project(req)
    if req.method == "PUT"    and project_id:     return _update_project(req, project_id)
    if req.method == "DELETE" and project_id:     return _delete_project(req, project_id)

    return _json({"error": "Method not allowed or missing project ID."}, 405)


def _list_projects(req: https_fn.Request) -> https_fn.Response:
    """
    Return all projects. rows_remaining / is_finished are read from the
    project document until the queue engine moves to Firestore (Phase 4).

    Flask equivalent: list_projects() in api.py
    """
    uid, err = _require_auth(req)
    if err:
        return err

    result = []
    for p in load_projects():
        summary = p.copy()
        summary.setdefault("rows_remaining", 0)   # TODO Phase 4: count from queue_rows
        summary.setdefault("is_finished", False)
        result.append(summary)

    return _json({"projects": result})


def _create_project(req: https_fn.Request) -> https_fn.Response:
    """
    Create a new project. owner is set to Firebase UID (not plain username).

    Flask equivalent: create_project() in api.py
    """
    uid, err = _require_auth(req)
    if err:
        return err

    data          = req.get_json(force=True) or {}
    name          = (data.get("name") or "").strip()
    custom_schema = data.get("custom_schema")

    csv_sources = data.get("csv_sources")
    if csv_sources is not None:
        csv_sources = [s.strip() for s in csv_sources if isinstance(s, str) and s.strip()]
    else:
        legacy      = (data.get("source_csv") or "").strip()
        csv_sources = [legacy] if legacy else []

    if not name:
        return _json({"error": "Project name is required."}, 400)
    if not csv_sources:
        return _json({"error": "At least one source CSV is required."}, 400)

    if custom_schema:
        workflow_type = "CUSTOM"
    else:
        wtype_str = (data.get("workflow_type") or "").strip().upper()
        if wtype_str not in ("A", "B", "C"):
            return _json({"error": "Invalid workflow_type. Must be A, B, C, or provide a custom_schema."}, 400)
        workflow_type = wtype_str

    safe_name  = name.replace(" ", "_").lower()
    master_csv = f"backend/data/master_{safe_name}.csv"

    project = {
        "id":            str(uuid.uuid4()),
        "name":          name,
        "owner":         uid,
        "workflow_type": workflow_type,
        "csv_sources":   csv_sources,
        "master_csv":    master_csv,
        "is_finished":   False,
    }

    source_labels = data.get("source_labels")
    if source_labels and isinstance(source_labels, dict):
        project["source_labels"] = source_labels
    if custom_schema:
        project["custom_schema"] = custom_schema

    if not fs_save_project(project):
        return _json({"error": "Failed to save project. Please try again."}, 500)

    return _json(project, 201)


def _update_project(req: https_fn.Request, project_id: str) -> https_fn.Response:
    """
    Update a project. Fetches → mutates Python dict → full .set() replace.
    Only the project owner (by Firebase UID) may update.

    Flask equivalent: update_project() in api.py
    """
    uid, err = _require_auth(req)
    if err:
        return err

    project = get_project(project_id)
    if not project:
        return _json({"error": "Project not found"}, 404)
    if project.get("owner") != uid:
        return _json({"error": "Forbidden: you do not own this project."}, 403)

    data = req.get_json(force=True) or {}

    if "name"          in data: project["name"]          = data["name"].strip()
    if "workflow_type" in data: project["workflow_type"] = data["workflow_type"]

    if "custom_schema" in data:
        project["custom_schema"] = data["custom_schema"]
    elif "workflow_type" in data and data["workflow_type"] != "CUSTOM":
        project.pop("custom_schema", None)

    if "source_labels" in data:
        labels = data["source_labels"]
        if isinstance(labels, dict) and labels:
            project["source_labels"] = labels
        else:
            project.pop("source_labels", None)

    source_changed = False
    if "csv_sources" in data:
        new_sources = [s.strip() for s in data["csv_sources"] if isinstance(s, str) and s.strip()]
        if new_sources != project.get("csv_sources"):
            project["csv_sources"] = new_sources
            project.pop("source_csv", None)
            source_changed = True
    elif "source_csv" in data:
        new_source  = data["source_csv"].strip()
        old_sources = project.get("csv_sources") or ([project["source_csv"]] if project.get("source_csv") else [])
        if [new_source] != old_sources:
            project["csv_sources"] = [new_source]
            project.pop("source_csv", None)
            source_changed = True

    if not fs_save_project(project):
        return _json({"error": "Failed to update project. Please try again."}, 500)

    if source_changed:
        # TODO (Phase 4): clear queue_rows sub-collection for this project.
        logger.info(f"Source changed for {project_id}. Queue reset required in Phase 4.")

    return _json(project, 200)


def _delete_project(req: https_fn.Request, project_id: str) -> https_fn.Response:
    """
    Delete a project. Only the project owner (by Firebase UID) may delete.
    delete_files=true is accepted for compatibility but file deletion is Phase 3.

    Flask equivalent: delete_project() in api.py
    """
    uid, err = _require_auth(req)
    if err:
        return err

    project = get_project(project_id)
    if not project:
        return _json({"error": "Project not found"}, 404)
    if project.get("owner") != uid:
        return _json({"error": "Forbidden: you do not own this project."}, 403)

    if req.args.get("delete_files", "false").lower() == "true":
        # TODO (Phase 3): delete source CSVs and master CSV from Firebase Storage.
        logger.warning(
            f"delete_files=true for {project_id}: "
            f"Firebase Storage deletion not yet implemented. Remove files manually."
        )

    if not fs_delete_project(project_id):
        return _json({"error": "Failed to delete project. Please try again."}, 500)

    return _json({"deleted": project_id}, 200)


# ── GET /api/projects/<id>/task ───────────────────────────────────────────────

@https_fn.on_request()
def tasks(req: https_fn.Request) -> https_fn.Response:
    """
    Get the next available row for the authenticated user to label.

    ── PHASE 4 TODO ──────────────────────────────────────────────────────────
    Requires the queue_rows Firestore collection (not yet migrated).
    Implementation plan:
      1. Run a Firestore transaction on queue_rows/{projectId} collection:
           a. Query where status == "available" ORDER BY queue_position LIMIT 1
           b. Atomically set status = "locked", locked_by = uid, locked_at = now()
      2. Return row data (image_path, text_content, etc.)
      3. A Cloud Scheduler job must periodically unlock rows where
         locked_at < now() - N minutes (abandoned row cleanup).
    ──────────────────────────────────────────────────────────────────────────

    Flask equivalent: get_task() in api.py
    """
    if p := _preflight(req): return p

    uid, err = _require_auth(req)
    if err:
        return err

    project_id = _extract_project_id(req)
    if not project_id:
        return _json({"error": "Project ID is required."}, 400)

    project = get_project(project_id)
    if not project:
        return _json({"error": "Project not found"}, 404)

    return _json({
        "error": (
            "Task queue not yet migrated to Firestore (Phase 4). "
            "Use the Flask backend for labeling tasks."
        )
    }, 501)


# ── GET /api/projects/<id>/config ─────────────────────────────────────────────

@https_fn.on_request()
def config(req: https_fn.Request) -> https_fn.Response:
    """
    Return the UI schema for a project's workflow so the frontend can render
    the labeling form dynamically.

    For preset workflows (A, B, C): returns the inlined _WORKFLOW_SCHEMAS entry.
    For CUSTOM workflows: returns the custom_schema stored in the project document.

    Fully implemented — no engine or file-system dependency.

    Flask equivalent: get_project_config() in api.py
    """
    if p := _preflight(req): return p

    uid, err = _require_auth(req)
    if err:
        return err

    project_id = _extract_project_id(req)
    if not project_id:
        return _json({"error": "Project ID is required."}, 400)

    project = get_project(project_id)
    if not project:
        return _json({"error": "Project not found"}, 404)

    wtype = project.get("workflow_type", "")

    if wtype == "CUSTOM":
        custom_schema = project.get("custom_schema")
        if not custom_schema:
            return _json({"error": "Custom schema not found in project"}, 404)
        return _json({"workflow_type": "CUSTOM", **custom_schema})

    schema = _WORKFLOW_SCHEMAS.get(wtype)
    if not schema:
        return _json({"error": f"Schema not found for workflow type '{wtype}'"}, 404)

    return _json(schema)


# ── POST /api/projects/<id>/submit ────────────────────────────────────────────

@https_fn.on_request()
def submit(req: https_fn.Request) -> https_fn.Response:
    """
    Accept and persist a completed label for the row currently assigned to the user.

    ── PHASE 4 TODO ──────────────────────────────────────────────────────────
    Requires the labels + queue_rows Firestore collections (not yet migrated).
    Implementation plan:
      1. Parse and validate the submitted label (workflow-specific fields).
      2. Write label to labels/{auto-id}:
           { project_id, row_id, labeler_uid, labeler_name, workflow, ...fields }
      3. Update queue_rows/{projectId}/{rowId}.status = "done".
      4. Check if all rows are done → update projects/{projectId}.is_finished = true.

    Workflow B multi-step pending state (entity → topic → sentiment) must be
    stored in pending_labels/{uid}_{rowId} between step calls because Cloud
    Functions are stateless (no equivalent of the _pending_entity_labels dict
    in workflows.py).
    ──────────────────────────────────────────────────────────────────────────

    Flask equivalent: submit_task() in api.py
    """
    if p := _preflight(req): return p

    uid, err = _require_auth(req)
    if err:
        return err

    project_id = _extract_project_id(req)
    if not project_id:
        return _json({"error": "Project ID is required."}, 400)

    project = get_project(project_id)
    if not project:
        return _json({"error": "Project not found"}, 404)

    return _json({
        "error": (
            "Label submission not yet migrated to Firestore (Phase 4). "
            "Use the Flask backend for labeling tasks."
        )
    }, 501)


# ── GET /api/manager/dashboard ────────────────────────────────────────────────

@https_fn.on_request()
def dashboard(req: https_fn.Request) -> https_fn.Response:
    """
    Return an overview of all projects owned by the authenticated user.

    Partial implementation:
      ✓ Project list + is_finished from Firestore
      ✗ rows_remaining / active_tasks     → TODO Phase 4 (queue_rows collection)
      ✗ completed_count / contributors    → TODO Phase 4 (labels collection)
      ✗ downloadable_files existence      → TODO Phase 3 (Firebase Storage)

    Flask equivalent: manager_dashboard() in api.py
    """
    if p := _preflight(req): return p

    uid, err = _require_auth(req)
    if err:
        return err

    all_projects = load_projects()
    owned        = [p for p in all_projects if p.get("owner") == uid]

    result = []
    for p in owned:
        is_finished = p.get("is_finished", False)

        # TODO (Phase 4): query queue_rows for live counts.
        rows_remaining = p.get("rows_remaining", 0)

        result.append({
            "id":                 p["id"],
            "name":               p["name"],
            "workflow_type":      p.get("workflow_type", ""),
            "rows_remaining":     rows_remaining,
            "active_tasks":       0,        # TODO Phase 4
            "is_finished":        is_finished,
            "downloadable_files": [],       # TODO Phase 3: list files from Firebase Storage
            "completed_count":    0,        # TODO Phase 4: count from labels collection
            "remaining_count":    rows_remaining,
            "total_tasks":        0,        # TODO Phase 4
            "completed_pct":      0.0,      # TODO Phase 4
            "remaining_pct":      100.0,    # TODO Phase 4
            "contributors":       [],       # TODO Phase 4: aggregate from labels collection
        })

    active_count    = sum(1 for p in owned if not p.get("is_finished", False))
    completed_count = sum(1 for p in owned if p.get("is_finished", False))

    return _json({
        "projects": result,
        "stats": {
            "total":          len(owned),
            "active":         active_count,
            "completed":      completed_count,
            "rows_remaining": 0,  # TODO Phase 4
        },
    })


# ── GET /api/manager/download/<id> ────────────────────────────────────────────

@https_fn.on_request()
def download(req: https_fn.Request) -> https_fn.Response:
    """
    Serve the master CSV file for a project.

    ── PHASE 3 TODO ──────────────────────────────────────────────────────────
    After the labels collection is populated (Phase 4), this endpoint should:
      1. Query labels where project_id == project_id.
      2. Build a CSV in memory (using Python's csv module).
      3. Return it as a streaming response with Content-Disposition: attachment.
    Firebase Storage is an alternative if large CSVs are pre-generated.
    ──────────────────────────────────────────────────────────────────────────

    Auth and ownership are enforced already.

    Flask equivalent: download_master() in api.py
    """
    if p := _preflight(req): return p

    uid, err = _require_auth(req)
    if err:
        return err

    project_id = _extract_project_id(req)
    if not project_id:
        return _json({"error": "Project ID is required."}, 400)

    project = get_project(project_id)
    if not project:
        return _json({"error": "Project not found"}, 404)

    if project.get("owner") != uid:
        return _json({"error": "Forbidden: you do not own this project."}, 403)

    if not project.get("master_csv"):
        return _json({"error": "No master CSV configured for this project."}, 404)

    return _json({
        "error": (
            "CSV download not yet migrated to Firebase (Phase 3). "
            "Use the Flask backend to download results."
        )
    }, 501)


# ── POST /api/upload-csv ──────────────────────────────────────────────────────

@https_fn.on_request()
def upload_csv(req: https_fn.Request) -> https_fn.Response:
    """
    Accept a CSV file upload.

    ── PHASE 3 TODO ──────────────────────────────────────────────────────────
    Cloud Functions have no persistent local disk. Implementation plan:
      1. Accept multipart/form-data with the CSV file.
      2. Upload the file bytes to Firebase Storage:
           gs://{project-id}.firebasestorage.app/sources/{uid}/{safe_filename}
      3. Return the gs:// or download URL to the frontend.
    ──────────────────────────────────────────────────────────────────────────

    Flask equivalent: upload_csv() in api.py
    """
    if p := _preflight(req): return p

    uid, err = _require_auth(req)
    if err:
        return err

    return _json({
        "error": (
            "CSV upload not yet migrated to Firebase Storage (Phase 3). "
            "Use the Flask backend to upload source files."
        )
    }, 501)
