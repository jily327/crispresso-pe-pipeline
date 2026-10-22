"""M4 gates exercised through verified archives and real committed backend tables.

Rehydration below is offline fixture construction, not a new backend execution.
The separate integration family executes run_metrics with actual Core 2.3.4.
"""

import json
import gzip
import shutil
import zipfile
from pathlib import Path
from importlib.resources import files

import pytest
from pydantic import ValidationError

from peanalyzer.backend.metrics import parse_child
from peanalyzer.demux_verify import sha256_file
from peanalyzer.metrics import MetricResult, collect_metrics
from peanalyzer.metrics.models import ProductCounts
from peanalyzer.metrics.production import RUNTIME_DIGEST, digest, metric
from peanalyzer.metrics.products import prepared_products, contradictory_products
from peanalyzer.qualification import qualify
from peanalyzer.remediation import panel, pair
from peanalyzer.schemas import Target

EVIDENCE = Path(__file__).resolve().parents[1] / 'docs/validation'


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2)+'\n')


def hydrate(source, destination, inputs, lineage_key, lineage_hash, input_root, *, comparator):
    """Restore ZIP from committed text and bind a test execution to generated inputs."""
    name = 'unrouted' if comparator else 'confident'
    child = destination / f'output/CRISPResso_on_{name}'
    child.mkdir(parents=True)
    for filename in ('CRISPResso2_info.json', 'CRISPResso_mapping_statistics.txt',
                     'CRISPResso_quantification_of_editing_frequency.txt'):
        shutil.copyfile(source/filename, child/filename)
    running = json.loads((child/'CRISPResso2_info.json').read_text())['running_info']
    with zipfile.ZipFile(child/running['allele_frequency_table_zip_filename'], 'w') as archive:
        archive.write(source/'alleles.txt', running['allele_frequency_table_filename'])
    execution = json.loads((source/'execution.json').read_text())
    execution.update(inputs=inputs, **{lineage_key:lineage_hash}, runtime_identity={'image_digest':RUNTIME_DIGEST})
    write_json(destination/'execution.json', execution)
    for mate in (1, 2):
        shutil.copyfile(input_root/inputs['files'][f'r{mate}']['path'], destination/f'input_R{mate}.fastq.gz')


@pytest.fixture(scope='module')
def archive(tmp_path_factory):
    root = tmp_path_factory.mktemp('m4-offline')/'run'
    qualify(root)
    analysis = json.loads((root/'analysis/analysis_manifest.json').read_text())
    routing = json.loads((root/'routing/routing_manifest.json').read_text())
    for copy in ('copy1', 'copy2'):
        hydrate(EVIDENCE/f'm312/comparators/m31/{copy}', root/f'comparator/{copy}',
                analysis['samples']['1B'], 'analysis_manifest_sha256',
                sha256_file(root/'analysis/analysis_manifest.json'), root/'analysis', comparator=True)
        hydrate(EVIDENCE/f'm311/confident_core/{copy}', root/f'copies/{copy}',
                routing['cohorts'][copy], 'routing_manifest_sha256',
                sha256_file(root/'routing/routing_manifest.json'), root/'routing', comparator=False)
    return root


def collect(root, **overrides):
    args = dict(analysis_root=root/'analysis', sample_id='1B', targets=panel(), analysis_id='offline-regression',
                comparator_root=root/'comparator', routing_root=root/'routing',
                copy_roots={c:root/f'copies/{c}' for c in ('copy1', 'copy2')}, runtime_digest=RUNTIME_DIGEST)
    args.update(overrides)
    return collect_metrics(**args)


