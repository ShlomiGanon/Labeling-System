"""
run.py
------
Backend-specific entry point that provides a clear startup message.
"""

import os
import sys

# Ensures the current backend directory is at the front of the Python system path.
# This makes internal imports like 'CORE' and 'API' discoverable by the interpreter.
# Returns the absolute path of the directory containing this script.
# Returns None (modifies sys.path in-place).
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
if BACKEND_DIR not in sys.path:
    # Inserts the backend root as the first searching priority in the path list.
    # Returns None.
    sys.path.insert(0, BACKEND_DIR)

# Retrieves the global Flask application instance from the server core.
# Returns a Flask app object.
from CORE.server import app
# Retrieves the API blueprint containing all route definitions.
# Returns a Flask Blueprint object.
from API.api import api_bp

# Registers the API routes under the '/api' prefix to distinguish them from frontend routes.
# Returns None.
app.register_blueprint(api_bp, url_prefix="/api")

if __name__ == "__main__":
    debug = os.environ.get("DEBUG", "false").lower() == "true"
    port  = int(os.environ.get("PORT", 5000))

    print("-" * 60)
    print(" [BACKEND] Labeling System is starting...")
    print(" [STATUS]  Flask Server: ACTIVATED")
    print(" [STATUS]  API Routes:   REGISTERED")
    print(f" [MODE]    Debug: {debug}")
    print("-" * 60)
    print(f" [READY]   Server is listening on: http://0.0.0.0:{port}")
    print("-" * 60)

    # Development only — in production use:
    #   gunicorn --bind 0.0.0.0:5000 run:app
    app.run(debug=debug, host="0.0.0.0", port=port)
