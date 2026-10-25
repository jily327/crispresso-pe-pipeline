"""Local boundary, projection integrity, immutable access and failure regression."""
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from test_m7 import case, complete
from gui_helpers import fingerprint, forbid_execution
from peanalyzer.gui.app import create_app
from peanalyzer.gui.workspace import WorkspaceStore, snapshot
from peanalyzer.gui.projection import strict_result, percentage
from peanalyzer.workflow_storage import WorkflowError, artifact


@pytest.fixture
def ready(case):
    options,_=complete(case)
    return options['output']


def client(root):
    return TestClient(create_app([('Test analysis',root)],token='test-token'),base_url='http://127.0.0.1',headers={'X-Viewer-Token':'test-token'})


def open_view(c):
    registration=c.get('/api/v1/workspaces').json()[0]['registration_id']
    return c.post('/api/v1/workspaces/open',json={'registration_id':registration})


def test_local_access_and_capabilities(tmp_path):
    c=client(tmp_path/'missing')
    cap=c.get('/api/v1/capabilities').json()
    assert cap['read_only'] and not cap['scientific_execution'] and not cap['native_html_viewing']
    assert c.get('/api/v1/capabilities',headers={'X-Viewer-Token':''}).status_code==401
    assert c.get('/api/v1/capabilities',headers={'Host':'attacker.example'}).status_code==403
    assert c.get('/api/v1/capabilities',headers={'Origin':'https://attacker.example'}).status_code==403
    assert c.post('/api/v1/workspaces/open',json={'path':'/etc/passwd'}).status_code==422
    assert c.post('/api/v1/workspaces/open',json={'registration_id':'../../etc/passwd'}).status_code==409
    assert open_view(c).json()['error']['code']=='WORKSPACE_NOT_FOUND'
    for path in ('execute','resume','force','cancel','upload'):
        assert c.post('/api/v1/'+path).status_code in (404,405)


def test_verified_pe_zero_execution_immutable_and_stable_paging(ready,monkeypatch):
    before=fingerprint(ready);calls=forbid_execution(monkeypatch);c=client(ready)
    response=open_view(c);assert response.status_code==200,response.text
    view=response.json();base='/api/v1/workspaces/'+view['workspace_id']
    assert view['mode']=='precise_edit'
    assert c.get(base).json()==view
    full=c.get(base+'/observations?limit=200').json()
    paged=c.get(base+'/observations?limit=1').json()['items']+c.get(base+'/observations?offset=1&limit=200').json()['items']
    assert paged==full['items'] and full['items']==view['observations']
    source=next(s for s in view['artifacts'] if s['name']=='statistics/result.json')
    downloaded=c.get(base+'/artifacts/'+source['artifact_id'])
    assert downloaded.content==(ready/source['name']).read_bytes()
    assert downloaded.headers['x-artifact-sha256']==source['sha256']
    assert c.get(base+'/artifacts/not-inventoried').status_code==409
    assert c.get(base+'/observations?limit=201').status_code==422
    assert not calls and fingerprint(ready)==before
    assert not list(ready.glob('*lock*'))


@pytest.mark.parametrize('relative',['metrics/bc001/T1/result.json','statistics/result.json','report/source/result.json','report/report_manifest.json','workflow_manifest.json'])
def test_changed_workspace_invalidates_open_view_and_artifacts(ready,relative):
    c=client(ready);view=open_view(c).json();base='/api/v1/workspaces/'+view['workspace_id']
    p=ready/relative;p.write_bytes(p.read_bytes()+b' ')
    assert c.get(base).json()['error']['code']=='WORKSPACE_CHANGED'
    assert c.get(base+'/artifacts/'+view['artifacts'][0]['artifact_id']).json()['error']['code']=='WORKSPACE_NOT_OPEN'


@pytest.mark.parametrize('attack',['missing_completion','unknown_contract','unknown_status','svg','missing_metric','missing_input','modified_input'])
def test_corrupt_incomplete_and_unsupported_workspaces_fail_closed(ready,attack):
    if attack=='missing_completion':(ready/'workflow_manifest.json').unlink()
    elif attack in ('unknown_contract','unknown_status'):
        p=ready/'metrics/bc001/T1/result.json';d=json.loads(p.read_text())
        if attack=='unknown_contract':d['metric_contract_version']='future-v99'
        else:d['target_metrics']['total_precise_pe']['status']='UNKNOWN'
        p.write_text(json.dumps(d))
    elif attack=='svg':
        p=next((ready/'report/figures').glob('*.svg'));p.write_text('<invalid>')
    elif attack=='missing_metric':(ready/'metrics/bc001/T1/result.json').unlink()
    else:
        d=json.loads((ready/'workflow/plan.json').read_text());p=Path(d['inputs']['r1']['source_path'])
        if attack=='missing_input':p.unlink()
        else:p.write_bytes(p.read_bytes()+b'x')
    response=open_view(client(ready));assert response.status_code==409
    assert set(response.json())=={'error'}


