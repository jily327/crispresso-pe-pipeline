"""Serial installed-wheel qualification; scientific servers never overlap."""
import json,os,shutil,subprocess,time,urllib.request
from pathlib import Path
root=Path('/workspace/validation/practical-ux')
label=os.environ['QUALIFICATION_LABEL']
suite=Path('/workspace/practical-ux-inputs') if label=='source' else root/'wheel-suite'
python=root/(label+'-env')/'bin/python'
frontend=suite/'frontend'
node=frontend/'node_modules'
if not node.exists():node.symlink_to('/workspace/m11c-recovery/frontend/node_modules',target_is_directory=True)
env=dict(os.environ);env.pop('PYTHONPATH',None)
env.update(MPLCONFIGDIR='/tmp/m11b-mpl',XDG_CACHE_HOME='/tmp/m11b-cache',PLAYWRIGHT_CHROMIUM_EXECUTABLE='/usr/bin/chromium',M3_CORE_EXECUTABLE='/workspace/validation/m11c/bin/CRISPResso',M31_RUNTIME_IMAGE='pinellolab/crispresso2@sha256:b7e7971a87769aa584d31d21e199a9abca5f641c4f889c2e807cb6324fc8ce0c',PATH='/workspace/validation/m11c/bin:'+env['PATH'])
summary={}
for name,server,config,port,result in [
 ('viewer','gui_e2e_server.py','playwright.config.ts',8765,'results.json'),
 ('run','m11b_e2e_server.py','playwright.run.config.ts',8766,'run-results.json'),
 ('recovery','m11c_e2e_server.py','playwright.recovery.config.ts',8767,'recovery-results.json'),
 ('practical','practical_e2e_server.py','playwright.practical.config.ts',8768,'practical-results.json')]:
    case_env=dict(env,PRACTICAL_E2E_ROOT=str(root/(label+'-browser-practical')))
    case_env.update(M10_E2E_ROOT=str(root/(label+'-tests/m10')),M11_SETUP_ROOT=str(root/(label+'-browser-setup')),M10_E2E_EVIDENCE=str(root/(label+'-browser-immutability.json')),M11B_E2E_ROOT=str(root/(label+'-browser-run')),M11C_E2E_ROOT=str(root/(label+'-browser-recovery')),M11C_E2E_PYTHON=str(python),M11C_E2E_SERVER=str(suite/'tests/m11c_e2e_server.py'))
    with (root/f'{label}-browser-{name}-server.txt').open('w') as log:
        proc=subprocess.Popen([str(python),str(suite/'tests'/server)],cwd=suite,env=case_env,stdout=log,stderr=subprocess.STDOUT)
        try:
            deadline=time.monotonic()+600
            while True:
                if proc.poll() is not None:raise RuntimeError(f'{name} server exited {proc.returncode}; inspect server log')
                try:
                    request=urllib.request.Request(f'http://127.0.0.1:{port}/api/v1/capabilities',headers={'X-Viewer-Token':'e2e-local-token'})
                    with urllib.request.urlopen(request,timeout=1) as response:
                        if response.status==200:break
                except OSError:pass
                if time.monotonic()>deadline:raise TimeoutError(f'{name} server startup')
                time.sleep(.2)
            with (root/f'{label}-browser-{name}.txt').open('w') as testlog:
                run=subprocess.run([str(node/'.bin/playwright'),'test','--config',config],cwd=frontend,env=case_env,stdout=testlog,stderr=subprocess.STDOUT)
            dest=root/f'{label}-browser-{name}.json'
            shutil.copyfile(frontend/'test-results'/result,dest)
            summary[name]=json.loads(dest.read_text())['stats']
            (root/(label+'-browser-summary.json')).write_text(json.dumps(summary,indent=2)+'\n')
            print(name,summary[name],flush=True)
            if run.returncode:raise RuntimeError(f'{name} Playwright failed; inspect test log')
        finally:
            if proc.poll() is None:
                proc.terminate()
                try:proc.wait(timeout=60)
                except subprocess.TimeoutExpired:
                    raise RuntimeError(f'{name} server did not unwind; do not start another suite')
            else:proc.wait()
print('All selected-installation browser suites finished',flush=True)
