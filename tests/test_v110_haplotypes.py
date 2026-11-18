"""Independent integer fixtures for reversible references, quality indexing and physical-pair accounting."""
from collections import Counter
from random import Random

import pytest

from peanalyzer.demux_verify import VerifiedSample, sha256_file
from peanalyzer.fastq import FastqRecord
from peanalyzer.haplotypes import build_panel, measure_sample
from peanalyzer.observability import assess_pair
from peanalyzer.schemas import reverse_complement
from types import SimpleNamespace


def design():
    rng = Random(41)
    wt = ''.join(rng.choices('ACGT', k=160))
    wt = wt[:62] + 'G' + wt[63:94] + 'G' + wt[95:]
    templates = {}
    for label, a, b in (('WT', 'G', 'G'), ('A_only', 'A', 'G'),
                        ('B_only', 'G', 'A'), ('AB', 'A', 'A')):
        templates[label] = wt[:62] + a + wt[63:94] + b + wt[95:]
    return templates


def paired(name, left, right, *, reverse=False, low_mate=None, low_pos=None, prefix=('', '')):
    reads = (left, reverse_complement(right))
    if reverse:
        reads = reads[::-1]
    result = []
    for k, (head, dna) in enumerate(zip(prefix, reads), 1):
        scores = list('I' * len(dna))
        if k == low_mate:
            scores[low_pos] = '!'
        seq = head + dna
        result.append(FastqRecord(f'@{name}/{k}\n'.encode(), (seq+'\n').encode(), b'+\n',
                                  ('I'*len(head) + ''.join(scores) + '\n').encode()))
    return tuple(result)


def sample_file(tmp, pairs):
    files = [tmp / f'R{m}.fq' for m in (1, 2)]
    for j, path in enumerate(files):
        path.write_bytes(b''.join(pair[j].to_bytes() for pair in pairs))
    return VerifiedSample('sample', len(pairs), *files, *(sha256_file(p) for p in files))


@pytest.mark.parametrize('reverse_reads', [True, False])
@pytest.mark.parametrize('reverse_refs', [True, False])
def test_counts_using_two_directions_and_asymmetric_trims(tmp_path, reverse_reads, reverse_refs):
    truth = design()
    wt, pe = truth['WT'], truth['AB']
    orient = reverse_complement if reverse_refs else str
    panel = build_panel('target', {'copy1': {'WT': orient(wt), 'PE': orient(pe)}})
    target = SimpleNamespace(copy_name='copy1', wt_sequence=orient(wt), prime_edited_sequence=orient(pe))
    pairs, exact = [], Counter()
    for state, n in {'WT': 4, 'A_only': 2, 'B_only': 1, 'AB': 3}.items():
        for _ in range(n):
            seq = truth[state]
            rec = paired(len(pairs), seq[:140], seq[-135:], reverse=reverse_reads, prefix=('TAG', 'GG'))
            pairs.append(rec)
            exact[assess_pair(tuple(r.trimmed(trim) for r, trim in zip(rec, (3, 2))), [target])['canonical']] += 1
    row = measure_sample(sample_file(tmp_path, pairs), panel, (3, 2), False)
    assert exact == {'exact_WT': 4, 'exact_PE': 3, 'other_or_unassessable': 3}
    expected = {'WT': 4, 'A_only': 1 if reverse_refs else 2, 'B_only': 2 if reverse_refs else 1, 'AB': 3}
    for method in ('two_site_q30', 'full_templates'):
        assert row[method]['combined']['counts'] == expected
    assert row['exact_double_edit_fraction'] == {'numerator': 3, 'denominator': 7, 'fraction': 3 / 7}
    assert row['site_orientation'] == {f'R{2 if reverse_reads != reverse_refs else 1}_forward': 10}


def test_one_site_observable_quality_reversal_other_site_and_exclusions(tmp_path):
    truth = design()
    panel = build_panel('target', {'c': {'WT': truth['WT'], 'PE': truth['AB']}})
    pe = truth['AB']
    # Physical R1 reads the supplied reference in reverse. A low quality at
    # original coordinate 94 removes B but cannot remove A.
    rows = [paired(1, pe, pe, reverse=True, low_mate=1, low_pos=len(pe)-1-94),
            paired(2, pe[44:83], pe[44:83], reverse=True),
            paired(3, pe[:130], truth['WT'][-130:]),
            paired(4, pe[:20], pe[-20:])]
    result = measure_sample(sample_file(tmp_path, rows), panel, (0, 0), False)
    calls = result['two_site_q30']['combined']
    assert (calls['site_A']['numerator'], calls['site_A']['denominator']) == (2, 2)
    assert calls['site_B']['denominator'] == calls['assessable'] == 0
    assert calls['double_edit']['fraction'] is None
    assert sum(result['site_exclusions'].values()) == 4
    assert result['full_templates']['combined']['counts']['AB'] == 1


def test_duplicated_references_preserve_target_and_unresolved_copy(tmp_path):
    truth = design()
    pair = {'WT': truth['WT'], 'PE': truth['AB']}
    panel = build_panel('shared', {'one': pair, 'two': pair})
    row = measure_sample(sample_file(tmp_path, [paired(1, truth['AB'], truth['AB'])]), panel, (0, 0), False)
    for method in ('two_site_q30', 'full_templates'):
        assert row[method]['combined']['counts']['AB'] == row[method]['unresolved_copy']['counts']['AB'] == 1
        assert row[method]['copies']['one']['double_edit']['fraction'] is None
        assert row[method]['copies']['two']['double_edit']['fraction'] is None


def test_competing_orientation_and_reconstructable_other():
    truth = design()
    wt = truth['WT']
    changed = wt[:60] + ('A' if wt[60] != 'A' else 'C') + wt[61:]
    target = SimpleNamespace(copy_name='c', wt_sequence=wt, prime_edited_sequence=truth['AB'])
    read = assess_pair(paired(9, changed[:130], changed[-129:], reverse=True), [target])
    assert read['canonical'] == 'other_or_unassessable' and read['reason'] is None
    assert read['sequence'] == changed and read['forward_mate'] == 2
    assert assess_pair(paired(0, wt[:45], wt[-45:]), [target])['reason'] == 'INSUFFICIENT_EXACT_PAIR_OVERLAP'
    symmetric = wt[:65] + reverse_complement(wt[:65])
    symmetrical_target = SimpleNamespace(copy_name='c', wt_sequence=symmetric, prime_edited_sequence=symmetric)
    read = assess_pair(paired(0, symmetric, symmetric), [symmetrical_target])
    assert read['canonical'] == 'other_or_unassessable' and read['reason'] == 'UNRESOLVED_READ_ORIENTATION'


def test_repeat_and_edit_dependent_copy_marker_rejected():
    truth = design()
    pair = {'WT': truth['WT'], 'PE': truth['AB']}
    with pytest.raises(ValueError, match='uniquely'):
        build_panel('target', {'one': pair, 'two': pair}, [5, 125])
    with pytest.raises(ValueError, match='contains an edit'):
        build_panel('target', {'one': pair}, [60, 125])
