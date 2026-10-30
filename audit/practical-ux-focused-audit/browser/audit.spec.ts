// Independent auditor browser spec (frozen BROWSER.md B01-B11). Real loopback server, real token,
// actual browser File inputs (setInputFiles with paths and with buffers) - never a server path string.
import {test,expect,type Page,type APIRequestContext} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import fs from 'node:fs';import path from 'node:path';import crypto from 'node:crypto';import {execFileSync} from 'node:child_process';
const ROOT=process.env.AUDIT_E2E_ROOT!;const FIX=process.env.AUDIT_FIXTURES!;const PY=process.env.AUDIT_PY!;const TOKEN='audit-e2e-token';
const H={'X-Viewer-Token':TOKEN};
const sha=(b:Buffer)=>crypto.createHash('sha256').update(b).digest('hex');
const EVID=path.join(ROOT,'evidence');fs.mkdirSync(EVID,{recursive:true});
function note(name:string,value:unknown){fs.appendFileSync(path.join(EVID,'browser-evidence.jsonl'),JSON.stringify({test:name,value})+'\n')}
async function caps(r:APIRequestContext){return (await (await r.get('/api/v1/setup/capabilities',{headers:H})).json()).files as any[]}
async function api(r:APIRequestContext,method:string,url:string,data?:unknown){const res=await r.fetch('/api/v1/'+url,{method,headers:{...H,'Content-Type':'application/json'},data:data===undefined?undefined:JSON.stringify(data)});return {status:res.status(),body:await res.json().catch(()=>null)}}
async function newAnalysis(page:Page){await page.goto('/#'+TOKEN);await page.getByRole('button',{name:'New Analysis',exact:true}).click();await expect(page.getByLabel('Browse R1 FASTQ')).toBeVisible()}
function victims(){const out:Record<string,string>={};for(const d of [path.join(ROOT,'external-victim'),path.join(ROOT,'legacy','pe')])for(const f of fs.readdirSync(d)){const p=path.join(d,f);const s=fs.statSync(p);out[p]=`${s.ino}:${s.mode}:${s.mtimeMs}:${sha(fs.readFileSync(p))}`}out['dir:'+ROOT]=fs.readdirSync(ROOT).filter(x=>!['evidence','final-ready','register-ready','hold-final','release-final','hold-register','release-register','fail-final'].includes(x)).sort().join(',');return out}

test('B01/B02 Windows-origin, unicode and duplicate names; path and buffer inputs; replacement; bytes exact',async({page})=>{
  const before=victims();await newAnalysis(page);
  const r1=fs.readFileSync(path.join(FIX,'R1.fastq.gz')),r2=fs.readFileSync(path.join(FIX,'R2.fastq.gz'));
  const names=['C:\\Users\\lab\\Desktop\\pool_R1.fastq.gz','..\\..\\VICTIM.fastq.gz','../../VICTIM.fastq.gz','sámple R1 – ☃.fastq.gz','dup.fastq.gz','dup.fastq.gz'];
  const seen:any[]=[];
  for(const [i,name] of names.entries()){
    const label=await page.getByLabel(/^(Browse|Replace) R1 FASTQ$/).first();
    const resp=page.waitForResponse(r=>r.url().includes('/setup/uploads/fastq'));
    await label.setInputFiles({name,mimeType:'application/gzip',buffer:i%2?r2:r1});
    const res=await resp;const req=res.request();const body=JSON.parse((await res.body()).toString());
    seen.push({name,status:res.status(),req_url:req.url(),entry:body});
    expect(res.status()).toBe(200);
    expect(body.file_id).toMatch(/^[0-9a-f]{32}$/);expect(JSON.stringify(body)).not.toContain(ROOT);
    expect(body.sha256).toBe(sha(i%2?r2:r1));expect(body.size_bytes).toBe(String((i%2?r2:r1).length));
    const stored=fs.readFileSync(path.join(ROOT,'private','uploads',body.file_id,'input.fastq.gz'));expect(sha(stored)).toBe(body.sha256);
    await expect(page.getByLabel('Pool R1')).toHaveValue(body.file_id);
  }
  // Actual on-disk fixture path through the native file input, twice (same file selected sequentially)
  for(const n of [1,2]){const resp=page.waitForResponse(r=>r.url().includes('/setup/uploads/fastq'));await page.getByLabel('Replace R1 FASTQ').setInputFiles(path.join(FIX,'R1.fastq.gz'));const prev=await page.getByLabel('Pool R1').inputValue();await resp;await expect(page.getByLabel('Pool R1')).not.toHaveValue(prev);
    const id=await page.getByLabel('Pool R1').inputValue();const b=(await caps(page.request)).find(f=>f.file_id===id);seen.push({native:n,entry:b});expect(b.sha256).toBe(sha(r1))}
  const ids=seen.map(s=>s.entry.file_id);expect(new Set(ids).size).toBe(ids.length);
  // nothing was written outside the private upload root; victims identical
  expect(victims()).toEqual(before);
  const listing=fs.readdirSync(path.join(ROOT,'private','uploads'));for(const d of listing)expect(fs.readdirSync(path.join(ROOT,'private','uploads',d)).sort()).toEqual(['input.fastq.gz','upload.json']);
  note('B01',seen);
});

