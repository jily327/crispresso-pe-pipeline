"""Independent truth fixtures for ambiguity of a read's intended-site alignment."""
from collections import Counter
import random

import pytest

from peanalyzer.backend.intended_sites import _observe, _summarize
from peanalyzer.schemas import reverse_complement


def known_pair(*, reverse=False, gap_width=1, other_at_b=False, gap_left=False):
    rng = random.Random(84321)
    prefix, suffix = (''.join(rng.choices('ACGT',k=20)) for _ in range(2))
    wt = prefix + 'G'*(gap_width+1) + 'TCTACGACTTCG' + suffix
    a, b = len(prefix)+gap_width, len(prefix)+gap_width+8
    intended = wt[:a] + 'A' + wt[a+1:b] + 'A' + wt[b+1:]
    assert wt[b] != 'A'
    observed = 'C' if other_at_b else 'A'
    group = '-' * gap_width + 'A' if gap_left else 'A' + '-' * gap_width
    variant = prefix + group + wt[a+1:b] + observed + wt[b+1:]
    if reverse:
        def rc(dna):
            return reverse_complement(dna.replace('-', 'N')).replace('N','-')
        wt, intended, variant = rc(wt), rc(intended), rc(variant)
        a,b = len(wt)-1-b, len(wt)-1-a
    counts = Counter()
    for seq,n in ((wt,10),(variant,5)):
        _observe({'Aligned_Sequence':seq,'Reference_Sequence':wt},(wt,intended,(a,b)),n,counts)
    return _summarize(counts)


@pytest.mark.parametrize('reverse', [False,True])
@pytest.mark.parametrize('width', [1,2,3])
@pytest.mark.parametrize('other', [True,False])
@pytest.mark.parametrize('gap_left', [True,False])
def test_ambiguous_gap_over_a_mismatch_preserves_the_disjoint_marginal(reverse,width,other,gap_left):
    r=known_pair(reverse=reverse,gap_width=width,other_at_b=other,gap_left=gap_left)
    disputed,stable=('B','A') if reverse else ('A','B')
    assert (r['site_'+disputed]['numerator'],r['site_'+disputed]['denominator'])==(0,10)
    assert (r['site_'+stable]['numerator'],r['site_'+stable]['denominator'])==(0 if other else 5,15)
    assert r['joint_assessable']==10
    assert r['counts']['WT']==10 and r['counts']['unassessable']==5 and r['counts']['other_mixed']==0
    assert r['qc']['alternative_alignment_site_'+disputed]==5


def test_insertion_can_change_the_observed_base_without_a_gap_in_the_query():
    rng=random.Random(913)
    pre=''.join(rng.choices('ACGT',k=32)); post=''.join(rng.choices('ACGT',k=41))
    wt=pre+'G'+post
    # The G may align to either A or T (both mismatch) with the other inserted.
    # Retain B if A's observed base could change.
    a,b=len(pre),len(pre)+8
    edit=wt[:a]+'A'+wt[a+1:b]+('ACGT'.replace(wt[b], '')[0])+wt[b+1:]
    counts=Counter()
    _observe({'Reference_Sequence':pre+'-G'+post,'Aligned_Sequence':pre+'AT'+edit[a+1:]},
             (wt,edit,(a,b)),7,counts)
    report=_summarize(counts)
    assert report['site_A']['denominator']==0
    assert (report['site_B']['numerator'],report['site_B']['denominator'])==(7,7)
    assert report['counts']['unassessable']==7


def brute_force_alignment_truth(wt, read):
    # Enumerate complete monotone paths. Core allows a gap to extend or to
    # close with a paired column, never direct switching to the opposite gap.
    paths=[]
    def walk(r,q,ar,aq):
        if r==len(wt) and q==len(read):
            score=0
            for i,(x,y) in enumerate(zip(ar,aq)):
                if '-' not in (x,y):
                    score += 5 if x==y else -4
                    continue
                col=ar if x=='-' else aq
                tail = not col[:i].strip('-') or not col[i+1:].strip('-')
                score += -2 if tail or (i and col[i-1]=='-') else -20
            paths.append((score,ar,aq))
            return
        if r<len(wt) and q<len(read):
            walk(r+1,q+1,ar+wt[r],aq+read[q])
        if r<len(wt) and not ar.endswith('-'):
            walk(r+1,q,ar+wt[r],aq+'-')
        if q<len(read) and not aq.endswith('-'):
            walk(r,q+1,ar+'-',aq+read[q])
    walk(0,0,'','')
    top=max(p[0] for p in paths)
    return [(ar,aq) for score,ar,aq in paths if score==top]


def test_no_disputed_site_accepted_across_exhaustive_small_global_alignments():
    from peanalyzer.backend.site_placement import uncertain_sites
    rng=random.Random(881)
    for _ in range(60):
        wt=''.join(rng.choices('ACGT',k=6)); read=''.join(rng.choices('ACGT',k=5))
        sites=(1,4)
        all_calls=set()
        best=brute_force_alignment_truth(wt,read)
        for ref,query in best:
            lo=len(query)-len(query.lstrip('-')); hi=len(query.rstrip('-'))
            obs=tuple(q if lo<=col<hi else None for col,(r,q) in enumerate(zip(ref,query)) if r!='-')
            all_calls.add(tuple(obs[p] for p in sites))
        for ref,query in best:
            lo=len(query)-len(query.lstrip('-')); hi=len(query.rstrip('-'))
            obs=[q if lo<=col<hi else None for col,(r,q) in enumerate(zip(ref,query)) if r!='-']
            native=[obs[p] for p in sites]
            disputed=uncertain_sites(ref,query,sites,native,(-20,-2))
            for i in range(2):
                if native[i] is not None and len({x[i] for x in all_calls})>1:
                    assert i in disputed


def test_unqualified_incentive_is_excluded_without_changing_fixed_native_rows():
    from peanalyzer.backend.site_placement import scoring_parameters
    wt='AGTACG'; pe='AATATG'
    scoring=scoring_parameters(dict(needleman_wunsch_gap_open=-20,needleman_wunsch_gap_extend=-2,
                                    needleman_wunsch_aln_matrix_loc='EDNAFULL'),
                               dict(sequence=wt,gap_incentive=[0,0,1,0,0,0,0]))
    assert scoring is None
    counts=Counter()
    _observe(dict(Reference_Sequence=wt,Aligned_Sequence=wt),(wt,pe,(1,4)),11,counts,scoring)
    assert counts['fixed_WT']==11 and counts['unassessable']==11
    assert counts['unqualified_alignment_scoring']==11
