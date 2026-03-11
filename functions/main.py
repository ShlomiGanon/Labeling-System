# main.py
# -------
# Firebase Cloud Functions entry point.
# API routes from backend/API/api.py will be migrated here one by one.
#
# Migration status
# ─────────────────────────────────────────────────────────────
# [ ] POST   /api/login
# [ ] POST   /api/logout
# [ ] GET    /api/me
# [ ] GET    /api/projects
# [ ] POST   /api/projects
# [ ] PUT    /api/projects/<id>
# [ ] DELETE /api/projects/<id>
# [ ] GET    /api/projects/<id>/task
# [ ] GET    /api/projects/<id>/config
# [ ] POST   /api/projects/<id>/submit
# [ ] GET    /api/manager/dashboard
# [ ] GET    /api/manager/download/<id>
# [ ] POST   /api/upload-csv

from firebase_functions import https_fn
from firebase_admin import initialize_app

initialize_app()

# ── Placeholder — replace with real route implementations ────────────────────

@https_fn.on_request()
def api(req: https_fn.Request) -> https_fn.Response:
    """
    Single catch-all function placeholder.
    Will be split into individual route functions as migration progresses.
    """
    return https_fn.Response(
        '{"error": "Cloud Functions not yet implemented. Use Flask backend."}',
        status=501,
        mimetype="application/json",
    )
