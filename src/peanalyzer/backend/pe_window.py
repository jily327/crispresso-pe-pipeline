"""Reference.include_idxs is authoritative for native window-based statistics."""

from peanalyzer.geometry import aligner, intended_edits
from peanalyzer.pe_reference import outside_window


def normalize_include_idxs(value, reference_length):
    """Validate list or CRISPResso2's JSON ndarray encoding; fail closed."""
    if isinstance(value,dict):
        if set(value)!={'_type','value'} or value['_type']!='np.ndarray':
            raise ValueError('unknown authoritative include_idxs serialization')
        value=value['value']
    if not isinstance(value,list) or any(type(p) is not int or not 0<=p<reference_length for p in value):
        raise ValueError('authoritative include_idxs must be a one-dimensional list of valid integer positions')
    return sorted(set(value))


def audit_window(metrics, plan, refs, *, args=None):
    """Expose native positions and map them back to each supplied reference."""
    if refs['Reference']['sequence'] != plan.backend.wt_sequence or refs['Prime-edited']['sequence'] != plan.backend.prime_edited_sequence:
        raise ValueError('unexpected CRISPResso WT or intended reference')
    alignment = aligner().align(plan.original.wt_sequence, plan.original.prime_edited_sequence)
    edits = intended_edits(plan.original, alignment[0]) if len(alignment) == 1 else None
    windows = {}
    for name, edited in [('Reference', False), ('Prime-edited', True)]:
        ref = refs[name]
        positions = ref.get('include_idxs')
        indices = normalize_include_idxs(positions, len(ref['sequence'])) if positions is not None else None
        original = sorted(plan.original_position(p, edited=edited) for p in indices) if indices is not None else None
        windows[name] = dict(backend_positions=indices, original_positions=original)
    original = windows['Reference']['original_positions']
    coordinates = plan.original.quantification_window_coordinates
    explicit = coordinates not in (None, '0')
    requested = set()
    if explicit:
        for interval in coordinates.split('_'):
            first, last = map(int, interval.split('-'))
            requested.update(range(first,last+1))
        if original is not None and set(original) - requested:
            raise ValueError('Core effective WT window exceeds the explicit supplied intervals')
    metrics['authoritative_reference_quantification_window'] = original
    metrics['window_audit'] = dict(source='CRISPResso2_info.json results.refs.Reference.include_idxs',
        coordinate_system='zero-based WT positions in supplied reference orientation',
        backend_positions=windows['Reference']['backend_positions'], original_wt_positions=original,
        requested_source='explicit_WT_intervals' if explicit else 'guide_relative_Core_defaults_or_settings',
        supplied_coordinates=coordinates,
        missing_requested_positions=sorted(requested-set(original)) if explicit and original is not None else None,
        backend_settings={k:args[k] for k in ('quantification_window_coordinates','quantification_window_center',
                          'quantification_window_size','prime_editing_pegRNA_extension_quantification_window_size',
                          'exclude_bp_from_left','exclude_bp_from_right') if args is not None and k in args},
        outside_intended_edits=outside_window(edits, original) if original is not None and edits is not None else None,
        references=windows)
