import pytest

from peanalyzer.backend.pe_window import audit_window
from peanalyzer.backend.pooled import BackendError, backend_target
from peanalyzer.backend.synthetic import changed
from peanalyzer.geometry import geometry
from peanalyzer.pe_reference import mirror_window, native_reference
from peanalyzer.remediation import panel
from peanalyzer.schemas import reverse_complement


def inverted(target):
    return target.model_copy(update=dict(
        wt_sequence=reverse_complement(target.wt_sequence),
        prime_edited_sequence=reverse_complement(target.prime_edited_sequence),
        quantification_window_coordinates=mirror_window(target.quantification_window_coordinates,len(target.wt_sequence))))


def polymorphic_panel():
    first, secondary = panel()
    pos = 140
    def mutate(sequence): return sequence[:pos] + changed(sequence[pos]) + sequence[pos+1:]
    secondary=secondary.model_copy(update=dict(wt_sequence=mutate(secondary.wt_sequence),
                                               prime_edited_sequence=mutate(secondary.prime_edited_sequence)))
    return [first, secondary]


@pytest.mark.parametrize('window', [None,'0','0-1_20-28_200-200'])
def test_each_copy_preserves_all_experimental_inputs(window):
    target=panel()[0].model_copy(update=dict(quantification_window_coordinates=window))
    reverse=inverted(target)
    plan=backend_target(reverse)
    assert plan.orientation=='reverse' and plan.backend==target
    g=geometry([reverse],reference_only=True)
    assert g['status']!='BLOCKED'
    annotation=g['copies'][reverse.copy_name]
    forward=geometry([target],reference_only=True)['copies'][target.copy_name]
    assert sorted(len(target.wt_sequence)-1-p for p in annotation['quantification_window_positions'])==forward['quantification_window_positions']
    assert annotation['edits'][0]['wt_position']==len(target.wt_sequence)-1-forward['edits'][0]['wt_position']


def test_ambiguous_orientation_and_unmatched_extension_are_rejected_even_with_explicit_window():
    target=panel()[0]
    wt=target.wt_sequence
    for replace, orientation in [(reverse_complement(target.pegRNA_spacer),'both'),(target.pegRNA_spacer,'multiple')]:
        ambiguous=target.model_copy(update=dict(wt_sequence=replace+wt[len(replace):]))
        assert native_reference(ambiguous).orientation==orientation
        with pytest.raises(BackendError,match='NONUNIQUE_SPACER_LOCATION'): backend_target(ambiguous)
    missing=target.model_copy(update=dict(pegRNA_extension='A'*30,quantification_window_coordinates='10-20'))
    assert geometry([missing],reference_only=True)['status']=='BLOCKED'


@pytest.mark.parametrize('reverse', [False,True])
def test_retained_copy_variant_mapped_from_complete_extension(reverse):
    targets=polymorphic_panel()
    if reverse: targets=list(map(inverted,targets))
    g=geometry(targets,reference_only=True)
    assert g['status']!='BLOCKED'
    info=g['copies']['copy2']['native_reference']
    assert info['native_error']=='PE_EXTENSION_LOCATION_UNSUPPORTED'
    m=info['extension_match']
    assert (m['status'],m['mismatch_count'],m['anchor_copies'])==('copy_polymorphism',1,['copy1'])
    row=m['mismatches'][0];pos=239-140 if reverse else 140
    assert row['original_wt_position']==row['original_pe_position']==pos
    assert row['experimental_extension_index']==4
    assert row['observed']==targets[1].wt_sequence[pos] and row['expected']==targets[0].wt_sequence[pos]
    assert not next(d for d in g['diagnostics'] if d['position']==pos)['usable_for_routing']


def test_window_audit_uses_authoritative_instead_of_predicted_positions():
    tgt=inverted(panel()[0]);plan=native_reference(tgt)
    refs={name:dict(sequence=seq,include_idxs={'_type':'np.ndarray','value':[10,11]})
          for name,seq in [('Reference',plan.backend.wt_sequence),('Prime-edited',plan.backend.prime_edited_sequence)]}
    report={}
    audit_window(report,plan,refs)
    assert report['authoritative_reference_quantification_window']==[228,229]
    assert report['window_audit']['outside_intended_edits'][0]['wt_position']==117


def test_secondary_analyzed_alone_does_not_infer_natural_polymorphism():
    _, secondary = polymorphic_panel()
    g=geometry([secondary],reference_only=True)
    evidence=g['copies']['copy2']['native_reference']['extension_match']
    assert g['status']=='BLOCKED' and evidence['mismatch_count'] is None
    assert evidence['candidate_mismatch_count']==1
    assert evidence['candidate_mismatches'][0]['original_pe_position']==140


def test_zero_selects_native_guide_defaults_for_pe_window_estimate():
    target=panel()[0]
    def estimate(t): return geometry([t],reference_only=True)['copies'][t.copy_name]['quantification_window_positions']
    assert estimate(target)==estimate(target.model_copy(update={'quantification_window_coordinates':'0'}))


def test_mixed_copy_strands_preserve_individual_native_plans_and_block_cross_copy_routing():
    a,b=panel()
    g=geometry([a,inverted(b)])
    assert g['status']=='BLOCKED' and not g['diagnostics'] and g['anchor_copy'] is None
    assert any(r['code']=='MIXED_REFERENCE_STRANDS_NO_COMMON_COPY_COORDINATES' for r in g['reasons'])
    assert {v['native_reference']['orientation'] for v in g['copies'].values()}=={'forward','reverse'}
