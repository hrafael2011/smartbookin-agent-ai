import { defineConfig, devices } from '@playwright/test'

/** Puerto dedicado para E2E: evita choque con `npm run dev` en 5173. */
const e2ePort = Number(process.env.PLAYWRIGHT_WEB_PORT || '5174')
const e2eOrigin = `http://127.0.0.1:${e2ePort}`

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: 'list',
  use: {
    baseURL: e2eOrigin,
    trace: 'on-first-retry',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: `npm run dev -- --host 127.0.0.1 --port ${e2ePort}`,
    url: e2eOrigin,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
})
