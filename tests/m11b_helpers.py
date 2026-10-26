"""Deterministic lifecycle fixtures shared by API, worker and browser tests."""
import csv
import os
import time
from pathlib import Path
from fastapi.testclient import TestClient
from m7_fixtures import fixture
from peanalyzer.gui.app import create_app
from peanalyzer.gui.execution import RuntimeSettings
from peanalyzer.gui.setup_models import DraftContent, PETargetDraft


def application(root,mode='precise_edit',runtime=None):
    root=Path(root)
    if mode=='precise_edit':options=fixture(root/'inputs',samples=1,copies=2)
    else:
        from m8_fixtures import fixture as nuclease
        options=nuclease(root/'inputs',[[('WT',12),('deletion',4),('net_zero',4)]])
    output=root/'outputs';output.mkdir()
    app=create_app(token='test',setup_files=[options['r1'],options['r2']],setup_output_roots=[output],
        runtime=runtime or RuntimeSettings(crispresso=os.environ.get('M3_CORE_EXECUTABLE','CRISPResso')))
    refs=app.state.drafts.references;ids=list(refs.entries)
    targets=[]
    for row in csv.DictReader(options['targets'].open()):
        if mode=='precise_edit':targets.append({k:v for k,v in row.items() if k in PETargetDraft.model_fields})
        else:targets.append(dict(analysis_mode=mode,target_name=row['target_name'],copy_name=row['copy_name'],
            wt_sequence=row['wt_sequence'],profile=row['nuclease_profile'],tigr_target_sequence=row['tigr_target_sequence'],tigr_window=row['tigr_window']))
    content=DraftContent(analysis_name='Lifecycle '+mode,r1=ids[0],r2=ids[1],
        samples=[dict(r,paired=False) for r in csv.DictReader(options['samples'].open())],targets=targets,
        analysis_mode=mode,library_profile='custom',trim_r1='8',trim_r2='8',output_root=ids[2],workspace_name='analysis')
    client=TestClient(app,base_url='http://127.0.0.1',headers={'X-Viewer-Token':'test'})
    return app,client,content,options,output


def reviewed(client,content):
    d=client.post('/api/v1/drafts',json={}).json()
    d=client.patch('/api/v1/drafts/'+d['draft_id'],json=dict(revision=0,content=content.model_dump())).json()
    v=client.post('/api/v1/drafts/'+d['draft_id']+'/validate',json=dict(revision=d['revision']))
    assert v.status_code==200 and v.json()['status']=='VALID',v.text
    p=client.get('/api/v1/drafts/'+d['draft_id']+'/preview',params=dict(revision=d['revision'])).json()
    return dict(draft_id=d['draft_id'],revision=d['revision'],plan_identity_sha256=p['plan_identity_sha256'],scientific_identity_sha256=p['scientific_identity_sha256'])


def wait_for(client,key,predicate=lambda j:j['state'] in ('COMPLETED','CANCELLED','FAILED'),timeout=90):
    start=time.monotonic()
    while time.monotonic()-start<timeout:
        response=client.get('/api/v1/jobs/'+key);assert response.status_code==200,response.text
        value=response.json()
        if predicate(value):return value
        time.sleep(.03)
    raise AssertionError('Job did not reach requested state: '+str(value))
