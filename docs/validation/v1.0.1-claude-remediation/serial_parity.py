"""Genuine scientific parity using one invocation container at a time.

Run with the candidate wheel's Python, --scratch NEW_DIRECTORY. This supplements
(not substitutes a claimed pass for) the three-container isolation regression on
small VFS Docker storage. Both science versions use the shipped guarded wrapper;
existing containers are observed read-only and are never started/stopped/deleted.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import shlex
import sys
import tarfile

parser=argparse.ArgumentParser()
parser.add_argument('--scratch',type=Path,required=True)
args=parser.parse_args()
repo=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(repo/'tests'))
from peanalyzer import workflow as w
from peanalyzer.docker_runtime import Docker
from peanalyzer.gui.app import create_app
from peanalyzer.gui.workspace import WorkspaceStore
from fastapi.testclient import TestClient
from docker_runtime_helpers import wrapper

root=args.scratch;root.mkdir(parents=True,exist_ok=False)
# Select previous scientific modules only in the workflow interpreter. The
# shipped runtime entry must import the installed candidate runtime package.
relay=root/'guarded-runtime'
relay.write_text('#!/bin/sh\nexec env -u PYTHONPATH '+shlex.quote(wrapper())+' \"$@\"\n')
relay.chmod(0o755)
previous='59e6755aa2cc1dbe67b6decd88865d9616a3c7e4'
archive=subprocess.check_output(['git','-C',str(repo),'archive',previous,'src'])
with tarfile.open(fileobj=io.BytesIO(archive)) as tar:tar.extractall(root/'previous',filter='data')
api=Docker();_,containers=api.request('GET','/containers/json?all=1')
existing={v['Id']:api.inspect(v['Id'])['State'] for v in containers}
results={}
def fingerprint(path):
 return {str(p.relative_to(path)):(hashlib.sha256(p.read_bytes()).hexdigest(),p.stat().st_mtime_ns) for p in path.rglob('*') if p.is_file()}
def science(value):
 if isinstance(value,list):return [science(v) for v in value]
 if isinstance(value,dict):return {k:science(v) for k,v in value.items() if k not in {'population_id','source_result_sha256','source_result','result_sha256'}}
 return value
for mode in ('precise_edit','indel_nuclease'):
 if mode=='precise_edit':from m7_fixtures import fixture
 else:from m8_fixtures import fixture
 base=root/mode;base.mkdir()
 options=fixture(base/'inputs');options['contrasts']=base/'inputs/contrasts.yaml'
 options['crispresso']=str(relay)
 baseline=base/'baseline';candidate=base/'candidate'
 plan=base/'baseline-options.json';plan.write_text(json.dumps({**options,'output':baseline},default=str))
 with (base/'baseline.log').open('w') as log:
  subprocess.run([sys.executable,'-c','import json,sys;from peanalyzer.workflow import execute_workflow;execute_workflow(**json.load(open(sys.argv[1])))',str(plan)],
   cwd=base,env={**os.environ,'PYTHONPATH':str(root/'previous/src')},check=True,stdout=log,stderr=subprocess.STDOUT)
 historical=fingerprint(baseline)
 w.execute_workflow(**{**options,'output':candidate})
 assert w.verify_workflow_output(candidate).status=='COMPLETED'
 fields=('target_metrics','copies','eligibility','qc','product_evidence','derived_metrics') if mode=='precise_edit' else ('metrics','class_counts','aligned_reads','unaligned_reads','fraction_of_indel_reads_by_net_size','alleles')
 count=0;primary={}
 for path in sorted((candidate/'metrics').glob('*/*/result.json')):
  a=json.loads((baseline/path.relative_to(candidate)).read_text());b=json.loads(path.read_text())
  for field in fields:assert science(a[field])==science(b[field]),field;count+=1
  metric=b['target_metrics']['total_precise_pe'] if mode=='precise_edit' else b['metrics']['indel_fraction']
  primary[b['sample_id']]=(metric['numerator'],metric['denominator'])
 expected=[(4,24),(8,24),(16,24),(20,24)] if mode=='precise_edit' else [(2,20),(4,20),(14,20),(16,20)]
 assert list(primary.values())==expected
 a=json.loads((baseline/'statistics/result.json').read_text());b=json.loads((candidate/'statistics/result.json').read_text())
 for field in ('observations','group_summaries','contrasts'):
  assert science(a[field])==science(b[field]);count+=1
 assert w.verify_workflow_output(baseline).status=='COMPLETED'
 if mode=='precise_edit':WorkspaceStore([]).register_completed('Synthetic parity',candidate,finalize=True)
 app=create_app([(None,baseline),(None,candidate)],token='test')
 with TestClient(app,base_url='http://127.0.0.1',headers={'X-Viewer-Token':'test'}) as client:
  for entry in client.get('/api/v1/workspaces').json():
   response=client.post('/api/v1/workspaces/open',json={'registration_id':entry['registration_id']})
   assert response.status_code==200,response.text
   for observation in response.json()['observations']:
    if observation['copy_name'] is None and observation['metric_name']==('total_precise_pe' if mode=='precise_edit' else 'indel_fraction'):
     assert (int(observation['numerator']),int(observation['denominator']))==primary[observation['sample_id']];count+=1
 assert fingerprint(baseline)==historical
 if mode=='precise_edit':
  from openpyxl import load_workbook
  book=load_workbook(candidate/'PEAnalyzer_Summary.xlsx',read_only=True,data_only=True)
  for row in list(book['Summary'].values)[1:]:
   numerator,denominator=primary[row[1]]
   assert row[5]==f'{numerator} / {denominator}' and abs(row[4]-numerator/denominator)<1e-14;count+=1
  book.close()
 assert all(api.inspect(cid)['State']==state for cid,state in existing.items())
 results[mode]=dict(passed_checks=count,primary=primary,previous_candidate=previous,
  historical_bytes_and_mtimes_unchanged=True,existing_containers_unchanged=len(existing),
  observed_image_id=api.image(),baseline_runtime='same genuine guarded wrapper; previous scientific source')
 (root/'results.json').write_text(json.dumps(results,indent=2)+'\n')