def test_actual_stale_verifier_error_is_preserved(ready):
    marker=ready/'workflow_manifest.json';d=json.loads(marker.read_text())
    ref=d['stage_inventory']['raw_inputs'];p=ready/ref['path'];stage=json.loads(p.read_text());stage['stage_signature_sha256']='0'*64
    p.write_text(json.dumps(stage));d['stage_inventory']['raw_inputs']=artifact(ready,p).model_dump();marker.write_text(json.dumps(d))
    response=open_view(client(ready));assert response.status_code==409
    assert response.json()['error']['code']=='STALE_STAGE_IDENTITY'
    assert response.json()['error']['stage_id']=='raw_inputs'


@pytest.mark.parametrize('attack',['registration','child','traversal','fifo'])
def test_symlinks_traversal_and_special_files_rejected(tmp_path,attack):
    root=tmp_path/'root';root.mkdir()
    if attack=='registration':
        link=tmp_path/'link';link.symlink_to(root,target_is_directory=True)
        with pytest.raises(WorkflowError):WorkspaceStore([('unsafe',link)])
    elif attack=='traversal':
        with pytest.raises(WorkflowError):WorkspaceStore([('unsafe',root/'../root')])
    else:
        if attack=='child':(root/'escape').symlink_to('/etc/passwd')
        else:
            import os
            os.mkfifo(root/'pipe')
        with pytest.raises(WorkflowError):snapshot(root)


def test_change_during_projection_rejected(ready,monkeypatch):
    import peanalyzer.gui.workspace as workspace
    original=workspace.project
    def changed(*a,**k):
        result=original(*a,**k)
        (ready/'added-after-verification.txt').write_text('changed')
        return result
    monkeypatch.setattr(workspace,'project',changed)
    assert open_view(client(ready)).json()['error']['code']=='WORKSPACE_CHANGED'


@pytest.mark.parametrize('field,value',[('discard_indel_reads',True),('min_bp_quality_or_N',30),('min_bp_quality_or_N','0')])
def test_final_nuclease_qualification_is_owned_by_existing_model(field,value):
    path=Path(__file__).parents[1]/'docs/validation/m81/allele-probe/result.json'
    raw=json.loads(path.read_text());raw['provenance']['execution']['resolved_backend_arguments'][field]=value
    with pytest.raises(ValueError,match='UNQUALIFIED_NUCLEASE_CONFIGURATION'):strict_result(raw,'metric')


@pytest.mark.parametrize('version',[True,2,'1'])
def test_unsupported_schema_not_projected(version):
    with pytest.raises(WorkflowError,match='UNSUPPORTED_CONTRACT'):
        strict_result({'schema_version':version,'metric_contract_version':'m4-v1'},'metric')


def test_percentage_formats_stored_fraction_only():
    assert percentage(None) is None and percentage(0.0)=='0%' and percentage(0.125)=='12.5%'


def test_integer_transport_is_lossless_beyond_javascript_safe_range():
    from types import SimpleNamespace
    from peanalyzer.gui.projection import ratio
    from peanalyzer.gui.models import Value
    count=2**80+1
    value=Value(**ratio(SimpleNamespace(numerator=count,denominator=count,fraction=1.0)))
    decoded=json.loads(value.model_dump_json())
    assert decoded['numerator']==decoded['denominator']==str(count)
    assert decoded['fraction']==1.0


def test_pre_remediation_nuclease_result_is_not_accepted_as_current():
    raw=json.loads((Path(__file__).parents[1]/'docs/validation/m8/allele-probe/result.json').read_text())
    with pytest.raises(ValueError,match='nuclease provenance mismatch'):strict_result(raw,'metric')


def test_generated_frontend_contract_matches_python_models():
    import importlib.util
    root=Path(__file__).parents[1]
    spec=importlib.util.spec_from_file_location('viewer_types',root/'scripts/generate_viewer_types.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    assert (root/'frontend/src/models/api.ts').read_text()==module.generate()