def test_historical_m31_production_result_and_schema(archive):
    result = collect(archive)
    assert result.eligibility.target_metric_status == 'REPORTABLE'
    assert result.eligibility.anchor_invariant
    native, exact = result.target_metrics.target_crispresso_native_pe, result.target_metrics.total_precise_pe
    assert (native.numerator, native.denominator) == (30, 105)
    assert (exact.numerator, exact.denominator) == (20, 55)
    assert (native.backend_input_reads, native.aligned_reads, native.unaligned_reads) == (125, 105, 20)
    assert exact.population_denominator_exclusions == 70
    assert exact.backend_counts_role == 'parallel_native_analysis'
    for copy, n, a, u, p, e, d in [('copy1',45,42,3,18,12,30), ('copy2',30,28,2,12,8,20)]:
        row = result.copies[copy]
        assert row.copy_metric_status == 'REPORTABLE'
        assert (row.native.population_input_reads, row.native.backend_input_reads, row.native.aligned_reads,
                row.native.unaligned_reads) == (n,n,a,u)
        assert (row.native.numerator, row.native.denominator) == (p,a)
        assert (row.precise.numerator, row.precise.denominator) == (e,d)
        assert row.precise.products.pe_plus_extra_change == (6 if copy=='copy1' else 4)
        assert row.precise.population_denominator_exclusions == n-d
        assert row.native.population_id != native.population_id
        assert row.native.routing_conditioned and row.precise.routing_conditioned
    assert sum(c.native.numerator for c in result.copies.values()) == 30
    assert sum(c.native.denominator for c in result.copies.values()) == 70
    assert sum(c.precise.numerator for c in result.copies.values()) == 20
    assert sum(c.precise.denominator for c in result.copies.values()) == 50
    assert (result.qc.routing_assigned_reads, result.qc.routing_quarantined_reads) == (75,50)
    assert result.qc.routing_quarantine_fraction.model_dump() == {'numerator':50, 'denominator':125}
    assert MetricResult.model_validate_json(result.model_dump_json()) == result
    assert result.provenance.artifacts


def test_installed_result_schema_matches_executable_models():
    packaged=json.loads(files('peanalyzer.metrics').joinpath('result.schema.json').read_text())
    assert packaged==MetricResult.model_json_schema()
    assert files('peanalyzer').joinpath('barcode_sets/qi_hitom_v1.csv').is_file()
    assert files('peanalyzer').joinpath('profiles/qi_hitom_v1.yaml').is_file()


def mutate_info(root, change, *, copy=False):
    path = root/('copies/copy1/output/CRISPResso_on_confident' if copy else
                 'comparator/copy2/output/CRISPResso_on_unrouted')/'CRISPResso2_info.json'
    data=json.loads(path.read_text());change(data);write_json(path,data)


@pytest.mark.parametrize('attack,code',[
    ('missing_anchor','MISSING_ANCHOR_RESULT'),
    ('malformed_window','AUTHORITATIVE_QUANTIFICATION_WINDOW_INVALID'),
    ('empty_window','EMPTY_AUTHORITATIVE_QUANTIFICATION_WINDOW'),
    ('diagnostic_window','DIAGNOSTIC_IN_AUTHORITATIVE_QUANTIFICATION_WINDOW'),
    ('counter_mismatch','BACKEND_COUNTER_RECONCILIATION_FAILED'),
    ('missing_backend','MISSING_INCOMPLETE_BACKEND_METRICS'),
    ('missing_provenance','MISSING_REQUIRED_PROVENANCE'),
    ('null_software','MISSING_REQUIRED_PROVENANCE'),
    ('null_execution','MISSING_REQUIRED_PROVENANCE'),
    ('wrong_input','BACKEND_INPUT_LINEAGE_MISMATCH'),
    ('wrong_guide','BACKEND_CONFIGURATION_MISMATCH'),
    ('wrong_reference','BACKEND_REFERENCE_MISMATCH'),
])
def test_native_artifact_negative_gates(archive,tmp_path,attack,code):
    root=tmp_path/'run';shutil.copytree(archive,root)
    if attack=='missing_anchor': shutil.rmtree(root/'comparator/copy2')
    elif attack=='missing_backend': (root/'comparator/copy2/output/CRISPResso_on_unrouted/CRISPResso2_info.json').unlink()
    elif attack in ('malformed_window','empty_window','diagnostic_window'):
        value = {'_type':'np.ndarray','value':[True]} if attack=='malformed_window' else [] if attack=='empty_window' else [40]
        mutate_info(root,lambda d:d['results']['refs']['Reference'].update(include_idxs=value))
    elif attack=='counter_mismatch': mutate_info(root,lambda d:d['running_info']['alignment_stats'].update(N_TOT_READS=999))
    elif attack=='wrong_reference': mutate_info(root,lambda d:d['results']['refs']['Reference'].update(sequence='ACGT'))
    elif attack=='wrong_input': (root/'comparator/copy2/input_R1.fastq.gz').write_bytes(b'bad')
    else:
        path=root/'comparator/copy2/execution.json';data=json.loads(path.read_text())
        if attack=='missing_provenance': data.pop('runtime_identity')
        elif attack=='null_software': data['software']=None
        elif attack=='null_execution': data=None
        else: data['argv'][data['argv'].index('--prime_editing_pegRNA_spacer_seq')+1]='AAAA'
        write_json(path,data)
    result=collect(root)
    native=result.target_metrics.target_crispresso_native_pe
    assert native.status=='BLOCKED' and code in native.reason_codes
    assert native.numerator is native.denominator is None
    assert result.target_metrics.total_precise_pe.status=='REPORTABLE'


