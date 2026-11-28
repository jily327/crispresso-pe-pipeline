import {defineConfig} from '@playwright/test';
import base from './playwright.config';
export default defineConfig({...base,testDir:'./e2e-practical',timeout:Number(process.env.PEANALYZER_E2E_JOB_TIMEOUT_MS||180000)+60000,
  expect:{timeout:Number(process.env.PEANALYZER_E2E_ASSERT_TIMEOUT_MS||5000)},
  reporter:[['list'],['json',{outputFile:'test-results/practical-results.json'}]],
  use:{...base.use,baseURL:'http://127.0.0.1:8768'}});
