import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: './e2e', timeout: 120000, fullyParallel: false, workers: 1,
  reporter: [['list'], ['json', { outputFile: 'test-results/results.json' }]],
  use: { launchOptions: { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE }, baseURL: process.env.M10_E2E_URL || 'http://127.0.0.1:8765', viewport: { width: 1366, height: 768 }, trace: 'retain-on-failure', screenshot: 'only-on-failure' },
});
