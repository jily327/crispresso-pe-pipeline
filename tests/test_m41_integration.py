"""Real 2.3.4 ambiguous reads, preprocessing attrition, discarded rows and exits."""

import csv
import gzip
import io
import json
import os
import shlex
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

from peanalyzer.analysis_fastq import prepare_analysis_fastqs
from peanalyzer.backend.metrics import parse_child
from peanalyzer.backend.pooled import Executable, resolve_executable
from peanalyzer.demux import demultiplex
from peanalyzer.metrics import run_metrics
from peanalyzer.metrics.production import RUNTIME_DIGEST
from peanalyzer.metrics.products import aligned_products
from peanalyzer.remediation import pair
from peanalyzer.routing import route_analysis
from peanalyzer.schemas import Config
from peanalyzer.synthetic_routing import write_challenges

pytestmark = [pytest.mark.crispresso_integration,
              pytest.mark.skipif(os.environ.get('M41_INTEGRATION') != '1', reason='set M41_INTEGRATION=1 with actual pinned Core')]


def prepare_variant(root, kind):
    root.mkdir(parents=True)
    targets, _ = write_challenges(root/'synthetic')
    sequence = targets[0].wt_sequence
    if kind == 'ambiguous':
        third = next(b for b in 'ACGT' if b not in (sequence[122], targets[0].prime_edited_sequence[122]))
        sequence = sequence[:122] + third + sequence[123:]
    records = pair(sequence, identifier='m41_' + kind, length=150 if kind=='ambiguous' else 100)
    prefixes = ('GCTTGCGTTGGAGTGAGTACGGTGTGC', 'CTGTGTAGTGAGTTGGATGCTGGATGG')
    for mate, record in enumerate(records, 1):
        with gzip.open(root/f'synthetic/raw_R{mate}.fastq.gz', 'ab') as handle:
            handle.write(record.header + prefixes[mate-1].encode() + record.sequence_line +
                         record.plus + b'I'*27 + record.quality_line)
    demultiplex(r1=root/'synthetic/raw_R1.fastq.gz', r2=root/'synthetic/raw_R2.fastq.gz',
                samples_path=root/'synthetic/samples.csv', config=Config(schema_version=1), output=root/'demux')
    prepare_analysis_fastqs(root/'demux', root/'analysis')
    route_analysis(root/'analysis', '1B', targets, root/'routing')
    (root/'fixture.json').write_text(json.dumps(dict(kind=kind, added_pair_id='m41_'+kind,
        added_sequence=sequence, mate_length=len(records[0].sequence), original_pairs=125, prepared_pairs=126), indent=2)+'\n')
    return targets


@pytest.fixture(scope='module', params=['ambiguous', 'preprocessing'])
def variant(request, tmp_path_factory):
    base = Path(os.environ['M41_RESULTS_DIR']) if 'M41_RESULTS_DIR' in os.environ else tmp_path_factory.mktemp('m41-real')
    root = base/request.param
    targets = prepare_variant(root, request.param)
    core = resolve_executable(os.environ.get('M3_CORE_EXECUTABLE', 'CRISPResso'))
    result = run_metrics(analysis_root=root/'analysis', sample_id='1B', targets=targets,
        analysis_id='m41-'+request.param, output=root/'metrics', routing_root=root/'routing', core=core)
    return request.param, root, targets, result, core


def test_actual_ambiguous_and_preprocessing_native_partition(variant):
    kind, _, _, result, _ = variant
    native = result.target_metrics.target_crispresso_native_pe
    assert native.status == 'REPORTABLE' and result.eligibility.anchor_invariant
    assert native.backend_input_reads == 126
    expected = (126, 0, 106, 105, 1) if kind=='ambiguous' else (125, 1, 105, 105, 0)
    assert (native.reads_after_preprocessing, native.preprocessing_count_delta, native.aligned_reads,
            native.ordinary_classified_aligned_reads, native.ambiguous_aligned_reads) == expected
    assert native.discarded_aligned_reads == 0 and native.unaligned_reads == 20
    assert (native.numerator, native.denominator) == (30, expected[2])
    for parsed in result.anchor_evidence['backend_metrics'].values():
        assert parsed['native']['denominator'] == parsed['mapping_statistics']['READS ALIGNED']


