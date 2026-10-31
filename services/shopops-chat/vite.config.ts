/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5174,
    strictPort: true,
    headers: { 'Content-Security-Policy': "frame-ancestors 'self' http://localhost:5175 http://127.0.0.1:5175" },
    proxy: {
      '/api/chat/': 'http://127.0.0.1:8001',
      '/api/operations/navigation': 'http://127.0.0.1:8000',
    },
  },
  test: { environment: 'jsdom', setupFiles: ['./src/test/setup.ts'] },
})
