"""Actual conventional Core anchor invariance, not pooled/confident surrogates."""

import os
from pathlib import Path
import pytest

from peanalyzer.analysis_fastq import prepare_analysis_fastqs
from peanalyzer.backend.comparator import run_comparator
from peanalyzer.backend.pooled import resolve_executable
from peanalyzer.backend.synthetic import write_synthetic_run
from peanalyzer.demux import demultiplex
from peanalyzer.synthetic_routing import write_challenges
from peanalyzer.schemas import Config

pytestmark=[pytest.mark.crispresso_integration,
            pytest.mark.skipif(os.environ.get('M311_INTEGRATION')!='1',reason='set M311_INTEGRATION=1 with actual pinned Core')]


@pytest.fixture(scope='module',params=['m3','m31'])
def comparator(request,tmp_path_factory):
    base=Path(os.environ['M311_RESULTS_DIR']) if 'M311_RESULTS_DIR' in os.environ else tmp_path_factory.mktemp('m311-comparators')
    root=base/request.param
    root.mkdir(parents=True,exist_ok=False)
    writer=write_synthetic_run if request.param=='m3' else write_challenges
    targets,_=writer(root/'synthetic')
    demultiplex(r1=root/'synthetic/raw_R1.fastq.gz',r2=root/'synthetic/raw_R2.fastq.gz',
                samples_path=root/'synthetic/samples.csv',config=Config(schema_version=1),output=root/'demux')
    prepare_analysis_fastqs(root/'demux',root/'analysis')
    result=run_comparator(root/'analysis','1B',targets,root/'comparator',
                          resolve_executable(os.environ.get('M3_CORE_EXECUTABLE','CRISPResso')),
                          runtime_identity={'image_digest':os.environ.get('M31_RUNTIME_IMAGE')})
    return request.param,result


def test_actual_all_read_native_counts_for_every_anchor(comparator):
    name,result=comparator
    expected=(350,330,20,120,330) if name=='m3' else (125,105,20,30,105)
    assert set(result['anchors'])=={'copy1','copy2'}
    for row in result['anchors'].values():
        assert tuple(row[k] for k in ('backend_input_reads','aligned_reads','unaligned_reads','numerator','denominator'))==expected


def test_actual_comparator_eligibility_and_anchor_invariance(comparator):
    _,result=comparator
    assert result['anchor_invariant']
    assert result['status']=='SUPPORTED_IN_TESTED_FIXTURE'
    assert result['scope']=='qualification_only_all_prepared_pairs_not_confident_copy_cohort'
    for metrics in result['backend_metrics'].values():
        stats=metrics['alignment_counters']
        assert stats['N_TOT_READS']==sum(stats[k] for k in ('N_CACHED_ALN','N_COMPUTED_ALN','N_CACHED_NOTALN','N_COMPUTED_NOTALN'))