def test_empirical_anchor_difference_from_independently_reconciled_tables(archive,tmp_path):
    root=tmp_path/'run';shutil.copytree(archive,root)
    child=root/'comparator/copy2/output/CRISPResso_on_unrouted'
    mutate_info(root,lambda d:d['results']['alignment_stats']['counts_total'].update({'Reference':74,'Prime-edited':31}))
    path=child/'CRISPResso_quantification_of_editing_frequency.txt'
    lines=path.read_text().splitlines();header=lines[0].split('\t');idx=header.index('Reads_aligned')
    for i in (1,2):
        row=lines[i].split('\t');row[idx]=str(74 if row[0]=='Reference' else 31);lines[i]='\t'.join(row)
    path.write_text('\n'.join(lines)+'\n')
    # Keep independent allele/JSON/quantification reconciliation valid while
    # changing one anchor's native result by one ordinary aligned read.
    running=json.loads((child/'CRISPResso2_info.json').read_text())['running_info']
    archive_path=child/running['allele_frequency_table_zip_filename']
    import csv
    import io
    with zipfile.ZipFile(archive_path) as z:
        rows=list(csv.DictReader(io.StringIO(z.read(running['allele_frequency_table_filename']).decode()),delimiter='\t'))
    for name,delta in [('Reference',-1),('Prime-edited',1)]:
        row=next(r for r in rows if r['Reference_Name']==name and int(r['#Reads'])>1)
        row['#Reads']=str(int(row['#Reads'])+delta)
    buffer=io.StringIO();writer=csv.DictWriter(buffer,fieldnames=rows[0].keys(),delimiter='\t',lineterminator='\n')
    writer.writeheader();writer.writerows(rows)
    with zipfile.ZipFile(archive_path,'w') as z:z.writestr(running['allele_frequency_table_filename'],buffer.getvalue())
    result=collect(root)
    assert result.anchor_evidence['failures']=={}
    assert len(result.anchor_evidence['backend_metrics'])==2
    assert not result.eligibility.anchor_invariant
    assert 'ANCHOR_DEPENDENT_NATIVE_RESULT' in result.target_metrics.target_crispresso_native_pe.reason_codes
    assert result.target_metrics.target_crispresso_native_pe.numerator is None


