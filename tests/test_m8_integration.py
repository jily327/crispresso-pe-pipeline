"""Real pinned Core nuclease cases, including both TIGR cut-boundary insertions."""
import json
import os
from pathlib import Path
import pytest
from m8_fixtures import fixture,target,CASES
from peanalyzer.analysis_fastq import prepare_analysis_fastqs,PreparationConfig
from peanalyzer.backend.pooled import resolve_executable
from peanalyzer.demux import demultiplex
from peanalyzer.nuclease.backend import run_nuclease_metrics
from peanalyzer.validation import load_config
from peanalyzer import workflow as w

pytestmark=[pytest.mark.crispresso_integration,
    pytest.mark.skipif(os.environ.get('M8_INTEGRATION')!='1',reason='requires qualified M8 Core runtime')]


def root(tmp_path,name):
    return Path(os.environ.get('M8_RESULTS_DIR',tmp_path/'m8'))/name


@pytest.mark.parametrize('case',list(CASES))
def test_authoritative_nuclease_cases(tmp_path,case):
    p=root(tmp_path,case);options=fixture(p/'inputs',[[(case,12)]])
    demultiplex(r1=options['r1'],r2=options['r2'],samples_path=options['samples'],config=load_config(options['config']),output=p/'demux')
    prepare_analysis_fastqs(p/'demux',p/'analysis',PreparationConfig(r1_analysis_trim_5p=8,r2_analysis_trim_5p=8))
    result=run_nuclease_metrics(analysis_root=p/'analysis',sample_id='bc001',targets=[target()],analysis_id=case,
        output=p/'metrics',core=resolve_executable(os.environ.get('M3_CORE_EXECUTABLE','CRISPResso')),runtime_digest=options['runtime_digest'])
    expected=CASES[case][1]
    assert result.backend_input_reads==result.aligned_reads==12 and result.unaligned_reads==0
    assert sum(a.reads for a in result.alleles)==12
    assert {(a.n_inserted,a.n_deleted,a.n_mutated) for a in result.alleles}=={expected}
    assert result.metrics['indel_fraction'].numerator==12*bool(expected[0] or expected[1])
    assert result.metrics['substitution_containing_fraction'].numerator==12*bool(expected[2])
    if case=='net_zero':assert result.fraction_of_indel_reads_by_net_size['0'].numerator==12
    argv=result.provenance.execution['argv']
    assert not any('prime_edit' in a or 'guide_seq' in a or 'ignore_substitutions' in a or 'legacy_insertion' in a for a in argv)
    (p/'oracle.json').write_text(json.dumps(dict(case=case,expected=list(expected),observed=[list(expected)],
        primary=result.metrics['indel_fraction'].model_dump(),counts=result.class_counts,
        aligned=result.aligned_reads,backend_input=result.backend_input_reads,window=target().window,
        current_insertion_mode=True,passed=True),indent=2)+'\n')


