import { expect, test, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import fs from 'node:fs';
import path from 'node:path';
function fields(){return JSON.parse(fs.readFileSync(path.join(process.env.M11_SETUP_ROOT!,'draft-fields.json'),'utf8'))}
async function start(page:Page,mode:'PE'|'nuclease'){
  await page.goto('/#e2e-local-token');await page.getByRole('button',{name:'New Analysis',exact:true}).click();
  await page.getByLabel('Analysis name',{exact:true}).fill('Browser setup study');
  await page.getByLabel('Pool R1').selectOption({label:'raw_R1.fastq.gz'});await page.getByLabel('Pool R2').selectOption({label:'raw_R2.fastq.gz'});
  await page.getByRole('button',{name:'Add sample',exact:true}).click();
  const row=fields().samples[0];for(const key of ['sample_name','barcode_id','forward_barcode','reverse_barcode','editor','treatment','dpi','biological_replicate'])await page.locator(`[id="samples.0.${key}"]`).fill(row[key]);
  await page.getByRole('button',{name:'Continue to Mode'}).click();await page.getByRole('radio',{name:mode==='PE'?/Precise Edit/:/Indel \/ Nuclease/}).check();
  await page.getByRole('button',{name:'Continue to Target'}).click();
  await page.getByLabel('Target name',{exact:true}).fill('T1');await page.getByLabel('Copy name',{exact:true}).fill('copy1');await page.getByLabel('WT amplicon',{exact:true}).fill(fields().targets[0].wt_sequence);
  if(mode==='PE'){const row=fields().targets[0];for(const key of ['prime_edited_sequence','pegRNA_spacer','pegRNA_extension','nicking_guide','pegRNA_scaffold'])await page.locator(`[id="targets.0.${key}"]`).fill(row[key]||'')}
}
async function configuration(page:Page){await page.getByRole('button',{name:'4. Configuration'}).click();await page.getByLabel('Library extraction profile').selectOption('custom');await page.getByLabel('R1 analysis 5′ trim').fill('8');await page.getByLabel('R2 analysis 5′ trim').fill('8');await page.getByLabel('Proposed output parent (optional)').selectOption({label:'outputs'});await page.getByLabel('Proposed workspace name').fill('future-study')}
async function review(page:Page){await page.getByRole('button',{name:'Validate & Review'}).click();await expect(page.getByRole('region',{name:'Validated plan preview'})).toBeVisible();await expect(page.getByRole('button',{name:'Run Analysis',exact:true})).toBeDisabled()}
test('PE setup through real Python validation → deterministic Review without execution',async({page})=>{await start(page,'PE');await configuration(page);await review(page);await expect(page.getByRole('rowheader',{name:'edits',exact:true})).toBeVisible();const digest=await page.locator('.identities dd').first().textContent();await page.getByRole('button',{name:'Validate & Review'}).click();await expect(page.locator('.identities dd').first()).toHaveText(digest!);await page.getByRole('button',{name:'Open Existing Analysis'}).click();await page.getByLabel('Registered workspace').selectOption({label:'PE reference study'});await page.getByRole('button',{name:'Open and verify'}).click();await expect(page.getByRole('heading',{name:'Exact intended PE',exact:true})).toBeVisible();await page.getByRole('button',{name:'New Analysis',exact:true}).click();await expect(page.getByRole('region',{name:'Validated plan preview'})).toBeVisible()});
test('explicit nuclease window 0-0 → locked full contract → Review',async({page})=>{await start(page,'nuclease');await page.getByLabel(/Quantification window coordinates/).fill('0-0');await configuration(page);await page.getByRole('button',{name:'Validate draft',exact:true}).click();await expect(page.getByRole('status').filter({hasText:'VALID · revision'})).toBeVisible();await page.getByText('View full qualified scientific configuration',{exact:true}).click();const table=page.getByRole('table',{name:'Backend resolved scientific configuration (read-only)'});await expect(table.locator('tbody tr')).toHaveCount(58);await expect(table.getByRole('textbox')).toHaveCount(0);await review(page);await expect(page.getByText('"0-0"',{exact:true}).first()).toBeVisible()});
test('TIGR W2 and W1 annotations come from backend; accessible and responsive',async({page})=>{page.on('dialog',d=>d.accept());await start(page,'nuclease');await page.getByLabel('Target profile').selectOption('tigr_tas_v1');await expect(page.getByLabel('Selected window')).toHaveValue('W2');await page.getByLabel('18-nt TIGR target').fill(fields().targets[0].wt_sequence.slice(30,48));await configuration(page);await page.getByRole('button',{name:'3. Target'}).click();await page.getByRole('button',{name:'Validate draft',exact:true}).click();const annotations=page.getByRole('region',{name:'Backend target preview'});await expect(annotations.getByText('"34-43"',{exact:true})).toBeVisible();await page.getByLabel('Selected window').selectOption('W1');await expect(annotations).toHaveCount(0);await page.getByRole('button',{name:'Validate draft',exact:true}).click();await expect(annotations.getByText('"34-35_42-43"',{exact:true})).toBeVisible();await expect(annotations.getByText('"W1"',{exact:true})).toBeVisible();for(const width of [1920,1366,683]){await page.setViewportSize({width,height:768});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true)}const results=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();expect(results.violations).toEqual([]);await page.getByRole('button',{name:'4. Configuration'}).click();await review(page)});
test('invalid sentinel cannot reach Review and first error is focusable',async({page})=>{await start(page,'nuclease');await page.getByLabel(/Quantification window coordinates/).fill('0');await configuration(page);await page.getByRole('button',{name:'Validate & Review'}).click();const field=page.locator('[id="targets.0.quantification_window_coordinates"]');await expect(field).toHaveAttribute('aria-invalid','true');await expect(field).toBeFocused();await expect(page.getByRole('region',{name:'Validated plan preview'})).toHaveCount(0);await field.fill('0-0');await page.getByRole('button',{name:'5. Review'}).click();await expect(page.getByRole('region',{name:'Validated plan preview'})).toBeVisible()});

