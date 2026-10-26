"""M7 state-machine, containment, resume and selective-force qualification."""
from collections import Counter
import csv
import json
from pathlib import Path
import shutil
import time

import pytest
from pydantic import ValidationError

from m7_fixtures import fixture
from peanalyzer import workflow as w
from peanalyzer.metrics import collect_metrics
from peanalyzer.workflow_models import Plan, StageManifest, WorkflowManifest

EXECUTORS=('demultiplex','prepare_analysis_fastqs','route_analysis','run_metrics','summarize','stats','generate_report')


@pytest.fixture
def case(tmp_path,monkeypatch):
    options=fixture(tmp_path/'inputs',samples=2,reads=2)
    core=tmp_path/'CRISPResso'
    core.write_text('#!/bin/sh\nprintf "CRISPResso 2.3.4\\n"\n');core.chmod(0o755)
    options['crispresso']=str(core)
    counts=Counter()
    def metrics(**kwargs):
        output=Path(kwargs.pop('output'));output.mkdir(parents=True)
        kwargs.pop('core')
        result=collect_metrics(**kwargs,comparator_root=output/'comparator')
        (output/'result.json').write_text(result.model_dump_json(indent=2)+'\n')
        (output/'execution_failures.json').write_text('{}\n')
        return result
    monkeypatch.setattr(w,'run_metrics',metrics)
    for name in EXECUTORS:
        original=getattr(w,name)
        def wrapped(*args,_name=name,_original=original,**kwargs):
            counts[_name]+=1
            return _original(*args,**kwargs)
        monkeypatch.setattr(w,name,wrapped)
    return options,counts


def complete(case):
    options,counts=case
    result=w.execute_workflow(**options)
    assert result['metrics_results']==2
    w.verify_workflow_output(options['output'])
    counts.clear()
    return options,counts


def read(path):return json.loads(Path(path).read_text())
def write(path,data):Path(path).write_text(json.dumps(data,sort_keys=True)+'\n')
def plan(options):return w.load(options['output']/'workflow/plan.json',Plan)
def stage_path(options,kind):
    node=next(n for n in plan(options).nodes if n.stage_kind==kind)
    return options['output']/w.stage_manifest_path(node)


def test_dag_two_samples_two_targets(case):
    options,_=case
    updated=fixture(options['samples'].parent,samples=2,targets=2,reads=2)
    updated['crispresso']=options['crispresso']
    p=w.build_workflow_plan(**updated)
    assert len(p.nodes)==14
    assert len([n for n in p.nodes if n.stage_kind=='routing'])==4
    assert len([n for n in p.nodes if n.stage_kind=='metrics'])==4
    assert {n.sample_id for n in p.nodes if n.stage_kind=='metrics'}=={'bc001','bc002'}
    assert all(len([t for t in p.targets if t.target_name==name])==2 for name in p.expected_targets)
    for n in p.nodes:
        if n.stage_kind=='metrics':assert n.dependencies==['analysis',f'routing::{n.sample_id}::{n.target_name}']


def test_semantic_dag_order_invariance(case):
    options,_=case
    before=w.build_workflow_plan(**options)
    for role in ('samples','targets'):
        path=options[role];lines=path.read_text().splitlines()
        path.write_text('\n'.join([lines[0],*reversed(lines[1:])])+'\n')
    after=w.build_workflow_plan(**options)
    assert before.nodes==after.nodes and before.samples==after.samples and before.targets==after.targets
    assert before.inputs['samples'].sha256!=after.inputs['samples'].sha256


@pytest.mark.parametrize('attack',['cycle','missing','duplicate','path','sample'])
def test_plan_dag_rejects_hand_edits(case,attack):
    options,_=case;value=w.build_workflow_plan(**options).model_dump(mode='json')
    if attack=='cycle':value['nodes'][0]['dependencies']=['report']
    elif attack=='missing':value['nodes'][2]['dependencies']=['absent']
    elif attack=='duplicate':value['nodes'].append(value['nodes'][-1])
    elif attack=='path':value['nodes'][2]['output_path']='../outside'
    else:value['expected_samples'].append('bc001')
    with pytest.raises(ValidationError):Plan.model_validate(value)


