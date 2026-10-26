"""Ambiguity-only placements veto single-copy uniqueness, never qualify reads."""
import json
from pathlib import Path

import pytest

from peanalyzer.geometry import geometry
from peanalyzer.remediation import indel_designs,pair,panel
from peanalyzer.routing import RoutingPolicy,route_pair
from test_readthrough import records,targets

EVIDENCE=Path(__file__).resolve().parents[1]/'docs/validation/readthrough-singlecopy'
BASELINE=json.loads((EVIDENCE/'baseline-070.json').read_text())
DESIGNS={d['id']:ts for d,ts in indel_designs()}


@pytest.mark.parametrize('expected',BASELINE,ids=lambda r:r['design']+'-'+r['copy'])
def test_all_72_single_copy_panels_retain_070_decisions(expected):
    target=next(t for t in DESIGNS[expected['design']] if t.copy_name==expected['copy'])
    report=geometry([target])
    assert report['status']==expected['geometry_status']
    assert report['reasons']==expected['geometry_reasons']
    for trial in expected['trials']:
        sequence=target.wt_sequence if trial['state']=='WT' else target.prime_edited_sequence
        result=route_pair(pair(sequence,length=trial['length']),[target],report,RoutingPolicy())
        assert {k:result[k] for k in ('category','assigned_copy','reason')}=={k:trial[k] for k in ('category','assigned_copy','reason')}


@pytest.mark.parametrize('seed,copy',[(11,'copy2'),(29,'copy1'),(29,'copy2'),(47,'copy2')])
def test_four_audited_wt_routing_flips_are_restored(seed,copy):
    target=next(t for t in DESIGNS[f'deletion_60_seed{seed}'] if t.copy_name==copy)
    report=geometry([target]);result=route_pair(pair(target.wt_sequence,length=100),[target],report,RoutingPolicy())
    assert report['status']=='BLOCKED'
    assert result['category']=='ALIGNMENT_FAILURE' and result['assigned_copy'] is None
    assert result['reason']=='nonunique single-copy placement'
    assert any(a['viable_placements'] for a in result['alignments'])
    witnesses=[a for a in result['alignments'] if a.get('ambiguity_only_placements')]
    assert witnesses and all(a['viable_placements']==0 and a['failure']=='STATE_IDENTITY_BELOW_MINIMUM' for a in witnesses)


@pytest.mark.parametrize('mate',[1,2])
@pytest.mark.parametrize('different_span',[False,True])
def test_witness_union_is_used_only_for_span_veto(monkeypatch,mate,different_span):
    import peanalyzer.routing as routing
    original=routing.copy_placements;target=panel()[0];report=geometry([target]);recs=pair(target.wt_sequence)
    before=route_pair(recs,[target],report,RoutingPolicy())
    assert before['assigned_copy']==target.copy_name
    def add_witness(*args):
        placements,audit=original(*args)
        if args[3]==mate:
            witness=dict(placements[0])
            if different_span:del witness[max(witness)]
            args[-1].append(witness)
        return placements,audit
    monkeypatch.setattr(routing,'copy_placements',add_witness)
    after=route_pair(recs,[target],report,RoutingPolicy())
    assert after['alignments']==before['alignments']  # No new viable placement or edit coverage.
    if different_span:
        assert after['category']=='ALIGNMENT_FAILURE' and after['reason']=='nonunique single-copy placement'
    else:assert after==before


def test_witness_without_qualified_placement_cannot_assign(monkeypatch):
    import peanalyzer.routing as routing
    def witnesses_only(*args):
        args[-1].append({0:('A',40,0),239:('T',40,149)})
        return [],[]
    monkeypatch.setattr(routing,'copy_placements',witnesses_only)
    target=panel()[0];result=route_pair(pair(target.wt_sequence),[target],geometry([target]),RoutingPolicy())
    assert result['assigned_copy'] is None and result['reason']=='COPY_HAS_NO_QUALIFIED_STATE_PLACEMENT'


@pytest.mark.parametrize('state',['wt_sequence','prime_edited_sequence'])
@pytest.mark.parametrize('lengths',[(150,150),(211,211),(238,238),(238,273)])
def test_unique_single_copy_readthrough_still_assigns(state,lengths):
    target=targets()[0];result=route_pair(records(getattr(target,state),*lengths),[target],geometry([target]),RoutingPolicy())
    assert result['category']=='ASSIGNED_COPY' and result['assigned_copy']==target.copy_name
    assert RoutingPolicy().min_alignment_identity==0.8


def test_witness_cannot_rescue_an_empty_qualified_projection(monkeypatch):
    import peanalyzer.routing as routing
    def unprojected(*args):
        args[-1].append({0:('A',40,0),239:('T',40,149)})
        return [{}],[]
    monkeypatch.setattr(routing,'copy_placements',unprojected)
    target=panel()[0];result=route_pair(pair(target.wt_sequence),[target],geometry([target]),RoutingPolicy())
    assert result['assigned_copy'] is None and result['reason']=='nonunique single-copy placement'
