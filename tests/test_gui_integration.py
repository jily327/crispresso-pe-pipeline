"""Real completed workflows cross verifier → projection → API; E2E reuses these roots."""
import json
import os
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from gui_helpers import fingerprint, forbid_execution
from peanalyzer import workflow
from peanalyzer.gui.app import create_app

pytestmark=[pytest.mark.crispresso_integration,
    pytest.mark.skipif(os.environ.get('M10_INTEGRATION')!='1',reason='set M10_INTEGRATION=1 with qualified Core 2.3.4')]


@pytest.mark.parametrize('mode',['precise_edit','indel_nuclease'])
def test_real_verified_workspace_viewer(mode,tmp_path,monkeypatch):
    from m7_fixtures import fixture as pe_fixture
    from m8_fixtures import fixture as nuclease_fixture
    root=Path(os.environ.get('M10_RESULTS_DIR',tmp_path/'m10'))/mode
    fixture=pe_fixture if mode=='precise_edit' else nuclease_fixture
    populations=[[('WT',16),('net_zero',4)],[('WT',12),('deletion',8)],[('WT',4),('deletion',16)],[('WT',2),('deletion',18)]]
    options=fixture(root/'inputs') if mode=='precise_edit' else fixture(root/'inputs',populations)
    options.update(output=root/'workflow',crispresso=os.environ.get('M3_CORE_EXECUTABLE','CRISPResso'),contrasts=root/'inputs/contrasts.yaml')
    workflow.execute_workflow(**options)
    before=fingerprint(options['output']);calls=forbid_execution(monkeypatch)
    import peanalyzer.gui.workspace as viewer_workspace
    full_verify=viewer_workspace.verify_workflow_output;verification_calls=[]
    def counted(*a,**k):
        verification_calls.append(1);return full_verify(*a,**k)
    monkeypatch.setattr(viewer_workspace,'verify_workflow_output',counted)
    c=TestClient(create_app([(mode,options['output'])],token='test'),base_url='http://127.0.0.1',headers={'X-Viewer-Token':'test'})
    reg=c.get('/api/v1/workspaces').json()[0]['registration_id']
    response=c.post('/api/v1/workspaces/open',json={'registration_id':reg})
    assert response.status_code==200,response.text
    view=response.json();base='/api/v1/workspaces/'+view['workspace_id']
    assert view['mode']==mode and view['native_html']=='Not produced'
    stats=json.loads((options['output']/'statistics/result.json').read_text())
    for actual,stored in zip(view['groups'],stats['group_summaries']):
        assert actual['mean']==stored['mean_biological_sample_fraction']
    assert view['contrasts'][0]['p']==view['contrasts'][0]['q']==stats['contrasts'][0]['p_value']
    if mode=='indel_nuclease':
        assert len(view['nuclease'][0]['expected_configuration'])==58
        assert any(b['net_size']=='0' for b in view['nuclease'][0]['bins'])
        page=c.get(base+'/alleles/bc001?limit=1').json()
        rest=c.get(base+'/alleles/bc001?offset=1&limit=100').json()
        assert len(page['items']+rest['items'])==int(page['total'])
    for suffix in ('json','svg','html'):
        source=next(s for s in view['artifacts'] if s['kind']==suffix)
        r=c.get(base+'/artifacts/'+source['artifact_id']);assert r.status_code==200
        assert r.content==(options['output']/source['name']).read_bytes()
        assert r.headers['content-disposition'].startswith('attachment;')
    assert c.get(base).status_code==200 and fingerprint(options['output'])==before and calls==[]
    assert len(verification_calls)==1
    (root/'projection.json').write_text(json.dumps(view,indent=2)+'\n')
    (root/'viewer-evidence.json').write_text(json.dumps(dict(mode=mode,scientific_executor_calls=0,
        unchanged_workspace_and_input_files=len(before),byte_and_mtime_identity=True,verifier='verify_workflow_output',workspace=str(options['output'])),indent=2)+'\n')
