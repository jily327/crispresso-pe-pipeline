"""Independent regression attacks on the M3.1.1 routing boundary."""

import json

import pytest

from peanalyzer.backend.core import verify_routing_output, run_confident_core
from peanalyzer.backend.comparator import evaluate_anchors
from peanalyzer.demux_verify import sha256_file
from peanalyzer.geometry import geometry, edit_regions
from peanalyzer.qualification import qualify
from peanalyzer.remediation import panel, pair, indel_designs, chimera_challenges, difficult_challenges
from peanalyzer.routing import RoutingPolicy, route_pair, route_analysis


@pytest.mark.parametrize('descriptor,targets',list(indel_designs()),ids=lambda x:x['id'] if isinstance(x,dict) else None)
def test_indel_design_is_symmetric_or_explicitly_blocked(descriptor,targets):
    report=geometry(targets)
    outcomes={}
    for t in targets:
        for state,seq in [('WT',t.wt_sequence),('PE',t.prime_edited_sequence)]:
            for length in (100,150,len(seq)):
                row=route_pair(pair(seq,length=length),targets,report,RoutingPolicy())
                assert row['assigned_copy'] in (None,t.copy_name)
                outcomes[t.copy_name,state,length]=row['assigned_copy']
    if report['status']!='BLOCKED':
        assert all(v==k[0] for k,v in outcomes.items())
    elif any(v is None for v in outcomes.values()):
        assert 'PE_EDIT_GEOMETRY_ROUTING_UNQUALIFIED' in {r['code'] for r in report['reasons']}


def test_poor_state_does_not_veto_good_state():
    targets=next(ts for d,ts in indel_designs() if d['id']=='insertion_30_seed29')
    report=geometry(targets)
    rows=[route_pair(pair(t.prime_edited_sequence),targets,report,RoutingPolicy()) for t in targets]
    assert all(r['category']=='ASSIGNED_COPY' for r in rows)
    assert any(a.get('failure') for r in rows for a in r['alignments'])


def test_competing_copy_failure_is_not_positive_evidence(monkeypatch):
    import peanalyzer.routing as routing
    original=routing.copy_placements
    def missing(sequence,qualities,target,*args):
        return ([],[]) if target.copy_name=='copy2' else original(sequence,qualities,target,*args)
    monkeypatch.setattr(routing,'copy_placements',missing)
    targets=panel()
    row=route_pair(pair(targets[0].wt_sequence),targets,geometry(targets),RoutingPolicy())
    assert row['assigned_copy'] is None
    assert row['reason']=='COPY_HAS_NO_QUALIFIED_STATE_PLACEMENT'


def test_equivalent_query_projection_cannot_be_resolved_by_identical_base(monkeypatch):
    import peanalyzer.routing as routing
    original=routing.copy_placements
    def ambiguous(*args):
        placements,audit=original(*args)
        extra=dict(placements[0])
        if 40 not in extra: return placements,audit
        base,q,pos=extra[40];extra[40]=(base,q,pos+1)
        return placements+[extra],audit
    monkeypatch.setattr(routing,'copy_placements',ambiguous)
    targets=panel()
    assert route_pair(pair(targets[0].wt_sequence),targets,geometry(targets),RoutingPolicy())['category']=='ALIGNMENT_FAILURE'


@pytest.mark.parametrize('positions',[(20,45,70,90),(150,170,195,220),(40,)])
def test_one_sided_geometry_is_blocked(positions):
    report=geometry(panel(positions))
    assert report['status']=='BLOCKED'
    assert 'EDIT_NOT_FLANKED_BY_PAIR_DIAGNOSTICS' in {r['code'] for r in report['reasons']}
    if len(positions)==1:
        assert 'INSUFFICIENT_PAIR_DIAGNOSTICS_FOR_ROUTING_POLICY' in {r['code'] for r in report['reasons']}


def test_geometry_counts_match_selected_policy_and_reports_distances():
    report=geometry(panel())
    assert report['status']=='SAFE'
    flank=report['pairwise'][0]['edit_flanks'][0]
    assert flank['upstream']==[40,80] and flank['downstream']==[165,205]
    assert (flank['upstream_distance'],flank['downstream_distance'])==(42,43)
    assert geometry(panel(),min_distinguishing_sites=5)['status']=='BLOCKED'


def test_contiguous_edit_interval_and_insertion_boundary():
    edits=[dict(wt_position=None,wt_boundary=122,kind='insertion')]*3
    assert edit_regions(edits)==[dict(start=122,end=122,kinds=['insertion'])]
    edits=[dict(wt_position=p,kind='deletion') for p in range(122,162)]
    assert edit_regions(edits)==[dict(start=122,end=162,kinds=['deletion'])]


def test_chimeric_edit_transfer():
    rows=chimera_challenges()
    assert len(rows)==48 and all(r['passed'] for r in rows)
    assert not any(r['production_admitted'] for r in rows)
    supported=[r for r in rows if r['geometry'] in ('flanked','three_copy')]
    assert all(r['category']=='CONFLICTING_DIAGNOSTIC_EVIDENCE' for r in supported)


