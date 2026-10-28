const fs=require('fs'),path=require('path'),cp=require('child_process');
const {chromium}=require('playwright');
// Maintainer-only browser driver. Activate the fresh app venv before starting.
// Playwright and Chromium belong to the separate TEST environment, not the app.
const [pkg,root,core,browserPath='/usr/bin/chromium']=process.argv.slice(2);
if(!pkg||!root||!core)throw Error('Usage: node browser_smoke.cjs PACKAGE NEW_ROOT TRUSTED_CORE [CHROMIUM]');
fs.mkdirSync(root);fs.mkdirSync(path.join(root,'outputs'));fs.cpSync(path.join(pkg,'fixtures'),path.join(root,'inputs'),{recursive:true});
(async()=>{const browser=await chromium.launch({executablePath:browserPath,headless:true,args:['--no-sandbox']});const results={browser:await browser.version(),windows_wsl:false,modes:{}};
try{for(const mode of ['pe','nuclease']){
 const input=path.join(root,'inputs',mode),data=JSON.parse(fs.readFileSync(path.join(input,'draft-values.json')));
 const server=cp.spawn('bash',[path.join(pkg,'launch-new-analysis.sh'),path.join(input,'raw_R1.fastq.gz'),path.join(input,'raw_R2.fastq.gz'),path.join(root,'outputs'),core],{cwd:root,env:{...process.env,PYTHONUNBUFFERED:'1'}});
 let logs='';server.stdout.on('data',d=>logs+=d);server.stderr.on('data',d=>logs+=d);
 try{const url=await new Promise((resolve,reject)=>{const timeout=setTimeout(()=>{clearInterval(tick);reject(Error('launcher startup timeout'))},20000);const tick=setInterval(()=>{const match=logs.match(/http:\/\/127\.0\.0\.1:8765\/#[A-Za-z0-9_-]+/);if(match){clearInterval(tick);clearTimeout(timeout);resolve(match[0])}else if(server.exitCode!==null){clearInterval(tick);clearTimeout(timeout);reject(Error('launcher exited'))}},100)});
 const page=await browser.newPage();await page.goto(url);await page.getByRole('button',{name:'New Analysis',exact:true}).click();await page.getByLabel('Analysis name',{exact:true}).fill('Installed wheel '+mode);
 await page.getByLabel('Pool R1').selectOption({label:'raw_R1.fastq.gz'});await page.getByLabel('Pool R2').selectOption({label:'raw_R2.fastq.gz'});await page.getByRole('button',{name:'Add sample',exact:true}).click();
 for(const key of ['sample_name','barcode_id','forward_barcode','reverse_barcode','editor','treatment','dpi','biological_replicate'])await page.locator(`[id="samples.0.${key}"]`).fill(String(data.samples[0][key]));
 await page.getByRole('button',{name:'2. Mode'}).click();await page.getByRole('radio',{name:mode==='pe'?/Precise Edit/:/Indel \/ Nuclease/}).check();await page.getByRole('button',{name:'3. Target'}).click();
 for(let i=0;i<data.targets.length;i++){if(i)await page.getByRole('button',{name:'Add copy',exact:true}).click();const row=data.targets[i];for(const key of ['target_name','copy_name','wt_sequence'])await page.locator(`[id="targets.${i}.${key}"]`).fill(row[key]);if(mode==='pe'){for(const key of ['prime_edited_sequence','pegRNA_spacer','pegRNA_extension','nicking_guide','pegRNA_scaffold'])await page.locator(`[id="targets.${i}.${key}"]`).fill(row[key]||'')}else{page.once('dialog',d=>d.accept());await page.getByLabel('Target profile').selectOption('tigr_tas_v1');await page.getByLabel('18-nt TIGR target').fill(row.tigr_target_sequence);await page.getByLabel('Selected window').selectOption(row.tigr_window)}}
 await page.getByRole('button',{name:'4. Configuration'}).click();await page.getByLabel('Library extraction profile').selectOption('custom');await page.getByLabel('R1 analysis 5′ trim').fill('8');await page.getByLabel('R2 analysis 5′ trim').fill('8');await page.getByLabel('Proposed output parent (optional)').selectOption({label:'outputs'});await page.getByLabel('Proposed workspace name').fill(mode+'-browser');
 await page.getByRole('button',{name:'Validate & Review'}).click();await page.getByRole('button',{name:'Run Analysis',exact:true}).waitFor();if(fs.existsSync(path.join(root,'outputs',mode+'-browser')))throw Error('pre-Run workspace exists');
 await page.getByRole('button',{name:'Run Analysis',exact:true}).click();await page.getByRole('button',{name:'Open Results',exact:true}).waitFor({timeout:180000});await page.getByRole('button',{name:'Open Results',exact:true}).click();await page.getByRole('tab',{name:'Overview',exact:true}).waitFor();await page.getByRole('heading',{name:mode==='pe'?'Exact intended PE':'Indel fraction',exact:true}).waitFor();
 const metric=JSON.parse(fs.readFileSync(path.join(root,'outputs',mode+'-browser','metrics/bc001/T1/result.json')));const v=mode==='pe'?metric.target_metrics.total_precise_pe:metric.metrics.indel_fraction;const expected=mode==='pe'?[2,24]:[8,20];if(v.numerator!==expected[0]||v.denominator!==expected[1])throw Error('Existing fixture oracle mismatch');
 results.modes[mode]={review_run_open_results:'PASS',setup_scientific_workspace_absent:true,numerator:v.numerator,denominator:v.denominator};await page.close();
 }finally{server.kill('SIGTERM');await new Promise(resolve=>server.exitCode!==null?resolve():server.once('exit',resolve));}
}
fs.writeFileSync(path.join(root,'summary.json'),JSON.stringify(results,null,2)+'\n');console.log(JSON.stringify(results));
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exitCode=1});