test('B02 mid-body page close leaves no selectable partial; reload keeps only complete uploads',async({browser})=>{
  const ctx=await browser.newContext();const page=await ctx.newPage();await newAnalysis(page);
  const big=process.env.AUDIT_BIG!;const before=(await caps(page.request)).filter(f=>f.origin==='upload').map(f=>f.file_id);
  const started=page.waitForRequest(r=>r.url().includes('/setup/uploads/fastq'));
  await page.getByLabel('Browse R1 FASTQ').setInputFiles(big);await started;await page.waitForTimeout(800);await ctx.close();
  const p2=await browser.newPage();await p2.goto('/#'+TOKEN);
  await expect.poll(async()=>fs.readdirSync(path.join(ROOT,'private','uploads')).filter(d=>!before.includes(d)&&fs.readdirSync(path.join(ROOT,'private','uploads',d)).some(n=>n.startsWith('.partial'))).length,{timeout:30000}).toBe(0);
  const after=(await caps(p2.request)).filter(f=>f.origin==='upload');
  const bigSha=sha(fs.readFileSync(big));
  expect(after.filter(f=>!before.includes(f.file_id)).every(f=>f.sha256===bigSha)).toBe(true); // either nothing or the complete file
  note('B02-abort',{new_entries:after.filter(f=>!before.includes(f.file_id)).length});
  await p2.close();
});

test('B03 official template download structure',async({page})=>{
  await newAnalysis(page);const dl=page.waitForEvent('download');await page.getByRole('button',{name:'Download Excel template'}).click();const d=await dl;
  const p=path.join(EVID,'template-downloaded.xlsx');await d.saveAs(p);expect(d.suggestedFilename()).toBe('PEAnalyzer-samples-v1.xlsx');
  const info=JSON.parse(execFileSync(PY,['-c',`import zipfile,json,sys,hashlib
from openpyxl import load_workbook
z=zipfile.ZipFile(sys.argv[1]);b=load_workbook(sys.argv[1])
print(json.dumps(dict(sha=hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest(),parts=sorted(z.namelist()),sheets=b.sheetnames,headers=[c.value for c in b['Samples'][1]],
 formulas=any(c.data_type=='f' for s in b for r in s for c in r),macros=any('vba' in n.lower() for n in z.namelist()),ext=any('externalLink' in n for n in z.namelist()))))`,p]).toString());
  expect(info.sheets).toEqual(['Instructions','Samples']);expect(info.formulas||info.macros||info.ext).toBe(false);
  expect(info.headers.slice(0,6)).toEqual(['barcode_id','sample_name','editor','treatment','dpi','biological_replicate']);note('B03',info);
});

