"""Test-only local server guarding real prebuilt fixtures against execution/mutation."""
from contextlib import asynccontextmanager
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
(setup_root/'draft-fields.json').write_text(json.dumps(setup_fields))
def setup_inventory():
    return {str(p.relative_to(setup_root)):(p.read_bytes(),p.stat().st_mtime_ns) if p.is_file() else 'directory' for p in setup_root.rglob('*')}
setup_before=setup_inventory()
patch=pytest.MonkeyPatch()
calls=forbid_execution(patch)
def forbid_routing(*a,**k):
    calls.append('routing trial');raise AssertionError('Setup attempted routing')
patch.setattr('peanalyzer.routing.route_pair',forbid_routing)
import peanalyzer.gui.workspace as workspace
original_verifier=workspace.verify_workflow_output
verification_calls=[]
def counted_verify(*a,**k):
    verification_calls.append(1);return original_verifier(*a,**k)
patch.setattr(workspace,'verify_workflow_output',counted_verify)
app=create_app([('PE reference study',paths[0]),('Nuclease reference study',paths[1]),('Invalid workspace',root/'missing'),(None,paths[0]),(None,paths[1]),(None,root/'unique')],token='e2e-local-token',setup_files=[setup_options['r1'],setup_options['r2']],setup_output_roots=[setup_root/'outputs'])
def record_audit():
    unchanged=all(fingerprint(p)==original[str(p)] for p in paths) and setup_inventory()==setup_before
    evidence=dict(full_verifier_calls=len(verification_calls),scientific_executor_calls=len(calls),workspace_and_input_bytes_and_mtimes_unchanged=unchanged,
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
