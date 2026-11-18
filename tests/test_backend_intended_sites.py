import random
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import pytest

from peanalyzer.backend.intended_sites import (
    _observe, _panel, _summarize, _uncertain_deletions, _window_report, run_core_sites,
)
from peanalyzer.docker_runtime import IMAGE


def reference():
    wt = ''.join(random.Random(1195).choices('ACGT', k=140))
    sites = (63, 76)
    pe = list(wt)
    for pos in sites:
        pe[pos] = next(c for c in 'ACGT' if c != wt[pos])
    return wt, ''.join(pe), sites


def test_per_site_observation_and_mixed_states():
    wt, pe, (a,b) = reference()
    counts = Counter()

    def add(seq, n):
        _observe(dict(Reference_Sequence=wt, Aligned_Sequence=seq), (wt, pe, (a,b)), n, counts)

    add(wt, 3)
    add(pe, 5)
    add(pe[:b] + 'N' + pe[b+1:], 7)  # Recognized A, unknown B
    add('-' * (a+1) + pe[a+1:], 2)    # Missing A coverage, recognized B
    other = next(c for c in 'ACGT' if c not in (wt[a], pe[a]))
    add(pe[:a] + other + pe[a+1:], 11)  # Unexpected A, intended B
    add(pe[:15] + ('ACGT'.replace(wt[15], '')[0]) + pe[16:], 13)
    out = _summarize(counts)
    assert out['counts'] == dict(WT=3, A_only=0, B_only=0, AB=18, other_mixed=11, unassessable=9)
    assert [(out[m]['numerator'], out[m]['denominator']) for m in ('site_A', 'site_B', 'any_edit', 'double_edit')] == [
        (25, 39), (31, 34), (29, 32), (18, 32)]
    assert out['qc']['AB_full_length_exact'] == 5
    assert out['qc']['AB_with_additional_change'] == 13


@pytest.mark.parametrize('query', ['ATT-TCG', 'AT-TTCG', 'A-TTTCG'])
def test_repetitive_deletion_placement_is_unresolved(query):
    assert _uncertain_deletions('ATTTTCG', query, 0, 6, [1, 5]) == {0}


def test_nonrepetitive_deletion_and_terminal_gap():
    assert _uncertain_deletions('ACTAG', 'AC-AG', 0, 4, [2,3]) == set()
    assert _uncertain_deletions('TTTAG', '--TAG', 2, 4, [1,3]) == set()
    assert _summarize(Counter())['site_A']['fraction'] is None


def test_copy_coordinates_can_shift_if_sites_map_uniquely():
    wt, pe, sites = reference()
    t = SimpleNamespace(copy_name='one', wt_sequence=wt, prime_edited_sequence=pe)
    peer = SimpleNamespace(copy_name='two', wt_sequence='G' + wt, prime_edited_sequence='G' + pe)
    designs = _panel([t, peer])
    assert list(designs['two'][2]) == [i + 1 for i in sites]
    # Mutation changes local context in one copy and breaks the target correspondence.
    p = sites[0] - 5
    peer.wt_sequence = peer.wt_sequence[:p] + 'N' + peer.wt_sequence[p+1:]
    with pytest.raises(ValueError):
        _panel([t, peer])


def test_window_and_runtime_admission(tmp_path):
    wt, pe, sites = reference()
    r = _window_report({'include_idxs': [9,10]}, (wt, pe, sites), '8-10')
    assert r['outside_window'] == list(sites) and r['requested_indices_excluded'] == [8]
    with pytest.raises(ValueError, match='expanded'):
        _window_report({'include_idxs': [8,9,10,11]}, (wt, pe, sites), '8-10')
    t = SimpleNamespace(copy_name='one', wt_sequence=wt, prime_edited_sequence=pe,
                        quantification_window_center=-1)
    kwargs = dict(targets=[t], r1=Path('missing'), r2=Path('missing'), core=SimpleNamespace(version='2.3.4'),
                  output=tmp_path/'results', runtime_digest=IMAGE)
    with pytest.raises(ValueError, match='EMPTY_INPUT'):
        run_core_sites(**kwargs, input_pairs=0)
    with pytest.raises(ValueError, match='Guide-relative'):
        run_core_sites(**kwargs, input_pairs=1)
    assert not kwargs['output'].exists()
