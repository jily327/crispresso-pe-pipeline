"""Separate mutable exports from frozen scientific evidence, without broad exclusions."""
from copy import copy
from pathlib import Path
from types import SimpleNamespace
import os
import subprocess
import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from test_m7 import case,complete
from peanalyzer.gui.app import create_app
from peanalyzer.gui.workspace import WorkspaceStore,snapshot
from peanalyzer.gui.summary_workbook import FILENAME,write_summary
from peanalyzer.gui.export_integrity import EXCEL_LOCK
from peanalyzer.gui import desktop


@pytest.fixture
def exported(case):
    options,_=complete(case);root=options['output'];before=snapshot(root)
    store=WorkspaceStore([]);view=store.register_completed('Export',root,finalize=True)
    assert {k:v for k,v in snapshot(root).items() if k!=FILENAME}==before
    return root,store,view


@pytest.mark.parametrize('name',[FILENAME,EXCEL_LOCK])
def test_create_open_modify_delete_independently_preserves_science(exported,name):
    root,store,view=exported;path=root/name
    baseline=store.get(view.workspace_id).view
    original=(root/FILENAME).read_bytes()
    if name==EXCEL_LOCK:path.write_bytes(b'Excel owner')
    with path.open('rb') as opened:
        assert opened.read()
        assert store.get(view.workspace_id).view==baseline
    path.write_bytes(b'user edit')
    assert store.get(view.workspace_id).view==baseline
    assert store.export_status(view.workspace_id)['state']==('CHANGED' if name==FILENAME else 'UNCHANGED')
    path.unlink()
    assert store.get(view.workspace_id).view==baseline
    assert store.export_status(view.workspace_id)['state']==('MISSING' if name==FILENAME else 'UNCHANGED')
    path.write_bytes(original if name==FILENAME else b'new lock')
    assert store.get(view.workspace_id).view==baseline
    assert store.export_status(view.workspace_id)['state']=='UNCHANGED'


def test_creation_after_open_is_not_a_verified_export(case):
    options,_=complete(case);root=options['output'];store=WorkspaceStore([(None,root)])
    view=store.open(store.catalog()[0].registration_id)
    assert store.export_status(view.workspace_id)['state']=='MISSING'
    (root/FILENAME).write_bytes(b'user file')
    assert store.get(view.workspace_id).view==view
    assert store.export_status(view.workspace_id)['state']=='UNVERIFIED'
    assert store.open(store.catalog()[0].registration_id).verified
    assert store.export_status(view.workspace_id)['state']=='UNVERIFIED'


@pytest.mark.parametrize('name,kind',[
    ('unknown.xlsx','file'),('~$other.xlsx','file'),('folder','dir'),
    (FILENAME,'dir'),(EXCEL_LOCK,'dir'),(FILENAME,'symlink'),(EXCEL_LOCK,'symlink'),
    ('workflow/plan.json','file'),('statistics/result.json','file'),
    ('metrics/bc001/T1/result.json','file'),('report/'+FILENAME,'file'),(EXCEL_LOCK,'fifo')])
def test_exclusions_never_hide_unknowns_scientific_changes_or_unsafe_types(exported,name,kind):
    root,store,view=exported;path=root/name
    if path.exists():path.unlink()
    if kind=='dir':path.mkdir()
    elif kind=='symlink':path.symlink_to(root/'workflow_manifest.json')
    elif kind=='fifo':os.mkfifo(path)
    else:path.write_bytes(b'changed')
    with pytest.raises(ValueError):store.get(view.workspace_id)


def test_reopen_restart_and_semantic_changes_do_not_claim_original_integrity(exported):
    root,store,view=exported;path=root/FILENAME;book=load_workbook(path)
    font=copy(book['Summary']['A2'].font);font.bold=True
    book['Summary']['A1'].font=font
    book.save(path);book.close()
    assert store.export_status(view.workspace_id)['state']=='CHANGED'
    reopened=store.open(store.catalog()[0].registration_id)
    assert store.export_status(reopened.workspace_id)['state']=='CHANGED'
    restart=WorkspaceStore([(None,root)]);fresh=restart.open(restart.catalog()[0].registration_id)
    assert restart.export_status(fresh.workspace_id)['state']=='CONTENTS_MATCH'
    assert 'not authenticated' in restart.export_status(fresh.workspace_id)['message']
    book=load_workbook(path);book['Summary']['D2']='999 / 999';book.save(path);book.close()
    another=WorkspaceStore([(None,root)]);last=another.open(another.catalog()[0].registration_id)
    assert another.export_status(last.workspace_id)['state']=='UNVERIFIED'
    assert another.get(last.workspace_id).view.verified


