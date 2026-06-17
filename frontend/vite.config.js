import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// API base is configurable at build/runtime via VITE_API_BASE.
// In Docker/Render the frontend is served statically and talks to the backend service.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, host: true },
  preview: { port: 4173, host: true },
})
