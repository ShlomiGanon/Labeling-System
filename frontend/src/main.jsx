import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import './index.css'

/**
 * Entry point for the React application.
 * Mounts the App component into the #root element in index.html.
 * StrictMode is enabled to catch common development issues early.
 */
ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
