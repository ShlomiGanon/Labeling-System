"""
start_up.py
-----------
Global startup script for the entire Labeling System.
Launches both the Backend and Frontend in separate processes.
"""

import subprocess
import time
import sys
import os

# Verifies and prepares the frontend environment by installing dependencies and building the project.
# Since build artifacts and node_modules are ignored by Git, this ensures the system is functional on a fresh pull.
# Returns None.
def prepare_frontend():
    frontend_dir = "frontend"
    node_modules = os.path.join(frontend_dir, "node_modules")
    dist_dir = os.path.join(frontend_dir, "dist")

    # Checks if the node_modules directory is missing to trigger an initial installation.
    if not os.path.exists(node_modules):
        print(">>> Node modules missing. Running npm install...")
        # Executes the package installation synchronously before proceeding.
        # Returns a CompletedProcess instance.
        subprocess.run(["npm", "install"], cwd=frontend_dir, shell=True, check=True)

    # Checks if the production build directory is missing to trigger a new compilation.
    if not os.path.exists(dist_dir):
        print(">>> Build folder missing. Generating production artifacts (npm run build)...")
        # Compiles the React source code into static assets for the Flask backend to serve.
        # Returns a CompletedProcess instance.
        subprocess.run(["npm", "run", "build"], cwd=frontend_dir, shell=True, check=True)

# Spawns a background process to run the Flask backend.
# This keeps the backend server alive independently of the main startup sequence.
# Returns a Subprocess.Popen object representing the running backend.
def start_backend():
    # Joins parts of the file path to find the backend entry point relatively.
    # Returns a path string.
    backend_script = os.path.join("backend", "run.py")
    print(">>> Starting Backend...")
    # Launches the backend script using the current Python interpreter.
    # Returns a process handle.
    return subprocess.Popen([sys.executable, backend_script])

# Spawns a background process to run the React/Vite frontend development server.
# This triggers the automatic compilation and serving of the client-side code.
# Returns a Subprocess.Popen object representing the running frontend.
def start_frontend():
    frontend_dir = "frontend"
    print(">>> Starting Frontend (Vite)...")
    # Executes the 'npm run dev' command inside the frontend directory.
    # Uses the shell environment to resolve the npm executable on Windows.
    # Returns a process handle.
    return subprocess.Popen(["npm", "run", "dev"], cwd=frontend_dir, shell=True)

if __name__ == "__main__":
    # Provides visual feedback that the orchestration script is active.
    # Returns None.
    print("=" * 60)
    print("   L A B E L I N G   S Y S T E M   L A U N C H E R")
    print("=" * 60)

    # Executes the environment preparation step before launching any services.
    # Returns None.
    prepare_frontend()

    p_back = None
    p_front = None

    try:
        # Initiates the backend server process.
        # Returns a Popen instance.
        p_back = start_backend()
        # Pauses the main thread to allow the backend to initialize its ports.
        # Returns None.
        time.sleep(2)
        # Initiates the frontend development server process.
        # Returns a Popen instance.
        p_front = start_frontend()

        print("\n [NOTICE] Both processes are running. Press CTRL+C to stop everything.\n")
        
        # Enters an infinite monitoring loop to keep the parent script alive.
        while True:
            # Yields the processor briefly to prevent a performance hit from the loop.
            # Returns None.
            time.sleep(1)
            
    except KeyboardInterrupt:
        # Gracefully terminates all sub-processes when the user sends an interrupt signal.
        print("\n>>> Stopping System...")
        if p_back:
            # Sends a termination signal to the running backend process.
            # Returns None.
             p_back.terminate()
        if p_front:
            # Sends a termination signal to the running frontend process.
            # Returns None.
             p_front.terminate()
        print(">>> Cleanup complete. Goodbye.")
