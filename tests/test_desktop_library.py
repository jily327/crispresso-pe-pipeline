"""Discovery is bounded catalogue metadata, never a filesystem execution API."""
import json
import pytest
from fastapi.testclient import TestClient
from peanalyzer.gui.app import create_app
from peanalyzer.gui.workspace import WorkspaceStore
from peanalyzer.gui.library import scan
from test_m7 import case, complete
from gui_helpers import fingerprint


def markers(root, version='0.8.0', status='COMPLETED'):
    (root/'workflow').mkdir(parents=True)
    (root/'workflow/plan.json').write_text('{}')
    (root/'workflow_manifest.json').write_text(json.dumps({'status':status,'workflow_contract_version':'m7-v1','software_identity':{'pipeline_version':version}}))


def test_empty_and_duplicate_roots(tmp_path):
    assert scan([tmp_path]) == ([],False)
    markers(tmp_path/'run')
    store=WorkspaceStore([], [tmp_path,tmp_path,tmp_path/'run'])
    assert len(store.catalog())==1
    assert '0.8.0' in store.catalog()[0].label
    identity=store.catalog()[0].registration_id
    assert store.refresh_library()['registrations'][0].registration_id==identity


@pytest.mark.parametrize('version',['0.8.0','0.9.0','1.0.0'])
def test_catalogue_version_is_provenance_not_name(tmp_path,version):
    root=tmp_path/'Run_v9.9.9';markers(root,version)
    assert f'PEAnalyzer {version}' in scan([tmp_path])[0][0][1]
    # Marker names and a version string alone cannot authorize Open.
    store=WorkspaceStore([], [tmp_path])
    with pytest.raises(ValueError):store.open(store.catalog()[0].registration_id)


def test_many_refresh_and_disappearance(tmp_path):
    for i in range(20):markers(tmp_path/f'run{i}')
    store=WorkspaceStore([], [tmp_path]);assert len(store.catalog())==20
    markers(tmp_path/'later','0.9.0')
    assert len(store.refresh_library()['registrations'])==21
    (tmp_path/'later/workflow/plan.json').unlink()
    assert len(store.refresh_library()['registrations'])==20


@pytest.mark.parametrize('kind',['directory','manifest','plan','workflow','fifo'])
def test_symlinks_and_special_markers_not_followed(tmp_path,kind):
    real=tmp_path/'real';markers(real)
    library=tmp_path/'library';library.mkdir()
    link=library/'alias'
    if kind=='directory':link.symlink_to(real,target_is_directory=True)
    else:
        markers(link)
        p={'manifest':link/'workflow_manifest.json','plan':link/'workflow/plan.json','workflow':link/'workflow','fifo':link/'workflow_manifest.json'}[kind]
        if p.is_dir():
            (p/'plan.json').unlink();p.rmdir();p.symlink_to(real/'workflow',target_is_directory=True)
        else:
            p.unlink()
            if kind=='fifo':
                import os
                os.mkfifo(p)
            else:p.symlink_to(real/('workflow_manifest.json' if kind=='manifest' else 'workflow/plan.json'))
    assert scan([library])[0]==[]


def test_incomplete_malformed_and_incompatible_are_visible(tmp_path):
    for name in ['incomplete','malformed','future']:markers(tmp_path/name)
    (tmp_path/'incomplete/workflow_manifest.json').unlink()
    (tmp_path/'malformed/workflow_manifest.json').write_text('{broken')
    markers_data=tmp_path/'future/workflow_manifest.json'
    markers_data.write_text('{"status":"COMPLETED","workflow_contract_version":"future"}')
    labels=[label for _,label in scan([tmp_path])[0]]
    assert sum('Incomplete' in label for label in labels)==1
    assert sum('incompatible' in label for label in labels)==2


def test_budgets_and_unsafe_root(tmp_path,monkeypatch):
    from peanalyzer.gui import library
    markers(tmp_path/'a/b/c/deep')
    monkeypatch.setattr(library,'MAX_DEPTH',2)
    assert scan([tmp_path])==([],True)
    for i in range(10):markers(tmp_path/f'r{i}')
    monkeypatch.setattr(library,'MAX_ENTRIES',3)
    rows,limited=scan([tmp_path]);assert len(rows)==3 and limited
    monkeypatch.setattr(library,'MAX_INSPECTED',1)
    assert scan([tmp_path])[1]
    with pytest.raises(ValueError):WorkspaceStore([], [tmp_path/'..'])


def test_real_verified_open_remains_read_only(case):
    options,_=complete(case);root=options['output'];before=fingerprint(root)
    app=create_app(token='test',workspace_library_roots=[root.parent])
    c=TestClient(app,base_url='http://127.0.0.1',headers={'X-Viewer-Token':'test'})
    rows=c.get('/api/v1/workspaces').json();assert len(rows)==1
    assert c.post('/api/v1/workspace-library/refresh',json={'path':'/'}).status_code==422
    assert c.post('/api/v1/workspaces/open',json={'registration_id':rows[0]['registration_id']}).status_code==200
    assert fingerprint(root)==before
    assert not (root/'PEAnalyzer_Summary.xlsx').exists()


def test_discovered_workspaces_protect_new_output_destinations(tmp_path):
    root=tmp_path/'library';root.mkdir();first=root/'first';markers(first)
    app=create_app(token='test',workspace_library_roots=[root],setup_output_roots=[first])
    assert first in app.state.drafts.protected
    # The unchanged setup boundary must reject a new output nested in a discovered analysis.
    from peanalyzer.gui.setup_validation import compile_draft
    from m11b_helpers import application
    inputs,c,content,_,_=application(tmp_path/'inputs-fixture')
    ref=content.output_root
    inputs.state.drafts.references.paths[ref]=first
    inputs.state.drafts.protected=app.state.drafts.protected
    d=c.post('/api/v1/drafts').json()
    c.patch('/api/v1/drafts/'+d['draft_id'],json={'revision':0,'content':content.model_dump()})
    result=c.post('/api/v1/drafts/'+d['draft_id']+'/validate',json={'revision':1}).json()
    assert result['status']=='INVALID'
    assert any('OUTPUT' in issue['code'] for issue in result['issues'])
    client=TestClient(app,base_url='http://127.0.0.1',headers={'X-Viewer-Token':'test'})
    later=root/'later';markers(later)
    assert client.post('/api/v1/workspace-library/refresh',json={}).status_code==200
    assert first in app.state.drafts.protected and later in app.state.drafts.protected
    inputs.state.jobs.close()
