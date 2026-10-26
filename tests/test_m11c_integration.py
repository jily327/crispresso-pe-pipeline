"""Qualified native PE/nuclease interrupted-resume and selective-force parity."""
import csv
import gzip
import json
import os
from pathlib import Path
import shutil
import sys
import time
import pytest
from m11b_helpers import application,reviewed,wait_for
from test_m11b_integration import full_science
from peanalyzer import workflow as w
from peanalyzer.workflow_recovery import options_from_plan
from peanalyzer.workflow_models import Plan
from peanalyzer.gui.setup_models import PETargetDraft

pytestmark=[pytest.mark.crispresso_integration,pytest.mark.skipif(os.environ.get('M11C_INTEGRATION')!='1',reason='requires native qualified Core 2.3.4')]


def confirm(c,v):
    r=c.post(f"/api/v1/recovery/{v['recovery_id']}/execute",json=dict(revision=v['revision'],recovery_plan_sha256=v['recovery_plan_sha256'],confirmed=True))
    assert r.status_code==200,r.text
    job=wait_for(c,r.json()['job_id'],timeout=240)
    assert job['state']=='COMPLETED',job
    assert c.get('/api/v1/workspaces/'+job['workspace_id']).status_code==200
    return job


@pytest.mark.parametrize('mode',['precise_edit','indel_nuclease','ambiguous_pe'])
def test_native_cancel_resume_force_and_clean_parity(tmp_path,monkeypatch,mode):
    root=Path(os.environ.get('M11C_RESULTS_DIR',tmp_path/'m11c'))/mode
    app,c,content,options,out=application(root,'indel_nuclease' if mode=='indel_nuclease' else 'precise_edit')
    if mode=='ambiguous_pe':
        from peanalyzer.remediation import indel_designs
        from peanalyzer.schemas import reverse_complement
        targets=next(ts for d,ts in indel_designs() if d['id']=='deletion_1_seed11')
        content.targets=[PETargetDraft.model_validate({k:'' if v is None else v for k,v in t.model_dump().items() if k in PETargetDraft.model_fields}) for t in targets]
        for mate in (1,2):
            with gzip.open(options[f'r{mate}'],'wt') as stream:
                for t in targets:
                    for i in range(12):
                        seq=t.wt_sequence if i<6 else t.prime_edited_sequence
                        read=seq[:150] if mate==1 else reverse_complement(seq[-150:])
                        read=(content.samples[0].forward_barcode if mate==1 else content.samples[0].reverse_barcode)+read
                        stream.write(f'@{t.copy_name}_{i}/{mate}\n{read}\n+\n'+len(read)*'I'+'\n')
    script=Path(__file__).with_name('m11c_recovery_worker.py')
    monkeypatch.setattr('peanalyzer.gui.jobs.worker_command',lambda fd:[sys.executable,str(script),'--events-fd',str(fd)])
    (out/'pause-report').write_text('pause')
    response=c.post('/api/v1/jobs',json=reviewed(c,content));assert response.status_code==200,response.text
    key=response.json()['job_id']
    end=time.monotonic()+240
    while not (out/'report-ready').exists():
        job=c.get('/api/v1/jobs/'+key).json()
        assert job['state'] not in {'FAILED','COMPLETED'},job
        assert time.monotonic()<end
        time.sleep(.05)
    c.post('/api/v1/jobs/'+key+'/cancel',json={});cancelled=wait_for(c,key)
    assert cancelled['state']=='CANCELLED' and not cancelled['workspace_id']
    (out/'report-ready').unlink()
    v=c.post('/api/v1/jobs/'+key+'/recovery',json={}).json()
    assert v['classification']=='RESUMABLE',v
    assert [s['stage_id'] for s in v['stages'] if s['action']=='RUN']==['report']
    # Recovery itself is cancellable through the SAME lifecycle, without any
    # completion registration. The next inspection still reuses upstream work.
    response=c.post(f"/api/v1/recovery/{v['recovery_id']}/execute",json=dict(revision=v['revision'],recovery_plan_sha256=v['recovery_plan_sha256'],confirmed=True))
    assert response.status_code==200,response.text
    recovery_key=response.json()['job_id'];end=time.monotonic()+60
    while not (out/'report-ready').exists():
        assert time.monotonic()<end
        time.sleep(.03)
    c.post('/api/v1/jobs/'+recovery_key+'/cancel',json={})
    recovery_cancelled=wait_for(c,recovery_key)
    assert recovery_cancelled['state']=='CANCELLED' and not recovery_cancelled['workspace_id']
    (out/'pause-report').unlink()
    v=c.post('/api/v1/jobs/'+recovery_key+'/recovery',json={}).json()
    assert v['classification']=='RESUMABLE',v
    recovered=confirm(c,v);workspace=out/'analysis'
    final=w.verify_workflow_output(workspace)
    assert final.session.executed_stages==['report']
    stored=w.load(workspace/'workflow/plan.json',Plan)
    direct=options_from_plan(stored);direct['output']=out/'clean'
    w.execute_workflow(**direct);w.verify_workflow_output(direct['output'])
    expected=full_science(direct['output']);assert full_science(workspace)==expected
    equal_payloads=[]
    for relative in ('analysis','routing','report/figures'):
        for path in sorted((workspace/relative).rglob('*')):
            if path.is_file() and path.suffix in ('.gz','.tsv','.svg'):
                other=direct['output']/path.relative_to(workspace)
                if path.suffix=='.gz':assert gzip.decompress(path.read_bytes())==gzip.decompress(other.read_bytes())
                else:assert path.read_bytes()==other.read_bytes()
                equal_payloads.append(path.relative_to(workspace).as_posix())
    # Controlled incomplete report: explicit advanced force, never force on a
    # successfully verified completed workspace through the recovery UI.
    (workspace/'workflow_manifest.json').unlink()
    report_node=next(n for n in stored.nodes if n.stage_kind=='report')
    (workspace/w.stage_manifest_path(report_node)).unlink()
    registration=next(k for k,p in app.state.recovery.registrations.items() if p==workspace)
    v=c.post('/api/v1/recovery',json={'registration_id':registration}).json()
    assert not v['executable']
    v=c.post(f"/api/v1/recovery/{v['recovery_id']}/preview",json=dict(revision=v['revision'],force=['report'])).json()
    assert v['closure']==['report'] and v['executable']
    confirm(c,v);assert full_science(workspace)==expected
    # Representative scientific rerun: reuse analysis/routing, rerun all metrics.
    (workspace/'workflow_manifest.json').unlink()
    v=c.post('/api/v1/recovery',json={'registration_id':registration}).json()
    v=c.post(f"/api/v1/recovery/{v['recovery_id']}/preview",json=dict(revision=v['revision'],force=['metrics'])).json()
    confirm(c,v);forced=w.verify_workflow_output(workspace)
    assert all(n in forced.session.reused_stages for n in ['demux','analysis'])
    assert set(forced.session.executed_stages)=={n.stage_id for n in stored.nodes if n.stage_kind in {'metrics','metrics_manifest','statistics','report'}}
    assert full_science(workspace)==expected
    metric=json.loads((workspace/'metrics/bc001/T1/result.json').read_text()) if mode!='ambiguous_pe' else json.loads(next((workspace/'metrics/bc001').glob('*/result.json')).read_text())
    if mode=='indel_nuclease':
        assert len(metric['provenance']['scientific_identity']['backend_settings'])==58
        assert metric['metrics']['indel_fraction']['numerator']==8 and metric['metrics']['indel_fraction']['denominator']==20
    elif mode=='precise_edit':
        assert metric['target_metrics']['total_precise_pe']['numerator']==2 and metric['target_metrics']['total_precise_pe']['denominator']==24
    else:
        for n in stored.nodes:
            if n.stage_kind=='routing':assert w.read_json(workspace/w.stage_manifest_path(n))['status']=='SKIPPED_SCIENTIFIC_GATE'
    (root/'recovery-parity.json').write_text(json.dumps(dict(mode=mode,cancelled=cancelled['state'],recovered=recovered['state'],
        fresh_science_sha256=w.digest(expected),recovered_science_sha256=w.digest(full_science(workspace)),
        report_force=True,metrics_force=True,recovery_cancelled=recovery_cancelled['state'],reused=forced.session.reused_stages,executed=forced.session.executed_stages,
        m10_open=True,equal_payloads=equal_payloads,metric=metric.get('metrics',metric.get('target_metrics'))),indent=2)+'\n')
    app.state.jobs.close()
