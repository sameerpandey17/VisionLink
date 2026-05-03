import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/ingest': 'http://localhost:8000',
      '/api': 'http://localhost:8000',
      '/stream': { target: 'ws://localhost:8000', ws: true },
    },
  },
})
