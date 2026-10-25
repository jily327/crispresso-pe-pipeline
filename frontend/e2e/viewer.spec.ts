import { expect, test, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
async function open(page:Page,label='PE reference study') {
  await page.goto('/#e2e-local-token');
  await page.getByLabel('Registered workspace').selectOption({label});
  await page.getByRole('button',{name:'Open and verify'}).click();
  await expect(page.getByRole('heading',{name:label,exact:true})).toBeVisible();
}
async function tab(page:Page,name:string) {
  await page.getByRole('tab',{name,exact:true}).click();
  await expect(page.getByRole('tab',{name,exact:true})).toHaveAttribute('aria-selected','true');
}

test('real PE workspace → five views, exact/native distinction, source download and reopen',async({page})=>{
  const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
  await open(page);
  await expect(page.getByRole('heading',{name:'Exact intended PE',exact:true})).toBeVisible();
  await expect(page.getByRole('heading',{name:'CRISPResso native PE',exact:true})).toBeVisible();
  await tab(page,'Samples');await page.getByRole('button',{name:'Inspect bio1',exact:true}).click();
  await expect(page.getByRole('region',{name:'Sample detail'})).toBeVisible();await page.getByRole('button',{name:'Close sample detail'}).click();
  await tab(page,'QC');await expect(page.getByText('This is not a universal input → aligned → exact funnel.',{exact:false})).toBeVisible();
  await tab(page,'Statistics');await expect(page.getByRole('table',{name:'Biological replicate summaries · stored unweighted means'})).toBeVisible();
  await tab(page,'Provenance');await expect(page.getByText('Not produced',{exact:true})).toBeVisible();
  await page.getByLabel('Filter artifact names').fill('statistics/result.json');
  const waiting=page.waitForEvent('download');await page.getByRole('button',{name:'Download',exact:true}).click();
  expect((await waiting).suggestedFilename()).toBe('result.json');
  await page.getByRole('button',{name:'Close workspace'}).click();await page.getByRole('button',{name:'Open and verify'}).click();
  await expect(page.getByRole('heading',{name:'Exact intended PE',exact:true})).toBeVisible();expect(errors).toEqual([]);
});

test('real nuclease data preserves partition, overlap, net-zero, alleles and qualified configuration',async({page})=>{
  await open(page,'Nuclease reference study');
  await expect(page.getByRole('heading',{name:'Indel fraction',exact:true})).toBeVisible();
  await expect(page.getByRole('table',{name:'Exclusive biological classes · accepted aligned population'})).toBeVisible();
  await expect(page.getByRole('table',{name:'Overlapping metrics — do not sum'})).toBeVisible();
  await expect(page.getByText('0 · Net zero indel')).toBeVisible();
  await tab(page,'Samples');await page.getByRole('button',{name:'Inspect bio1',exact:true}).click();
  await expect(page.getByRole('table',{name:/Alleles ·/})).toBeVisible();
  await tab(page,'Provenance');await page.getByText('Qualified scientific configuration · backend-validated expected values',{exact:true}).click();
  await expect(page.getByRole('rowheader',{name:'discard_indel_reads',exact:true})).toBeVisible();
  expect(await page.locator('iframe,object,embed').count()).toBe(0);
});

test('invalid workspace refuses scientific display',async({page})=>{
  await page.goto('/#e2e-local-token');await page.getByLabel('Registered workspace').selectOption({label:'Invalid workspace'});
  await page.getByRole('button',{name:'Open and verify'}).click();await expect(page.getByRole('alert')).toBeVisible();
  await expect(page.getByRole('tab')).toHaveCount(0);await page.getByText('Technical details',{exact:true}).click();
  await expect(page.getByText('WORKSPACE_NOT_FOUND',{exact:true})).toBeVisible();
});

test('keyboard tabs, accessible tables, AA scan and desktop/200-percent reflow',async({page})=>{
  await open(page);await page.getByRole('tab',{name:'Overview',exact:true}).focus();await page.keyboard.press('ArrowRight');
  await expect(page.getByRole('tab',{name:'Samples',exact:true})).toBeFocused();
  await page.keyboard.press('End');await expect(page.getByRole('tab',{name:'Provenance',exact:true})).toBeFocused();
  await tab(page,'Overview');
  const results=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();
  expect(results.violations).toEqual([]);
  await page.screenshot({path:'test-results/overview-1366.png',fullPage:true});
  await page.setViewportSize({width:1920,height:1080});await page.screenshot({path:'test-results/overview-1920.png',fullPage:true});
  // A 1366px desktop at 200% browser zoom exposes a 683px CSS layout viewport.
  await page.setViewportSize({width:683,height:384});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
  await expect(page.getByRole('heading',{name:'Exact intended PE',exact:true})).toBeVisible();
  await page.screenshot({path:'test-results/overview-200-percent.png',fullPage:true});
});

test('local API denies missing session and cross-origin access',async({request})=>{
  expect((await request.get('/api/v1/capabilities')).status()).toBe(401);
  expect((await request.get('/api/v1/capabilities',{headers:{'X-Viewer-Token':'e2e-local-token','Origin':'https://outside.example'}})).status()).toBe(403);
});

test('a failed revalidation hides an already opened scientific view',async({page})=>{
  await open(page);
  await page.route('**/api/v1/workspaces/*',async route=>{
    if(route.request().method()==='GET')await route.fulfill({status:409,contentType:'application/json',body:JSON.stringify({error:{code:'WORKSPACE_CHANGED',message:'The workspace changed. Results have been hidden; reopen to verify.',detail:'Test revalidation failure',stage_id:null}})});
    else await route.continue();
  });
  await page.getByRole('tab',{name:'Samples',exact:true}).click();await expect(page.getByRole('alert')).toBeVisible();
  await expect(page.getByRole('heading',{name:'Exact intended PE',exact:true})).toHaveCount(0);
  await expect(page.getByRole('tab')).toHaveCount(0);
});
