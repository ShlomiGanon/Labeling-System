import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import './index.css'
import { LanguageProvider } from './i18n/LanguageContext.jsx'

/**
 * Entry point for the React application.
 * Mounts the App component into the #root element in index.html.
 * StrictMode is enabled to catch common development issues early.
 * LanguageProvider wraps the entire tree so every component can access
 * the current language and the t() translation function.
 */
ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <LanguageProvider>
      <App />
    </LanguageProvider>
  </React.StrictMode>,
)
