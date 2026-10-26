"""Final N1/N2 regressions without changing the established routing architecture."""

import hashlib
import json
from pathlib import Path

import pytest

from peanalyzer.backend.comparator import evaluate_anchors, normalize_include_idxs
from peanalyzer.fastq import FastqRecord
from peanalyzer.geometry import geometry
from peanalyzer.qualification import qualify
from peanalyzer.remediation import panel, pair, indel_designs, qualify_indels
from peanalyzer.routing import route_pair, RoutingPolicy


FLANK_REASON='EDIT_COVERAGE_NOT_FLANKED_BY_OBSERVED_DIAGNOSTICS'


def partial_cases(*, longer_partials=False):
    targets=panel()
    cases=[]
    upstream_end,downstream_start=(160,85) if longer_partials else (145,115)
    for target,other in ((targets[0],targets[1]),(targets[1],targets[0])):
        for state in ('WT','PE'):
            own=target.wt_sequence if state=='WT' else target.prime_edited_sequence
            donor=other.wt_sequence if state=='WT' else other.prime_edited_sequence
            for kind,sequence in (
                ('upstream_partial_chimera',(own[:100]+donor[100:])[:upstream_end]),
                ('upstream_genuine_partial',own[:upstream_end]),
                ('downstream_partial_chimera',(donor[:140]+own[140:])[downstream_start:]),
                ('downstream_genuine_partial',own[downstream_start:]),
                ('fully_flanked_chimera',own[:100]+donor[100:]),
                ('genuine_flanks_on_different_mates',own),
            ):
                identifier=f'{target.copy_name}_{state}_{kind}'
                records=pair(sequence,identifier)
                expected='CONFLICTING_DIAGNOSTIC_EVIDENCE' if kind=='fully_flanked_chimera' else 'ASSIGNED_COPY' if kind=='genuine_flanks_on_different_mates' else FLANK_REASON
                cases.append(dict(read_id=identifier,truth_class=kind,state=state,diagnostic_copy=target.copy_name,
                                  edit_origin=other.copy_name if 'chimera' in kind else target.copy_name,
                                  expected_category=expected,fragment_sequence=sequence,records=records))
        for side,sequence in (('upstream',target.wt_sequence[25:110]),('downstream',target.wt_sequence[150:])):
            identifier=f'{target.copy_name}_{side}_does_not_cover_edit'
            cases.append(dict(read_id=identifier,truth_class=f'{side}_does_not_cover_edit',state='unobserved',
                              diagnostic_copy=target.copy_name,edit_origin='unobserved',expected_category='ASSIGNED_COPY',
                              fragment_sequence=sequence,records=pair(sequence,identifier)))
    return targets,cases


@pytest.mark.parametrize('case',partial_cases()[1],ids=lambda c:c['read_id'])
def test_partial_molecule_observed_flanks(case):
    targets,_=partial_cases()
    report=geometry(targets)
    assert report['status']=='SAFE'
    row=route_pair(case['records'],targets,report,RoutingPolicy())
    assert row['category']==case['expected_category']
    assert row['assigned_copy']==(case['diagnostic_copy'] if row['category']=='ASSIGNED_COPY' else None)
    assert row['edit_flanking']
    if case['expected_category']==FLANK_REASON:
        for flank in row['edit_flanking']:
            assert flank['pair_covers_edit'] and not flank['flanking_eligible']
            side='upstream' if case['truth_class'].startswith('upstream') else 'downstream'
            assert len(flank[f'observed_{side}_diagnostics'])==2
            opposite='downstream' if side=='upstream' else 'upstream'
            assert flank[f'observed_{opposite}_diagnostics']==[]
    elif 'does_not_cover_edit' in case['truth_class']:
        assert all(not f['pair_covers_edit'] and f['flanking_eligible'] for f in row['edit_flanking'])
    elif case['truth_class']=='genuine_flanks_on_different_mates':
        assert all(f['pair_covers_edit'] and f['flanking_eligible'] for f in row['edit_flanking'])
        observed={e['position']:{o['mate'] for o in e['observations']} for e in row['evidence']}
        assert observed[40]==observed[80]=={1}
        assert observed[165]==observed[205]=={2}


