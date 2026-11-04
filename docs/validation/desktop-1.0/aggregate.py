"""Fail-closed collection of completed release gates; no scientific execution."""
import ast,hashlib,json,subprocess,xml.etree.ElementTree as ET
from pathlib import Path
root=Path('/workspace/v1-desktop-qualification');repo=Path('/workspace/crispresso-pe-pipeline-v1')
base='432b7cca6436947d626e2699c2ee53ea3fc93f24'
candidate='ec05776a3c902ccc0460a888e9052b8b4555b786'
records={}
for label in ['source','wheel']:
 suite=ET.parse(root/(label+'-tests-final/tests.xml')).find('testsuite')
 assert int(suite.attrib['tests'])==1999 and all(suite.attrib[k]=='0' for k in ['failures','errors','skipped'])
 cases=suite.findall('testcase');assert len(cases)==1999
 records[label+'_python']={**suite.attrib,'complete':True}
 browser=json.loads((root/(label+'-browser-summary.json')).read_text())
 assert set(browser)=={'viewer','run','recovery','practical'}
 for value in browser.values():assert value['unexpected']==value['skipped']==value['flaky']==0
 assert browser['viewer']['expected']==20 and browser['run']['expected']==6 and browser['recovery']['expected']==8 and browser['practical']['expected']==3
 records[label+'_browser']={'suites':browser,'total':sum(v['expected'] for v in browser.values())}
frontend=(root/'frontend-tests-final.log').read_text();assert '59 passed (59)' in frontend
records['frontend']=59
ids=[line for line in (root/'integration-collection.log').read_text().splitlines() if line.startswith('tests/') and '::' in line];assert len(ids)==90
records['integration_each_installation']=90
package=json.loads((root/'packaging.json').read_text());assert package['candidate']==candidate and package['all_package_members_identical']
assert package['member_count']==92
records['packaging']=package
records['wheel_import']=json.loads((root/'wheel-import.json').read_text());assert 'site-packages' in records['wheel_import']['import_path']
assert records['wheel_import']['version']=='1.0.0'
assert records['wheel_import']['installed_package_members_verified']==92
frozen=json.loads((repo/'docs/validation/desktop-1.0/frozen-core.json').read_text())
for name,value in frozen['sha256'].items():
 assert hashlib.sha256((repo/name).read_bytes()).hexdigest()==value
 assert hashlib.sha256(subprocess.check_output(['git','show',base+':'+name],cwd=repo)).hexdigest()==value
records['frozen_files']=frozen['unchanged_files']
history=json.loads((root/'historical-compatibility.json').read_text())
assert {v['version'] for v in history}=={'0.8.0','0.9.0','1.0.0'}
assert all(v['opened'] and v['bytes_unchanged'] and v['workbook_presence_unchanged'] for v in history)
records['historical_workspaces']=history
alsw=json.loads((root/'alsw-excel-parity.json').read_text())
assert sum(len(v['rows']) for v in alsw)==19 and all(v['all_rows_match_authoritative_target_counts'] and v['historical_files_unchanged'] for v in alsw)
records['alsw_verified_samples']=19
records['base']=base;records['tested_candidate']=candidate
records['source_python_candidate']='d5bae60701b2327cc88d0d48e53d49a83d5cf8ce'
records['source_python_preservation']=json.loads((root/'source-python-byte-preservation.json').read_text())
assert records['source_python_preservation']['unchanged_python_files']==154
for name,checksum in records['source_python_preservation']['hashes'].items():
 assert hashlib.sha256((repo/name).read_bytes()).hexdigest()==checksum
records['final_source_packaging_checks']=6
records['production_files']=subprocess.check_output(['git','diff','--name-status',base,candidate,'--','src','frontend/src','frontend/index.html','frontend/package.json','frontend/package-lock.json','desktop','pyproject.toml'],cwd=repo,text=True).splitlines()
records['production_files']=[line for line in records['production_files'] if 'frontend/src/tests/' not in line]
records['real_windows_tested']=False
records['limitations']=['Actual Windows/WSL Explorer and BAT smoke testing is unavailable in this Linux environment.',
 'The Excel finalization boundary is the GUI; the scientific CLI stages are unchanged.',
 'Discovery is bounded and read-only; verification may require original inputs and absolute lineage paths.',
 'The preserved 0.7.1 ALSW workspace is detected but rejected by the current viewer as stale; its original 0.7.1 verifier was used solely for the isolated export parity study.',
 'Explorer convenience and explicit theme persistence depend on local desktop/browser support.']
records['status']='READY FOR INDEPENDENT FOCUSED AUDIT'
(root/'qualification.json').write_text(json.dumps(records,indent=2)+'\n')
print('All required gates completed',flush=True)