def test_completed_resume_executes_nothing_and_preserves_completion(case,monkeypatch):
    options,counts=complete(case)
    marker=options['output']/'workflow_manifest.json';before=marker.read_bytes()
    for name in EXECUTORS:
        monkeypatch.setattr(w,name,lambda *a,**k:pytest.fail('executor called during reuse'))
    result=w.resume_workflow(**options)
    assert result['executed_stages']==[] and len(result['reused_stages'])==10
    assert marker.read_bytes()==before
    monkeypatch.setattr(w,'resolve_executable',lambda *a,**k:pytest.fail('verifier probed backend'))
    assert w.verify_workflow_output(options['output']).status=='COMPLETED'
    assert not options['output'].with_name('.workflow.m7-lock').exists()


@pytest.mark.parametrize('family,expected',[
    ('report',{'generate_report':1}),('statistics',{'summarize':1,'generate_report':1}),
    ('metrics',{'run_metrics':2,'summarize':1,'generate_report':1}),
    ('routing',{'route_analysis':2,'run_metrics':2,'summarize':1,'generate_report':1}),
    ('analysis',{'prepare_analysis_fastqs':1,'route_analysis':2,'run_metrics':2,'summarize':1,'generate_report':1}),
    ('demux',{'demultiplex':1,'prepare_analysis_fastqs':1,'route_analysis':2,'run_metrics':2,'summarize':1,'generate_report':1}),
    ('all',{'demultiplex':1,'prepare_analysis_fastqs':1,'route_analysis':2,'run_metrics':2,'summarize':1,'generate_report':1})])
def test_selective_force_exact_calls(case,family,expected):
    options,counts=complete(case)
    w.execute_workflow(**options,resume=True,force=[family])
    assert dict(counts)==expected
    w.verify_workflow_output(options['output'])


def test_force_union_is_order_independent(case):
    options,_=case;p=w.build_workflow_plan(**options)
    assert w.force_closure(p,['report','routing'])==w.force_closure(p,['routing','report'])==w.force_closure(p,['routing'])


@pytest.mark.parametrize('family',['report','metrics','all'])
def test_force_requires_resume(case,family):
    options,_=case
    with pytest.raises(w.WorkflowError,match='INVALID_FORCE'):w.execute_workflow(**options,force=[family])
    assert not options['output'].exists()


def test_existing_root_not_adopted(case):
    options,_=case;options['output'].mkdir();sentinel=options['output']/'sentinel';sentinel.write_text('keep')
    with pytest.raises(w.WorkflowError,match='OUTPUT_EXISTS'):w.execute_workflow(**options)
    assert sentinel.read_text()=='keep'


@pytest.mark.parametrize('kind,relative,family',[
    ('analysis','analysis/03_analysis_fastq/bc001_R1.analysis.fastq.gz','analysis'),
    ('routing','routing/bc001/T1/routing_manifest.json','routing'),
    ('metrics','metrics/bc001/T1/result.json','metrics'),
    ('statistics','statistics/result.json','statistics'),
    ('report','report/report.html','report')])
def test_corruption_requires_correct_force(case,kind,relative,family):
    options,_=complete(case);path=options['output']/relative;path.write_bytes(path.read_bytes()+b' ')
    with pytest.raises(w.WorkflowError):w.execute_workflow(**options,resume=True)
    assert not (options['output']/'workflow_manifest.json').exists()
    if family!='report':
        with pytest.raises(w.WorkflowError):w.execute_workflow(**options,resume=True,force=['report'])
    w.execute_workflow(**options,resume=True,force=[family])
    w.verify_workflow_output(options['output'])


def test_report_svg_corruption(case):
    options,_=complete(case);path=next((options['output']/'report/figures').glob('*.svg'))
    path.write_bytes(path.read_bytes()+b'x')
    with pytest.raises(w.WorkflowError):w.resume_workflow(**options)
    w.resume_workflow(**options,force=['report'])


