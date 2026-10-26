import { test,expect,type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import fs from 'node:fs';
import path from 'node:path';
const root=process.env.M11B_E2E_ROOT!;
function fields(mode:string){return JSON.parse(fs.readFileSync(path.join(root,'fields.json'),'utf8'))[mode]}
async function setup(page:Page,mode:string,name:string,workspace:string){
  await page.goto('/#e2e-local-token');await page.getByRole('button',{name:'New Analysis',exact:true}).click();
  await page.getByLabel('Analysis name',{exact:true}).fill(name);
  await page.getByLabel('Pool R1').selectOption({label:`${mode}_R1.fastq.gz`});await page.getByLabel('Pool R2').selectOption({label:`${mode}_R2.fastq.gz`});
  const data=fields(mode);await page.getByRole('button',{name:'Add sample',exact:true}).click();
  for(const key of ['sample_name','barcode_id','forward_barcode','reverse_barcode','editor','treatment','dpi','biological_replicate'])await page.locator(`[id="samples.0.${key}"]`).fill(String(data.samples[0][key]));
  await page.getByRole('button',{name:'2. Mode'}).click();await page.getByRole('radio',{name:mode==='pe'?/Precise Edit/:/Indel \/ Nuclease/}).check();
  await page.getByRole('button',{name:'3. Target'}).click();
  for(let i=0;i<data.targets.length;i++){
    if(i)await page.getByRole('button',{name:'Add copy',exact:true}).click();
    const row=data.targets[i];
    for(const key of ['target_name','copy_name','wt_sequence'])await page.locator(`[id="targets.${i}.${key}"]`).fill(row[key]);
    if(mode==='pe'){for(const key of ['prime_edited_sequence','pegRNA_spacer','pegRNA_extension','nicking_guide','pegRNA_scaffold'])await page.locator(`[id="targets.${i}.${key}"]`).fill(row[key]||'')}
    else{page.once('dialog',d=>d.accept());await page.getByLabel('Target profile').selectOption('tigr_tas_v1');await page.getByLabel('18-nt TIGR target').fill(row.tigr_target_sequence);await page.getByLabel('Selected window').selectOption(row.tigr_window)}
  }
  await page.getByRole('button',{name:'4. Configuration'}).click();await page.getByLabel('Library extraction profile').selectOption('custom');
  await page.getByLabel('R1 analysis 5′ trim').fill('8');await page.getByLabel('R2 analysis 5′ trim').fill('8');
  await page.getByLabel('Proposed output parent (optional)').selectOption({label:'outputs'});await page.getByLabel('Proposed workspace name').fill(workspace);
  await page.getByRole('button',{name:'Validate & Review'}).click();await expect(page.getByRole('button',{name:'Run Analysis',exact:true})).toBeEnabled();
}
async function cancel(page:Page){await page.getByRole('button',{name:'Cancel analysis',exact:true}).click();await expect(page.getByRole('dialog')).toBeVisible();await page.getByRole('button',{name:'Confirm cancellation'}).click()}
for(const mode of ['pe','nuclease'])test(`${mode}: real Review → Run → verified completion → existing M10`,async({page})=>{
  await setup(page,mode,`Browser ${mode} lifecycle`,mode+'-happy');const science=await page.locator('.identities dd').first().textContent();
  await page.getByRole('button',{name:'Run Analysis',exact:true}).click();await expect(page.getByRole('table',{name:'Authoritative stage progress'})).toBeVisible();
  await expect(page.getByRole('button',{name:'Open Results',exact:true})).toBeVisible({timeout:120000});
  await expect(page.getByText(science!,{exact:true})).toBeVisible();expect(await page.getByRole('progressbar').count()).toBe(0);
  for(const width of [1366,1920,683]){await page.setViewportSize({width,height:768});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true)}
  expect((await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze()).violations).toEqual([]);
  await page.getByRole('button',{name:'Open Results',exact:true}).click();await expect(page.getByRole('tab',{name:'Overview',exact:true})).toBeVisible();
  await expect(page.getByRole('heading',{name:mode==='pe'?'Exact intended PE':'Indel fraction',exact:true})).toBeVisible();
});
test('stale Review refuses Run before science',async({page})=>{
  await setup(page,'pe','Stale review','stale');const file=path.join(root,'pe_R1.fastq.gz'),original=fs.readFileSync(file);
  try{fs.appendFileSync(file,'changed');await page.getByRole('button',{name:'Run Analysis',exact:true}).click();await expect(page.getByRole('alert')).toContainText('DRAFT_INPUT_CHANGED');expect(fs.existsSync(path.join(root,'outputs','stale'))).toBe(false)}finally{fs.writeFileSync(file,original)}
});
test('live job reload reconnects without a second submission; cancel cleans child',async({page})=>{
  await setup(page,'pe','Fixture cancellation reload','reload');let submits=0;page.on('request',r=>{if(r.method()==='POST'&&r.url().endsWith('/api/v1/jobs'))submits++});
  await page.getByRole('button',{name:'Run Analysis',exact:true}).click();await expect(page.getByRole('button',{name:'Cancel analysis',exact:true})).toBeVisible();
  const id=await page.locator('#run-main .identities dd').first().textContent();await page.reload();await expect(page.getByText(id!,{exact:true})).toBeVisible();
  await expect(page.getByText('Current stage: demux',{exact:true})).toBeVisible();
  await cancel(page);await expect(page.locator('#run-main [role="status"]')).toContainText('CANCELLING');await page.reload();
  await expect(page.locator('#run-main [role="status"]')).toContainText('CANCELLED',{timeout:15000});expect(submits).toBe(1);
  expect(await page.getByRole('button',{name:'Open Results',exact:true}).count()).toBe(0);
  const pid=Number(fs.readFileSync(path.join(root,'outputs','fixture-child-pid'),'utf8'));expect(()=>process.kill(pid,0)).toThrow();
});
test('busy worker refuses a second reviewed Run without queueing',async({page})=>{
  await setup(page,'pe','Fixture cancellation busy','busy-first');await page.getByRole('button',{name:'Run Analysis',exact:true}).click();await expect(page.getByRole('button',{name:'Cancel analysis',exact:true})).toBeVisible();
  await setup(page,'pe','Second reviewed study','busy-second');await page.getByRole('button',{name:'Run Analysis',exact:true}).click();await expect(page.getByRole('alert')).toContainText('WORKER_BUSY');
  expect(fs.existsSync(path.join(root,'outputs','busy-second'))).toBe(false);await page.getByRole('button',{name:'Run status',exact:true}).click();await cancel(page);
  await expect(page.locator('#run-main [role="status"]')).toContainText('CANCELLED',{timeout:15000});
});
test('backend failure retains actual code, failing stage and message',async({page})=>{
  await setup(page,'pe','Fixture failure diagnostic','failure');await page.getByRole('button',{name:'Run Analysis',exact:true}).click();
  await expect(page.locator('#run-main [role="status"]')).toContainText('FAILED');await page.getByText('Technical details',{exact:true}).click();
  await expect(page.getByText(/Code: BROWSER_BACKEND_FAILURE/)).toBeVisible();await expect(page.getByText(/Specific backend fixture diagnostic/)).toBeVisible();
  expect(await page.getByRole('button',{name:'Open Results',exact:true}).count()).toBe(0);
});
