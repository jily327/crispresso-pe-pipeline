import {defineConfig} from '@playwright/test';
import base from './playwright.config';
export default defineConfig({...base,testDir:'./e2e-practical',timeout:180000,
  reporter:[['list'],['json',{outputFile:'test-results/practical-results.json'}]],
  use:{...base.use,baseURL:'http://127.0.0.1:8768'}});
