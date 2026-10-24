"""D1/D2 terminal read-through invariance without relaxed internal evidence."""
from dataclasses import replace
import random

import pytest

from peanalyzer.fastq import FastqRecord
from peanalyzer.geometry import aligner,geometry,columns
from peanalyzer.routing import RoutingPolicy,route_pair,reference_span_identity
from peanalyzer.observability import assess_pair,reconstruct,reconstruct_product,population_observability
from peanalyzer.remediation import panel,pair
from peanalyzer.schemas import reverse_complement


def targets():
    return [t.model_copy(update={k:getattr(t,k)[:211] for k in ('wt_sequence','prime_edited_sequence')}) for t in panel()]


def records(sequence,left=150,right=150,tail='random'):
    rng=random.Random(713)
    result=[]
    for mate,length in ((1,left),(2,right)):
        seq=sequence[:length] if mate==1 else reverse_complement(sequence[-length:])
        extra=max(0,length-len(sequence))
        seq+=(''.join(rng.choice('ACGT') for _ in range(extra)) if tail=='random' else (tail*(extra+1))[:extra])
        result.append(FastqRecord(f'@read/{mate}\n'.encode(),(seq+'\n').encode(),b'+\n',('I'*len(seq)+'\n').encode()))
    return tuple(result)


@pytest.mark.parametrize('state',['wt_sequence','prime_edited_sequence'])
@pytest.mark.parametrize('lengths',[(150,150),(211,211),(238,238),(238,273),(273,238),(211,273)])
def test_exact_readthrough_matrix(state,lengths):
    ts=targets();seq=getattr(ts[0],state)
    actual=assess_pair(records(seq,*lengths),ts)
    assert actual['reason'] is None
    assert actual['sequence']==seq
    assert actual['canonical']==('exact_WT' if state=='wt_sequence' else 'exact_PE')


@pytest.mark.parametrize('tail',['random','A','AC','GCTAGCCAT'])
@pytest.mark.parametrize('state',['wt_sequence','prime_edited_sequence'])
def test_terminal_sequence_not_biological_identity(tail,state):
    ts=targets();seq=getattr(ts[0],state)
    assert assess_pair(records(seq,500,700,tail),ts)['canonical']==assess_pair(records(seq,211,211),ts)['canonical']


@pytest.mark.parametrize('lengths',[(150,150),(211,211),(238,238),(238,273),(273,238)])
def test_both_routing_orientations(lengths):
    ts=targets();report=geometry(ts);policy=RoutingPolicy()
    for t in ts:
        for seq in (t.wt_sequence,t.prime_edited_sequence):
            result=route_pair(records(seq,*lengths),ts,report,policy)
            assert (result['category'],result['assigned_copy'])==('ASSIGNED_COPY',t.copy_name)
    assert policy.min_alignment_identity==0.8


@pytest.mark.parametrize('kind',['mismatch','insertion','deletion'])
def test_internal_disagreement_stays_in_identity(kind):
    reference=panel()[0].wt_sequence
    if kind=='mismatch':query=reference[:60]+''.join('A' if b!='A' else 'C' for b in reference[60:70])+reference[70:]
    elif kind=='insertion':query=reference[:60]+'AGCTAGCTAG'+reference[60:]
    else:query=reference[:60]+reference[70:]
    engine=aligner(reads=True)
    alignment=engine.align(reference,query)[0]
    cols=columns(alignment);paired=[i for i,(a,b) in enumerate(cols) if a is not None and b is not None]
    span=cols[paired[0]:paired[-1]+1]
    expected=sum(a is not None and b is not None and reference[a]==query[b] for a,b in span)/len(span)
    identity=reference_span_identity(reference,query,alignment)
    assert identity==expected and identity<1
    assert any(a is None for a,b in span) if kind=='insertion' else True
    assert any(b is None for a,b in span) if kind=='deletion' else True
    terminal=reference+'AGCTAGCTAG'
    assert reference_span_identity(reference,terminal,engine.align(reference,terminal)[0])==1


def test_low_identity_biological_alignment_still_fails():
    ts=targets();seq='N'*len(ts[0].wt_sequence)
    result=route_pair(records(seq,238,273),ts,geometry(ts),RoutingPolicy())
    assert result['category']=='ALIGNMENT_FAILURE'
    assert any(a.get('failure')=='STATE_IDENTITY_BELOW_MINIMUM' for a in result['alignments'])


@pytest.mark.parametrize('attack',['mismatch','insertion','deletion','truncated','mate_disagreement','insufficient_mate'])
@pytest.mark.parametrize('state',['wt_sequence','prime_edited_sequence'])
def test_nonexact_and_partial_never_gain_exactness(attack,state):
    ts=targets();seq=getattr(ts[0],state)
    changed=seq[:50]+('A' if seq[50]!='A' else 'C')+seq[51:]
    if attack=='mismatch':seq=changed
    elif attack=='insertion':seq=seq[:50]+'AGCT'+seq[50:]
    elif attack=='deletion':seq=seq[:50]+seq[54:]
    elif attack=='truncated':seq=seq[20:-20]
    recs=records(seq,238,273)
    if attack=='mate_disagreement':recs=(recs[0],records(changed,238,273)[1])
    if attack=='insufficient_mate':recs=records(seq,238,9)
    result=assess_pair(recs,ts)
    assert result['canonical'] not in ('exact_WT','exact_PE')


