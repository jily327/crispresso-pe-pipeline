"""Project stored, inventory-bound evidence into sample-level tables."""
import json
from peanalyzer.gui.models import ClassValue, FieldValue, ScientificPanel
from peanalyzer.workflow_storage import WorkflowError

SITE_OUTCOMES = {'site_A': 'Site A edited (including double)', 'site_B': 'Site B edited (including double)',
                 'A_only': 'Site A only', 'B_only': 'Site B only', 'double_edit': 'Complete double edit',
                 'any_edit': 'Any intended edit'}


def diagnostic_fields(evidence):
    values = []
    def add(name, value):
        if isinstance(value, dict) and value:
            for k, v in value.items():
                add(f'{name} · {k}', v)
        elif isinstance(value, list) and any(isinstance(v, dict) for v in value):
            for i, item in enumerate(value, 1):
                add(f'{name} [{i}]', item)
        else:
            text = value if isinstance(value, str) or value is None else json.dumps(value)
            values.append(FieldValue(name=name, value=text))
    for key, value in evidence.items():
        add(key, value)
    return values


def panel(sample, target, method, scope, status, source, *, definition='', evidence=None, ratios=None, reasons=()):
    from peanalyzer.gui.projection import percentage
    measurements = []
    for name, value in (ratios or {}).items():
        n, d, f = (value[k] for k in ('numerator', 'denominator', 'fraction'))
        measurements.append(ClassValue(name=name, numerator=None if n is None else str(n),
                                       denominator=None if d is None else str(d), fraction=f, percentage=percentage(f)))
    # A population can have callable marginal observations even when no joint
    # haplotype is observable. Each stored fraction carries its own denominator.
    if measurements and status in ('ASSESSED', 'REPORTABLE', 'NO_CALLABLE_SITE_PAIRS'):
        if all(m.fraction is None for m in measurements):
            status = 'NOT_ASSESSABLE'
        elif status == 'NO_CALLABLE_SITE_PAIRS':
            status = 'ASSESSED'
    return ScientificPanel(sample_id=sample, target=target, method=method, population=scope, status=status,
                           reasons=list(reasons), definition=definition, measurements=measurements,
                           evidence=diagnostic_fields(evidence or {}), source=source)


def site_panels(raw, source, sample, target, *, canonical_record=None, replay_legacy=False):
    if (raw['sample_id'], raw['target_name']) != (sample, target):
        raise WorkflowError('SOURCE_IDENTITY_MISMATCH', 'Two-site measurement and metric stage identities differ')
    status = raw['status']
    panels = [panel(sample, target, 'Two-site read-pair assessment', 'Combined target', status, source,
                    reasons=raw.get('reason_codes', ()),
                    definition='Forward mate is relative to the supplied WT amplicon. Counts describe observed read pairs.',
                    evidence={k: raw[k] for k in ('input_pairs', 'declared_negative_control', 'site_orientation',
                              'site_exclusions', 'full_template_exclusions', 'site_coordinates_0based', 'analysis_trim_5p',
                              'copy_marker_starts_0based', 'site_flank_length', 'site_min_phred', 'backend_input_order',
                              'diagnostic', 'reference_panel_sha256') if k in raw})]
    for key, method, denominator in (
            ('two_site_q30', 'Concordant two-site calls (Q30)', 'pairs with both sites callable and concordant in both mates'),
            ('full_templates', 'Exact full-length haplotypes', 'pairs reconstructed as an exact WT, A-only, B-only or double-edit template')):
        group = raw.get(key)
        if group is None:
            continue
        scopes = [('Combined target', group['combined']), *[(f'Copy · {c}', v) for c, v in group['copies'].items()],
                  ('Unresolved copy', group['unresolved_copy'])]
        for scope, row in scopes:
            ratios = {label: row[name] for name, label in SITE_OUTCOMES.items()}
            panels.append(panel(sample, target, method, scope, status, source,
                                definition=(f'Each numerator counts the named outcome. The joint denominator counts {denominator} in this population. '
                                            + ('Site A and site B use pairs assessable at each respective site.' if key == 'two_site_q30'
                                               else 'Site A and site B use the same four full-length templates.')),
                                evidence={'Assessable pairs': row['assessable'], **row['counts']}, ratios=ratios))
    exact = raw.get('exact_double_edit_fraction')
    if canonical_record is not None:
        from peanalyzer.canonical_site_metric import canonical_site_metric
        exact = canonical_site_metric(canonical_record)
    if exact and ('status' in exact or replay_legacy):
        panels.append(panel(sample, target, 'Exact WT or intended product', 'Combined target', exact.get('status', status), source,
                            reasons=exact.get('reason_codes', ()),
                            definition='Exact full-length double-edit pairs divided by exact WT plus exact double-edit pairs.',
                            ratios={'Complete double edit': exact}))
    backend = raw.get('backend')
    if backend:
        scope = 'Combined target'
        panels.append(panel(sample, target, 'CRISPResso allele assessment', scope, backend['status'], source,
                            reasons=backend.get('reason_codes', ()),
                            evidence={k: backend[k] for k in ('input_pairs', 'preprocessed', 'aligned', 'ambiguous',
                                      'discarded', 'preprocessing_loss', 'unaligned', 'windows', 'version', 'diagnostic', 'qc') if k in backend}))
        scopes = ([(scope, backend['combined'])] if 'combined' in backend else [])
        scopes.extend((f'Alignment to {c} reference', v) for c, v in backend.get('backend_reference', {}).items())
        for scope, row in scopes:
            panels.append(panel(sample, target, 'Sites in aligned CRISPResso alleles', scope, backend['status'], source,
                                definition='Each numerator counts the named outcome in aligned alleles. Site A and site B each use alleles observable at that site. Joint outcomes use alleles observable at both sites, including unexpected bases and internally flanked deletions. Per-reference rows describe alignment assignments.',
                                ratios={label: row[k] for k, label in SITE_OUTCOMES.items() if k in row},
                                evidence={**row['counts'], **{k: row[k] for k in ('native_window_modified', 'qc', 'joint_assessable') if k in row}}))
    return panels


