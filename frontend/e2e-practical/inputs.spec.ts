import {test,expect} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
const root=process.env.PRACTICAL_E2E_ROOT!;
for(const mode of ['pe','nuclease'])test(`${mode}: actual browser file inputs + XLSX → Review → Run → Results`,async({page})=>{
  const fields=JSON.parse(fs.readFileSync(path.join(root,'fields.json'),'utf8'))[mode];
  await page.goto('/#e2e-local-token');await page.getByRole('button',{name:'New Analysis',exact:true}).click();
  await page.getByLabel('Analysis name',{exact:true}).fill(mode==='pe'?'Hold final PE':'Browser nuclease');
  const receipts:any[]=[];
  for(const mate of ['R1','R2']){
    await page.getByLabel(`Browse ${mate} FASTQ`).setInputFiles(path.join(root,mode,'inputs',`raw_${mate}.fastq.gz`));
    await expect(page.getByLabel(`Replace ${mate} FASTQ`)).toBeEnabled();
    const caps=await (await page.request.get('/api/v1/setup/capabilities',{headers:{'X-Viewer-Token':'e2e-local-token'}})).json();
    const id=await page.getByLabel(`Pool ${mate}`).inputValue();receipts.push(caps.files.find((f:any)=>f.file_id===id));
  }
  await expect.poll(()=>receipts.length).toBe(2);
  for(let i=0;i<2;i++){const bytes=fs.readFileSync(path.join(root,mode,'inputs',`raw_R${i+1}.fastq.gz`));expect(receipts[i].sha256).toBe(crypto.createHash('sha256').update(bytes).digest('hex'));expect(receipts[i].size_bytes).toBe(String(bytes.length))}
  await page.getByRole('button',{name:'4. Configuration'}).click();await page.getByLabel('Library extraction profile').selectOption('custom');
  await page.getByRole('button',{name:'1. Samples'}).click();
  const downloaded=page.waitForEvent('download');await page.getByRole('button',{name:'Download Excel template'}).click();expect((await downloaded).suggestedFilename()).toBe('PEAnalyzer-samples-v1.xlsx');
  page.once('dialog',d=>d.accept());await page.getByLabel('Import Excel template').setInputFiles(path.join(root,mode,'samples.xlsx'));
  await expect(page.getByLabel('Sample name',{exact:true})).toHaveValue(fields.samples[0].sample_name);
  await expect(page.getByText(/1 samples imported · 1 valid/)).toBeVisible();
  await page.getByLabel('Editor',{exact:true}).fill(fields.samples[0].editor); // imported rows remain editable
  expect((await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze()).violations).toEqual([]);
  await page.getByRole('button',{name:'2. Mode'}).click();await page.getByRole('radio',{name:mode==='pe'?/Precise Edit/:/Indel \/ Nuclease/}).check();
  await page.getByRole('button',{name:'3. Target'}).click();
  for(let i=0;i<fields.targets.length;i++){
    if(i)await page.getByRole('button',{name:'Add copy',exact:true}).click();const row=fields.targets[i];
    for(const key of ['target_name','copy_name','wt_sequence'])await page.locator(`[id="targets.${i}.${key}"]`).fill(row[key]);
    if(mode==='pe'){for(const key of ['prime_edited_sequence','pegRNA_spacer','pegRNA_extension','nicking_guide','pegRNA_scaffold'])await page.locator(`[id="targets.${i}.${key}"]`).fill(row[key]||'')}
    else{page.once('dialog',d=>d.accept());await page.getByLabel('Target profile').selectOption('tigr_tas_v1');await page.getByLabel('18-nt TIGR target').fill(row.tigr_target_sequence);await page.getByLabel('Selected window').selectOption(row.tigr_window)}
  }
  await page.getByRole('button',{name:'4. Configuration'}).click();await page.getByLabel('R1 analysis 5′ trim').fill('8');await page.getByLabel('R2 analysis 5′ trim').fill('8');
  await page.getByLabel('Proposed output parent (optional)').selectOption({label:'outputs'});await page.getByLabel('Proposed workspace name').fill(mode);
  await page.getByRole('button',{name:'Validate & Review'}).click();await expect(page.getByRole('button',{name:'Run Analysis',exact:true})).toBeEnabled();
  expect(fs.existsSync(path.join(root,'outputs',mode))).toBe(false);
  await page.getByRole('button',{name:'Run Analysis',exact:true}).click();
  if(mode==='pe'){
    try{await expect(page.getByRole('heading',{name:'Final verification in progress'})).toBeVisible({timeout:90000});
      await expect(page.locator('#run-main [role="status"]')).toContainText('RUNNING');
      expect(await page.getByText('Current stage: No scientific stage active',{exact:true}).count()).toBe(0);
      expect(await page.getByRole('button',{name:'Open Results',exact:true}).count()).toBe(0);
      await page.reload();await expect(page.getByRole('heading',{name:'Final verification in progress'})).toBeVisible();
    }finally{fs.writeFileSync(path.join(root,'final-release'),'release')}
  }
  await expect(page.getByRole('button',{name:'Open Results',exact:true})).toBeVisible({timeout:120000});await page.getByRole('button',{name:'Open Results',exact:true}).click();
  await page.getByRole('tab',{name:'Samples',exact:true}).click();
  if(mode==='pe'){
    const table=page.getByRole('table',{name:'Primary PE metrics across biological samples'});await expect(table).toBeVisible();
    await expect(table.getByRole('columnheader',{name:'Exact intended PE'})).toBeVisible();await expect(table.getByRole('columnheader',{name:'CRISPResso Prime-edited reference fraction'})).toBeVisible();
    await expect(table.getByText('2 / 24',{exact:true})).toHaveCount(2);
    expect(await page.getByLabel('Stored metric series').locator('optgroup').evaluateAll(items=>items.map(e=>e.getAttribute('label')))).toEqual(['Primary biological metrics','Copy-specific routed diagnostics']);
  }else{await expect(page.getByRole('table',{name:'Biological sample observations'})).toBeVisible()}
  expect((await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze()).violations).toEqual([]);
  for(const width of [1366,683]){await page.setViewportSize({width,height:768});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true)}
});
test('failed replacement and invalid workbook preserve editable selections',async({page})=>{
  await page.goto('/#e2e-local-token');await page.getByRole('button',{name:'New Analysis',exact:true}).click();
  await page.getByLabel('Browse R1 FASTQ').setInputFiles(path.join(root,'pe/inputs/raw_R1.fastq.gz'));await expect(page.getByLabel('Replace R1 FASTQ')).toBeEnabled();
  const prior=await page.getByLabel('Pool R1').inputValue();
  await page.getByLabel('Replace R1 FASTQ').setInputFiles({name:'broken.fastq.gz',mimeType:'application/gzip',buffer:Buffer.from('broken')});
  await expect(page.getByRole('alert')).toContainText('INVALID_FASTQ_UPLOAD');await expect(page.getByLabel('Pool R1')).toHaveValue(prior);
  await page.getByRole('button',{name:'Add sample',exact:true}).click();await page.getByLabel('Sample name',{exact:true}).fill('manual');
  page.once('dialog',d=>d.accept());await page.getByLabel('Import Excel template').setInputFiles(path.join(root,'bad.xlsx'));
  await expect(page.getByText(/Row 2 · barcode_id: 9Z/)).toBeVisible();await expect(page.getByLabel('Sample name',{exact:true})).toHaveValue('manual');
});
