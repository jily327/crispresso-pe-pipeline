"""Qualified real GUI workers versus equivalent direct workflow execution."""
import gzip
import json
import os
from pathlib import Path
import time
import pytest
from fastapi.testclient import TestClient
from m11b_helpers import application, reviewed, wait_for
from peanalyzer.gui.app import create_app
from peanalyzer.gui.execution import ExecutionSpec
from peanalyzer.workflow import execute_workflow, verify_workflow_output
from peanalyzer.workflow_storage import digest, WorkflowError, sha
from test_m7_integration import science

pytestmark=[pytest.mark.crispresso_integration,
    pytest.mark.skipif(os.environ.get('M11B_INTEGRATION')!='1',reason='requires qualified Core 2.3.4')]


def full_science(root):
    result=science(root)
    for key,value in list(result['metrics'].items()):
        data=json.loads((root/'metrics'/key).read_text())
        if data.get('analysis_mode')=='indel_nuclease':
            result['metrics'][key]={k:v for k,v in data.items() if k not in ('analysis_id','provenance')}
            result['metrics'][key]['scientific_identity']=data['provenance']['scientific_identity']
        else:
            result['metrics'][key]['anchor_evidence']=data['anchor_evidence']
    return result


@pytest.mark.parametrize('mode',['precise_edit','indel_nuclease'])
def test_real_gui_direct_parity_and_independent_viewer(mode,tmp_path):
    root=Path(os.environ.get('M11B_RESULTS_DIR',tmp_path/'m11b'))/mode
    app,c,content,options,out=application(root,mode)
    request=reviewed(c,content)
    response=c.post('/api/v1/jobs',json=request);assert response.status_code==200,response.text
    job=wait_for(c,response.json()['job_id'],timeout=180)
    assert job['state']=='COMPLETED',job
    assert job['scientific_identity_sha256']==request['scientific_identity_sha256']
    assert job['plan_identity_sha256']==request['plan_identity_sha256']
    gui=out/'analysis';manifest=verify_workflow_output(gui)
    spec=ExecutionSpec.model_validate_json(app.state.jobs.jobs[job['job_id']].payload)
    plan=json.loads((gui/'workflow/plan.json').read_text())
    assert spec.scientific_identity_sha256==digest(spec.compiled['science'])
    assert request['scientific_identity_sha256'] in manifest.session.argv
    assert job['execution_spec_sha256'] in manifest.session.argv
    for item in job['input_metadata']:
        role=item['name'].split('.')[0]
        assert plan['inputs'][role]['sha256']==item['value']
    direct=dict(options,output=out/'direct',title=content.analysis_name,crispresso=spec.runtime.crispresso)
    # Equivalent concrete metadata uses canonical M7 source files captured by the
    # accepted job; original raw FASTQs are identical. No GUI worker on this side.
    for role in ('samples','targets','config','barcodes'):direct[role]=Path(plan['inputs'][role]['source_path'])
    execute_workflow(**direct)
    verify_workflow_output(direct['output'])
    expected=full_science(gui);actual=full_science(direct['output'])
    assert expected==actual
    view=c.get('/api/v1/workspaces/'+job['workspace_id']).json()
    assert view['mode']==mode and view['observations']
    # Survives loss of all transient draft/job state and reopens through the exact
    # unchanged external-workspace path in a new application instance.
    app.state.jobs.close();del app
    fresh=TestClient(create_app([('Independent reopen',gui)],token='test'),base_url='http://127.0.0.1',headers={'X-Viewer-Token':'test'})
    reg=fresh.get('/api/v1/workspaces').json()[0]['registration_id']
    opened=fresh.post('/api/v1/workspaces/open',json={'registration_id':reg})
    assert opened.status_code==200,opened.text
    assert [{k:v for k,v in row.items() if k!='source'} for row in opened.json()['observations']]==[{k:v for k,v in row.items() if k!='source'} for row in view['observations']]
    assert [r['source']['sha256'] for r in opened.json()['observations']]==[r['source']['sha256'] for r in view['observations']]
    metric=json.loads((gui/'metrics/bc001/T1/result.json').read_text())
    if mode=='indel_nuclease':
        assert len(metric['provenance']['scientific_identity']['backend_settings'])==58
        assert metric['metrics']['indel_fraction']['numerator']==8
        assert metric['metrics']['indel_fraction']['denominator']==20
        assert len(opened.json()['nuclease'][0]['expected_configuration'])==58
    else:
        assert metric['target_metrics']['total_precise_pe']['numerator']==2
        assert metric['target_metrics']['total_precise_pe']['denominator']==24
    # Deterministic payload bytes across differently rooted executions.
    equal=[]
    for relative in ('analysis','routing','report/figures'):
        for p in sorted((gui/relative).rglob('*')):
            if p.is_file() and p.suffix in ('.gz','.tsv','.svg'):
                q=direct['output']/p.relative_to(gui)
                if p.suffix=='.gz':assert gzip.decompress(p.read_bytes())==gzip.decompress(q.read_bytes())
                else:assert p.read_bytes()==q.read_bytes()
                equal.append(p.relative_to(gui).as_posix())
    evidence=dict(mode=mode,review_scientific_identity=request['scientific_identity_sha256'],
        job_scientific_identity=job['scientific_identity_sha256'],execution_spec_sha256=job['execution_spec_sha256'],
        state=job['state'],finished_stages=job['finished_stages'],science_sha256=digest(expected),
        direct_science_sha256=digest(actual),equal_payloads=equal,independent_m10_reopen=True,
        metrics=metric.get('metrics') or metric.get('target_metrics'),
        provenance_differences='Root-bound population IDs, source result hashes, paths, invocation and timestamps; compared science excludes only these documented provenance fields.')
    (root/'parity.json').write_text(json.dumps(evidence,indent=2)+'\n')