@pytest.mark.parametrize('attack',['double_reference','other_copy_in_tail','periodic_product'])
def test_multiple_product_boundaries_fail_closed(attack):
    ts=targets();seq=ts[0].wt_sequence
    if attack=='periodic_product':
        ts=[ts[0].model_copy(update={'wt_sequence':'AC'*100,'prime_edited_sequence':'AC'*50+'TT'+'AC'*49})]
        seq=ts[0].wt_sequence;recs=records(seq,238,273,'AC')
    else:
        tail=seq if attack=='double_reference' else ts[1].wt_sequence
        recs=records(seq,len(seq)*2,len(seq)*2,tail)
    result=assess_pair(recs,ts)
    assert result['canonical']=='other_or_unassessable' and result['reason']


def test_state_collision_and_order_symmetry():
    ts=targets();first=ts[0];seq=first.wt_sequence
    ts[1]=ts[1].model_copy(update={'prime_edited_sequence':seq})
    recs=records(seq,238,273)
    assert assess_pair(recs,ts)['canonical']=='state_collision'
    a,b=assess_pair(recs,ts),assess_pair(recs,list(reversed(ts)))
    for result in (a,b): result['geometry'].sort(key=lambda row:row['copy'])
    assert a==b


@pytest.mark.parametrize('state',['wt_sequence','prime_edited_sequence'])
def test_state_label_swap_does_not_choose_trimming(state):
    ts=targets();swapped=[t.model_copy(update={'wt_sequence':t.prime_edited_sequence,'prime_edited_sequence':t.wt_sequence}) for t in ts]
    recs=records(getattr(ts[0],state),238,273)
    a,b=assess_pair(recs,ts),assess_pair(recs,swapped)
    assert a['sequence']==b['sequence'] and a['reason']==b['reason'] is None
    assert {a['canonical'],b['canonical']}=={'exact_WT','exact_PE'}


def test_population_uses_same_biological_reconstruction(tmp_path):
    ts=targets();recs=records(ts[0].wt_sequence,400,400,'AC')
    paths=[tmp_path/f'R{i}.fastq' for i in (1,2)]
    for p,r in zip(paths,recs):p.write_bytes(r.to_bytes())
    assert assess_pair(recs,ts)['canonical']=='exact_WT'
    assert not population_observability(paths,ts)['reconstruction_ambiguity_reason_counts']


@pytest.mark.parametrize('seed',[11,29,47])
def test_deletion_competing_placement_remains_an_ambiguity_veto(seed):
    from peanalyzer.remediation import indel_designs
    ts=next(ts for d,ts in indel_designs() if d['id']==f'deletion_60_seed{seed}')
    report=geometry(ts)
    assert report['status']=='BLOCKED'
    for t in ts:
        result=route_pair(pair(t.wt_sequence,length=100),ts,report,RoutingPolicy())
        assert result['assigned_copy'] is None
        assert result['reason']=='diagnostic placement differs across competing alignments'
        witnesses=[a for a in result['alignments'] if a.get('ambiguity_only_placements')]
        assert witnesses
        assert all(a['failure']=='STATE_IDENTITY_BELOW_MINIMUM' and a['viable_placements']==0 for a in witnesses)


def test_ambiguity_support_excludes_terminal_query_bases_but_never_qualifies():
    from peanalyzer.routing import deletion_ambiguity_candidate
    reference=panel()[0].wt_sequence
    query=reference[:60]+reference[140:]
    policy=RoutingPolicy()
    for left,right in [('', ''), ('G'*73, 'T'*91)]:
        # Explicit alignment columns separate boundary semantics from aligner heuristics.
        cols=[(None,i) for i in range(len(left))]
        cols += [(i,len(left)+i) for i in range(60)]
        cols += [(i,None) for i in range(60,140)]
        cols += [(i,len(left)+i-80) for i in range(140,len(reference))]
        cols += [(None,len(left)+len(query)+i) for i in range(len(right))]
        assert deletion_ambiguity_candidate(reference,left+query+right,cols,policy)
        damaged='N'*60+query[60:]
        assert not deletion_ambiguity_candidate(reference,left+damaged+right,cols,policy)


@pytest.mark.parametrize('different',[False,True])
def test_rejected_witness_only_vetoes_conflicting_diagnostic_projection(monkeypatch,different):
    import peanalyzer.routing as routing
    original=routing.copy_placements
    def witness(*args):
        placements,audit=original(*args)
        if placements and 40 in placements[0]:
            extra=dict(placements[0])
            if different:
                b,q,p=extra[40];extra[40]=(b,q,p+1)
            args[-1].append(extra)
        return placements,audit
    monkeypatch.setattr(routing,'copy_placements',witness)
    ts=targets();result=route_pair(records(ts[0].wt_sequence,238,273),ts,geometry(ts),RoutingPolicy())
    assert (result['assigned_copy'] is None)==different


@pytest.mark.parametrize('tail',['random','A','AC','GCTAGCCAT'])
def test_unique_routing_with_long_terminal_overhang(tail):
    ts=targets();report=geometry(ts)
    for t in ts:
        for seq in (t.wt_sequence,t.prime_edited_sequence):
            a=route_pair(records(seq,211,211),ts,report,RoutingPolicy())
            b=route_pair(records(seq,500,700,tail),ts,report,RoutingPolicy())
            assert (a['category'],a['assigned_copy'])==(b['category'],b['assigned_copy'])==('ASSIGNED_COPY',t.copy_name)


def test_query_insertion_at_internal_reference_coordinate_is_not_terminal():
    reference=panel()[0].wt_sequence
    query='A'*150
    alignment=aligner(reads=True).align(reference,query)[0]
    assert reference_span_identity(reference,query,alignment)<0.8
    ts=panel()
    assert route_pair(pair('A'*200),ts,geometry(ts),RoutingPolicy())['category']=='ALIGNMENT_FAILURE'