def test_actual_products_remain_on_their_own_populations(variant):
    kind, _, _, result, _ = variant
    exact = result.target_metrics.total_precise_pe
    assert exact.status == 'REPORTABLE' and (exact.numerator, exact.denominator) == (20, 55)
    assert exact.population_input_reads == exact.products.classification_input_reads == 126
    assert exact.products.denominator_exclusions == 71
    copy = result.copies['copy1']
    assert copy.native.status == copy.precise.status == 'REPORTABLE'
    assert copy.native.backend_input_reads == 46
    assert (copy.precise.numerator, copy.precise.denominator) == (12, 30)
    assert copy.precise.products.classification_input_reads == (43 if kind=='ambiguous' else 42)
    assert copy.native.ambiguous_aligned_reads == (1 if kind=='ambiguous' else 0)
    assert copy.precise.products.denominator_exclusions == (13 if kind=='ambiguous' else 12)


def test_actual_allele_categories_and_discarded_reconciliation(variant):
    kind, root, targets, result, core = variant
    child = root/'metrics/comparator/copy1/output/CRISPResso_on_unrouted'
    info = json.loads((child/'CRISPResso2_info.json').read_text())
    with zipfile.ZipFile(child/info['running_info']['allele_frequency_table_zip_filename']) as archive:
        rows = list(csv.DictReader(io.StringIO(archive.read(info['running_info']['allele_frequency_table_filename']).decode()), delimiter='\t'))
    ambiguous = sum(int(r['#Reads']) for r in rows if r['Reference_Name'].startswith('AMBIGUOUS_'))
    assert ambiguous == (1 if kind=='ambiguous' else 0)
    # Qualification-only backend option: production target definitions are unchanged.
    execution = json.loads((root/'metrics/comparator/copy1/execution.json').read_text())
    work = root/'discarded'; work.mkdir()
    for mate in (1, 2):
        shutil.copyfile(root/f'metrics/comparator/copy1/input_R{mate}.fastq.gz', work/f'input_R{mate}.fastq.gz')
    sequence = targets[0].wt_sequence
    deleted = sequence[:145] + sequence[146:]
    for mate, record in enumerate(pair(deleted, identifier='m41_window_deletion'), 1):
        with gzip.open(work/f'input_R{mate}.fastq.gz', 'ab') as handle:
            handle.write(record.to_bytes())
    argv = execution['argv'] + ['--discard_indel_reads']
    with (work/'stdout.txt').open('w') as out, (work/'stderr.txt').open('w') as err:
        run = subprocess.run(argv, cwd=work, stdout=out, stderr=err, check=False)
    assert run.returncode == 0
    parsed = parse_child(work/'output/CRISPResso_on_unrouted', routed_pairs=127, one_input_record_per_pair=True)
    native = parsed['native']
    assert native['discarded_aligned_reads'] > 0
    assert native['ambiguous_aligned_reads'] == ambiguous
    assert native['aligned_reads'] == sum(native[k] for k in
        ('ordinary_classified_aligned_reads', 'ambiguous_aligned_reads', 'discarded_aligned_reads'))
    products = aligned_products(work/'output/CRISPResso_on_unrouted', targets[0])
    assert products.classification_input_reads == native['aligned_reads']
    assert products.unresolved_unassessable >= native['discarded_aligned_reads'] + ambiguous
    (work/'evidence.json').write_text(json.dumps(dict(argv=argv, return_code=run.returncode,
        runtime_digest=RUNTIME_DIGEST, added_product=deleted, metrics=parsed, products=products.model_dump()), indent=2)+'\n')


