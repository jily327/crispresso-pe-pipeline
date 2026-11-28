"""Independently recount raw pair calls and check integer agreement by physical barcode."""
import argparse
import csv
from collections import Counter
from functools import lru_cache
from types import SimpleNamespace
from pathlib import Path

from peanalyzer.barcodes import ExtractionRule, identify_read, load_catalog
from peanalyzer.fastq import paired_fastq
from peanalyzer.observability import assess_pair
from peanalyzer.schemas import reverse_complement

from audit import CATALOG, COPY_NAMES, STATES, haplotypes, validate_sources, json_write


def verify(inputs, work):
    paths, panels = validate_sources(inputs)
    refs = panels['EPSPS_284bp']
    bank = haplotypes(refs)
    targets = [SimpleNamespace(copy_name=c, wt_sequence=r['wt_sequence'],
                               prime_edited_sequence=r['intended_pe_sequence']) for c, r in refs.items()]
    catalog = load_catalog(CATALOG)
    extraction = ExtractionRule(start=0, length=9)

    @lru_cache(maxsize=8192)
    def barcode(prefix, end):
        hit = identify_read(prefix, extraction, catalog.ends[end], 0)
        return hit.barcode_id[1:] if hit.barcode_id else '?'

    motifs = {state: s[134:170] for s, (c, state) in bank.items() if c == COPY_NAMES[0]}
    families = {c: [refs[c]['wt_sequence'][x:x + 15] for x in (99, 226)] for c in COPY_NAMES}
    matrix, independent = Counter(), Counter()
    legacy = Counter()
    alsw_ends = {}
    for panel in ('ALSW_211bp', 'ALSW_253bp'):
        entries = panels[panel].values()
        for mate in (1, 2):
            alsw_ends[panel, mate] = {((r['wt_sequence'] if mate == 1 else reverse_complement(r['wt_sequence']))[:16]).encode()
                                      for r in entries}
    alsw_ends_at_offset = Counter()
    totals = {}
    for dataset, base in [('EPSPS', 'EPSPS_1106'), ('ALSW', 'ALSW_dif_knots')]:
        totals[dataset] = 0
        for raw1, raw2 in paired_fastq(*(paths[f'{base}_R{i}.fastq.gz'] for i in (1, 2))):
            b = barcode(raw1.sequence[:9], 'forward') + barcode(raw2.sequence[:9], 'reverse')
            matrix[dataset, b] += 1
            totals[dataset] += 1
            if dataset == 'ALSW':
                for (panel, mate), anchors in alsw_ends.items():
                    read = raw1.sequence if mate == 1 else raw2.sequence
                    for offset in (27, 69):
                        if read[offset:offset+16] in anchors:
                            alsw_ends_at_offset[panel, mate, offset] += 1
                continue
            if len(raw1.sequence) <= 26 or len(raw2.sequence) <= 27:
                continue
            s1, s2 = raw1.sequence[26:].decode(), raw2.sequence[27:].decode()
            q1, q2 = raw1.quality_line[26:].rstrip(), raw2.quality_line[27:].rstrip()
            observed = []
            for read, qual, reverse in ((s1, q1, True), (s2, q2, False)):
                hits = []
                for state, motif in motifs.items():
                    query = reverse_complement(motif) if reverse else motif
                    pos = read.find(query)
                    if pos >= 0:
                        if read.find(query, pos + 1) >= 0:
                            hits.append(None)
                        # The two sites are at offsets 12 and 23 in a 36-base window.
                        hits.append(state if min(qual[pos+12], qual[pos+23]) >= 63 else None)
                observed.append(hits[0] if len(hits) == 1 else None)
            if observed[0] and observed[0] == observed[1]:
                copies = [c for c, markers in families.items()
                          if all(s1.count(reverse_complement(m)) == s2.count(m) == 1 for m in markers)]
                # Reject mixed evidence even when one family has both markers.
                for c, markers in families.items():
                    if c not in copies and any(m in s2 or reverse_complement(m) in s1 for m in markers):
                        copies = []
                        break
                name = copies[0] if len(copies) == 1 else 'unresolved'
                independent[b, 'both_mates_Q30_sites', name, observed[0]] += 1
            if len(s1) + len(s2) >= 294:
                for template, (c, state) in bank.items():
                    if template.startswith(s2) and reverse_complement(template).startswith(s1):
                        independent[b, 'full_pair_template_exact', c, state] += 1
            result = assess_pair((raw2.trimmed(27), raw1.trimmed(26)), targets)
            legacy[b, result['canonical']] += 1

    with (work / 'barcodes.csv').open() as f:
        for row in csv.DictReader(f):
            for ds in totals:
                assert int(row[ds + '_pairs']) == matrix[ds, row['barcode']]
    for ds, total in totals.items():
        assert sum(v for (d, _), v in matrix.items() if d == ds) == total
    with (work / 'haplotypes.csv').open() as f:
        for row in csv.DictReader(f):
            b, method, c = row['barcode'], row['method'], row['copy']
            for state in STATES:
                groups = (*COPY_NAMES, 'unresolved') if c == 'combined' else (c,)
                assert int(row[state]) == sum(independent[b, method, group, state] for group in groups), row
            if c == 'combined' and method == 'full_pair_template_exact':
                assert legacy[b, 'exact_WT'] == int(row['WT']), row
                assert legacy[b, 'exact_PE'] == int(row['AB']), row
    json_write(work / 'alsw-panel-observations.json',
               [{'panel': p, 'mate': m, 'trim_offset': o, 'matching_16nt_anchors': alsw_ends_at_offset[p, m, o]}
                for p, m in sorted(alsw_ends) for o in (27, 69)])
    json_write(work / 'pair-verification.json', dict(pairs_recounted=totals,
               barcode_matrix='passed', two_site_by_barcode_and_copy='passed',
               full_template_by_barcode_and_copy='passed', normalized_v101_exact_WT_and_PE='passed'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inputs', type=Path)
    parser.add_argument('work', type=Path)
    args = parser.parse_args()
    verify(args.inputs, args.work)
