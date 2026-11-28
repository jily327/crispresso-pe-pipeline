"""Extract native Core counts from its original files and independently recount allele events."""
import csv
import hashlib
import io
import json
import zipfile
from collections import Counter
from pathlib import Path

from peanalyzer.backend.metrics import child_file, integer, table

# These names are the 2.3.4 quantification table columns and JSON integer fields.
FIELDS = {
    'Reads_aligned': 'counts_total', 'Modified': 'counts_modified', 'Unmodified': 'counts_unmodified',
    'Discarded': 'counts_discarded', 'Insertions': 'counts_insertion', 'Deletions': 'counts_deletion',
    'Substitutions': 'counts_substitution', 'Only Insertions': 'counts_only_insertion',
    'Only Deletions': 'counts_only_deletion', 'Only Substitutions': 'counts_only_substitution',
    'Insertions and Deletions': 'counts_insertion_and_deletion',
    'Insertions and Substitutions': 'counts_insertion_and_substitution',
    'Deletions and Substitutions': 'counts_deletion_and_substitution',
    'Insertions Deletions and Substitutions': 'counts_insertion_and_deletion_and_substitution',
}
INTERSECTIONS = ('', 'Only Insertions', 'Only Deletions', 'Insertions and Deletions',
                 'Only Substitutions', 'Insertions and Substitutions', 'Deletions and Substitutions',
                 'Insertions Deletions and Substitutions')


def extract_native(info_path):
    child = Path(info_path).parent
    info = json.loads(Path(info_path).read_text())
    run, results = info['running_info'], info['results']
    if run['version'] != '2.3.4' or not run.get('end_time_string'):
        raise ValueError('Incomplete or unsupported native run')
    refs = results['ref_names']
    stats = results['alignment_stats']
    mapping_path = child_file(child, run['mapping_stats_filename'])
    quant_path = child_file(child, run['quant_of_editing_freq_filename'])
    allele_path = child_file(child, run['allele_frequency_table_zip_filename'])
    mapping_row, = table(mapping_path)
    mapping = {k: integer(v) for k, v in mapping_row.items()}
    raw, merged, aligned = (mapping[k] for k in ('READS IN INPUTS', 'READS AFTER PREPROCESSING', 'READS ALIGNED'))
    counters = run['alignment_stats']
    if not (aligned <= merged <= raw and integer(counters['N_TOT_READS']) == merged
            and mapping['N_CACHED_ALN'] + mapping['N_COMPUTED_ALN'] == aligned
            and mapping['N_CACHED_NOTALN'] + mapping['N_COMPUTED_NOTALN'] == merged - aligned
            and all(integer(counters[k]) == mapping[k] for k in mapping if k.startswith('N_'))):
        raise ValueError('Native mapping and alignment counters disagree')
    per_ref = {}
    for row in table(quant_path):
        name = row['Amplicon']
        counts = {k: integer(row[k]) for k in FIELDS}
        if (name in per_ref or integer(row['Reads_in_input']) != raw
                or integer(row['Reads_aligned_all_amplicons']) != aligned
                or any(counts[k] != integer(stats[field][name]) for k, field in FIELDS.items())):
            raise ValueError('Native per-reference JSON and quantification table disagree')
        per_ref[name] = counts
    if set(per_ref) != set(refs) or len(set(refs)) != len(refs):
        raise ValueError('Inconsistent native reference inventory')
    tally = {ref: Counter() for ref in refs}
    ambiguous = 0
    abundances = Counter()
    with zipfile.ZipFile(allele_path) as archive:
        with archive.open(run['allele_frequency_table_filename']) as raw_table:
            rows = csv.DictReader(io.TextIOWrapper(raw_table), delimiter='\t')
            for row in rows:
                n = integer(row['#Reads'])
                ref = row['Reference_Name']
                identity = tuple(sorted((k, v) for k, v in row.items() if k not in ('%Reads', '#Reads')))
                abundances[identity] += n
                if ref in tally:
                    t = tally[ref]
                    mask = 0
                    for bit, (field, event) in enumerate(zip(('n_inserted', 'n_deleted', 'n_mutated'),
                                                            ('Insertions', 'Deletions', 'Substitutions'))):
                        if integer(row[field]):
                            mask |= 1 << bit
                            t[event] += n
                    if mask:
                        t[INTERSECTIONS[mask]] += n
                    status = 'Modified' if mask else 'Unmodified'
                    if row['Read_Status'] != status.upper():
                        raise ValueError('Native allele event fields and status disagree')
                    t[status] += n
                    t['Reads_aligned'] += n
                elif ref.startswith('AMBIGUOUS_') and ref[len('AMBIGUOUS_'):] in tally:
                    ambiguous += n
                elif ref.startswith('DISCARDED_') and ref[len('DISCARDED_'):] in tally:
                    tally[ref[len('DISCARDED_'):]]['Discarded'] += n
                else:
                    raise ValueError('Unknown native reference assignment')
    if (sum(abundances.values()) != aligned
            or ambiguous != integer(stats['class_counts'].get('AMBIGUOUS', 0))
            or any(tally[r][key] != n for r, values in per_ref.items() for key, n in values.items())):
        raise ValueError('Detailed allele recount disagrees with native counts')
    identity_bytes = json.dumps(sorted(abundances.items()), ensure_ascii=True, separators=(',', ':')).encode()
    counts = dict(backend_input_reads=raw, reads_after_preprocessing=merged, aligned_reads=aligned,
                  unaligned_reads=merged-aligned, preprocessing_count_delta=raw-merged, ambiguous_aligned_reads=ambiguous,
                  discarded_aligned_reads=sum(t['Discarded'] for t in tally.values()))
    if 'Prime-edited' in per_ref:
        counts.update(numerator=per_ref['Prime-edited']['Reads_aligned'], denominator=aligned)
    return dict(counts=counts, per_reference=per_ref, allele_identity_sha256=hashlib.sha256(identity_bytes).hexdigest(),
                allele_identities=len(abundances), paths=dict(quantification=quant_path, mapping=mapping_path, alleles=allele_path))