@pytest.mark.parametrize('attack',['signature','dependency','artifact_path','artifact_hash','stage_id','stage_kind','status','contract','unknown','schema_bool'])
def test_stage_manifest_hand_edits(case,attack):
    options,_=complete(case);path=stage_path(options,'metrics');value=read(path)
    if attack=='signature':value['stage_signature_sha256']='0'*64
    elif attack=='dependency':next(iter(value['dependencies'].values()))['manifest']['sha256']='0'*64
    elif attack=='artifact_path':value['output_artifacts'][0]['path']='../outside'
    elif attack=='artifact_hash':value['output_artifacts'][0]['sha256']='0'*64
    elif attack=='stage_id':value['node']['stage_id']='metrics::other::T1'
    elif attack=='stage_kind':value['node']['stage_kind']='report'
    elif attack=='status':value['status']='REPORTABLE'
    elif attack=='contract':value['workflow_contract_version']='m7-v2'
    elif attack=='unknown':value['unexpected']=True
    else:value['schema_version']=True
    write(path,value)
    with pytest.raises(w.WorkflowError):w.resume_workflow(**options)


def test_dependency_metadata_tamper_invalidates_descendants(case):
    options,_=complete(case);path=stage_path(options,'analysis');value=read(path)
    value['validation'].append('hand-edited');write(path,value)
    with pytest.raises(w.WorkflowError):w.resume_workflow(**options)


@pytest.mark.parametrize('location',['root','stage','stage_manifest','forced_child'])
def test_symlink_deletion_never_leaves_workspace(case,tmp_path,location):
    options,_=case;outside=tmp_path/'outside';outside.mkdir();sentinel=outside/'sentinel';sentinel.write_text('keep')
    if location=='root':
        options['output'].symlink_to(outside,target_is_directory=True)
        with pytest.raises(w.WorkflowError,match='UNSAFE_PATH'):w.execute_workflow(**options)
    else:
        complete(case)
        if location=='stage':
            path=options['output']/'report';shutil.rmtree(path);path.symlink_to(outside,target_is_directory=True)
        elif location=='stage_manifest':
            path=stage_path(options,'report');path.unlink();path.symlink_to(sentinel)
        else:(options['output']/'report'/'foreign').symlink_to(outside,target_is_directory=True)
        with pytest.raises(w.WorkflowError,match='UNSAFE_PATH'):w.resume_workflow(**options,force=['report'])
    assert sentinel.read_text()=='keep'


@pytest.mark.parametrize('path',['../outside','/tmp/outside','report\\outside','report/../../outside'])
def test_path_traversal_model_and_storage(case,path):
    options,_=complete(case);manifest=read(stage_path(options,'report'))
    manifest['output_artifacts'][0]['path']=path
    with pytest.raises(ValidationError):StageManifest.model_validate(manifest)
    with pytest.raises(w.WorkflowError):w.owned(options['output'],path)


def test_foreign_lock_preserved(case):
    options,_=case;lock=options['output'].with_name('.workflow.m7-lock');lock.write_text('foreign')
    with pytest.raises(w.WorkflowError,match='WORKFLOW_LOCKED'):w.execute_workflow(**options)
    assert lock.read_text()=='foreign' and not options['output'].exists()


def test_interrupted_without_orphan_resumes_upstream(case,monkeypatch):
    options,counts=case;original=w.run_metrics
    def fail(**kwargs):raise RuntimeError('injected before output')
    monkeypatch.setattr(w,'run_metrics',fail)
    with pytest.raises(w.WorkflowError,match='injected'):w.execute_workflow(**options)
    assert not (options['output']/'workflow_manifest.json').exists()
    assert not options['output'].with_name('.workflow.m7-lock').exists()
    monkeypatch.setattr(w,'run_metrics',original);counts.clear()
    result=w.resume_workflow(**options)
    assert dict(counts)=={'run_metrics':2,'summarize':1,'generate_report':1}
    assert 'analysis' in result['reused_stages']


