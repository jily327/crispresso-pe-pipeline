/* Run against a local viewer with the three verified synthetic workspaces registered by label. */
const { createRequire } = require('node:module');
const { resolve } = require('node:path');
const viewerRequire = createRequire(resolve('frontend/package.json'));
const { chromium, expect } = viewerRequire('@playwright/test');

async function check() {
  const url = process.env.V110_BROWSER_URL;
  if (!url) throw new Error('Set V110_BROWSER_URL to the loopback viewer URL and session fragment.');
  const browser = await chromium.launch({ executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE });
  const page = await browser.newPage();
  const rows = [];
  try {
    await page.goto(url);
    async function open(name) {
      await page.getByLabel('Registered workspace').selectOption({label: name});
      await page.getByRole('button', {name: 'Open and verify'}).click();
      await expect(page.getByRole('heading', {name,exact:true})).toBeVisible();
      await expect(page.getByRole('tab',{name:'Overview'})).toHaveAttribute('aria-selected','true');
    }
    async function counts(table, outcome, n, d) {
      const row = page.getByRole('table',{name:table,exact:true}).getByRole('row').filter({has:page.getByRole('rowheader',{name:outcome,exact:true})});
      const cells = row.getByRole('cell');
      await expect(cells.nth(0)).toHaveText(String(n));
      await expect(cells.nth(1)).toHaveText(String(d));
      rows.push({table,outcome,numerator:n,denominator:d});
    }
    await open('Two-site synthetic study');
    await counts('Concordant two-site calls (Q30) · Combined target','Site A only',6,40);
    await counts('Concordant two-site calls (Q30) · Combined target','Site B only',8,40);
    await counts('Concordant two-site calls (Q30) · Combined target','Complete double edit',6,40);
    await counts('Sites in aligned CRISPResso alleles · Combined target','Complete double edit',6,40);
    await counts('Exact full-length haplotypes · Combined target','Complete double edit',4,38);
    await counts('Concordant two-site calls (Q30) · Unresolved copy','Complete double edit',6,40);
    const copy1 = page.locator('article').filter({has:page.getByRole('heading',{name:'Concordant two-site calls (Q30) · Copy · copy1',exact:true})});
    await expect(copy1.locator('.status')).toContainText('NOT ASSESSABLE');
    await expect(copy1.getByRole('row').filter({has:page.getByRole('rowheader',{name:'Complete double edit',exact:true})}).getByRole('cell').last()).toHaveText('Not assessable');
    await expect(page.getByRole('region',{name:'Excel summary integrity'})).toContainText('Summary counts match verified science');
    await page.getByRole('tab',{name:'QC',exact:true}).click();
    await expect(page.getByRole('rowheader',{name:'backend_input_order',exact:true})).toBeVisible();
    await page.getByLabel('Biological sample').selectOption('bc002');
    await expect(page.getByText('EMPTY_NEGATIVE_CONTROL',{exact:true}).first()).toBeVisible();
    await page.getByRole('tab',{name:'Overview',exact:true}).click();
    await expect(page.locator('.metric-card .metric-value').first()).toHaveText('—');
    for(const [window,total,chr13] of [['W2',3,1],['W3',4,2]]) {
      await open(window+' synthetic study');
      const label='Nuclease outcomes · '+(window==='W2'?'W2 primary window':'W3 exploratory window');
      await counts(label+' · Combined target','indel fraction',total,16);
      await counts(label+' · Copy · chr03g','indel fraction',1,6);
      await counts(label+' · Copy · chr13g','indel fraction',chr13,7);
    }
    console.log(JSON.stringify({chromium:browser.version(),results:rows,empty_control:'EMPTY_NEGATIVE_CONTROL',empty_metric:'unavailable',physical_mate_order_visible:true,zero_eligible_copy:'NOT_ASSESSABLE',excel_export_status:'CONTENTS_MATCH'},null,2));
  } finally {
    await browser.close();
  }
}
check().catch(error=>{console.error(error);process.exitCode=1;});