def test_matched_difficult_states_are_not_duplicate_evidence():
    rows=difficult_challenges()
    assert len(rows)==36 and all(r['passed'] for r in rows)
    assert len({r['content_sha256'] for r in rows})==len(rows)
    for copy in ('copy1','copy2'):
        for kind in {r['truth_class'] for r in rows}:
            matched=[r for r in rows if r['copy']==copy and r['truth_class']==kind]
            assert len(matched)==2 and matched[0]['category']==matched[1]['category']


@pytest.fixture(scope='module')
def regression(tmp_path_factory):
    root=tmp_path_factory.mktemp('regression')/'m31'
    result=qualify(root)
    return root,result


def test_original_125_is_unchanged(regression):
    root,result=regression
    assert result['routing_gate']=='PASS'
    assert (result['input_pairs'],result['assigned_pairs'],result['quarantined_pairs'])==(125,75,50)
    assert result['cross_routed_ids']==result['unsafe_assigned_ids']==[]
    verify_routing_output(root/'routing')


@pytest.mark.parametrize('attack',['quarantine_assigned','unknown_copy','compatible','missing_compatible','category_counts','cohort_counts','duplicate_id','wrong_id','unknown_category','policy_identity'])
def test_ledger_semantic_attacks(regression,tmp_path,attack):
    import shutil
    root,_=regression
    destination=tmp_path/'routing';shutil.copytree(root/'routing',destination)
    ledger=destination/'routing_ledger.jsonl';manifest=destination/'routing_manifest.json'
    rows=[json.loads(s) for s in ledger.read_text().splitlines()];data=json.loads(manifest.read_text())
    assigned=next(r for r in rows if r['assigned_copy'])
    quarantined=next(r for r in rows if not r['assigned_copy'])
    if attack=='quarantine_assigned': assigned['category']='CONFLICTING_DIAGNOSTIC_EVIDENCE'
    elif attack=='unknown_copy': assigned['assigned_copy']='copy999'
    elif attack=='compatible': assigned['compatible_copies']=['copy1','copy2']
    elif attack=='missing_compatible': assigned.pop('compatible_copies')
    elif attack=='category_counts': data['categories']['ASSIGNED_COPY']+=1
    elif attack=='cohort_counts': data['cohorts']['copy1']['pairs']+=1
    elif attack=='duplicate_id': rows.append(rows[0])
    elif attack=='wrong_id': assigned['read_id']='absent'
    elif attack=='unknown_category': quarantined['category']='UNKNOWN'
    elif attack=='policy_identity': data['policy_identity']['qualified']=False
    ledger.write_text(''.join(json.dumps(r)+'\n' for r in rows));data['ledger_sha256']=sha256_file(ledger)
    manifest.write_text(json.dumps(data))
    with pytest.raises(ValueError): verify_routing_output(destination)


@pytest.mark.parametrize('policy',[RoutingPolicy(diagnostic_min_quality=0,min_distinguishing_sites=1),
                                  RoutingPolicy(diagnostic_min_quality=20),RoutingPolicy(max_equivalent_alignments=17),
                                  RoutingPolicy(min_alignment_identity=.7)])
def test_unqualified_policy_never_reaches_core(regression,tmp_path,policy):
    root,_=regression
    output=tmp_path/'experimental'
    manifest=route_analysis(root/'analysis','1B',panel(),output,policy)
    assert not manifest['policy_identity']['qualified']
    verify_routing_output(output)
    with pytest.raises(ValueError,match='requires qualified routing policy'):
        run_confident_core(output,'copy1',tmp_path/'core',None)


def anchor_metrics():
    return {c:dict(native=dict(backend_input_reads=125,reads_after_preprocessing=125,preprocessing_count_delta=0,aligned_reads=105,unaligned_reads=20,numerator=30,denominator=105),
                   authoritative_reference_quantification_window=[111,112,*range(140,150)]) for c in ('copy1','copy2')}


@pytest.mark.parametrize('field',['backend_input_reads','aligned_reads','unaligned_reads','numerator','denominator'])
def test_anchor_dependence_blocks_every_integer(field):
    metrics=anchor_metrics();metrics['copy2']['native'][field]+=1
    result=evaluate_anchors(panel(),metrics)
    assert not result['anchor_invariant'] and result['status']=='BLOCKED'


def test_comparator_requires_all_anchors_edit_state_and_authoritative_window():
    metrics=anchor_metrics()
    assert evaluate_anchors(panel(),metrics)['status']=='SUPPORTED_IN_TESTED_FIXTURE'
    metrics['copy2']['authoritative_reference_quantification_window'].append(40)
    assert evaluate_anchors(panel(),metrics)['status']=='BLOCKED'
    metrics=anchor_metrics();metrics.pop('copy2')
    assert evaluate_anchors(panel(),metrics)['status']=='BLOCKED'
    targets=panel();targets[1]=targets[1].model_copy(update={'prime_edited_sequence':targets[1].wt_sequence})
    assert evaluate_anchors(targets,anchor_metrics())['status']=='BLOCKED'
