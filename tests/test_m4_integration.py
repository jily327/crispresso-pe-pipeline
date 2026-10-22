"""Production M4 API exercised against actual digest-pinned Core 2.3.4."""

import os
from pathlib import Path

import pytest

from peanalyzer.analysis_fastq import prepare_analysis_fastqs
from peanalyzer.backend.pooled import resolve_executable
from peanalyzer.backend.synthetic import write_synthetic_run
from peanalyzer.demux import demultiplex
from peanalyzer.metrics import run_metrics, MetricResult
from peanalyzer.metrics.production import RUNTIME_DIGEST
from peanalyzer.qualification import qualify
from peanalyzer.remediation import panel
from peanalyzer.schemas import Config

pytestmark = [pytest.mark.crispresso_integration,
              pytest.mark.skipif(os.environ.get('M4_INTEGRATION') != '1', reason='set M4_INTEGRATION=1 with actual Core 2.3.4')]


@pytest.fixture(scope='module', params=['m31', 'm3'])
def production(request, tmp_path_factory):
    base = Path(os.environ['M4_RESULTS_DIR']) if 'M4_RESULTS_DIR' in os.environ else tmp_path_factory.mktemp('m4-real')
    root = base/request.param
    if request.param == 'm31':
        qualify(root)
        targets, routing = panel(), root/'routing'
    else:
        root.mkdir(parents=True, exist_ok=False)
        targets, _ = write_synthetic_run(root/'synthetic')
        demultiplex(r1=root/'synthetic/raw_R1.fastq.gz', r2=root/'synthetic/raw_R2.fastq.gz',
                    samples_path=root/'synthetic/samples.csv', config=Config(schema_version=1), output=root/'demux')
        prepare_analysis_fastqs(root/'demux', root/'analysis')
        # Historical Pooled cohorts remain unsafe and never become M4 copy cohorts.
        routing = None
    result = run_metrics(analysis_root=root/'analysis', sample_id='1B', targets=targets,
                         analysis_id=request.param+'-m4-qualification', output=root/'m4', routing_root=routing,
                         core=resolve_executable(os.environ.get('M3_CORE_EXECUTABLE', 'CRISPResso')),
                         runtime_digest=RUNTIME_DIGEST)
    return request.param, root, result


def test_actual_target_native_and_exact_populations(production):
    name, root, result = production
    native, exact = result.target_metrics.target_crispresso_native_pe, result.target_metrics.total_precise_pe
    expected = (125,105,20,30,105) if name=='m31' else (350,330,20,120,330)
    assert (native.backend_input_reads,native.aligned_reads,native.unaligned_reads,native.numerator,native.denominator)==expected
    assert result.eligibility.anchor_invariant and native.status=='REPORTABLE'
    if name=='m31': assert (exact.numerator,exact.denominator)==(20,55)
    assert native.population_id==exact.population_id and exact.population_input_reads==expected[0]
    assert MetricResult.model_validate_json((root/'m4/result.json').read_text())==result


def test_actual_copy_metrics_only_admit_verified_cohorts(production):
    name, _, result = production
    if name=='m3':
        assert all(c.copy_metric_status=='BLOCKED' for c in result.copies.values())
        return
    for copy,n,a,u,p,e,d in [('copy1',45,42,3,18,12,30),('copy2',30,28,2,12,8,20)]:
        row=result.copies[copy]
        assert row.copy_metric_status=='REPORTABLE'
        assert (row.native.confident_input_reads,row.native.backend_input_reads,row.native.aligned_reads,row.native.unaligned_reads)==(n,n,a,u)
        assert (row.native.numerator,row.native.denominator)==(p,a)
        assert (row.precise.numerator,row.precise.denominator)==(e,d)
    assert (result.qc.routing_assigned_reads,result.qc.routing_quarantined_reads)==(75,50)