def test_real_analyze_archive_and_warning_preservation(tmp_path):
    import csv
    import gzip
    from m7_fixtures import write_csv
    from peanalyzer.remediation import indel_designs
    from peanalyzer.schemas import reverse_complement
    from peanalyzer.demux import demultiplex
    from peanalyzer.validation import load_config
    from peanalyzer.gui.drafts import SetupReferences
    from peanalyzer.gui.setup_models import PETargetDraft
    root=Path(os.environ.get('M11B_RESULTS_DIR',tmp_path/'m11b'))/'archive-warning'
    app,c,content,options,out=application(root)
    targets=next(ts for d,ts in indel_designs() if d['id']=='deletion_1_seed11')
    content.targets=[PETargetDraft.model_validate({k:'' if v is None else v for k,v in t.model_dump().items() if k in PETargetDraft.model_fields}) for t in targets]
    rows=[t.model_dump() for t in targets];write_csv(options['targets'],list(rows[0]),rows)
    for mate in (1,2):
        with gzip.open(options[f'r{mate}'],'wt') as stream:
            for target in targets:
                for i in range(12):
                    seq=target.wt_sequence if i<6 else target.prime_edited_sequence
                    read=seq[:150] if mate==1 else reverse_complement(seq[-150:])
                    read=(content.samples[0].forward_barcode if mate==1 else content.samples[0].reverse_barcode)+read
                    stream.write(f'@{target.copy_name}_{i}/{mate}\n{read}\n+\n'+len(read)*'I'+'\n')
    archive=root/'archive'
    demultiplex(r1=options['r1'],r2=options['r2'],samples_path=options['samples'],config=load_config(options['config']),output=archive)
    extra=SetupReferences(archives=[archive]);app.state.drafts.references.paths.update(extra.paths);app.state.drafts.references.entries.update(extra.entries)
    content.input_mode='analyze';content.r1=content.r2=None;content.demux=next(iter(extra.entries))
    before={p.relative_to(archive).as_posix():sha(p) for p in archive.rglob('*') if p.is_file()}
    request=reviewed(c,content);validation=app.state.drafts.get(request['draft_id']).validation
    response=c.post('/api/v1/jobs',json=request);assert response.status_code==200,response.text
    job=wait_for(c,response.json()['job_id'],timeout=180);assert job['state']=='COMPLETED',job
    assert job['warnings']==[i.model_dump() for i in validation.issues if i.severity=='WARNING']
    assert any('NONUNIQUE' in i['message'] for i in job['warnings'])
    assert any(s['status']=='SKIPPED_SCIENTIFIC_GATE' for s in job['stages'])
    metric=json.loads((out/'analysis/metrics/bc001/SYN/result.json').read_text())
    assert metric['target_metrics']['total_precise_pe']['numerator']==12
    assert metric['target_metrics']['total_precise_pe']['denominator']==24
    assert all(v['precise']['status']=='BLOCKED' for v in metric['copies'].values())
    assert before=={p.relative_to(archive).as_posix():sha(p) for p in archive.rglob('*') if p.is_file()}
    assert verify_workflow_output(out/'analysis').status=='COMPLETED'
    (root/'archive-warning.json').write_text(json.dumps(dict(state=job['state'],warnings=job['warnings'],
        stages=job['stages'],target_precise=metric['target_metrics']['total_precise_pe'],archive_unchanged=True),indent=2)+'\n')
    app.state.jobs.close()