@pytest.mark.parametrize('attack,code',[
    ('stale_policy','STALE_OR_UNQUALIFIED_ROUTING_POLICY'),
    ('ledger','ROUTED_HANDOFF_VERIFICATION_FAILED'),
    ('missing_cohort','ROUTED_HANDOFF_VERIFICATION_FAILED'),
    ('routed_backend_mismatch','ROUTED_BACKEND_INPUT_MISMATCH'),
    ('missing_backend','MISSING_INCOMPLETE_BACKEND_METRICS'),
    ('copy_empty_window','EMPTY_AUTHORITATIVE_QUANTIFICATION_WINDOW'),
])
def test_copy_gates_do_not_restrict_target_population(archive,tmp_path,attack,code):
    root=tmp_path/'run';shutil.copytree(archive,root)
    if attack=='stale_policy':
        path=root/'routing/routing_manifest.json';data=json.loads(path.read_text())
        data['policy_identity']['id']='m311-diagnostic-q30-sites2-cap16-identity08-v1';write_json(path,data)
    elif attack=='ledger': (root/'routing/routing_ledger.jsonl').write_text('{}\n')
    elif attack=='missing_cohort': (root/'routing/copy1_R1.fastq.gz').unlink()
    elif attack=='missing_backend': (root/'copies/copy1/execution.json').unlink()
    elif attack=='copy_empty_window': mutate_info(root,lambda d:d['results']['refs']['Reference'].update(include_idxs=[]),copy=True)
    else:
        path=root/'copies/copy1/output/CRISPResso_on_confident/CRISPResso_mapping_statistics.txt'
        lines=path.read_text().splitlines();values=lines[1].split('\t');values[0]='46'
        path.write_text(lines[0]+'\n'+'\t'.join(values)+'\n')
    result=collect(root)
    assert result.target_metrics.target_crispresso_native_pe.status=='REPORTABLE'
    assert result.target_metrics.total_precise_pe.denominator==55
    assert code in result.copies['copy1'].native.reason_codes
    assert result.copies['copy1'].native.numerator is None


def test_unsupported_geometry_preserves_target_exact(archive):
    result=collect(archive,targets=panel((20,45,70,90)))
    assert result.eligibility.routing_geometry_status=='BLOCKED'
    assert all('UNSUPPORTED_ROUTING_GEOMETRY' in c.precise.reason_codes for c in result.copies.values())


def test_missing_runtime_provenance_preserves_prepared_exact_metric(archive):
    result=collect(archive,runtime_digest=None)
    assert result.target_metrics.total_precise_pe.status=='REPORTABLE'
    assert 'MISSING_REQUIRED_PROVENANCE' in result.eligibility.block_reason_codes


def test_shared_state_products_count_each_pair_once(archive):
    targets=panel();targets[1]=targets[0].model_copy(update={'copy_name':'duplicate_product'})
    paths=[archive/f'analysis/03_analysis_fastq/1B_R{m}.analysis.fastq.gz' for m in (1,2)]
    counts=prepared_products(paths,targets)
    single=prepared_products(paths,targets[:1])
    assert counts==single and counts.classification_input_reads==125


def test_cross_copy_contradictory_definitions_are_blocked(archive):
    targets=panel();targets[1]=targets[1].model_copy(update={'prime_edited_sequence':targets[0].wt_sequence})
    assert contradictory_products(targets)
    result=collect(archive,targets=targets)
    assert result.target_metrics.total_precise_pe.status=='BLOCKED'
    assert 'CONTRADICTORY_EXACT_PRODUCT_DEFINITIONS' in result.target_metrics.total_precise_pe.reason_codes


def test_zero_exact_denominator_is_not_zero_efficiency():
    products=ProductCounts(unresolved_unassessable=10,denominator_exclusions=10,classification_input_reads=10)
    record=metric('total_precise_pe','precise','target_all_prepared','population',10,products=products)
    assert record.status=='NOT_ASSESSABLE' and record.numerator is record.denominator is None
    assert record.reason_codes==['ZERO_EXACT_DENOMINATOR']