def test_genuine_and_chimeric_partial_sequences_are_intentionally_indistinguishable():
    _,cases=partial_cases()
    digest=lambda c:hashlib.sha256(b''.join(r.sequence_line+r.quality_line for r in c['records'])).hexdigest()
    for copy in ('copy1','copy2'):
        for state in ('WT','PE'):
            for side in ('upstream','downstream'):
                selected=[c for c in cases if c['diagnostic_copy']==copy and c['state']==state and c['truth_class'].startswith(side)]
                assert len(selected)==2 and digest(selected[0])==digest(selected[1])


def test_longer_partial_fragments_preserve_the_same_observed_flank_decisions():
    targets,cases=partial_cases(longer_partials=True)
    report=geometry(targets)
    for case in cases:
        row=route_pair(case['records'],targets,report,RoutingPolicy())
        assert row['category']==case['expected_category']


@pytest.mark.parametrize('start,end,covered',[(0,122,False),(0,123,True),(122,240,True),(123,240,False)])
def test_substitution_coverage_boundary(start,end,covered):
    targets=panel()
    row=route_pair(pair(targets[0].prime_edited_sequence[start:end]),targets,geometry(targets),RoutingPolicy())
    assert all(f['pair_covers_edit']==covered for f in row['edit_flanking'])
    assert row['category']==(FLANK_REASON if covered else 'ASSIGNED_COPY')


def test_unsequenced_gap_between_mates_is_not_edit_coverage():
    targets=panel();seq=targets[0].wt_sequence
    left=pair(seq[:90])[0];right=pair(seq[-30:])[1]
    row=route_pair((left,right),targets,geometry(targets),RoutingPolicy())
    assert row['category']=='ASSIGNED_COPY'
    assert all(not f['pair_covers_edit'] for f in row['edit_flanking'])


def test_three_copy_flanked_panel_keeps_all_copies_assignable():
    targets=panel(three=True)
    report=geometry(targets)
    assert report['status']=='SAFE'
    for target in targets:
        for sequence in (target.wt_sequence,target.prime_edited_sequence):
            row=route_pair(pair(sequence),targets,report,RoutingPolicy())
            assert row['assigned_copy']==target.copy_name


def test_low_quality_opposite_flank_cannot_rescue_partial_fragment():
    targets=panel();seq=targets[0].prime_edited_sequence[:190]
    records=list(pair(seq))
    r=records[1];q=bytearray(r.quality_line);q[189-165]=chr(20+33).encode()[0]
    records[1]=FastqRecord(r.header,r.sequence_line,r.plus,bytes(q))
    row=route_pair(tuple(records),targets,geometry(targets),RoutingPolicy())
    assert row['category']==FLANK_REASON
    assert all(not f['observed_downstream_diagnostics'] for f in row['edit_flanking'])


@pytest.mark.parametrize('design_id,fragment',[
    ('insertion_30_seed29','inside_insert_to_end'),
    ('insertion_30_seed29','wt_before_boundary'),
    ('deletion_1_seed29','deletion_junction_upstream_only'),
])
def test_indel_edit_coverage_uses_state_coordinates(design_id,fragment):
    descriptor,targets=next((d,ts) for d,ts in indel_designs() if d['id']==design_id)
    report=geometry(targets)
    assert report['status']=='SAFE'
    target=targets[0]
    if fragment=='inside_insert_to_end': sequence=target.prime_edited_sequence[descriptor['edit_start']+10:]
    elif fragment=='wt_before_boundary': sequence=target.wt_sequence[:descriptor['edit_start']]
    else: sequence=target.prime_edited_sequence[:145]
    row=route_pair(pair(sequence),targets,report,RoutingPolicy())
    assert row['category']==('ASSIGNED_COPY' if fragment=='wt_before_boundary' else FLANK_REASON)


