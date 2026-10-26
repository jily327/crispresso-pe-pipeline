"""Descriptive 100-sample / four-target mocked planning measurement, no backend."""
import json
from pathlib import Path
import sys
import tempfile
import time

REPO=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(REPO/'tests'))
from m7_fixtures import fixture
from peanalyzer.workflow import build_workflow_plan,force_closure,_graph_change

with tempfile.TemporaryDirectory(prefix='m7-planning-') as temporary:
    root=Path(temporary)
    options=fixture(root/'inputs',samples=100,targets=4,reads=0)
    core=root/'CRISPResso';core.write_text('#!/bin/sh\necho "CRISPResso 2.3.4"\n');core.chmod(0o755)
    options['crispresso']=str(core)
    start=time.perf_counter();plan=build_workflow_plan(**options);planning=time.perf_counter()-start
    start=time.perf_counter();_graph_change(plan,plan,['metrics']);closure=force_closure(plan,['metrics']);resume=time.perf_counter()-start
    assert len(plan.nodes)==806 and len(closure)==403
    result=dict(samples=100,targets=4,nodes=806,metrics_force_descendants=403,
                plan_seconds=planning,resume_graph_and_force_seconds=resume,
                backend_executions=0,interpretation='Descriptive only; no performance pass threshold. Full artifact hashing is additional I/O.')
    (REPO/'docs/validation/m7/performance.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps(result))