def reference_panels(geometry, source, sample, target):
    output = []
    for copy, info in geometry['copies'].items():
        reference = info.get('native_reference')
        if not reference:
            continue
        # Original coordinates and original copy identity are authoritative in this display.
        evidence = {**reference, 'predicted_window_positions': info['quantification_window_positions'],
                    'predicted_window_scope': info['quantification_window_scope'],
                    'outside_predicted_window': info['outside_predicted_window']}
        output.append(panel(sample, target, 'Reference orientation and RTT compatibility', f'Copy · {copy}',
                            'BLOCKED' if reference.get('native_error') else 'ASSESSED', source,
                            definition='Normalization orients the supplied WT and intended amplicons for the backend. Guides retain their experimental orientation. Edit coordinates refer to the supplied copy.',
                            evidence=evidence))
    return output


def window_panels(result, source):
    output = []
    evidence = result.anchor_evidence
    for copy, record in evidence.get('extension_alleles', {}).items():
        output.append(panel(result.sample_id, result.target_id, 'Experimental extension allele counts', f'Copy · {copy}',
                            record.get('status', 'ASSESSED'), source, reasons=record.get('reason_codes', ()), evidence={k:v for k,v in record.items() if k != 'artifacts'},
                            definition='Allele counts cover the copy positions where the experimental extension differs from the supplied copy.'))
    anchors = {c: v['window_audit'] for c, v in evidence.get('backend_metrics', {}).items() if v.get('window_audit')}
    for label, audits in (('Target population', anchors), ('Routed copy', evidence.get('copy_windows', {}))):
        for copy, audit in audits.items():
            output.append(panel(result.sample_id, result.target_id, 'Effective CRISPResso window',
                                f'{label} · {copy}', 'ASSESSED', source,
                                definition='Effective positions come from the completed backend run. Outside-window edits are listed in original amplicon coordinates.',
                                evidence=audit))
    return output


def window_name(window):
    chosen = window.get('selected_window')
    if chosen == 'W2':
        return 'W2 primary window'
    return f'{chosen} exploratory window' if chosen else 'Explicit window'


def multicopy_nuclease_panels(result, source):
    counts = result.population.model_dump() if hasattr(result.population, 'model_dump') else result.population
    panels = [panel(result.sample_id, result.target_id, 'Nuclease population accounting', 'Combined target',
                    result.status, source, evidence=counts,
                    definition='Prepared reads, unaligned reads and ambiguous origins are accounted for by physical read.')]
    labels = sorted({window_name(w) for w in result.windows.values()})
    for copy, row in [(None, result.combined), *result.copies.items()]:
        window = result.windows[copy] if copy is not None else result.windows
        selected = window_name(window) if copy is not None else ' / '.join(labels)
        scope = f'Copy · {copy}' if copy is not None else 'Combined target'
        panels.append(panel(result.sample_id, result.target_id, f'Nuclease outcomes · {selected}', scope,
                            row.status, source, reasons=row.reason_codes, evidence={'Window coordinates by reference' if copy is None else 'Window coordinates': window,
                                                          'Assessable aligned reads': row.aligned_reads, **row.class_counts},
                            ratios={k.replace('_', ' '): v.model_dump() for k,v in row.metrics.items()},
                            definition='Each numerator counts assessable aligned reads with the named outcome in the selected window. The denominator is the assessable aligned count in this population. A combined-target read contributes once.'))
        if row.fraction_of_indel_reads_by_net_size:
            panels.append(panel(result.sample_id, result.target_id, f'Net indel size · {selected}', scope, row.status, source,
                                definition='Reads with the given net indel size divided by all indel-containing reads in this population and window.',
                                ratios={f'{size} bp': v.model_dump() for size, v in row.fraction_of_indel_reads_by_net_size.items()}))
    return panels
