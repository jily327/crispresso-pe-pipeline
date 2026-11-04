"""Run retained browser suites serially against the selected installation."""
import json,os,subprocess,time,urllib.request,shutil,sys
from pathlib import Path
root=Path('/workspace/v1-final-remediation');label=sys.argv[1]
suite=Path('/workspace/crispresso-pe-pipeline-v1') if label=='source' else root/'wheel-tests-input'
python=Path('/workspace/v1-desktop-qualification/source-env/bin/python') if label=='source' else root/'wheel-env/bin/python';frontend=suite/'frontend'
node=frontend/'node_modules'
if not node.exists():node.symlink_to('/workspace/crispresso-pe-pipeline-v1/frontend/node_modules',target_is_directory=True)
env=dict(os.environ);env.pop('PYTHONPATH',None)
env.update(MPLCONFIGDIR='/tmp/v1-mpl',XDG_CACHE_HOME='/tmp/v1-cache',PLAYWRIGHT_CHROMIUM_EXECUTABLE='/usr/bin/chromium',M3_CORE_EXECUTABLE='/workspace/m11c1-remediation/native-bin/CRISPResso',M31_RUNTIME_IMAGE='pinellolab/crispresso2@sha256:b7e7971a87769aa584d31d21e199a9abca5f641c4f889c2e807cb6324fc8ce0c',PATH='/workspace/m11c1-remediation/native-bin:/workspace/m11c1-remediation/native-env/bin:'+env['PATH'])
summary_path=root/(label+'-browser-summary.json')
summary=json.loads(summary_path.read_text()) if summary_path.exists() else {}
for name,server,config,port,result in [
 ('viewer','gui_e2e_server.py','playwright.config.ts',8765,'results.json'),
 ('run','m11b_e2e_server.py','playwright.run.config.ts',8766,'run-results.json'),
 ('recovery','m11c_e2e_server.py','playwright.recovery.config.ts',8767,'recovery-results.json'),
 ('practical','practical_e2e_server.py','playwright.practical.config.ts',8768,'practical-results.json')]:
 if len(sys.argv)>2 and name not in sys.argv[2:]:continue
 case_env=dict(env,PRACTICAL_E2E_ROOT=str(root/(label+'-browser-practical-final')),
  M10_E2E_ROOT=os.environ.get('VIEWER_FIXTURES',str(root/(label+'-tests-final/m10'))),M11_SETUP_ROOT=str(root/(label+'-browser-setup-final')),
  M10_E2E_EVIDENCE=str(root/(label+'-browser-immutability.json')),M11B_E2E_ROOT=str(root/(label+'-browser-run-final')),
  M11C_E2E_ROOT=str(root/(label+'-browser-recovery-final')),M11C_E2E_PYTHON=str(python),M11C_E2E_SERVER=str(suite/'tests/m11c_e2e_server.py'))
 with (root/f'{label}-browser-{name}-server.log').open('w') as log:
  proc=subprocess.Popen([str(python),str(suite/'tests'/server)],cwd=suite,env=case_env,stdout=log,stderr=subprocess.STDOUT)
  try:
   deadline=time.monotonic()+600
   while True:
    if proc.poll() is not None:raise RuntimeError(f'{name} server exited {proc.returncode}')
    try:
     request=urllib.request.Request(f'http://127.0.0.1:{port}/api/v1/capabilities',headers={'X-Viewer-Token':'e2e-local-token'})
     with urllib.request.urlopen(request,timeout=1) as response:
      if response.status==200:break
    except OSError:pass
    if time.monotonic()>deadline:raise TimeoutError(name+' server startup')
    time.sleep(.2)
   with (root/f'{label}-browser-{name}.log').open('w') as testlog:
    run=subprocess.run([str(node/'.bin/playwright'),'test','--config',config],cwd=frontend,env=case_env,stdout=testlog,stderr=subprocess.STDOUT)
   dest=root/f'{label}-browser-{name}.json';shutil.copyfile(frontend/'test-results'/result,dest)
   summary[name]=json.loads(dest.read_text())['stats'];(root/(label+'-browser-summary.json')).write_text(json.dumps(summary,indent=2)+'\n')
   print(name,summary[name],flush=True)
   if run.returncode:raise RuntimeError(name+' Playwright failed')
  finally:
   if proc.poll() is None:
    proc.terminate();proc.wait(timeout=60)
   else:proc.wait()
print('All browser suites completed',flush=True)
