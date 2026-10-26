import { defineConfig } from '@playwright/test';
import base from './playwright.config';
export default defineConfig({...base,testDir:'./e2e-run',timeout:180000,
  reporter:[['list'],['json',{outputFile:'test-results/run-results.json'}]],
  use:{...base.use,baseURL:process.env.M11B_E2E_URL||'http://127.0.0.1:8766'}});
