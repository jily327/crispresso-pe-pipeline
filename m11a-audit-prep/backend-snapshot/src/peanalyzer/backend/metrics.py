"""Pinned integer-count parity and separate exact-haplotype denominators."""

import csv
import io
import zipfile
from collections import Counter
from fractions import Fraction
from pathlib import Path

from peanalyzer.demux_verify import read_json
from peanalyzer.schemas import reverse_complement

COUNTERS=('N_TOT_READS','N_CACHED_ALN','N_COMPUTED_ALN','N_CACHED_NOTALN','N_COMPUTED_NOTALN')
from peanalyzer.observability import MIN_EXACT_PAIR_OVERLAP, assess_pair

KNOWN_BACKEND_FAILURE_REASONS = frozenset({
    'BACKEND_EXECUTION_FAILED', 'BACKEND_COUNTER_RECONCILIATION_FAILED',
    'BACKEND_AMBIGUOUS_RECONCILIATION_FAILED', 'BACKEND_OUTPUT_MALFORMED',
    'BACKEND_REFERENCE_MISMATCH', 'BACKEND_INPUT_LINEAGE_MISMATCH',
    'BACKEND_CONFIGURATION_MISMATCH', 'BACKEND_PRODUCT_RECONCILIATION_FAILED',
    'ROUTED_BACKEND_INPUT_MISMATCH', 'MISSING_INCOMPLETE_BACKEND_METRICS',
    'MISSING_REQUIRED_PROVENANCE', 'UNQUALIFIED_BACKEND_RUNTIME',
})


def validated_failure_reason(value):
    """Codes are exact uppercase tokens; raw diagnostics are never authoritative."""
    if not isinstance(value, str):
        return 'INVALID_BACKEND_FAILURE_REASON'
    return value if value in KNOWN_BACKEND_FAILURE_REASONS else 'UNKNOWN_BACKEND_FAILURE_REASON'


class MetricContractError(ValueError):
    def __init__(self, message, code='BACKEND_COUNTER_RECONCILIATION_FAILED'):
        self.code = code
        super().__init__(message)


def backend_failure_code(exc):
    """Keep known execution and artifact failures distinct from missing results."""
    if isinstance(exc, MetricContractError):
        return exc.code
    if getattr(exc, 'code', None) == 'COMMAND_FAILED':
        return 'BACKEND_EXECUTION_FAILED'
    if getattr(exc, 'code', None) == 'VERSION_MISMATCH':
        return 'UNQUALIFIED_BACKEND_RUNTIME'
    if getattr(exc, 'code', None) == 'BACKEND_REFERENCE_MISMATCH':
        return exc.code
    if isinstance(exc, FileNotFoundError):
        return 'MISSING_INCOMPLETE_BACKEND_METRICS'
    return 'BACKEND_OUTPUT_MALFORMED'


def aligned_partition(data, alleles, totals):
    """Reconcile exclusive 2.3.4 allele rows with JSON reference/discard counts."""
    code = 'BACKEND_AMBIGUOUS_RECONCILIATION_FAILED'
    ordinary, discarded = Counter(), Counter()
    ambiguous = 0
    for row in alleles:
        name, count = row['Reference_Name'], integer(row['#Reads'])
        if name in totals:
            ordinary[name] += count
        elif name.startswith('AMBIGUOUS_') and name.removeprefix('AMBIGUOUS_') in totals:
            ambiguous += count
        elif name.startswith('DISCARDED_') and name.removeprefix('DISCARDED_') in totals:
            discarded[name.removeprefix('DISCARDED_')] += count
        else:
            raise MetricContractError('unknown aligned allele category', code)
    expected = {k: integer(v) for k, v in data['results']['alignment_stats']['counts_discarded'].items()}
    if (set(expected) != set(totals) or any(ordinary[k] != v for k, v in totals.items())
            or any(discarded[k] != v for k, v in expected.items())
            or ambiguous != integer(data['results']['alignment_stats']['class_counts'].get('AMBIGUOUS', 0))):
        raise MetricContractError('allele/ordinary/discarded reference counts disagree', code)
    return dict(ordinary_classified_aligned_reads=sum(totals.values()),
                ambiguous_aligned_reads=ambiguous, discarded_aligned_reads=sum(expected.values()))