@pytest.mark.parametrize('cancel',[False,True])
def test_metrics_orphan_needs_force_and_cancellation_unwinds(case,monkeypatch,cancel):
    options,counts=case;original=w.run_metrics
    def fail(**kwargs):
        Path(kwargs['output']).mkdir(parents=True)
        raise SystemExit(143) if cancel else RuntimeError('partial backend output')
    monkeypatch.setattr(w,'run_metrics',fail)
    with pytest.raises(SystemExit if cancel else w.WorkflowError):w.execute_workflow(**options)
    assert not (options['output']/'workflow_manifest.json').exists()
    assert not options['output'].with_name('.workflow.m7-lock').exists()
    monkeypatch.setattr(w,'run_metrics',original)
    with pytest.raises(w.WorkflowError,match='ORPHANED_STAGE_OUTPUT'):w.resume_workflow(**options)
    w.resume_workflow(**options,force=['metrics'])


def test_completion_invalidated_before_forced_execution(case,monkeypatch):
    options,_=complete(case)
    def fail(**kwargs):
        assert not (options['output']/'workflow_manifest.json').exists()
        raise RuntimeError('forced report fails')
    monkeypatch.setattr(w,'generate_report',fail)
    with pytest.raises(w.WorkflowError,match='forced report'):w.resume_workflow(**options,force=['report'])
    assert not stage_path(options,'report').exists()


@pytest.mark.parametrize('change,family',[('title','report'),('trims','analysis'),('runtime','metrics'),('policies','metrics'),('samples','demux'),('raw','demux'),('targets','routing')])
def test_changed_inputs_require_earliest_force(case,change,family):
    options,counts=complete(case)
    if change=='title':options['title']='Changed title'
    elif change=='trims':options['analysis_r1_trim_5p']=9;options['analysis_r2_trim_5p']=9
    elif change=='runtime':options['runtime_digest']='explicit-unqualified-runtime'
    elif change=='policies':options['tolerance_policies']=options['samples'].parent/'policies.json'
    elif change=='samples':options['samples'].write_text(options['samples'].read_text().replace('synthetic-editor','renamed-editor'))
    elif change=='targets':
        lines=options['targets'].read_text().splitlines()
        options['targets'].write_text('\n'.join([lines[0],*reversed(lines[1:])])+'\n')
    else:
        # Equivalent gzip payload, different authoritative bytes.
        import gzip
        data=gzip.decompress(options['r1'].read_bytes());options['r1'].write_bytes(gzip.compress(data,mtime=12))
    with pytest.raises(w.WorkflowError):w.resume_workflow(**options)
    w.resume_workflow(**options,force=[family])
    w.verify_workflow_output(options['output'])


def test_version_attack_rejected(case):
    options,_=complete(case);Path(options['crispresso']).write_text('#!/bin/sh\necho "CRISPResso 2.4.0"\n')
    with pytest.raises(w.WorkflowError,match='VERSION_MISMATCH'):w.resume_workflow(**options)


def test_source_mutation_before_stage_completion(case,monkeypatch):
    options,_=case;original=w.demultiplex
    def mutate(**kwargs):
        result=original(**kwargs)
        options['samples'].write_text(options['samples'].read_text()+'\n')
        return result
    monkeypatch.setattr(w,'demultiplex',mutate)
    with pytest.raises(w.WorkflowError,match='SOURCE_CHANGED'):w.execute_workflow(**options)
    assert not stage_path(options,'demux').exists()
    assert not (options['output']/'workflow_manifest.json').exists()


def test_duplicate_and_swapped_result_defense(case):
    options,_=complete(case);root=options['output'];paths=[root/f'metrics/bc{i:03}/T1/result.json' for i in (1,2)]
    a,b=[p.read_bytes() for p in paths];paths[0].write_bytes(b);paths[1].write_bytes(a)
    with pytest.raises(w.WorkflowError,match='METRICS_IDENTITY_MISMATCH'):w._metrics_results(plan(options))
    paths[0].write_bytes(a);paths[1].write_bytes(b)
    extra=root/'metrics/duplicate';extra.mkdir();(extra/'result.json').write_bytes(a)
    with pytest.raises(w.WorkflowError,match='METRICS_COVERAGE_MISMATCH'):w._metrics_results(plan(options))


