"""Regression: routing must not produce state-selected copy cohorts at observed mate lengths.

geometry() qualifies intended-indel routing at 100/150-nt and full-length mates only.
qi_hitom_v1 prepared mates are 150 - 9 barcode - 18 bridge = 123 nt. For this design a
123-nt R1 ends 7 nt inside a 10-nt intended insertion; before the fix, every PE pair was
quarantined while every WT pair was assigned, giving a qualified, verified, PE-free cohort.
"""
import gzip

import pytest

from peanalyzer.analysis_fastq import prepare_analysis_fastqs
from peanalyzer.barcodes import bundled_catalog, load_catalog
from peanalyzer.demux import demultiplex
from peanalyzer.fastq import FastqRecord
from peanalyzer.geometry import geometry
from peanalyzer.metrics.products import prepared_products
from peanalyzer.routing import RoutingPolicy, observed_state_symmetry, route_analysis, route_pair
from peanalyzer.schemas import Config, Target, reverse_complement

WT = ('GACACTCGCTATGAATCTCTGATTTACCCACTCTGCCAAACTCCAGCGCGGTCAGTTCCATCACCCTAAGTAACCGAATAATGCG'
      'TTCGCTCTATTGACTACGACGCGCTCATTCCCTTGTCGGAGAGTTATGGAACAAGGACGCTGTCTGAGACTAGAAGACAGATAGT'
      'GCACACGACCGGCGTCGGAGAAACTCTATT')
SITE, INSERT = 116, 'GATTACAGGT'
PE = WT[:SITE] + INSERT + WT[SITE:]
TARGET = Target(target_name='T1', copy_name='A', wt_sequence=WT, prime_edited_sequence=PE,
                pegRNA_spacer=WT[SITE - 30:SITE - 10],
                pegRNA_extension=reverse_complement(PE[SITE - 20:SITE + 8]))


def perfect_pair(molecule, length):
    reads = (molecule[:length], reverse_complement(molecule[-length:]))
    return tuple(FastqRecord(f'@m/{i}\n'.encode(), (s + '\n').encode(), b'+\n', ('I' * len(s) + '\n').encode())
                 for i, s in enumerate(reads, 1))


def test_design_passes_existing_geometry_gate_but_123nt_routing_is_state_selective():
    report = geometry([TARGET])
    assert report['status'] != 'BLOCKED'
    assert 123 not in {t['mate_length'] for t in report['indel_placement_qualification']['trials']}
    wt = route_pair(perfect_pair(WT, 123), [TARGET], report, RoutingPolicy())
    pe = route_pair(perfect_pair(PE, 123), [TARGET], report, RoutingPolicy())
    assert (wt['assigned_copy'], pe['assigned_copy']) == ('A', None)


def hitom_reads(tmp_path, molecules):
    catalog = load_catalog(bundled_catalog()).ends
    bridges = ('GGAGTGAGTACGGTGTGC', 'GAGTTGGATGCTGGATGG')
    mates = ([], [])
    for index, molecule in enumerate(molecules):
        reads = ((catalog['forward']['F1'] + bridges[0] + molecule)[:150],
                 (catalog['reverse']['RB'] + bridges[1] + reverse_complement(molecule))[:150])
        for mate, read in enumerate(reads):
            mates[mate].append(f'@p{index}/{mate + 1}\n{read}\n+\n{"I" * len(read)}\n')
    for mate in (0, 1):
        (tmp_path / f'R{mate + 1}.fastq.gz').write_bytes(gzip.compress(''.join(mates[mate]).encode(), mtime=0))
    (tmp_path / 'samples.csv').write_text('sample_name,barcode_id,forward_barcode_id,reverse_barcode_id\nS1,1B,F1,RB\n')
    demultiplex(r1=tmp_path / 'R1.fastq.gz', r2=tmp_path / 'R2.fastq.gz', samples_path=tmp_path / 'samples.csv',
                config=Config(schema_version=1), output=tmp_path / 'demux')
    return prepare_analysis_fastqs(tmp_path / 'demux', tmp_path / 'prepared')


def test_observed_geometry_blocks_state_selected_confident_cohort(tmp_path):
    manifest = hitom_reads(tmp_path, [WT] * 5 + [PE] * 5)
    paths = [tmp_path / 'prepared' / manifest['samples']['1B']['files'][f'r{m}']['path'] for m in (1, 2)]
    # The independent all-read target metric is unaffected: 5 / (5 + 5).
    products = prepared_products(paths, [TARGET])
    assert (products.exact_pe, products.exact_wt) == (5, 5)
    failures = observed_state_symmetry(paths, [TARGET], geometry([TARGET]), RoutingPolicy())
    assert failures == [dict(copy='A', left_length=123, right_length=123, wt_assigned='A', pe_assigned=None)]
    with pytest.raises(ValueError, match='PE_EDIT_GEOMETRY_ROUTING_UNQUALIFIED at observed mate lengths'):
        route_analysis(tmp_path / 'prepared', '1B', [TARGET], tmp_path / 'routing')
    assert not (tmp_path / 'routing').exists()


def test_symmetric_observed_geometry_still_routes(tmp_path):
    # Same design with full-length mates (2x250): both states are assigned.
    report = geometry([TARGET])
    for molecule in (WT, PE):
        assert route_pair(perfect_pair(molecule, len(molecule)), [TARGET], report, RoutingPolicy())['assigned_copy'] == 'A'
