"""Integer reconciliation of Core's two-WT alignment with its input and output files."""
import argparse
import csv
import io
import json
from collections import Counter
from decimal import Decimal
from pathlib import Path
from zipfile import ZipFile

from audit import BASES, COPY_NAMES, STATES, calls, haplotypes, json_write, rc, table, validate_sources
from peanalyzer.fastq import paired_fastq, read_fastq, read_id


def rows(path):
    with path.open() as f:
        return list(csv.DictReader(f, delimiter='\t'))


def recount(work, population, refs, barcode_ids):
    run = work / ('CRISPResso_on_' + population)
    info = json.loads((run / 'CRISPResso2_info.json').read_text())
    assert info['running_info']['version'] == '2.3.4'
    for name in COPY_NAMES:
        reported = info['results']['refs'][name]
        assert reported['sequence'] == refs[name]['wt_sequence']
        assert reported['include_idxs']['value'] == [146, 157]
    alleles = haplotypes(refs)
    exact_merged, exact_aligned = Counter(), Counter()
    for record in read_fastq(run / 'out.extendedFrags.fastq.gz'):
        exact_merged[alleles.get(record.sequence.decode(), 'other')] += 1

    by_sequence = {}
    aligned_counts = Counter()
    site, symbols, ordinary, ambiguous = Counter(), Counter(), Counter(), Counter()
    with ZipFile(run / 'Alleles_frequency_table.zip') as z:
        with z.open('Alleles_frequency_table.txt') as f:
            for row in csv.DictReader(io.TextIOWrapper(f), delimiter='\t'):
                name, n = row['Reference_Name'], int(row['#Reads'])
                seq = row['Aligned_Sequence']
                literal = seq.replace('-', '')
                canonical = min(literal, rc(literal))
                if canonical in by_sequence:
                    raise ValueError('Nonunique backend allele for a merged sequence')
                aligned_counts[canonical] = n
                if name not in COPY_NAMES:
                    by_sequence[canonical] = ('unresolved', 'ambiguous')
                    ambiguous[name] += n
                    continue
                ref_alignment = row['Reference_Sequence']
                assert ref_alignment.replace('-', '') == refs[name]['wt_sequence']
                assert len(ref_alignment) == len(seq)
                bases = ''.join(a for a, r in zip(seq, ref_alignment) if r != '-')
                a, b = bases[146], bases[157]
                pair = a + b
                state = STATES[BASES.index(pair)] if pair in BASES else 'other'
                by_sequence[canonical] = (name, state)
                site[name, state] += n
                symbols[name, 146, a] += n
                symbols[name, 157, b] += n
                ordinary[name] += n
                if literal in alleles:
                    copy, state = alleles[literal]
                    assert copy == name
                    exact_aligned[copy, state] += n
    totals = rows(run / 'CRISPResso_mapping_statistics.txt')[0]
    raw = int(totals['READS IN INPUTS'])
    merged = int(totals['READS AFTER PREPROCESSING'])
    aligned = int(totals['READS ALIGNED'])
    assert exact_merged.total() == merged
    assert ordinary.total() + ambiguous.total() == aligned
    summaries = {r['Amplicon']: r for r in rows(run / 'CRISPResso_quantification_of_editing_frequency.txt')}
    barcode_rows = list(csv.DictReader((work / 'barcodes.csv').read_text().splitlines()))
    assert raw == sum(int(r['EPSPS_pairs']) for r in barcode_rows
                      if (r['barcode'] == '1A' if population == '1A' else '?' not in r['barcode']))
    replay = Counter()
    grouped = Counter()
    seen_ids = set()
    for record in read_fastq(run / 'out.extendedFrags.fastq.gz'):
        ident = read_id(record, 1)
        assert ident not in seen_ids
        seen_ids.add(ident)
        barcode = barcode_ids[ident]
        assert '?' not in barcode and (population != '1A' or barcode == '1A')
        seq = record.sequence.decode()
        key = min(seq, rc(seq))
        if key in by_sequence:
            replay[key] += 1
        copy, state = by_sequence.get(key, ('unresolved', 'unaligned'))
        grouped[barcode, copy, state] += 1
    assert replay == aligned_counts and grouped.total() == merged
    table(work / (population + '.core-by-barcode.csv'), ['barcode', 'backend_copy', 'site_bases', 'reads'],
          [(*key, n) for key, n in sorted(grouped.items())])
    by_copy = {}
    for name in COPY_NAMES:
        with (run / f'{name}.Quantification_window_nucleotide_frequency_table.txt').open() as f:
            data = list(csv.reader(f, delimiter='\t'))
        assert data[0][1:] == ['G', 'G']
        for symbol, a, b in data[1:]:
            assert (Decimal(a), Decimal(b)) == (symbols[name, 146, symbol], symbols[name, 157, symbol])
        assert ordinary[name] == int(summaries[name]['Reads_aligned'])
        assert all(exact_merged[name, state] == exact_aligned[name, state] for state in STATES)
        by_copy[name] = dict(ordinary_alignments=ordinary[name],
                             aligned_site_bases={s: site[name, s] for s in (*STATES, 'other')},
                             literal_merged_templates={s: exact_merged[name, s] for s in STATES},
                             native_window_modified=int(summaries[name]['Modified']))
    return dict(raw_pairs=raw, merged=merged, aligned=aligned, ambiguous=dict(ambiguous),
                unaligned_after_merge=merged-aligned, copies=by_copy,
                window_indices=[146, 157], version=info['running_info']['version'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inputs', type=Path)
    parser.add_argument('work', type=Path)
    args = parser.parse_args()
    paths, panels = validate_sources(args.inputs)
    refs = panels['EPSPS_284bp']
    fwd, rev = calls()
    barcode_ids = {read_id(a, 1): fwd.get(a.sequence[:9].decode(), '?') + rev.get(b.sequence[:9].decode(), '?')
                   for a, b in paired_fastq(paths['EPSPS_1106_R1.fastq.gz'], paths['EPSPS_1106_R2.fastq.gz'])}
    json_write(args.work / 'core-comparison.json',
               {pop: recount(args.work, pop, refs, barcode_ids) for pop in ('1A', 'all_known')})