def test_report_source_identity_and_fake_completion(case):
    options,_=complete(case);root=options['output'];p=plan(options)
    (root/'report/source/result.json').write_bytes((root/'statistics/result.json').read_bytes()+b' ')
    with pytest.raises(w.WorkflowError,match='REPORT_SOURCE_MISMATCH'):
        w.validate_stage(p,next(n for n in p.nodes if n.stage_kind=='report'),'COMPLETED')
    stage_path(options,'analysis').unlink()
    with pytest.raises(w.WorkflowError):w.verify_workflow_output(root)


def test_analyze_external_archive_immutable_even_force_all(case):
    options,_=complete(case);external=options['output']/'demux'
    before={p.relative_to(external):p.read_bytes() for p in external.rglob('*') if p.is_file()}
    analyze={k:v for k,v in options.items() if k not in ('r1','r2')}
    analyze.update(mode='analyze',demux_root=external,output=options['output'].with_name('analyze'))
    w.execute_workflow(**analyze)
    with pytest.raises(w.WorkflowError,match='INVALID_FORCE'):w.resume_workflow(**analyze,force=['demux'])
    w.resume_workflow(**analyze,force=['all'])
    assert before=={p.relative_to(external):p.read_bytes() for p in external.rglob('*') if p.is_file()}


def test_snapshot_history_preserved(case):
    options,_=complete(case);root=options['output'];old=plan(options).inputs['samples']
    old_bytes=(root/old.snapshot).read_bytes()
    options['samples'].write_text(options['samples'].read_text().replace('synthetic-editor','new-editor'))
    w.resume_workflow(**options,force=['demux'])
    new=plan(options).inputs['samples']
    assert old.snapshot!=new.snapshot and (root/old.snapshot).read_bytes()==old_bytes
    assert len(list((root/'workflow/plans').glob('*.json')))==2


def test_workflow_manifest_schema_and_packaged_resources(case):
    from importlib.resources import files
    options,_=complete(case)
    for name,model in [('workflow_manifest',WorkflowManifest),('stage_manifest',StageManifest)]:
        schema=json.loads(files('peanalyzer.workflow_resources').joinpath(name+'.schema.json').read_text())
        assert schema==model.model_json_schema() and schema['additionalProperties'] is False
    assert w.load(options['output']/'workflow_manifest.json',WorkflowManifest).workflow_contract_version=='m7-v1'


def test_large_dag_planning(case):
    options,_=case;updated=fixture(options['samples'].parent,samples=100,targets=4,reads=0)
    updated['crispresso']=options['crispresso']
    start=time.monotonic();p=w.build_workflow_plan(**updated);elapsed=time.monotonic()-start
    assert len(p.nodes)==806
    assert len(w.force_closure(p,['metrics']))==403
    # Deliberately descriptive, never a machine-speed-dependent correctness gate.
    print(json.dumps(dict(nodes=len(p.nodes),seconds=elapsed)))


def test_multi_target_execution_rejected_before_workspace_or_stage(case):
    options,counts=case
    changed=fixture(options['samples'].parent,samples=2,targets=2,reads=2)
    changed['crispresso']=options['crispresso']
    assert len(w.build_workflow_plan(**changed).expected_targets)==2
    with pytest.raises(w.WorkflowError,match='MULTI_TARGET_EXECUTION_UNSUPPORTED'):
        w.execute_workflow(**changed)
    assert not changed['output'].exists() and not counts