const CASES=JSON.parse(fs.readFileSync(path.join(FIX,'excel-cases.json'),'utf8'));
test('B04/B05 all 29 frozen workbooks through the file input: atomic failure, editable rows, invalidation',async({page})=>{
  test.setTimeout(600000);await newAnalysis(page);
  await page.getByRole('button',{name:'Add sample',exact:true}).click();await page.getByLabel('Sample name',{exact:true}).fill('manual-seed');
  const results:Record<string,any>={};let rowsNow=['manual-seed'];
  for(const [name,c] of Object.entries<any>(CASES)){
    page.once('dialog',d=>d.accept());
    const resp=page.waitForResponse(r=>r.url().includes('/setup/samples/import'));
    await page.getByLabel('Import Excel template').setInputFiles(path.join(FIX,name+'.xlsx'));await resp;
    // stateless parse: replay identical bytes over the same authenticated API to read the result body
    const body=await (await page.request.post('/api/v1/setup/samples/import?profile=qi_hitom_v1',{headers:{...H,'Content-Type':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'},data:fs.readFileSync(path.join(FIX,name+'.xlsx'))})).json();
    await expect(page.locator('[role=status]').filter({hasText:`${body.imported_count} samples imported · ${body.valid_count} valid · 0 warnings · ${body.errors.length} errors`})).toBeVisible();await page.waitForTimeout(400);
    const names=await page.locator('[id$=".sample_name"]').evaluateAll(es=>es.map(e=>(e as HTMLInputElement).value));
    const alert=await page.getByRole('alert').allInnerTexts();
    results[name]={expectation:c.expectation,errors:body.errors.length,rows:names.length,first:names[0],alert:alert.join(' | ').slice(0,200)};
    if(c.expectation==='reject'){expect(body.errors.length).toBeGreaterThan(0);expect(names).toEqual(rowsNow);expect(alert.join(' ')).toContain('No sample rows were replaced')}
    else{expect(body.errors).toEqual([]);expect(names.length).toBe(body.samples.length);rowsNow=names;
      // imported rows are editable and equal to returned rows
      expect(await page.locator('[id="samples.0.barcode_id"]').inputValue()).toBe(body.samples[0].barcode_id);
      expect(await page.locator('[id="samples.0.biological_replicate"]').inputValue()).toBe(body.samples[0].biological_replicate);}
  }
  // B05 edit an imported row, add/remove row; still unvalidated (no implicit Review)
  await page.locator('[id="samples.0.treatment"]').fill('edited-treatment');
  await page.getByRole('button',{name:'Add sample',exact:true}).click();await page.getByRole('button',{name:/Remove sample \d+/}).last().click();
  await expect(page.getByText(/Unvalidated edits|INVALID|VALID/).first()).toBeVisible();
  expect(fs.readdirSync(path.join(ROOT,'outputs'))).toEqual([]);   // import never runs science / writes outputs
  note('B04',results);
});

async function scenarioView(page:Page,rows:any[]){
  await page.route('**/api/v1/workspaces/**',async route=>{const res=await route.fetch();let v:any=null;try{v=await res.json()}catch{return route.fulfill({response:res})}
    if(v&&v.observations&&v.mode==='precise_edit'){v.observations=rows.map((r:any)=>({...r}));}
    await route.fulfill({response:res,json:v})});
}
async function openPE(page:Page){await page.goto('/#'+TOKEN);await page.getByRole('button',{name:'Open Existing Analysis'}).click().catch(()=>{});
  await page.getByLabel('Registered workspace').selectOption({index:0});await page.getByRole('button',{name:'Open and verify'}).click();
  await expect(page.getByRole('tab',{name:'Samples',exact:true})).toBeVisible()}
const SCEN=JSON.parse(fs.readFileSync(path.join(FIX,'metric-display.json'),'utf8')).scenarios;
for(const [scenario,rows] of Object.entries<any[]>(SCEN))test(`B08/B10 stored metric display: ${scenario}`,async({page})=>{
  await scenarioView(page,rows);await openPE(page);await page.getByRole('tab',{name:'Samples',exact:true}).click();
  const table=page.getByRole('table',{name:'Primary PE metrics across biological samples'});await expect(table).toBeVisible();
  const headers=await table.getByRole('columnheader').allInnerTexts();expect(headers).toEqual(['Sample / target','Editor / treatment','Dpi / biological replicate','Exact intended PE','CRISPResso Prime-edited reference fraction']);
  const got:any={};
  for(const row of rows){
    const key=`${row.sample_id}|${row.metric_name}|${row.copy_name}`;
    if(row.copy_name===null){
      const tr=table.getByRole('row').filter({has:page.getByRole('rowheader').filter({hasText:row.sample_id})});
      const col=row.metric_name==='total_precise_pe'?3:4;const cell=tr.locator('td').nth(col-1);const text=await cell.innerText();
      got[key]=text;
      expect(text).toContain(row.percentage??'—');expect(text).toContain(`${row.numerator??'—'} / ${row.denominator??'—'}`);expect(text).toContain(row.status.replaceAll('_',' '));
    }else{
      const sel=page.getByLabel('Stored metric series');const opt=sel.locator('optgroup[label="Copy-specific routed diagnostics"] option').filter({hasText:`${row.copy_name} · ${row.label}`});
      await sel.selectOption({value:await opt.first().getAttribute('value')});
      const t=page.getByRole('table',{name:'Biological sample observations'});const tr=t.getByRole('row').filter({has:page.getByRole('rowheader').filter({hasText:row.sample_id})});
      const cells=await tr.locator('td').allInnerTexts();got[key]=cells;
      expect(cells[2]).toBe(row.percentage??'—');expect(cells[3]).toBe(`${row.numerator??'—'} / ${row.denominator??'—'}`);expect(cells[4]).toContain(row.status.replaceAll('_',' '));
      await expect(page.getByText(/Copy-specific routed diagnostics: these values are conditional on confident copy routing/)).toBeVisible();
    }
  }
  if(scenario==='missing-comparator'){const tr=table.getByRole('row').nth(1);expect(await tr.locator('td').nth(3).innerText()).toBe('Not available')}
  // primary group precedes copy group in the series selector (DOM order and visible labels)
  expect(await page.getByLabel('Stored metric series').locator('optgroup').evaluateAll(g=>g.map(e=>e.getAttribute('label')))).toEqual(['Primary biological metrics','Copy-specific routed diagnostics']);
  note('B08-'+scenario,got);
});

test('B09/B10 definitions, keyboard disclosure, statistics/overview labelling of copy series (real PE workspace)',async({page})=>{
  await openPE(page);
  const cards=await page.locator('.metric-card h3').allInnerTexts();note('B09-overview-cards',cards);
  await page.getByRole('tab',{name:'Samples',exact:true}).click();
  const summary=page.getByText('Definition and population').first();await summary.focus();await page.keyboard.press('Enter');
  const det=page.locator('details').filter({has:summary}).first();expect(await det.getAttribute('open')).not.toBeNull();
  const text=await det.innerText();note('B09-definition',text);
  expect(text).toMatch(/Exact intended PE \/ \(exact WT \+ exact intended PE\)/);expect(text).toContain('Denominator: Exact WT + exact PE products');expect(text).toMatch(/Population: /);
  await page.keyboard.press('Escape');const escClosed=(await det.getAttribute('open'))===null;await page.keyboard.press('Enter');const enterToggled=(await det.getAttribute('open'))===null;
  note('B09-escape',{escape_closes:escClosed,enter_toggles_closed:enterToggled,focused_is_summary:await page.evaluate(()=>document.activeElement?.tagName)});
  const comp=page.getByRole('table',{name:'Primary PE metrics across biological samples'}).locator('td').nth(3);await comp.getByText('Definition and population').click();
  const ctext=await comp.innerText();expect(ctext).toContain('Prime-edited reference-assigned reads / authoritative aligned reads; not CRISPResso Modified%');expect(ctext).toContain('Denominator: Authoritative aligned reads');
  // copy series in Statistics: what does the Metric column say?
  const sel=page.getByLabel('Stored metric series');const copyOpts=await sel.locator('optgroup[label="Copy-specific routed diagnostics"] option').allInnerTexts();
  const v=await sel.locator('optgroup[label="Copy-specific routed diagnostics"] option').first().getAttribute('value');await sel.selectOption({value:v!});
  await page.getByRole('tab',{name:'Statistics',exact:true}).click();const stat=page.getByRole('table',{name:'Biological replicate summaries · stored unweighted means'});
  const metricCol=await stat.locator('tbody tr td:nth-child(2)').allInnerTexts();const selectedText=await sel.evaluate((s:any)=>s.options[s.selectedIndex].text);
  const statCallout=await page.locator('.callout').allInnerTexts();
  note('B10-statistics-copy-series',{copy_options:copyOpts,selected:selectedText,metric_column:metricCol,callouts:statCallout});
  await page.screenshot({path:path.join(EVID,'statistics-copy-series.png'),fullPage:true});
  const axe=(await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze()).violations;expect(axe).toEqual([]);
  await expect(page.locator('.read-only')).toHaveText('Local · 0.9.0');
});

test('B11 nuclease results unchanged: no PE columns, exclusive vs overlapping, stored counts',async({page})=>{
  await page.goto('/#'+TOKEN);await page.getByLabel('Registered workspace').selectOption({index:1});await page.getByRole('button',{name:'Open and verify'}).click();
  await expect(page.getByRole('heading',{name:'Indel fraction',exact:true})).toBeVisible();
  await expect(page.getByRole('table',{name:'Exclusive biological classes · accepted aligned population'})).toBeVisible();await expect(page.getByRole('table',{name:'Overlapping metrics — do not sum'})).toBeVisible();
  await page.getByRole('tab',{name:'Samples',exact:true}).click();expect(await page.getByRole('table',{name:'Primary PE metrics across biological samples'}).count()).toBe(0);
  const reg=(await (await page.request.get('/api/v1/workspaces',{headers:H})).json())[1].registration_id;
  const view=(await (await page.request.post('/api/v1/workspaces/open',{headers:{...H,'Content-Type':'application/json'},data:JSON.stringify({registration_id:reg})})).json());
  const t=page.getByRole('table',{name:'Biological sample observations'});
  const def=view.observations.find((o:any)=>o.metric_name==='indel_fraction').series_id;
  for(const o of view.observations.filter((o:any)=>o.series_id===def)){
    const cells=await t.getByRole('row').filter({has:page.getByRole('rowheader').filter({hasText:o.sample_id})}).locator('td').allInnerTexts();
    expect(cells[2]).toBe(o.percentage??'—');expect(cells[3]).toBe(`${o.numerator??'—'} / ${o.denominator??'—'}`);
  }
});

// ---------------- B07 final verification with real worker/registration barriers ----------------
async function launch(r:APIRequestContext,ws:string){
  const files=await caps(r);const leg=files.filter(f=>f.origin==='launcher'&&f.kind==='fastq');const r1=leg.find(f=>f.label==='raw_R1.fastq.gz');const r2=leg.find(f=>f.label==='raw_R2.fastq.gz');const out=files.find(f=>f.kind==='output_root');
  const t=JSON.parse(fs.readFileSync(path.join(process.env.AUDIT_PE_TEMPLATE!),'utf8'));
  const d=(await api(r,'POST','drafts',{})).body;const p=(await api(r,'PATCH','drafts/'+d.draft_id,{revision:d.revision,content:{...t,r1:r1.file_id,r2:r2.file_id,output_root:out.file_id,workspace_name:ws}})).body;
  const v=(await api(r,'POST',`drafts/${d.draft_id}/validate`,{revision:p.revision})).body;expect(v.status).toBe('VALID');
  const pv=(await api(r,'GET',`drafts/${d.draft_id}/preview?revision=${p.revision}`)).body;
  const j=(await api(r,'POST','jobs',{draft_id:d.draft_id,revision:p.revision,plan_identity_sha256:pv.plan_identity_sha256,scientific_identity_sha256:pv.scientific_identity_sha256})).body;expect(j.job_id).toBeTruthy();return j.job_id;
}
const flag=(n:string)=>fs.writeFileSync(path.join(ROOT,n),'1');const clear=()=>{for(const n of ['hold-final','release-final','hold-register','release-register','fail-final','final-ready','register-ready'])fs.rmSync(path.join(ROOT,n),{force:true})};
async function wait(n:string,t=400000){const end=Date.now()+t;while(!fs.existsSync(path.join(ROOT,n))){if(Date.now()>end)throw new Error('timeout '+n);await new Promise(r=>setTimeout(r,200))}}
async function job(r:APIRequestContext,id:string){return (await api(r,'GET','jobs/'+id)).body}
test.describe.serial('B07 verification timelines',()=>{
  test.setTimeout(900000);
  test('active → all stages complete → FINAL_VALIDATION → VIEWER_VERIFICATION → COMPLETED; reload, duplicate/out-of-order events',async({page})=>{
    clear();flag('hold-final');flag('hold-register');const id=await launch(page.request,'b07-ok');
    await page.goto('/#'+TOKEN);await expect(page.locator('#run-main [role="status"]')).toContainText('RUNNING',{timeout:60000});
    const sawActive=await page.getByText(/Current stage: (?!No scientific stage active)/).count();
    await wait('final-ready');
    const j1=await job(page.request,id);expect(j1.state).toBe('RUNNING');expect(j1.finished_stages).toBe(j1.total_stages);
    await expect(page.getByRole('heading',{name:'Final verification in progress'})).toBeVisible({timeout:15000});
    expect(await page.getByRole('button',{name:'Open Results'}).count()).toBe(0);
    await page.screenshot({path:path.join(EVID,'final-validation.png'),fullPage:true});
    await page.reload();await expect(page.getByRole('heading',{name:'Final verification in progress'})).toBeVisible({timeout:15000});
    // duplicated and reversed event delivery (presentation transport only)
    await page.route('**/api/v1/jobs/*/events*',async route=>{const res=await route.fetch();const b=await res.json();if(b&&b.items){b.items=[...b.items,...b.items].reverse()}await route.fulfill({response:res,json:b})});
    await page.reload();await expect(page.getByRole('heading',{name:'Final verification in progress'})).toBeVisible({timeout:15000});
    expect(await page.getByRole('button',{name:'Open Results'}).count()).toBe(0);await expect(page.locator('#run-main [role="status"]')).toContainText('RUNNING');
    await page.unroute('**/api/v1/jobs/*/events*');
    flag('release-final');await wait('register-ready');
    const j2=await job(page.request,id);const evs=(await api(page.request,'GET',`jobs/${id}/events?after=0&limit=500`)).body.items.map((e:any)=>e.status);
    expect(j2.state).toBe('RUNNING');expect(j2.cancellable).toBe(false);expect(evs).toContain('VIEWER_VERIFICATION');expect(j2.workspace_id).toBeNull();
    await page.reload();await expect(page.getByRole('heading',{name:'Final verification in progress'})).toBeVisible({timeout:15000});
    expect(await page.getByRole('button',{name:'Cancel analysis'}).count()).toBe(0);expect(await page.getByRole('button',{name:'Open Results'}).count()).toBe(0);
    await page.screenshot({path:path.join(EVID,'viewer-verification.png'),fullPage:true});
    const axe=(await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze()).violations;
    flag('release-register');await expect(page.getByRole('button',{name:'Open Results'})).toBeVisible({timeout:60000});
    const j3=await job(page.request,id);expect(j3.state).toBe('COMPLETED');expect(j3.workspace_id).toBeTruthy();
    expect(await page.getByRole('heading',{name:'Final verification in progress'}).count()).toBe(0);
    note('B07-ok',{sawActiveStageText:sawActive,j1:{state:j1.state,f:j1.finished_stages,t:j1.total_stages,c:j1.cancellable},j2:{state:j2.state,c:j2.cancellable},events:evs.slice(-6),axe:axe.length});clear();
  });
  test('cancel during FINAL_VALIDATION: CANCELLING/CANCELLED supersede verification text',async({page})=>{
    clear();flag('hold-final');const id=await launch(page.request,'b07-cancel');await page.goto('/#'+TOKEN);await wait('final-ready');
    await expect(page.getByRole('heading',{name:'Final verification in progress'})).toBeVisible({timeout:15000});
    await page.getByRole('button',{name:'Cancel analysis'}).click();await page.getByRole('button',{name:/Confirm cancellation/}).click();
    await expect(page.locator('#run-main [role="status"]')).toContainText(/CANCELLING|CANCELLED/,{timeout:15000});
    expect(await page.getByRole('heading',{name:'Final verification in progress'}).count()).toBe(0);
    await expect(page.locator('#run-main [role="status"]')).toContainText('CANCELLED',{timeout:120000});
    expect(await page.getByRole('heading',{name:'Final verification in progress'}).count()).toBe(0);expect(await page.getByRole('button',{name:'Open Results'}).count()).toBe(0);
    const j=await job(page.request,id);note('B07-cancel',{state:j.state,ws:j.workspace_id});expect(j.workspace_id).toBeNull();clear();
  });
  test('verification failure: FAILED supersedes stale verification text; no results',async({page})=>{
    clear();flag('hold-final');flag('fail-final');const id=await launch(page.request,'b07-fail');await page.goto('/#'+TOKEN);await wait('final-ready');
    await expect(page.getByRole('heading',{name:'Final verification in progress'})).toBeVisible({timeout:15000});flag('release-final');
    await expect(page.locator('#run-main [role="status"]')).toContainText('FAILED',{timeout:120000});
    expect(await page.getByRole('heading',{name:'Final verification in progress'}).count()).toBe(0);expect(await page.getByRole('button',{name:'Open Results'}).count()).toBe(0);
    const j=await job(page.request,id);note('B07-fail',{state:j.state,error:j.error,ws:j.workspace_id});expect(j.workspace_id).toBeNull();clear();
  });
});

test('B10b Statistics and sample-detail labelling for a copy-specific series',async({page})=>{
  await openPE(page);const sel=page.getByLabel('Stored metric series');
  const out:any={};
  for(const group of ['Primary biological metrics','Copy-specific routed diagnostics']){
    const v=await sel.locator(`optgroup[label="${group}"] option`).filter({hasText:'Exact intended PE'}).first().getAttribute('value');await sel.selectOption({value:v!});
    await page.getByRole('tab',{name:'Statistics',exact:true}).click();await expect(page.getByRole('tab',{name:'Statistics',exact:true})).toHaveAttribute('aria-selected','true');
    const stat=page.getByRole('table',{name:'Biological replicate summaries · stored unweighted means'});await expect(stat).toBeVisible();
    const rows=await stat.locator('tbody tr').evaluateAll(rs=>rs.map(r=>Array.from(r.children).slice(0,4).map(c=>(c as HTMLElement).innerText)));
    const callouts=await page.locator('.callout').allInnerTexts();
    await page.screenshot({path:path.join(EVID,`statistics-${group.startsWith('Copy')?'copy':'primary'}.png`),fullPage:true});
    await page.getByRole('tab',{name:'Samples',exact:true}).click();await page.getByRole('button',{name:/^Inspect /}).first().click();
    const card=await page.getByRole('region',{name:'Sample detail'}).locator('.metric-card').innerText();
    out[group]={selected:await sel.evaluate((s:any)=>s.options[s.selectedIndex].text),statistics_rows:rows,statistics_callouts:callouts,detail_card:card.split('\n').slice(0,8)};
    await page.getByRole('button',{name:'Close sample detail'}).click();
  }
  note('B10b',out);
});
