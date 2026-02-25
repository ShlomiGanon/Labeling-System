/**
 * client.js
 * ---------
 * This file handles all the communication between the React frontend 
 * and the Flask backend.
 */

/** 
 * A helper function to send requests to the backend.
 * It handles errors and converts the data to JSON automatically.
 */
async function request(method, url, body = null) {
  const options = {
    method,
    credentials: 'include', // Important: this shares the login session cookies
    headers: { 'Content-Type': 'application/json' },
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
