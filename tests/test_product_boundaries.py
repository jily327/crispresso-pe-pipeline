"""Overlength fragments challenge whole-product identity independently of edit status."""
import random
from types import SimpleNamespace

import pytest

from peanalyzer.haplotypes import full_call
from peanalyzer.observability import assess_pair, readthrough_boundaries, reconstruct_product
from peanalyzer.schemas import reverse_complement
from m7_fixtures import fixture
from peanalyzer.validation import load_targets


def reads(molecule, left_length, right_length):
    return (SimpleNamespace(sequence=molecule[:left_length].encode()),
            SimpleNamespace(sequence=reverse_complement(molecule[-right_length:]).encode()))


@pytest.mark.parametrize('swapped',[False,True])
@pytest.mark.parametrize('length_difference',[-11,0,17])
def test_competing_tandem_excludes_exact_and_four_template(tmp_path,swapped,length_difference):
    target=load_targets(fixture(tmp_path/'inputs',samples=1,copies=1,reads=0)['targets'])[0]
    wt=target.wt_sequence
    pe=target.prime_edited_sequence
    if length_difference < 0:
        pe=pe[:60]+pe[60-length_difference:]
    elif length_difference:
        pe=pe[:60]+'T'*length_difference+pe[60:]
    target=target.model_copy(update={'prime_edited_sequence':pe})
    panel=SimpleNamespace(templates={wt:[('copy','WT')],pe:[('copy','AB')]})
    n=len(pe)
    pair=reads(pe+pe,n+8,n+9)
    evidence=assess_pair(pair[::-1] if swapped else pair,[target])
    assert evidence['canonical']=='other_or_unassessable'
    assert evidence['reason']=='COMPETING_UNTRIMMED_PRODUCT'
    assert evidence['sequence']==pe+pe
    reasons=set()
    assert full_call(pair[0].sequence.decode(),reverse_complement(pair[1].sequence.decode()),panel,reasons) is None
    assert reasons=={'COMPETING_UNTRIMMED_PRODUCT'}


def test_readthrough_boundary_uses_the_opposite_mate_end():
    rng=random.Random(28121)
    product=''.join(rng.choices('ACTG',k=200))
    # Both overlong, or a single overlong mate in either orientation.
    for left,right in [(product+'GCTA','CTTG'+product),(product+'GCTA',product[-69:]),
                       (product[:88],'CTTG'+product)]:
        assert readthrough_boundaries(left,right)=={200}
        assert reconstruct_product(left,right,(product,))==(product,None)
    # Repeated opposite mate in the read-through tail also supports another boundary.
    mate=product[-60:]
    left=product+'GCTA'+mate+'T'
    assert readthrough_boundaries(left,mate)>={200,len(left)-1}
    assert reconstruct_product(left,mate,(product,))==(None,'UNRESOLVED_READTHROUGH_BOUNDARY')
