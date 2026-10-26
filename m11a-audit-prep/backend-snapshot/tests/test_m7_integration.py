"""Real pinned-backend raw-to-report M7 oracle, including resume and analyze."""
import gzip
import json
import os
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from m7_fixtures import fixture
from peanalyzer import workflow as w

pytestmark=[pytest.mark.crispresso_integration,
    pytest.mark.skipif(os.environ.get('M7_INTEGRATION')!='1',reason='set M7_INTEGRATION=1 with qualified Core 2.3.4')]


def read(path):return json.loads(Path(path).read_text())


def scientific(value):
    if isinstance(value,dict):
        return {k:scientific(v) for k,v in value.items() if k not in ('population_id','source_result_sha256')}
    if isinstance(value,list):return [scientific(v) for v in value]
    return value


def science(root):
    """Compare existing deterministic science, excluding explicitly root-bound provenance."""
    root=Path(root)
    m4={str(p.relative_to(root/'metrics')):scientific({k:read(p).get(k) for k in
        ('target_metrics','copies','qc','eligibility','derived_metrics','product_evidence')})
        for p in sorted((root/'metrics').rglob('result.json'))}
    m5=read(root/'statistics/result.json')
    return dict(metrics=m4,statistics=scientific({k:m5[k] for k in
        ('observations','group_summaries','contrasts','multiple_testing_families','unused_metadata_sample_ids')}),
        prepared={p.name:gzip.decompress(p.read_bytes()).decode() for p in sorted((root/'analysis').rglob('*.fastq.gz'))},
        routing={str(p.relative_to(root/'routing')):gzip.decompress(p.read_bytes()).decode()
                 for p in sorted((root/'routing').rglob('*.fastq.gz'))},
        ledgers={str(p.relative_to(root/'routing')):p.read_text() for p in sorted((root/'routing').rglob('*.tsv'))},
        figures={p.name:p.read_text() for p in sorted((root/'report/figures').glob('*.svg'))})


def validate(root):
    manifest=w.verify_workflow_output(root)
    assert manifest.status=='COMPLETED'
    demux=read(root/'demux/01_demux_QC/demux_summary.json') if (root/'demux').exists() else None
    if demux:
        assert demux['total_input_read_pairs']==demux['assigned_expected_pair']==96
        assert sum(demux[k] for k in ('assigned_expected_pair','unexpected_valid_barcode_pair','forward_only',
                    'reverse_only','no_barcode_match','ambiguous_barcode_match'))==96
    analysis=read(root/'analysis/analysis_manifest.json')
    assert sum(s['pairs'] for s in analysis['samples'].values())==96
    for i,numerator in enumerate((4,8,16,20),1):
        sample=f'bc{i:03}'
        route=read(root/f'routing/{sample}/T1/routing_manifest.json')
        assert route['input_pairs']==24
        assert sum(route['categories'].values())==24
        metric=read(root/f'metrics/{sample}/T1/result.json')['target_metrics']['target_crispresso_native_pe']
        assert metric['status']=='REPORTABLE' and (metric['numerator'],metric['denominator'])==(numerator,24)
    m5=read(root/'statistics/result.json');contrast=m5['contrasts'][0]
    assert contrast['used_group_a_count']==contrast['used_group_b_count']==2
    assert contrast['difference_in_biological_sample_fraction']==0.5
    assert contrast['permutation_count']==6 and contrast['extreme_count']==2
    assert contrast['p_value']==contrast['q_value']==1/3
    assert (root/'report/source/result.json').read_bytes()==(root/'statistics/result.json').read_bytes()
    page=(root/'report/report.html').read_text()
    for svg in (root/'report/figures').glob('*.svg'):
        ET.fromstring(svg.read_text());assert svg.read_text() in page
    return dict(status='COMPLETED',input_pairs=96,assigned_pairs=96,biological_samples=4,
        biological_targets=1,copies=2,metrics_results=4,native_counts=[[n,24] for n in (4,8,16,20)],
        contrast=dict(n_a=2,n_b=2,effect=0.5,permutations=6,p_value=1/3,q_value=1/3),
        stages=len(manifest.stage_inventory),svg_files=len(list((root/'report/figures').glob('*.svg'))))


def test_real_m7_end_to_end_resume_and_analyze(tmp_path,monkeypatch):
    root=Path(os.environ.get('M7_RESULTS_DIR',tmp_path/'m7'));root.mkdir(parents=True,exist_ok=True)
    options=fixture(root/'inputs');options.update(output=root/'clean',
        crispresso=os.environ.get('M3_CORE_EXECUTABLE','CRISPResso'),contrasts=root/'inputs/contrasts.yaml')
    clean=w.execute_workflow(**options,argv=['m7-integration','run'])
    evidence={'clean':validate(options['output'])}
    before=(options['output']/'workflow_manifest.json').read_bytes()
    with monkeypatch.context() as patch:
        for name in ('demultiplex','prepare_analysis_fastqs','route_analysis','run_metrics','summarize','stats','generate_report'):
            patch.setattr(w,name,lambda *a,**k:pytest.fail('completed resume executed a stage'))
        reused=w.resume_workflow(**options)
    assert not reused['executed_stages'] and len(reused['reused_stages'])==14
    assert (options['output']/'workflow_manifest.json').read_bytes()==before
    expected=science(options['output'])
    interrupted=dict(options,output=root/'resumed')
    with monkeypatch.context() as patch:
        def fail(**kwargs):raise RuntimeError('intentional interruption before M4')
        patch.setattr(w,'run_metrics',fail)
        with pytest.raises(w.WorkflowError,match='intentional interruption'):w.execute_workflow(**interrupted)
    assert not (root/'resumed/workflow_manifest.json').exists()
    resumed=w.resume_workflow(**interrupted)
    assert 'analysis' in resumed['reused_stages'] and len(resumed['executed_stages'])==7
    evidence['resumed']=validate(root/'resumed')
    assert science(root/'resumed')==expected
    analyze={k:v for k,v in options.items() if k not in ('r1','r2')}
    analyze.update(mode='analyze',demux_root=root/'clean/demux',output=root/'analyze')
    external_before={str(p.relative_to(root/'clean/demux')):w.sha(p) for p in (root/'clean/demux').rglob('*') if p.is_file()}
    w.execute_workflow(**analyze,argv=['m7-integration','analyze'])
    evidence['analyze']=validate(root/'analyze')
    assert science(root/'analyze')==expected
    assert external_before=={str(p.relative_to(root/'clean/demux')):w.sha(p) for p in (root/'clean/demux').rglob('*') if p.is_file()}
    evidence.update(completed_resume_execution_calls=0,clean_resumed_science_equal=True,
        run_analyze_science_equal=True,external_archive_unchanged=True)
    (root/'qualification.json').write_text(json.dumps(evidence,indent=2,sort_keys=True)+'\n')
