"""Requalify immutable real inputs from raw paired FASTQ, without copying them."""
import argparse
import json
from pathlib import Path
from peanalyzer.workflow import execute_workflow
from peanalyzer.metrics.production import RUNTIME_DIGEST

p=argparse.ArgumentParser()
p.add_argument('dataset',choices=['Azenta','AmpSeq'])
p.add_argument('output',type=Path)
p.add_argument('--resume',action='store_true')
p.add_argument('--forbid-execution',action='store_true')
p.add_argument('--force',action='append',default=[])
a=p.parse_args()
evidence=Path(__file__).resolve().parent
inputs=json.loads((evidence/'input-hashes.json').read_text())
if a.forbid_execution:
    import peanalyzer.workflow as workflow
    def forbidden(*args,**kwargs):raise AssertionError('execution API called on validated resume')
    for name in ('demultiplex','prepare_analysis_fastqs','route_analysis','run_metrics','summarize','stats','generate_report'):
        setattr(workflow,name,forbidden)
result=execute_workflow(mode='run',r1=Path(inputs[a.dataset+'_R1']['path']),r2=Path(inputs[a.dataset+'_R2']['path']),
    samples=evidence/f'{a.dataset}-samples.csv',targets=Path(inputs['targets_ALSW.csv']['path']),
    config=evidence/'config.yaml',output=a.output,crispresso='/workspace/validation/m61/bin/CRISPResso',
    runtime_digest=RUNTIME_DIGEST,title=f'{a.dataset} ALSW read-through qualification',resume=a.resume,force=a.force)
print(json.dumps(result,indent=2,sort_keys=True))
