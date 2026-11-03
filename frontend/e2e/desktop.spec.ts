import {expect,test} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
test('Light default, persistent keyboard theme, unchanged observations and dark accessibility',async({page})=>{
  await page.emulateMedia({colorScheme:'dark'});
  await page.goto('/#e2e-local-token');
  const theme=page.getByRole('combobox',{name:'Theme'});
  await expect(theme).toHaveValue('light');
  await page.getByLabel('Registered workspace').selectOption({label:'PE reference study'});
  const opened=page.waitForResponse(r=>r.url().endsWith('/workspaces/open'));
  await page.getByRole('button',{name:'Open and verify'}).click();
  const view=await (await opened).json();
  await theme.focus();await page.keyboard.press('ArrowDown');await page.keyboard.press('Enter');
  await expect(theme).toHaveValue('dark');
  await expect(page.locator('html')).toHaveAttribute('data-theme','dark');
  const current=await page.request.get(`/api/v1/workspaces/${view.workspace_id}`,{headers:{'X-Viewer-Token':'e2e-local-token'}});
  expect((await current.json()).observations).toEqual(view.observations);
  for(const tab of ['Overview','Samples','QC','Statistics','Provenance']){
    await page.getByRole('tab',{name:tab,exact:true}).click();
    await expect(page.getByRole('tab',{name:tab,exact:true})).toHaveAttribute('aria-selected','true');
    expect((await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze()).violations).toEqual([]);
  }
  for(const flow of ['New Analysis','Recover Analysis','Open Existing Analysis']){
    await page.getByRole('button',{name:flow,exact:true}).click();
    await expect(theme).toBeVisible();
    expect((await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze()).violations).toEqual([]);
  }
  await page.reload();await expect(theme).toHaveValue('dark');
  await theme.selectOption('light');await page.reload();await expect(theme).toHaveValue('light');
});
test('library refresh and manual reveal remain explicit conveniences',async({page})=>{
  const reveal:string[]=[];page.on('request',r=>{if(r.url().endsWith('/reveal'))reveal.push(r.url())});
  await page.goto('/#e2e-local-token');
  await page.getByRole('button',{name:'Refresh library'}).click();
  await expect(page.getByText('Analysis library refreshed.')).toBeVisible();
  await page.getByLabel('Registered workspace').selectOption({label:'PE reference study'});
  await page.getByRole('button',{name:'Open and verify'}).click();
  await expect(page.getByRole('button',{name:'Open output folder'})).toBeVisible();
  expect(reveal).toEqual([]);
  await page.getByRole('button',{name:'Open output folder'}).click();
  await expect(page.getByText('Open output folder is available on Windows / WSL. The analysis remains completed.')).toBeVisible();
  expect(reveal).toHaveLength(1);
  await page.reload();expect(reveal).toHaveLength(1);
});
