import { defineConfig } from '@playwright/test'
import { fileURLToPath } from 'node:url'

const root = fileURLToPath(new URL('../../', import.meta.url))
const lifecycle = {
  reuseExistingServer: false,
  timeout: 30_000,
  gracefulShutdown: { signal: 'SIGTERM' as const, timeout: 5_000 },
}

export default defineConfig({
  testDir: './specs',
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: 0,
  timeout: 30_000,
  expect: { timeout: 7_000 },
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: 'http://localhost:5175',
    browserName: 'chromium',
    ...(process.env.PLAYWRIGHT_CHANNEL ? { channel: process.env.PLAYWRIGHT_CHANNEL } : {}),
    viewport: { width: 1440, height: 900 },
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
  },
  webServer: [
    ...['shopops-api', 'shopops-chat-api'].map((service, index) => ({
      ...lifecycle,
      name: service,
      cwd: root,
      command: `services/${service}/.venv/bin/python tests/workspace/start-test-api.py ${index === 0 ? 'operations' : 'chat'}`,
      url: `http://127.0.0.1:${8000 + index}/health`,
    })),
    ...['shopops-web', 'shopops-chat', 'shopops-workspace'].map((service, index) => ({
      ...lifecycle,
      name: service,
      cwd: `${root}services/${service}`,
      command: 'npm run dev -- --host 0.0.0.0',
      url: `http://127.0.0.1:${5173 + index}`,
    })),
  ],
})