def integer(value):
    if type(value) is int and value>=0: return value
    if isinstance(value,str) and value.isdecimal(): return int(value)
    raise MetricContractError(f'invalid nonnegative integer: {value!r}')


def fraction(numerator,denominator):
    return dict(numerator=numerator,denominator=denominator,
                exact_fraction=str(Fraction(numerator,denominator)) if denominator else None,
                fraction=numerator/denominator if denominator else None)


def child_file(root, name):
    if not isinstance(name,str) or Path(name).name!=name or not name:
        raise MetricContractError('invalid child artifact filename')
    path=Path(root)/name
    if path.is_symlink(): raise MetricContractError('symlink child artifact')
    return path


def table(path):
    with path.open() as handle:
        reader=csv.DictReader(handle,delimiter='\t')
        if reader.fieldnames is None or len(reader.fieldnames)!=len(set(reader.fieldnames)):
            raise MetricContractError('duplicate/missing table fields')
        return list(reader)


def parse_child(root: Path, *, routed_pairs: int, one_input_record_per_pair: bool,
                preprocessing_preserves_records: bool=False) -> dict:
    """No denominator identity across preprocessing is assumed unless contracted."""
    try:
        data=read_json(Path(root)/'CRISPResso2_info.json'); running=data['running_info']
        if running['version']!='2.3.4' or not running.get('end_time_string'):
            raise MetricContractError('unsupported/incomplete child analysis')
        stats={k:integer(running['alignment_stats'][k]) for k in COUNTERS}
        aligned=stats['N_CACHED_ALN']+stats['N_COMPUTED_ALN']
        unaligned=stats['N_CACHED_NOTALN']+stats['N_COMPUTED_NOTALN']
        if stats['N_TOT_READS']!=aligned+unaligned:
            raise MetricContractError('alignment counters do not reconcile')
        mapping=table(child_file(root,running['mapping_stats_filename']))
        if len(mapping)!=1: raise MetricContractError('mapping table must contain exactly one row')
        mapping={k:integer(v) for k,v in mapping[0].items()}
        if mapping['READS AFTER PREPROCESSING']!=stats['N_TOT_READS'] or mapping['READS ALIGNED']!=aligned:
            raise MetricContractError('mapping/alignment counter mismatch')
        if any(mapping[k]!=stats[k] for k in COUNTERS[1:]):
            raise MetricContractError('mapping cache counter mismatch')
        input_reads=mapping['READS IN INPUTS']
        if one_input_record_per_pair and input_reads!=integer(routed_pairs):
            raise MetricContractError('router/backend input mismatch', 'ROUTED_BACKEND_INPUT_MISMATCH')
        if input_reads < stats['N_TOT_READS']:
            raise MetricContractError('preprocessing increased the input population')
        if preprocessing_preserves_records and input_reads!=stats['N_TOT_READS']:
            raise MetricContractError('record-preserving preprocessing contract violated')
        totals={k:integer(v) for k,v in data['results']['alignment_stats']['counts_total'].items()}
        if 'Prime-edited' not in totals:
            raise MetricContractError('unsupported nonexclusive reference accounting')
        quant=table(child_file(root,running['quant_of_editing_freq_filename']))
        if len(quant)!=len(totals) or {r['Amplicon'] for r in quant}!=set(totals):
            raise MetricContractError('quantification reference inventory mismatch')
        for row in quant:
            if integer(row['Reads_aligned_all_amplicons'])!=aligned or integer(row['Reads_aligned'])!=totals[row['Amplicon']] or integer(row['Reads_in_input'])!=input_reads:
                raise MetricContractError('native JSON/quantification integer parity failure')
            if integer(row['Discarded']) != integer(data['results']['alignment_stats']['counts_discarded'][row['Amplicon']]):
                raise MetricContractError('JSON/quantification discarded count mismatch', 'BACKEND_AMBIGUOUS_RECONCILIATION_FAILED')
        attrs=dict(backend_input_reads=input_reads,reads_after_preprocessing=stats['N_TOT_READS'],aligned_reads=aligned,unaligned_reads=unaligned,
                   preprocessing_count_delta=input_reads-stats['N_TOT_READS'],
                   unaligned_reason_counts={'unknown_backend_alignment_failure':unaligned})
        native={**attrs,**fraction(totals['Prime-edited'],aligned), 'metric':'crispresso_pe_reference_fraction',
                'reference_counts':totals,'source_numerator':"results.alignment_stats.counts_total['Prime-edited']",
                'source_denominator':'mapping READS ALIGNED; quantification Reads_aligned_all_amplicons'}
        with zipfile.ZipFile(child_file(root,running['allele_frequency_table_zip_filename'])) as archive:
            with archive.open(running['allele_frequency_table_filename']) as handle:
                alleles=list(csv.DictReader(io.TextIOWrapper(handle),delimiter='\t'))
        if sum(integer(r['#Reads']) for r in alleles)!=aligned:
            raise MetricContractError('allele counts do not equal aligned reads', 'BACKEND_AMBIGUOUS_RECONCILIATION_FAILED')
        partition = aligned_partition(data, alleles, totals)
        if sum(partition.values()) != aligned:
            raise MetricContractError('aligned partition does not reconcile', 'BACKEND_AMBIGUOUS_RECONCILIATION_FAILED')
        attrs.update(partition)
        native.update(partition)
        refs=data['results']['refs']
        exact=exact_haplotypes([(r['Aligned_Sequence'].replace('-','') if r['Reference_Name'] in totals else '',integer(r['#Reads'])) for r in alleles],
                               {refs['Reference']['sequence']},{refs['Prime-edited']['sequence']})
        exact.update(attrs)
        exact['backend_unaligned_excluded_reads']=unaligned
        exact['backend_preprocessing_count_delta']=input_reads-stats['N_TOT_READS']
        exact['aligned_product_excluded_reads']=exact['excluded_reads']
        exact['backend_input_excluded_reads']=input_reads-exact['denominator'] if input_reads>=stats['N_TOT_READS'] else None
        return dict(alignment_counters=stats,mapping_statistics=mapping,routed_pairs=routed_pairs,
                    authoritative_reference_quantification_window=refs['Reference'].get('include_idxs'),
                    contract=dict(one_input_record_per_pair=one_input_record_per_pair,preprocessing_preserves_records=preprocessing_preserves_records),
                    native=native,exact_haplotype=exact)
    except MetricContractError:
        raise
    except (OSError,KeyError,TypeError,ValueError,zipfile.BadZipFile) as exc:
        raise MetricContractError(str(exc), backend_failure_code(exc)) from exc


def exact_haplotypes(sequences, wt: set[str], pe: set[str]) -> dict:
    """Full sequences only. Shared copies are deduplicated; WT/PE collisions excluded."""
    counts=Counter()
    for sequence,count in sequences:
        count=integer(count)
        kind='state_collision' if sequence in wt&pe else 'exact_PE' if sequence in pe else 'exact_WT' if sequence in wt else 'other_or_unassessable'
        counts[kind]+=count
    n=counts['exact_PE']; d=n+counts['exact_WT']
    return dict(metric='precise_intended_PE_exact_haplotype_fraction',**fraction(n,d),
                exact_wt_reads=counts['exact_WT'],exact_pe_reads=n,excluded_reads=sum(counts.values())-d,
                exclusion_product_classes={k:v for k,v in counts.items() if k not in ('exact_WT','exact_PE')},
                origin_attribution='not inferred from biological product class')


def exact_pair_class(pair, targets) -> str:
    """Strict exact identity after state-symmetric, unique reconstruction."""
    return assess_pair(pair, targets)['canonical']
