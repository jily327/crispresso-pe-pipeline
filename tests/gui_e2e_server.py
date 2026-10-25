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
patch=pytest.MonkeyPatch()
calls=forbid_execution(patch)
app=create_app([('PE reference study',paths[0]),('Nuclease reference study',paths[1]),('Invalid workspace',root/'missing')],token='e2e-local-token')
def record_audit():
    unchanged=all(fingerprint(p)==original[str(p)] for p in paths)
    evidence=dict(scientific_executor_calls=len(calls),workspace_and_input_bytes_and_mtimes_unchanged=unchanged,
        workspaces=[str(p) for p in paths],guarded_functions='See gui_helpers.forbid_execution')
    Path(os.environ.get('M10_E2E_EVIDENCE',str(root/'browser-immutability.json'))).write_text(json.dumps(evidence,indent=2)+'\n')
    assert unchanged and not calls


@asynccontextmanager
async def lifespan(app):
    yield
    record_audit()
    patch.undo()


app.router.lifespan_context=lifespan
uvicorn.run(app,host='127.0.0.1',port=int(os.environ.get('M10_E2E_PORT','8765')),access_log=False)
