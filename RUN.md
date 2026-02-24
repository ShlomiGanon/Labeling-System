# How to Run the Labeling System

This project has two parts: a **Backend** (Python/Flask) and a **Frontend** (React/Vite).

## 1. Prerequisites
- **Python 3.8+** installed on your computer.
- **Node.js** (and npm) installed on your computer.

---

## 2. Setting up the Backend
The backend handles the data, projects, and labels.

1.  **Open a terminal** in the project root folder.
2.  **Install dependencies** (Flask, Flask-CORS, etc.):
    ```bash
    pip install flask flask-cors
    ```
3.  **Start the server**:
    ```bash
    python app.py
    ```
    *The server will start at `http://localhost:5000`.*

---

## 3. Setting up the Frontend
The frontend is the user interface where labeling happens.

1.  **Open a second terminal** in the `frontend` folder:
    ```bash
    cd frontend
    ```
2.  **Install dependencies**:
    ```bash
    npm install
    ```
3.  **Start the development server**:
    ```bash
    npm run dev
    ```
    *The app will be available at `http://localhost:5173` (or similar).*

---

## 4. How to use
1.  Open the frontend URL in your browser.
2.  **Login**: Enter any name to start.
3.  **Create a Project**: Click "New Project", give it a name, choose a workflow, and provide a path to a CSV file (e.g., `backend/data/sample.csv`).
4.  **Label**: Select the project from the dashboard and start labeling!
