"""Actual Core, prepared-contract, explicit-routing and metric-parity qualification."""

import os
from pathlib import Path

import pytest

from peanalyzer.backend.pooled import resolve_executable
from peanalyzer.backend.pooled import run_pooled_diagnostic, BackendError
from peanalyzer.backend.synthetic import design
from peanalyzer.schemas import Target, reverse_complement
from peanalyzer.qualification import qualify

pytestmark=[pytest.mark.crispresso_integration,pytest.mark.skipif(os.environ.get('M31_INTEGRATION')!='1',reason='set M31_INTEGRATION=1 with external 2.3.4 runtime')]


@pytest.fixture(scope='module')
def qualified(tmp_path_factory):
    root=Path(os.environ['M31_RESULTS_DIR']) if 'M31_RESULTS_DIR' in os.environ else tmp_path_factory.mktemp('m31')/'run'
    core=resolve_executable(os.environ.get('M3_CORE_EXECUTABLE','CRISPResso'))
    runtime={'image_digest':os.environ.get('M31_RUNTIME_IMAGE'),'identity_source':'explicit test environment; see external image inspection evidence'}
    result=qualify(root,core=core,runtime_identity=runtime)
    result['test_output_root']=str(root)
    return result


def test_real_explicit_router_quarantines_ambiguity(qualified):
    assert qualified['routing_gate']=='PASS'
    assert (qualified['input_pairs'],qualified['assigned_pairs'],qualified['quarantined_pairs'])==(125,75,50)
    assert qualified['cross_routed_ids']==qualified['unsafe_assigned_ids']==[]


def test_actual_core_native_exact_and_attrition(qualified):
    for copy,n,a,u,p,e,d in [('copy1',45,42,3,18,12,30),('copy2',30,28,2,12,8,20)]:
        result=qualified['backend_metrics'][copy]
        assert (result['native']['backend_input_reads'],result['native']['aligned_reads'],result['native']['unaligned_reads'])==(n,a,u)
        assert (result['native']['numerator'],result['native']['denominator'])==(p,a)
        assert (result['exact_haplotype']['numerator'],result['exact_haplotype']['denominator'])==(e,d)


def test_quality_order_and_wt_pe_retention(qualified):
    assert qualified['reference_order_invariant']
    assert all(not v['unsafe_assignments'] for v in qualified['quality_sensitivity'].values())
    assert qualified['editing_state_retention']['WT']==qualified['editing_state_retention']['precise_PE']=={'assigned':20,'total':20}
    assert (qualified['copy_agnostic_exact']['numerator'],qualified['copy_agnostic_exact']['denominator'])==(20,55)


def test_reverse_only_spacer_upstream_rejection_is_not_success(qualified,tmp_path):
    root=Path(qualified['test_output_root'])
    values=[Target.model_validate(t) for t in design()['targets']]
    values=[t.model_copy(update={'pegRNA_spacer':reverse_complement(t.pegRNA_spacer)}) for t in values]
    with pytest.raises(BackendError,match='COMMAND_FAILED'):
        run_pooled_diagnostic(r1=root/'analysis/03_analysis_fastq/1B_R1.analysis.fastq.gz',r2=root/'analysis/03_analysis_fastq/1B_R2.analysis.fastq.gz',
            targets=values,output=root/'orientation_rejection',core=resolve_executable(os.environ.get('M3_CORE_EXECUTABLE','CRISPResso')),
            pooled=resolve_executable(os.environ.get('M3_POOLED_EXECUTABLE','CRISPRessoPooled')),
            child_core_command=os.environ.get('M3_CHILD_CORE_COMMAND'),diagnostic_test_unsupported_guide=True)
    assert "3'->5' order" in (root/'orientation_rejection/stderr.log').read_text()
