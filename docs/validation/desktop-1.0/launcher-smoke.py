import json,os,shutil,subprocess
from pathlib import Path
root=Path('/workspace/v1-desktop-qualification/launcher-smoke');root.mkdir()
repo=Path('/workspace/crispresso-pe-pipeline-v1');binpath=root/'bin';binpath.mkdir()
(binpath/'docker').write_text('#!/bin/sh\nexit "${DOCKER_TEST_EXIT:-0}"\n');(binpath/'docker').chmod(0o755)
results=[]
for version in ['0.9.0','1.0.0']:
 release=root/('Release '+version);(release/'venv/bin').mkdir(parents=True);(release/'bin').mkdir()
 python=release/'venv/bin/python';python.write_text('''#!/usr/bin/env python3
import json,os,sys
from pathlib import Path
if sys.argv[1]=='-c':print(Path(__file__).parents[2].name.split()[-1])
else:Path(os.environ['LAUNCHER_CAPTURE']).write_text(json.dumps(sys.argv[1:]))
''');python.chmod(0o755)
 (release/'bin/CRISPResso').write_text('#!/bin/sh\nexit 0\n');(release/'bin/CRISPResso').chmod(0o755)
 shutil.copy2(repo/'desktop/run-oneclick.sh',release/'run-oneclick.sh')
 link=root/'peanalyzer-current';link.unlink(missing_ok=True);link.symlink_to(release,target_is_directory=True)
 capture=root/('arguments-'+version+'.json')
 env=dict(os.environ,PATH=str(binpath)+':'+os.environ['PATH'],PEANALYZER_LIBRARY_ROOT=str(root/'Library with spaces'),LAUNCHER_CAPTURE=str(capture))
 run=subprocess.run(['bash',str(link/'run-oneclick.sh'),'--port','8769'],env=env,capture_output=True,text=True,check=True)
 args=json.loads(capture.read_text());assert args[:2]==['-m','peanalyzer.gui'];assert args[-2:]==['--port','8769']
 assert args[args.index('--setup-output-root')+1]==str(root/'Library with spaces'/('v'+version))
 assert args[args.index('--workspace-library-root')+1]==str(root/'Library with spaces')
 assert 'Starting PEAnalyzer '+version in run.stdout
 results.append({'installed_version':version,'stable_entry':str(link),'argv':args,'exit':run.returncode})
 env['DOCKER_TEST_EXIT']='1';failed=subprocess.run(['bash',str(link/'run-oneclick.sh')],env=env,capture_output=True)
 assert failed.returncode!=0
subprocess.run(['bash','-n',str(repo/'desktop/run-oneclick.sh')],check=True)
Path('/workspace/v1-desktop-qualification/launcher-smoke.json').write_text(json.dumps({'mocked_runtime':True,'real_Windows_tested':False,'cases':results,'docker_failure_stops_startup':True,'shell_syntax_valid':True},indent=2)+'\n')
print('Stable entry update, spaces, version-derived roots and Docker failure: PASS')
