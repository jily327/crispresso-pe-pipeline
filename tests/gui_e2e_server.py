"""Test-only local server guarding real prebuilt fixtures against execution/mutation."""
from contextlib import asynccontextmanager
from contextvars import ContextVar
import json
import os
from pathlib import Path
import pytest
import uvicorn
from gui_helpers import fingerprint, forbid_execution
from peanalyzer.gui.app import create_app

root=Path(os.environ['M10_E2E_ROOT'])
paths=[root/mode/'workflow' for mode in ('precise_edit','indel_nuclease')]
original={str(p):fingerprint(p) for p in paths}
# Test fixture generation precedes setup's no-execution guard.
import csv
from m7_fixtures import fixture
from peanalyzer.gui.setup_models import PETargetDraft
setup_root=Path(os.environ['M11_SETUP_ROOT'])
setup_options=fixture(setup_root/'inputs',samples=2,copies=2)
(setup_root/'outputs').mkdir(parents=True,exist_ok=True)
setup_fields=dict(samples=list(csv.DictReader(setup_options['samples'].open())),
    targets=[{k:v for k,v in row.items() if k in PETargetDraft.model_fields} for row in csv.DictReader(setup_options['targets'].open())])
from peanalyzer.remediation import indel_designs
setup_fields['ambiguous_deletion']=[{k:'' if v is None else v for k,v in t.model_dump().items() if k in PETargetDraft.model_fields}
    for t in next(ts for d,ts in indel_designs() if d['id']=='deletion_1_seed11')]
import gzip
empty_files=[setup_root/f'empty_R{mate}.fastq.gz' for mate in (1,2)]
for path in empty_files:path.write_bytes(gzip.compress(b'',mtime=0))
(setup_root/'draft-fields.json').write_text(json.dumps(setup_fields))
def setup_inventory():
    return {str(p.relative_to(setup_root)):(p.read_bytes(),p.stat().st_mtime_ns) if p.is_file() else 'directory' for p in setup_root.rglob('*')}
setup_before=setup_inventory()
patch=pytest.MonkeyPatch()
calls=forbid_execution(patch)
# Setup must never classify a read. Opening a workspace must independently replay
# its existing routing ledger and state-observability witnesses within verification.
import peanalyzer.routing as routing
in_verifier=ContextVar('in_verified_open',default=False)
original_route=routing.route_pair
routing_replays=[]
def guard_routing(*args,**kwargs):
    if not in_verifier.get():
        calls.append('routing outside existing-workspace verifier')
        raise AssertionError('Setup attempted routing')
    routing_replays.append(1)
    return original_route(*args,**kwargs)
patch.setattr(routing,'route_pair',guard_routing)
import peanalyzer.gui.workspace as workspace
original_verifier=workspace.verify_workflow_output
verification_calls=[]
def counted_verify(*args,**kwargs):
    verification_calls.append(1)
    token=in_verifier.set(True)
    try:
        return original_verifier(*args,**kwargs)
    finally:
        in_verifier.reset(token)
patch.setattr(workspace,'verify_workflow_output',counted_verify)
app=create_app([('PE reference study',paths[0]),('Nuclease reference study',paths[1]),('Invalid workspace',root/'missing'),(None,paths[0]),(None,paths[1]),(None,root/'unique')],token='e2e-local-token',setup_files=[setup_options['r1'],setup_options['r2'],*empty_files],setup_output_roots=[setup_root/'outputs'])
def record_audit():
    unchanged=all(fingerprint(p)==original[str(p)] for p in paths) and setup_inventory()==setup_before
    evidence=dict(full_verifier_calls=len(verification_calls),scientific_executor_calls=len(calls),read_only_routing_replay_calls=len(routing_replays),
        workspace_and_input_bytes_and_mtimes_unchanged=unchanged,
        setup_inputs_and_proposed_output_unchanged=setup_inventory()==setup_before,workspaces=[str(p) for p in paths],guarded_functions='See gui_helpers.forbid_execution')
    Path(os.environ.get('M10_E2E_EVIDENCE',str(root/'browser-immutability.json'))).write_text(json.dumps(evidence,indent=2)+'\n')
    assert unchanged and not calls


@asynccontextmanager
async def lifespan(app):
    yield
    record_audit()
    patch.undo()


app.router.lifespan_context=lifespan
uvicorn.run(app,host='127.0.0.1',port=int(os.environ.get('M10_E2E_PORT','8765')),access_log=False)
