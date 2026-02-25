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

def start_backend():
    """
    Spawns the Flask backend using the designated run.py script.
    """
    backend_script = os.path.join("backend", "run.py")
    print(">>> Starting Backend...")
    # Use the current python interpreter to run the backend.
    return subprocess.Popen([sys.executable, backend_script])

def start_frontend():
    """
    Spawns the React/Vite frontend via npm.
    """
    frontend_dir = "frontend"
    print(">>> Starting Frontend (Vite)...")
    # 'shell=True' is often needed on Windows to resolve 'npm' as a command.
    return subprocess.Popen(["npm", "run", "dev"], cwd=frontend_dir, shell=True)

if __name__ == "__main__":
    print("=" * 60)
    print("   L A B E L I N G   S Y S T E M   L A U N C H E R")
    print("=" * 60)

    p_back = None
    p_front = None

    try:
        p_back = start_backend()
        # Small delay to let the backend start binding to port 5000 first.
        time.sleep(2)
        p_front = start_frontend()

        print("\n [NOTICE] Both processes are running. Press CTRL+C to stop everything.\n")
        
        # Keep the main process alive while the children are running.
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n>>> Stopping System...")
        if p_back: p_back.terminate()
        if p_front: p_front.terminate()
        print(">>> Cleanup complete. Goodbye.")
