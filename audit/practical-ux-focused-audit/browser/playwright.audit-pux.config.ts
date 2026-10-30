import {defineConfig} from '@playwright/test';
export default defineConfig({testDir:'./audit-pux',workers:1,retries:0,timeout:300000,reporter:[['list'],['json',{outputFile:'test-results/audit-pux.json'}]],
  use:{baseURL:'http://127.0.0.1:8779',trace:'retain-on-failure',launchOptions:{executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE}}});
