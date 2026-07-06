import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// API base is configurable at build/runtime via VITE_API_BASE.
// In Docker/Render the frontend is served statically and talks to the backend service.
//
// `base` controls the public path the built assets are served from:
//   - local dev / Render / custom domain: "/" (default)
//   - GitHub Project Pages: "/<repo>/" (set via VITE_BASE in the Pages workflow)
export default defineConfig({
  base: process.env.VITE_BASE || '/',
  plugins: [react()],
  server: { port: 5173, host: true },
  preview: { port: 4173, host: true },
})
