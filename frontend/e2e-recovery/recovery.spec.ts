import {test,expect,type Page} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import fs from 'node:fs';
import path from 'node:path';
import {spawn} from 'node:child_process';
const root=process.env.M11C_E2E_ROOT!;
async function inspect(page:Page,name:string){
  await page.goto('/#e2e-local-token');await page.getByRole('button',{name:'Recover Analysis',exact:true}).click();
  // Opaque registrations are server ordered; browser never submits a path.
  const names=['pe-resume','nuclease-resume','force','stale','completed','cancel','detached','kill'];
  await expect.poll(()=>page.getByLabel('Registered recovery workspace').locator('option').count()).toBeGreaterThanOrEqual(names.length);
  await page.getByLabel('Registered recovery workspace').selectOption({index:names.indexOf(name)});
  await page.getByRole('button',{name:'Inspect workspace',exact:true}).click();
}
async function confirm(page:Page,force=false){await page.getByRole('checkbox',{name:/I reviewed/}).check();await page.getByRole('button',{name:force?'Confirm forced recovery':'Confirm resume',exact:true}).click()}
async function completed(page:Page){await expect(page.locator('#run-main [role="status"]')).toContainText('COMPLETED',{timeout:90000});await page.getByRole('button',{name:'Open Results',exact:true}).click();await expect(page.getByRole('tab',{name:'Overview',exact:true})).toBeVisible()}
async function cancel(page:Page){await page.getByRole('button',{name:'Cancel analysis',exact:true}).click();await page.getByRole('button',{name:'Confirm cancellation'}).click();await expect(page.locator('#run-main [role="status"]')).toContainText('CANCELLED',{timeout:15000})}
for(const mode of ['pe-resume','nuclease-resume'])test(`${mode}: read-only preview → resume → verified M10`,async({page})=>{
  await inspect(page,mode);await expect(page.getByRole('table',{name:'Backend recovery stage plan'})).toBeVisible();
  expect(await page.getByRole('button',{name:'Confirm resume',exact:true}).isEnabled()).toBe(false);
  for(const width of [1920,1366,683]){await page.setViewportSize({width,height:768});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true)}
  expect((await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze()).violations).toEqual([]);
  await page.getByRole('checkbox',{name:/I reviewed/}).focus();await page.keyboard.press('Space');await page.keyboard.press('Tab');await expect(page.getByRole('button',{name:'Confirm resume',exact:true})).toBeFocused();await page.keyboard.press('Enter');
  await completed(page);await expect(page.getByRole('heading',{name:mode==='pe-resume'?'Exact intended PE':'Indel fraction',exact:true})).toBeVisible();
});
test('advanced force shows authoritative closure before removal and completion',async({page})=>{
  await inspect(page,'force');await expect(page.getByText('RESUMABLE_WITH_FORCE',{exact:true})).toBeVisible();
  await page.getByText('Advanced: force selected stage families').click();await page.getByRole('checkbox',{name:'report',exact:true}).check();
  expect(fs.existsSync(path.join(root,'force/workflow/report'))).toBe(true);
  await page.getByRole('button',{name:'Preview recovery selection'}).click();await expect(page.getByRole('button',{name:'Confirm forced recovery'})).toBeDisabled();
  await expect(page.getByRole('heading',{name:'Owned paths to remove or replace'})).toBeVisible();await confirm(page,true);await completed(page);
});
test('stale preview refuses confirmation without deleting a foreign arrival',async({page})=>{
  await inspect(page,'stale');await expect(page.getByRole('button',{name:'Confirm resume'})).toBeVisible();
  const foreign=path.join(root,'stale/workflow/foreign-arrival');fs.writeFileSync(foreign,'must survive');
  await confirm(page);await expect(page.getByRole('alert')).toContainText('RECOVERY_PLAN_CHANGED');expect(fs.readFileSync(foreign,'utf8')).toBe('must survive');
  expect(fs.existsSync(path.join(root,'stale/workflow/report'))).toBe(false);expect(fs.existsSync(path.join(root,'stale/workflow/workflow_manifest.json'))).toBe(false);
});
test('completed workspace routes to Open Results without resume/force',async({page})=>{
  await inspect(page,'completed');await expect(page.getByText('COMPLETED',{exact:true})).toBeVisible();expect(await page.getByRole('button',{name:'Confirm resume'}).count()).toBe(0);
  await page.getByRole('button',{name:'Open Results',exact:true}).click();await expect(page.getByRole('tab',{name:'Overview',exact:true})).toBeVisible();
});
for(const name of ['cancel','detached'])test(`${name}: recovery cancellation → new inspection → resume`,async({page})=>{
  await inspect(page,name);await confirm(page);await expect.poll(()=>fs.existsSync(path.join(root,name,'report-ready'))).toBe(true);
  if(name==='detached')await expect.poll(()=>fs.existsSync(path.join(root,name,'detached-pid'))).toBe(true);
  await cancel(page);expect(await page.getByRole('button',{name:'Open Results',exact:true}).count()).toBe(0);
  if(name==='detached'){const pid=Number(fs.readFileSync(path.join(root,name,'detached-pid'),'utf8'));expect(()=>process.kill(pid,0)).toThrow()}
  fs.unlinkSync(path.join(root,name,'pause-report'));await page.getByRole('button',{name:'Inspect Recovery'}).click();await expect(page.getByText('RESUMABLE',{exact:true})).toBeVisible();await confirm(page);await completed(page);
});
test('server SIGKILL: restart sees lease, cleanup contains escaped child, then recovery',async({page})=>{
  await inspect(page,'kill');await confirm(page);await expect.poll(()=>fs.existsSync(path.join(root,'kill/detached-pid'))).toBe(true);
  const old=Number(fs.readFileSync(path.join(root,'server-pid'),'utf8')),escaped=Number(fs.readFileSync(path.join(root,'kill/detached-pid'),'utf8'));
  process.kill(old,'SIGKILL');
  const restarted=spawn(process.env.M11C_E2E_PYTHON!,[process.env.M11C_E2E_SERVER!],{env:{...process.env,M11C_REUSE_FIXTURES:'1'},stdio:'ignore'});
  try{
    await expect.poll(()=>fs.readFileSync(path.join(root,'server-pid'),'utf8')).not.toBe(String(old));
    await expect.poll(async()=>{try{return (await page.request.get('/api/v1/capabilities',{headers:{'X-Viewer-Token':'e2e-local-token'}})).status()}catch{return 0}}).toBe(200);
    await inspect(page,'kill');
    // Either cleanup is still in progress (ACTIVE) or it has finished. Never two
    // workers; API-level lease test proves busy while the detached child lives.
    await expect.poll(()=>{try{process.kill(escaped,0);return false}catch{return true}},{timeout:20000}).toBe(true);
    fs.unlinkSync(path.join(root,'kill/pause-report'));await page.getByRole('button',{name:'Inspect workspace',exact:true}).click();await expect(page.getByText('RESUMABLE',{exact:true})).toBeVisible();await confirm(page);await completed(page);
  }finally{restarted.kill('SIGTERM');await new Promise<void>(resolve=>{if(restarted.exitCode!==null)resolve();else restarted.once('exit',()=>resolve())})}
});
