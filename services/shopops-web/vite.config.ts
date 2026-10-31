/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import { createConnectorHandler } from './mock/connectors.ts'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), {
    name: 'mock-connectors',
    configureServer(server) {
      const handle = createConnectorHandler()
      server.middlewares.use((request, response, next) => {
        if (request.url?.startsWith('/api/mock/')) handle(request, response)
        else next()
      })
    },
  }],
  server: {
    port: 5173,
    strictPort: true,
    headers: { 'Content-Security-Policy': "frame-ancestors 'self' http://localhost:5175 http://127.0.0.1:5175" },
    proxy: {
      '/api/operations/': 'http://127.0.0.1:8000',
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
  },
})