def test_overlapping_product_definitions_cannot_guess_wt_or_pe(tmp_path):
    from peanalyzer.analysis_fastq import prepare_analysis_fastqs
    from peanalyzer.demux import demultiplex
    from peanalyzer.schemas import Config
    # Two different full lengths can fit the same repeat-bearing mates. There
    # is no identical WT/PE definition, but reconstruction is non-unique.
    target=Target(target_name='repeat',copy_name='copy1',wt_sequence='A'*20,
                  prime_edited_sequence='A'*25,pegRNA_spacer='AAAAAAA',pegRNA_extension='TTTTT')
    prefixes=('GCTTGCGTTGGAGTGAGTACGGTGTGC','CTGTGTAGTGAGTTGGATGCTGGATGG')
    for mate,record in enumerate(pair('A'*25,length=15),1):
        with gzip.open(tmp_path/f'raw_R{mate}.fastq.gz','wb') as handle:
            handle.write(record.header+prefixes[mate-1].encode()+record.sequence_line+record.plus+b'I'*27+record.quality_line)
    (tmp_path/'samples.csv').write_text('sample_name,barcode_id,forward_barcode_id,reverse_barcode_id\nrepeat,1B,F1,RB\n')
    demultiplex(r1=tmp_path/'raw_R1.fastq.gz',r2=tmp_path/'raw_R2.fastq.gz',
                samples_path=tmp_path/'samples.csv',config=Config(schema_version=1),output=tmp_path/'demux')
    prepare_analysis_fastqs(tmp_path/'demux',tmp_path/'analysis')
    result=collect_metrics(analysis_root=tmp_path/'analysis',sample_id='1B',targets=[target],
                           analysis_id='ambiguous-repeat',comparator_root=tmp_path/'absent',runtime_digest=RUNTIME_DIGEST)
    record=result.target_metrics.total_precise_pe
    assert record.status=='NOT_ASSESSABLE'
    assert record.numerator is record.denominator is None
    assert record.reason_codes==['ZERO_EXACT_DENOMINATOR']
    assert record.products.unresolved_unassessable==1


@pytest.mark.parametrize('attack',['population','scope','numeric_blocked','float_count','native_denominator','extra_field'])
def test_schema_rejects_population_and_count_confusion(archive,attack):
    data=collect(archive).model_dump()
    record=data['target_metrics']['target_crispresso_native_pe']
    if attack=='population': record['population_id']='different'
    elif attack=='scope': record['population_scope']='confident_copy'
    elif attack=='numeric_blocked': record.update(status='BLOCKED',reason_codes=['TEST'],numerator=0,denominator=0)
    elif attack=='float_count': record['numerator']=30.0
    elif attack=='native_denominator': record['denominator']=104
    else: record['efficiency']=0.3
    with pytest.raises(ValidationError): MetricResult.model_validate(data)


def test_historical_m3_authoritative_counter_and_exact_regression(tmp_path):
    results=[]
    for copy,n,a,u,p,e,d in [('copy1',211,199,12,72,60,140),('copy2',139,131,8,48,40,90)]:
        child=tmp_path/copy;child.mkdir()
        source=EVIDENCE/f'm311/historical_pooled/SYN__{copy}'
        for path in source.iterdir(): shutil.copyfile(path,child/path.name)
        running=json.loads((child/'CRISPResso2_info.json').read_text())['running_info']
        with zipfile.ZipFile(child/running['allele_frequency_table_zip_filename'],'w') as z:
            z.write(child/'alleles.txt',running['allele_frequency_table_filename'])
        parsed=parse_child(child,routed_pairs=n,one_input_record_per_pair=True,preprocessing_preserves_records=True)
        assert (parsed['native']['backend_input_reads'],parsed['native']['aligned_reads'],parsed['native']['unaligned_reads'])==(n,a,u)
        assert (parsed['native']['numerator'],parsed['native']['denominator'])==(p,a)
        assert (parsed['exact_haplotype']['numerator'],parsed['exact_haplotype']['denominator'])==(e,d)
        results.append(parsed)
    assert sum(r['native']['numerator'] for r in results)==120
    assert sum(r['native']['denominator'] for r in results)==330
    assert sum(r['exact_haplotype']['numerator'] for r in results)==100
    assert sum(r['exact_haplotype']['denominator'] for r in results)==230
