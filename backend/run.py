"""
run.py
------
Backend-specific entry point that provides a clear startup message.
"""

import os
import sys

# Ensure the backend root and its children are in the system path.
# This allows 'import CORE.server' and 'import API.api' to work.
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# CORE.server handles the initialization of the Flask 'app' object.
from CORE.server import app
# API.api contains the route definitions.
from API.api import api_bp

# Register the routes.
app.register_blueprint(api_bp, url_prefix="/api")

if __name__ == "__main__":
    print("-" * 60)
    print(" [BACKEND] Labeling System is starting...")
    print(" [STATUS]  Flask Server: ACTIVATED")
    print(" [STATUS]  API Routes:   REGISTERED")
    print("-" * 60)
    print(" [READY]   Server is listening on: http://localhost:5000")
    print("-" * 60)
    
    # Run the server.
    app.run(debug=True, host="0.0.0.0", port=5000)
