import { defineConfig } from '@playwright/test';
import base from './playwright.config';
export default defineConfig({...base,testDir:'./e2e-run',timeout:Number(process.env.PEANALYZER_E2E_JOB_TIMEOUT_MS||180000),expect:{timeout:Number(process.env.PEANALYZER_E2E_ASSERT_TIMEOUT_MS||5000)},
  reporter:[['list'],['json',{outputFile:'test-results/run-results.json'}]],
  use:{...base.use,baseURL:process.env.M11B_E2E_URL||'http://127.0.0.1:8766'}});