@pytest.mark.parametrize('inventory',['samples','targets'])
def test_graph_growth_and_shrink_with_mocked_metrics(case,monkeypatch,inventory):
    options,counts=complete(case)
    # Only this mocked-science test bypasses the production scope guard.
    monkeypatch.setattr(w,'_check_execution_scope',lambda p:None)
    family='demux' if inventory=='samples' else 'routing'
    for size in (3,1):
        raw={k:options[k].read_bytes() for k in ('r1','r2')}
        fixture(options['samples'].parent,samples=size if inventory=='samples' else 2,
                targets=size if inventory=='targets' else 1,reads=2)
        if inventory=='targets':
            for key,data in raw.items():options[key].write_bytes(data)
        with pytest.raises(w.WorkflowError,match='WORKFLOW_GRAPH_MISMATCH'):
            w.resume_workflow(**options)
        result=w.resume_workflow(**options,force=[family])
        expected=size if inventory=='samples' else 2*size
        assert result['metrics_results']==expected
        assert len(w._metrics_results(plan(options)))==expected
        assert len(read(options['output']/'workflow_manifest.json')['stage_inventory'])==6+2*expected
        w.verify_workflow_output(options['output'])


def test_routing_scientific_block_preserves_complete_m4(case):
    options,counts=case
    fixture(options['samples'].parent,samples=2,reads=2,blocked=True)
    w.execute_workflow(**options)
    p=plan(options)
    routes=[w.load(options['output']/w.stage_manifest_path(n),StageManifest) for n in p.nodes if n.stage_kind=='routing']
    assert all(m.status=='SKIPPED_SCIENTIFIC_GATE' for m in routes)
    assert counts['route_analysis']==0 and counts['run_metrics']==2
    assert len(w._metrics_results(p))==2
    w.verify_workflow_output(options['output'])


def test_stats_and_contrast_change_forces_only_downstream(case):
    options,counts=case;options['contrasts']=options['samples'].parent/'contrasts.yaml'
    w.execute_workflow(**options);counts.clear()
    options['contrasts'].write_text(options['contrasts'].read_text().replace('contrast_id: native','contrast_id: renamed'))
    with pytest.raises(w.WorkflowError):w.resume_workflow(**options)
    w.resume_workflow(**options,force=['statistics'])
    assert dict(counts)=={'stats':1,'generate_report':1}


def test_m61_invalid_svg_fails_workflow_closed(case):
    import matplotlib.pyplot as plt
    options,_=case;before=plt.get_fignums()
    options['samples'].write_text(options['samples'].read_text().replace('synthetic-editor','ed\x01x'))
    with pytest.raises(w.WorkflowError,match='INVALID_GENERATED_SVG'):w.execute_workflow(**options)
    root=options['output']
    assert (root/'statistics/result.json').exists()
    assert not (root/'report').exists() and not (root/'workflow_manifest.json').exists()
    assert not stage_path(options,'report').exists()
    assert not list(root.glob('.*incomplete*'))
    assert not root.with_name('.workflow.m7-lock').exists() and plt.get_fignums()==before


def test_backend_operational_failure_not_scientific_block(case,monkeypatch):
    options,_=case;original=w.run_metrics
    def fail(**kwargs):
        result=original(**kwargs)
        write(Path(kwargs['output'])/'execution_failures.json',{'comparator':'backend failed'})
        return result
    monkeypatch.setattr(w,'run_metrics',fail)
    with pytest.raises(w.WorkflowError,match='BACKEND_EXECUTION_FAILED'):w.execute_workflow(**options)
    assert not stage_path(options,'metrics').exists()


def test_external_symlink_and_input_containment(case):
    options,_=complete(case)
    link=options['output'].with_name('archive-link');link.symlink_to(options['output']/'demux',target_is_directory=True)
    analyze={k:v for k,v in options.items() if k not in ('r1','r2')}
    analyze.update(mode='analyze',demux_root=link,output=options['output'].with_name('analyze'))
    with pytest.raises(w.WorkflowError,match='UNSAFE_PATH'):w.execute_workflow(**analyze)
    bad=dict(options,output=options['samples'].parent)
    with pytest.raises(w.WorkflowError,match='EXTERNAL_INPUT_PROTECTION'):w.build_workflow_plan(**bad)