def test_real_nuclease_workflow_and_resume(tmp_path,monkeypatch):
    p=root(tmp_path,'workflow');options=fixture(p/'inputs');options.update(output=p/'run',
        crispresso=os.environ.get('M3_CORE_EXECUTABLE','CRISPResso'),contrasts=p/'inputs/contrasts.yaml',title='Nuclease synthetic qualification')
    import peanalyzer.metrics.products as products
    def forbidden(*a,**k):pytest.fail('PE scientific executor called in nuclease mode')
    with monkeypatch.context() as patch:
        patch.setattr(w,'route_analysis',forbidden);patch.setattr(w,'geometry',forbidden);patch.setattr(w,'run_metrics',forbidden)
        patch.setattr(products,'prepared_products',forbidden)
        completed=w.execute_workflow(**options)
    assert len(completed['executed_stages'])==14
    w.verify_workflow_output(options['output'])
    result=json.loads((options['output']/'statistics/result.json').read_text())
    assert result['analysis_mode']=='indel_nuclease'
    primary=[r for r in result['observations'] if r['metric_name']=='indel_fraction']
    assert [r['numerator'] for r in primary]==[2,4,14,16]
    contrast=result['contrasts'][0]
    assert contrast['used_group_a_count']==contrast['used_group_b_count']==2
    assert contrast['difference_in_biological_sample_fraction']==0.6
    assert contrast['p_value']==contrast['q_value']==1/3
    before=(options['output']/'workflow_manifest.json').read_bytes()
    with monkeypatch.context() as patch:
        for name in ('demultiplex','prepare_analysis_fastqs','route_analysis','run_metrics','run_nuclease_metrics','summarize','stats','generate_report'):
            patch.setattr(w,name,forbidden)
        resumed=w.resume_workflow(**options)
    assert resumed['executed_stages']==[] and len(resumed['reused_stages'])==14
    assert (options['output']/'workflow_manifest.json').read_bytes()==before
    for family,expected in [('report',1),('statistics',2)]:
        with monkeypatch.context() as patch:
            patch.setattr(w,'run_nuclease_metrics',forbidden)
            force=w.resume_workflow(**options,force=[family])
        assert len(force['executed_stages'])==expected
    with pytest.raises(w.WorkflowError,match='STALE_STAGE_IDENTITY'):
        w.resume_workflow(**dict(options,title='Changed'))
    w.resume_workflow(**dict(options,title='Changed'),force=['report'])
    # A new analyze workspace reuses the immutable verified demux archive.
    analyze={k:v for k,v in options.items() if k not in ('r1','r2','contrasts')}
    analyze.update(mode='analyze',demux_root=p/'run/demux',output=p/'analyze')
    w.execute_workflow(**analyze);w.verify_workflow_output(p/'analyze')
    summarized=json.loads((p/'analyze/statistics/result.json').read_text())
    assert not summarized['contrasts']
    assert [(r['sample_id'],r['metric_name'],r['numerator'],r['denominator']) for r in summarized['observations']]==[(r['sample_id'],r['metric_name'],r['numerator'],r['denominator']) for r in result['observations']]
    assert (p/'run/report/source/result.json').read_bytes()==(p/'run/statistics/result.json').read_bytes()
    (p/'oracle.json').write_text(json.dumps(dict(passed=True,samples=4,conditions=2,biological_replicates_per_condition=2,
        primary_counts=[[n,20] for n in (2,4,14,16)],contrast=contrast,
        zero_execution_resume=True,report_force_only=True,statistics_force_no_backend=True,
        run_analyze_counts_equal=True,precise_edit_executors_called=0),indent=2)+'\n')


def test_generic_window_at_amplicon_ends_without_guide(tmp_path):
    p=root(tmp_path,'generic_boundary');options=fixture(p/'inputs',[[('WT',12)]])
    demultiplex(r1=options['r1'],r2=options['r2'],samples_path=options['samples'],config=load_config(options['config']),output=p/'demux')
    prepare_analysis_fastqs(p/'demux',p/'analysis',PreparationConfig(r1_analysis_trim_5p=8,r2_analysis_trim_5p=8))
    t=target(nuclease_profile=None,tigr_target_sequence=None,quantification_window_coordinates='0-0_239-239')
    result=run_nuclease_metrics(analysis_root=p/'analysis',sample_id='bc001',targets=[t],analysis_id='generic_boundary',
        output=p/'metrics',core=resolve_executable(os.environ.get('M3_CORE_EXECUTABLE','CRISPResso')),runtime_digest=options['runtime_digest'])
    assert result.metrics['unmodified_fraction'].numerator==result.aligned_reads==12
    assert result.provenance.scientific_identity['resolved_window']['intervals']==[[0,0],[239,239]]
    assert result.provenance.execution['resolved_backend_arguments']['guide_seq']==''
    (p/'oracle.json').write_text(json.dumps(dict(passed=True,aligned=12,unmodified=12,coordinates='0-0_239-239',guide=None,derivation='explicit'),indent=2)+'\n')