def test_actual_nonzero_core_exit_is_preserved_for_every_anchor(variant):
    _, root, targets, _, core = variant
    wrapper = root/'invalid_core'
    wrapper.write_text('#!/bin/sh\nexec '+shlex.quote(core.path)+' "$@" --m41-invalid-option\n')
    wrapper.chmod(0o755)
    result = run_metrics(analysis_root=root/'analysis', sample_id='1B', targets=targets,
        analysis_id='real-nonzero-exit', output=root/'failed_metrics',
        core=Executable(str(wrapper), '2.3.4', core.probe))
    assert result.target_metrics.target_crispresso_native_pe.reason_codes == ['BACKEND_EXECUTION_FAILED']
    assert result.target_metrics.total_precise_pe.status == 'REPORTABLE'
    assert result.anchor_evidence['failures'] == dict(copy1='BACKEND_EXECUTION_FAILED', copy2='BACKEND_EXECUTION_FAILED')
    for copy in ('copy1', 'copy2'):
        execution = json.loads((root/f'failed_metrics/comparator/{copy}/execution.json').read_text())
        assert execution['return_code'] != 0 and execution['reason_code'] == 'BACKEND_EXECUTION_FAILED'


@pytest.mark.parametrize('kind',['nonexact_only','routing_blocked'])
def test_actual_target_families_remain_independent_of_exact_and_routing_gates(tmp_path,kind):
    from peanalyzer.remediation import indel_designs, panel
    base = Path(os.environ['M41_RESULTS_DIR']) if 'M41_RESULTS_DIR' in os.environ else tmp_path
    root = base/kind;root.mkdir(parents=True)
    targets = panel() if kind=='nonexact_only' else next(t for d,t in indel_designs() if d['id']=='deletion_30_seed11')
    sequences=[]
    for target in targets:
        for state,seq in [('WT',target.wt_sequence),('PE',target.prime_edited_sequence)]:
            if kind=='nonexact_only': seq=seq[:55]+('A' if seq[55]!='A' else 'C')+seq[56:]
            for i in range(10): sequences.append((f'{target.copy_name}_{state}_{i}',seq))
    prefixes=('GCTTGCGTTGGAGTGAGTACGGTGTGC','CTGTGTAGTGAGTTGGATGCTGGATGG')
    for mate in (1,2):
        with gzip.open(root/f'raw_R{mate}.fastq.gz','wb') as handle:
            for identifier,seq in sequences:
                record=pair(seq,identifier=identifier)[mate-1]
                handle.write(record.header+prefixes[mate-1].encode()+record.sequence_line+record.plus+b'I'*27+record.quality_line)
    (root/'samples.csv').write_text('sample_name,barcode_id,forward_barcode_id,reverse_barcode_id\nsynthetic,1B,F1,RB\n')
    demultiplex(r1=root/'raw_R1.fastq.gz',r2=root/'raw_R2.fastq.gz',samples_path=root/'samples.csv',
                config=Config(schema_version=1),output=root/'demux')
    prepare_analysis_fastqs(root/'demux',root/'analysis')
    result=run_metrics(analysis_root=root/'analysis',sample_id='1B',targets=targets,analysis_id='m41-'+kind,
        output=root/'metrics',core=resolve_executable(os.environ.get('M3_CORE_EXECUTABLE','CRISPResso')))
    native,exact=result.target_metrics.target_crispresso_native_pe,result.target_metrics.total_precise_pe
    assert native.status=='REPORTABLE' and (native.numerator,native.denominator)==(20,40)
    assert exact.population_input_reads==exact.products.classification_input_reads==40
    if kind=='nonexact_only':
        assert exact.status=='NOT_ASSESSABLE' and exact.numerator is exact.denominator is None
        assert exact.reason_codes==['ZERO_EXACT_DENOMINATOR']
    else:
        assert exact.status=='REPORTABLE' and (exact.numerator,exact.denominator)==(20,40)
        assert result.eligibility.routing_geometry_status=='BLOCKED'
        assert all('UNSUPPORTED_ROUTING_GEOMETRY' in c.native.reason_codes for c in result.copies.values())
