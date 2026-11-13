"""Independent comparison of known-truth results through real local HTTP and XLSX.

Usage: python compare_layers.py BASELINE CANDIDATE OUTPUT_JSON
Run with the candidate installed; source input files must still be present.
"""
import json
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.request import Request,urlopen
from openpyxl import load_workbook
from peanalyzer.gui.workspace import WorkspaceStore

baseline,candidate,destination=map(Path,sys.argv[1:])
checks=[]
def check(name,actual,expected):
    checks.append(dict(name=name,passed=actual==expected))
    if actual!=expected:raise AssertionError((name,actual,expected))
def science(value):
    if isinstance(value,list):return [science(v) for v in value]
    if isinstance(value,dict):return {k:science(v) for k,v in value.items() if k not in {'population_id','source_result_sha256','source_result','result_sha256'}}
    return value
for relative in sorted(p.relative_to(candidate) for p in (candidate/'metrics').glob('*/*/result.json')):
    old=json.loads((baseline/relative).read_text());new=json.loads((candidate/relative).read_text())
    for key in ('target_metrics','copies','eligibility','qc','product_evidence','derived_metrics'):
        check(str(relative)+':'+key,science(new[key]),science(old[key]))
old=json.loads((baseline/'statistics/result.json').read_text());new=json.loads((candidate/'statistics/result.json').read_text())
for key in ('observations','group_summaries','contrasts'):
    # Source hashes necessarily differ with version/path provenance; the
    # observation itself has no scientific recomputation at these boundaries.
    def clean(value):
        if isinstance(value,list):return [clean(v) for v in value]
        if isinstance(value,dict):return {k:clean(v) for k,v in value.items() if k not in {'source_result_sha256','source_result','result_sha256'}}
        return value
    check('statistics:'+key,science(new[key]),science(old[key]))
store=WorkspaceStore([]);view=store.register_completed('Synthetic parity',candidate,finalize=True)
# Start the real HTTP application on loopback with an ephemeral token held only
# in memory. Never persist server startup output (which contains its token).
with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
import secrets
secret=secrets.token_urlsafe(32)
server_code='''import sys,uvicorn
from peanalyzer.gui.app import create_app
uvicorn.run(create_app([(None,sys.argv[1])],token=sys.argv[3]),host='127.0.0.1',port=int(sys.argv[2]),access_log=False)
'''
process=subprocess.Popen([sys.executable,'-c',server_code,str(candidate),str(port),secret],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
base=f'http://127.0.0.1:{port}'
def api(path,data=None):
    request=Request(base+path,data=json.dumps(data).encode() if data is not None else None,
        headers={'X-Viewer-Token':secret,'Origin':base,'Content-Type':'application/json'})
    with urlopen(request,timeout=30) as response:return json.load(response)
try:
    for attempt in range(200):
        try:registrations=api('/api/v1/workspaces');break
        except OSError:time.sleep(.05)
    else:raise RuntimeError('HTTP server did not start')
    http=api('/api/v1/workspaces/open',{'registration_id':registrations[0]['registration_id']})
    book=load_workbook(candidate/'PEAnalyzer_Summary.xlsx',read_only=True,data_only=True)
    rows={r[1]:r for r in list(book['Summary'].values)[1:]}
    for item in http['observations']:
        if item['copy_name'] is not None or item['metric_name'] not in ('total_precise_pe','target_crispresso_native_pe'):continue
        disk=json.loads((candidate/f"metrics/{item['sample_id']}/{item['target']}/result.json").read_text())['target_metrics'][item['metric_name']]
        check('HTTP counts:'+item['sample_id']+item['metric_name'],[item['numerator'],item['denominator']],[str(disk['numerator']),str(disk['denominator'])])
        check('HTTP fraction:'+item['sample_id']+item['metric_name'],item['fraction'],(disk['numerator']/disk['denominator']))
        row=rows[item['sample_id']];column=2 if item['metric_name']=='target_crispresso_native_pe' else 4
        # XLSX stores decimal text; compare at the export's documented float precision.
        if abs(row[column]-(disk['numerator']/disk['denominator']))>1e-14:raise AssertionError('Excel fraction mismatch')
        checks.append(dict(name='Excel fraction:'+item['sample_id']+item['metric_name'],passed=True))
        check('Excel counts:'+item['sample_id']+item['metric_name'],row[column+1],f"{disk['numerator']} / {disk['denominator']}")
    book.close()
    destination.write_text(json.dumps(dict(passed=len(checks),failed=0,checks=checks),indent=2)+'\n')
finally:
    process.terminate();process.wait(timeout=20)
