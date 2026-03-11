/**
 * client.js
 * ---------
 * This file handles all the communication between the React frontend
 * and the Flask backend.
 */
import { auth } from '../firebase.js';

/**
 * Returns the Firebase ID token for the currently signed-in Firebase user,
 * or null if Firebase Auth is not yet set up / no user is signed in.
 * Safe to call at any time — never throws.
 */
async function getFirebaseToken() {
  try {
    const user = auth.currentUser;
    if (!user) return null;
    return await user.getIdToken();
  } catch {
    return null;
  }
}

/**
 * A helper function to send requests to the backend.
 * It handles errors and converts the data to JSON automatically.
 *
 * Auth strategy (both run in parallel during migration):
 *  - credentials: 'include'  → Flask session cookie (current system, still works)
 *  - Authorization: Bearer   → Firebase ID token (added when a Firebase user is
 *                              signed in; ignored by the backend until Phase 3)
 */
async function request(method, url, body = null) {
  const token = await getFirebaseToken();

  const options = {
    method,
    credentials: 'include', // Important: this shares the login session cookies
    headers: { 'Content-Type': 'application/json' },
  }

  // Attach Firebase token when available. The Flask backend ignores this header
  // for now; it will be wired up when the backend migrates to Firebase Auth.
  if (token) {
    options.headers['Authorization'] = `Bearer ${token}`;
  }

  if (body !== null) {
    options.body = JSON.stringify(body)
  }

  try {
    const res = await fetch(url, options)
    const data = await res.json()
    return { ok: res.ok, data }
  } catch (err) {
    // If the server is down or there is no internet
    return { ok: false, data: { error: `Network error: ${err.message}` } }
  }
}

// Simple shortcuts for GET and POST requests
const get = (url) => request('GET', url)
const post = (url, body) => request('POST', url, body)


// ---------------------------------------------------------------------------
// Authentication (Login / Logout)
// ---------------------------------------------------------------------------

/** Log in with a username. */
export const login = (userName) => post('/api/login', { user_name: userName })

/** Log out the current user. */
export const logout = () => post('/api/logout', {})

/** Check if the user is already logged in when the page loads. */
export const getMe = () => get('/api/me')


// ---------------------------------------------------------------------------
// Projects
// ---------------------------------------------------------------------------

/** Get a list of all projects. */
export const getProjects = () => get('/api/projects')

/** Create a new labeling project. */
export const createProject = (data) => post('/api/projects', data)

/** Delete a project. If deleteFiles=true, also removes source and master CSVs. */
export const deleteProject = (projectId, deleteFiles = false) =>
  request('DELETE', `/api/projects/${projectId}?delete_files=${deleteFiles}`)

/** Update an existing project's details. */
export const updateProject = (projectId, data) =>
  request('PUT', `/api/projects/${projectId}`, data)


// ---------------------------------------------------------------------------
// Tasks
// ---------------------------------------------------------------------------

/** Get the next item (image/text) that needs to be labeled. */
export const getTask = (projectId) => get(`/api/projects/${projectId}/task`)

/** Send the finished label back to the server to be saved. */
export const submitLabel = (projectId, payload) =>
  post(`/api/projects/${projectId}/submit`, payload)

/** Get the UI schema/configuration for a project's workflow. */
export const getProjectConfig = (projectId) => get(`/api/projects/${projectId}/config`)


// ---------------------------------------------------------------------------
// Manager Dashboard
// ---------------------------------------------------------------------------

/** Get manager dashboard data (owned projects + stats). */
export const getManagerDashboard = () => get('/api/manager/dashboard')

/**
 * Build the URL for downloading a project's master CSV.
 * Pass source = null for the main master, or the source path string for a per-source master.
 */
export const getMasterDownloadUrl = (projectId, source = null) => {
  const base = `/api/manager/download/${projectId}`
  return source ? `${base}?source=${encodeURIComponent(source)}` : base
}

/**
 * Download a master CSV file, handling auth/permission errors in-app.
 * Returns { ok: true, blob, filename } on success,
 *         { ok: false, error: string }  on failure.
 */
export const downloadMasterFile = async (projectId, source = null) => {
  const url = getMasterDownloadUrl(projectId, source)
  try {
    const token = await getFirebaseToken();
    const headers = token ? { Authorization: `Bearer ${token}` } : {};
    const res = await fetch(url, { credentials: 'include', headers })
    if (!res.ok) {
      try {
        const data = await res.json()
        return { ok: false, error: data.error || `HTTP ${res.status}` }
      } catch {
        return { ok: false, error: `HTTP ${res.status}` }
      }
    }
    const blob = await res.blob()
    // Prefer server-supplied filename from Content-Disposition.
    const disposition = res.headers.get('Content-Disposition') || ''
    const match = disposition.match(/filename[^;=\n]*=(['"]?)([^'";\n]+)\1/)
    const filename = match ? match[2] : `master_${projectId}.csv`
    return { ok: true, blob, filename }
  } catch (err) {
    return { ok: false, error: `Network error: ${err.message}` }
  }
}