@pytest.mark.parametrize('exc',[OSError('disk full'),ValueError('export conversion failed')])
def test_optional_export_failure_still_publishes_verified_science(case,monkeypatch,exc):
    options,_=complete(case);root=options['output'];before=snapshot(root)
    def fail(*a,**kw):raise exc
    monkeypatch.setattr('peanalyzer.gui.summary_workbook.write_summary',fail)
    store=WorkspaceStore([]);view=store.register_completed('Export',root,finalize=True)
    assert store.get(view.workspace_id).view.verified
    result=store.export_status(view.workspace_id)
    assert result['state']=='MISSING' and 'Scientific analysis completed' in result['warning']
    assert snapshot(root)==before


def test_scientific_mutation_during_optional_failure_is_still_fatal(case,monkeypatch):
    options,_=complete(case);root=options['output']
    def fail(*a,**kw):
        (root/'statistics/result.json').write_bytes(b'corrupt')
        raise OSError('export failed too')
    monkeypatch.setattr('peanalyzer.gui.summary_workbook.write_summary',fail)
    store=WorkspaceStore([])
    with pytest.raises(ValueError):store.register_completed('Export',root,finalize=True)
    assert not store.opened


@pytest.mark.parametrize('code',[0,1,7])
def test_explorer_exit_is_not_desktop_confirmation(monkeypatch,code):
    monkeypatch.setattr(desktop.sys,'platform','win32')
    calls=[]
    def run(argv,**kwargs):
        calls.append((argv,kwargs));return SimpleNamespace(returncode=code)
    monkeypatch.setattr(desktop.subprocess,'run',run)
    result=desktop.reveal_output(Path('C:/analysis'))
    assert result['ok'] and result['state']=='REQUESTED' and not result['display_confirmed']
    assert result['exit_code']==code and calls[0][1]['check'] is False
    assert 'cannot be confirmed' in result['message']


def test_explorer_timeout_only_confirms_process_started(monkeypatch):
    monkeypatch.setattr(desktop.sys,'platform','win32')
    def timeout(*a,**kw):raise subprocess.TimeoutExpired('explorer',5)
    monkeypatch.setattr(desktop.subprocess,'run',timeout)
    result=desktop.reveal_output(Path('C:/analysis'))
    assert result['state']=='REQUESTED' and not result['display_confirmed'] and result['exit_code'] is None


def test_missing_workflow_keeps_incomplete_catalog_label(case):
    options,_=complete(case);root=options['output'];(root/'workflow_manifest.json').unlink()
    app=create_app(token='test',workspace_library_roots=[root])
    client=TestClient(app,base_url='http://127.0.0.1',headers={'X-Viewer-Token':'test'})
    key=client.get('/api/v1/workspaces').json()[0]['registration_id']
    assert client.post('/api/v1/workspaces/open',json={'registration_id':key}).status_code==409
    assert 'Incomplete — use Recovery' in client.get('/api/v1/workspaces').json()[0]['label']


def test_discovered_same_basename_has_parent_suffix(tmp_path):
    from test_desktop_library import markers
    for parent in ['version-one','version-two']:markers(tmp_path/parent/'Run','1.0.0')
    store=WorkspaceStore([], [tmp_path])
    labels=[r.label for r in store.catalog()]
    assert len(set(labels))==2
    assert any('version-one / Run' in label for label in labels)
    assert any('version-two / Run' in label for label in labels)


def test_accepted_input_order_is_preserved_without_altering_plan(case):
    options,_=complete(case);root=options['output'];before=snapshot(root)
    store=WorkspaceStore([]);view=store.register_completed('Ordered',root,finalize=True,sample_order=['bc002','bc001'])
    book=load_workbook(root/FILENAME)
    assert [book['Summary'].cell(i,2).value for i in [2,3]]==['bc002','bc001']
    assert 'Accepted GUI input order' in book['Definitions']['B8'].value
    book.close()
    assert {k:v for k,v in snapshot(root).items() if k!=FILENAME}==before
    fresh=WorkspaceStore([(None,root)]);reopened=fresh.open(fresh.catalog()[0].registration_id)
    assert fresh.export_status(reopened.workspace_id)['state']=='CONTENTS_MATCH'
