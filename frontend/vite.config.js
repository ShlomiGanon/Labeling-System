import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

/**
 * Vite configuration for the Labeling System frontend.
 *
 * Development mode:
 *   - React dev server runs on port 5173.
 *   - All /api/* requests are proxied to the Flask server on port 5000.
 *     This means you never get CORS errors during development.
 *
 * Production build:
 *   - Output goes to dist/ which Flask serves directly.
 */
export default defineConfig({
  plugins: [react()],

  server: {
    port: 5173,
    proxy: {
      // Forward all API calls to the Flask backend
      '/api': {
        target: 'http://localhost:5000',
        changeOrigin: true,
        secure: false,
      },
    },
  },

  build: {
    // Flask will serve files from frontend/dist/
    outDir: 'dist',
    emptyOutDir: true,
  },
})
