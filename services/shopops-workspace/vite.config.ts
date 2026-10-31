/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import type { Connect, Plugin } from 'vite'

const clients = { browser_url: 'http://127.0.0.1:5173', chat_url: 'http://localhost:5174' }
const configMiddleware: Connect.NextHandleFunction = (request, response, next) => {
  response.setHeader('Content-Security-Policy', `frame-src ${clients.browser_url} ${clients.chat_url}; object-src 'none'; base-uri 'self'`)
  response.setHeader('Referrer-Policy', 'no-referrer')
  if (request.url?.split('?')[0] !== '/client-config.json') { next(); return }
  response.statusCode = 200
  response.setHeader('Content-Type', 'application/json')
  response.setHeader('Cache-Control', 'no-store')
  response.end(JSON.stringify(clients))
}
const clientConfig: Plugin = {
  name: 'local-client-config',
  configureServer(server) { server.middlewares.use(configMiddleware) },
  configurePreviewServer(server) { server.middlewares.use(configMiddleware) },
}

export default defineConfig({
  plugins: [react(), clientConfig],
  server: { port: 5175, strictPort: true },
  preview: { port: 5175, strictPort: true },
  test: { environment: 'jsdom', setupFiles: ['./src/test/setup.ts'] },
})