def test_original_125_decisions_and_indel_admission_are_unchanged(tmp_path):
    result=qualify(tmp_path/'regression')
    assert (result['input_pairs'],result['assigned_pairs'],result['quarantined_pairs'])==(125,75,50)
    assert result['cross_routed_ids']==[] and result['routing_gate']=='PASS'
    historical=Path(__file__).resolve().parents[1]/'docs/validation/m311/original_125/routing_ledger.jsonl'
    read=lambda p:{r['read_id']:(r['category'],r['assigned_copy'],r['compatible_copies'])
                   for r in (json.loads(s) for s in p.read_text().splitlines())}
    assert read(historical)==read(tmp_path/'regression/routing/routing_ledger.jsonl')
    rows=qualify_indels()
    assert len(rows)==36 and sum(r['geometry_status']!='BLOCKED' for r in rows)==13
    assert all(r['passed'] and r['cross_assignments']==0 for r in rows)
    before=json.loads((historical.parents[1]/'indels_after.json').read_text())
    assert {r['id']:r['geometry_status'] for r in rows}=={r['id']:r['geometry_status'] for r in before}


def metrics_with_window(window):
    return {c:dict(native=dict(backend_input_reads=125,reads_after_preprocessing=125,preprocessing_count_delta=0,aligned_reads=105,unaligned_reads=20,numerator=30,denominator=105),
                   authoritative_reference_quantification_window=window) for c in ('copy1','copy2')}


@pytest.mark.parametrize('window',[[40,111,112],{'_type':'np.ndarray','value':[40,111,112]}])
def test_authoritative_window_diagnostic_blocks_both_serializations(window):
    result=evaluate_anchors(panel(),metrics_with_window(window))
    assert result['status']=='BLOCKED'
    assert result['anchor_invariant']
    assert result['authoritative_window_diagnostics']=={'copy1':[40],'copy2':[40]}
    assert 'DIAGNOSTIC_IN_AUTHORITATIVE_QUANTIFICATION_WINDOW' in result['reasons']


def test_real_backend_ndarray_serialization_is_normalized():
    path=Path(__file__).resolve().parents[1]/'docs/validation/m311/unrouted_core/m31/copy1/CRISPResso2_info.json'
    window=json.loads(path.read_text())['results']['refs']['Reference']['include_idxs']
    assert window['_type']=='np.ndarray' and isinstance(window['value'],list)
    assert normalize_include_idxs(window,240)==sorted(set(window['value']))
    # Same actual serialization shape with one diagnostic inside the window.
    window['value'].append(40)
    result=evaluate_anchors(panel(),metrics_with_window(window))
    assert result['status']=='BLOCKED' and result['authoritative_window_diagnostics']['copy1']==[40]


@pytest.mark.parametrize('window',[
    {},{'_type':'unknown','value':[40]},{'_type':'np.ndarray'},
    {'_type':'np.ndarray','value':'40'},{'_type':'np.ndarray','value':[[40]]},
    {'_type':'np.ndarray','value':[40],'extra':True},'40',[True],[40.0],['40'],[-1],[240],
])
def test_malformed_authoritative_windows_fail_closed(window):
    with pytest.raises(ValueError): normalize_include_idxs(window,240)
    result=evaluate_anchors(panel(),metrics_with_window(window))
    assert result['status']=='BLOCKED'
    assert 'AUTHORITATIVE_QUANTIFICATION_WINDOW_INVALID' in result['reasons']
    assert result['authoritative_windows']=={}


def test_valid_empty_window_is_distinct_from_missing_or_malformed():
    assert normalize_include_idxs([],240)==normalize_include_idxs({'_type':'np.ndarray','value':[]},240)==[]
    result=evaluate_anchors(panel(),metrics_with_window(None))
    assert result['status']=='BLOCKED' and 'AUTHORITATIVE_QUANTIFICATION_WINDOW_MISSING' in result['reasons']


@pytest.mark.parametrize('field',['backend_input_reads','aligned_reads','unaligned_reads','numerator','denominator'])
def test_ndarray_window_does_not_weaken_anchor_invariance(field):
    metrics=metrics_with_window({'_type':'np.ndarray','value':[111,112]})
    metrics['copy2']['native'][field]+=1
    result=evaluate_anchors(panel(),metrics)
    assert result['status']=='BLOCKED' and not result['anchor_invariant']
    assert 'ANCHOR_DEPENDENT_NATIVE_RESULT' in result['reasons']