test('duplicate biological replicate blocks Review and focuses replicate metadata',async({page})=>{
  await start(page,'PE');await configuration(page);
  await page.getByRole('button',{name:'1. Samples'}).click();
  await page.getByRole('button',{name:'Add sample',exact:true}).click();
  const first=fields().samples[0],second={...fields().samples[1],editor:first.editor,treatment:first.treatment,dpi:first.dpi,biological_replicate:first.biological_replicate};
  for(const key of ['sample_name','barcode_id','forward_barcode','reverse_barcode','editor','treatment','dpi','biological_replicate'])await page.locator(`[id="samples.1.${key}"]`).fill(second[key]);
  await page.getByRole('button',{name:'5. Review'}).click();
  await expect(page.locator('[id="samples.0.biological_replicate"]')).toBeFocused();
  await expect(page.locator('[id="samples.1.biological_replicate"]')).toHaveAttribute('aria-invalid','true');
  await expect(page.getByRole('region',{name:'Validated plan preview'})).toHaveCount(0);
  await page.locator('[id="samples.1.biological_replicate"]').fill('2');await page.getByRole('button',{name:'4. Configuration'}).click();await review(page);
});
test('paired metadata error focuses Block ID rather than sample name',async({page})=>{
  await start(page,'PE');await configuration(page);
  await page.getByRole('button',{name:'1. Samples'}).click();
  await page.getByLabel('Paired biological design (requires Block ID)').check();
  await page.getByRole('button',{name:'5. Review'}).click();
  await expect(page.locator('[id="samples.0.block_id"]')).toBeFocused();
  await expect(page.getByRole('region',{name:'Validated plan preview'})).toHaveCount(0);
  await page.locator('[id="samples.0.block_id"]').fill('block1');await page.getByRole('button',{name:'4. Configuration'}).click();await review(page);
});
test('ambiguous deletion reaches Review with authoritative limitation warnings',async({page})=>{
  await start(page,'PE');const target=fields().ambiguous_deletion[0];
  for(const key of ['target_name','copy_name','wt_sequence','prime_edited_sequence','pegRNA_spacer','pegRNA_extension','nicking_guide','pegRNA_scaffold'])await page.locator(`[id="targets.0.${key}"]`).fill(target[key]||'');
  await configuration(page);await review(page);
  await expect(page.getByText(/WARNING.*NONUNIQUE_REFERENCE_ALIGNMENT/).first()).toBeVisible();
  await expect(page.getByText(/WARNING.*NONUNIQUE_EDIT_ALIGNMENT/).first()).toBeVisible();
});
test('zero-pair raw pool blocks Review with an input error',async({page})=>{
  await start(page,'PE');await configuration(page);
  await page.getByRole('button',{name:'1. Samples'}).click();
  await page.getByLabel('Pool R1').selectOption({label:'empty_R1.fastq.gz'});
  await page.getByLabel('Pool R2').selectOption({label:'empty_R2.fastq.gz'});
  await page.getByRole('button',{name:'5. Review'}).click();
  await expect(page.getByLabel('Pool R1')).toBeFocused();
  await expect(page.getByLabel('Pool R1')).toHaveAttribute('aria-invalid','true');
  await expect(page.getByRole('region',{name:'Validated plan preview'})).toHaveCount(0);
});