@pytest.mark.parametrize('attack',['stage_hash','extra_stage','schema_bool','contract','plan_path','report_hash','status'])
def test_final_completion_hand_edits(case,attack):
    options,_=complete(case);path=options['output']/'workflow_manifest.json';value=read(path)
    if attack=='stage_hash':next(iter(value['stage_inventory'].values()))['sha256']='0'*64
    elif attack=='extra_stage':value['stage_inventory']['fake']=next(iter(value['stage_inventory'].values()))
    elif attack=='schema_bool':value['schema_version']=True
    elif attack=='contract':value['workflow_contract_version']='m7-v2'
    elif attack=='plan_path':value['plan']['path']='../plan.json'
    elif attack=='report_hash':value['report_manifest']['sha256']='0'*64
    else:value['status']='RUNNING'
    write(path,value)
    with pytest.raises(w.WorkflowError):w.verify_workflow_output(options['output'])


def test_timestamp_not_in_stage_signature(case):
    options,_=complete(case);p=plan(options);node=next(n for n in p.nodes if n.stage_kind=='report')
    record=w.load(stage_path(options,'report'),StageManifest)
    changed=record.model_copy(update={'started_at':'2000-01-01T00:00:00+00:00'})
    assert w.signature(p,node,record.dependencies)==w.signature(p,node,changed.dependencies)
    assert w.output_identity(record)==w.output_identity(changed)
    with pytest.raises(ValidationError):StageManifest.model_validate(dict(record.model_dump(),started_at='2000-01-01'))


def test_cli_run_analyze_thin_wrapper_and_failure(case,monkeypatch,capsys):
    from peanalyzer.cli import main
    options,_=case
    for mode in ('run','analyze'):
        args=[mode,'--samples',str(options['samples']),'--targets',str(options['targets']),
              '--config',str(options['config']),'--output',str(options['output']),
              '--crispresso',options['crispresso'],'--runtime-digest',options['runtime_digest'],
              '--analysis-r1-trim-5p','8','--analysis-r2-trim-5p','8']
        args+=['--r1',str(options['r1']),'--r2',str(options['r2'])] if mode=='run' else ['--demux-root','archive']
        observed=[]
        def execute(**kwargs):observed.append(kwargs);return {'mode':kwargs['mode']}
        monkeypatch.setattr(w,'execute_workflow',execute)
        assert main(args)==0 and json.loads(capsys.readouterr().out)['mode']==mode
        assert observed[0]['argv']==['peanalyzer',*args]
        def fail(**kwargs):raise w.WorkflowError('INJECTED','operational failure','metrics::bc001::T1')
        monkeypatch.setattr(w,'execute_workflow',fail)
        assert main(args)==2
        assert 'INJECTED' in capsys.readouterr().err


def test_real_process_lock_and_sigterm_cleanup(case):
    import multiprocessing
    import os
    import signal
    from peanalyzer.cli import sigterm_cleanup
    options,_=case
    context=multiprocessing.get_context('fork')
    receiver,sender=context.Pipe(duplex=False)
    def child():
        def pause(**kwargs):
            sender.send('locked')
            while True:time.sleep(0.1)
        w.demultiplex=pause
        with sigterm_cleanup():w.execute_workflow(**options)
    process=context.Process(target=child);process.start()
    try:
        assert receiver.poll(15) and receiver.recv()=='locked'
        with pytest.raises(w.WorkflowError,match='WORKFLOW_LOCKED'):w.execute_workflow(**options)
        os.kill(process.pid,signal.SIGTERM);process.join(15)
        assert not process.is_alive() and process.exitcode==143
        assert not options['output'].with_name('.workflow.m7-lock').exists()
        assert not (options['output']/'workflow_manifest.json').exists()
        assert not stage_path(options,'demux').exists()
        result=w.resume_workflow(**options)
        assert result['reused_stages']==['raw_inputs']
    finally:
        if process.is_alive():process.kill();process.join()
        receiver.close();sender.close()
