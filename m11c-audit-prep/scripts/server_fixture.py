"""TEST-ONLY real baseline JobStore adapter; in-process HTTP, no production hooks."""
import argparse,os,sys
from pathlib import Path
from common import baseline_import,read,write
from process_fixture import run,wait

def worker():
    from peanalyzer.gui import worker as module
    def fixed(spec,emit):
        emit(dict(status='WORKER_READY'))
        emit(dict(status='RUNNING',stage_id='raw_inputs',stage_kind='raw_inputs'))
        run(os.environ['AUDIT_TREE_ROOT'],escape='setsid',ignore=True,close_stdio=True,token='server-death-fixture')
    module.run=fixed
    return module.main()

def server(checkout,fixtures,root):
    baseline_import(checkout)
    from fastapi.testclient import TestClient
    from peanalyzer.gui.app import create_app
    from peanalyzer.gui.execution import RuntimeSettings
    from peanalyzer.gui import jobs
    root=Path(root);root.mkdir(parents=True,exist_ok=False);output=root/'outputs';output.mkdir()
    fixtures=Path(fixtures)
    jobs.worker_command=lambda fd:[sys.executable,str(Path(__file__).resolve()),'worker','--events-fd',str(fd)]
    os.environ['AUDIT_TREE_ROOT']=str(root/'tree')
    app=create_app(token='audit-only',setup_files=[fixtures/'raw_R1.fastq.gz',fixtures/'raw_R2.fastq.gz'],setup_output_roots=[output],runtime=RuntimeSettings(crispresso='unused-test-only'))
    with TestClient(app,base_url='http://127.0.0.1',headers={'X-Viewer-Token':'audit-only'}) as client:
        content=read(fixtures/'draft-template.json');ids=list(app.state.drafts.references.entries)
        content.update(r1=ids[0],r2=ids[1],output_root=ids[2],workspace_name='audit-job')
        draft=client.post('/api/v1/drafts',json={}).json()
        draft=client.patch('/api/v1/drafts/'+draft['draft_id'],json=dict(revision=0,content=content)).json()
        validation=client.post('/api/v1/drafts/'+draft['draft_id']+'/validate',json=dict(revision=draft['revision']))
        assert validation.status_code==200 and validation.json()['status']=='VALID',validation.text
        preview=client.get('/api/v1/drafts/'+draft['draft_id']+'/preview',params=dict(revision=draft['revision'])).json()
        request=dict(draft_id=draft['draft_id'],revision=draft['revision'],plan_identity_sha256=preview['plan_identity_sha256'],scientific_identity_sha256=preview['scientific_identity_sha256'])
        response=client.post('/api/v1/jobs',json=request);assert response.status_code==200,response.text
        wait(root/'tree/grandchild-ready.json')
        write(root/'accepted.json',dict(request=request,response=response.json(),job=client.get('/api/v1/jobs/'+response.json()['job_id']).json(),transport='FastAPI TestClient inside a killable server process; real JobStore and worker envelope'))
        wait(root/'release-server',40)

if __name__=='__main__':
    if sys.argv[1]=='worker':sys.argv.pop(1);raise SystemExit(worker())
    p=argparse.ArgumentParser();p.add_argument('--baseline',required=True);p.add_argument('--fixtures',required=True);p.add_argument('--output',required=True);a=p.parse_args();server(a.baseline,a.fixtures,a.output)
