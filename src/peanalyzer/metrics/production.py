"""Production result assembly over verified prepared/routed/Core boundaries.

No raw count dictionary is accepted as a qualified backend result. Collection
reopens the authoritative artifacts and verifies the execution's input lineage.
Archives must be immutable during collection, as at the M3.1.2 boundary.
"""

import hashlib
import json
from pathlib import Path

from peanalyzer.analysis_verify import verify_analysis_output
from peanalyzer.backend.comparator import evaluate_anchors, normalize_include_idxs, run_comparator
from peanalyzer.backend.core import run_confident_core, verify_routing_output
from peanalyzer.backend.metrics import MetricContractError, child_file, parse_child, backend_failure_code, validated_failure_reason
from peanalyzer.backend.pooled import BackendError, FIELDS, preflight_guides
from peanalyzer.demux_verify import read_json, sha256_file
from peanalyzer.geometry import geometry
from peanalyzer.metrics.models import (CopyMetrics, Eligibility, MetricRecord, MetricResult,
                                      Provenance, QC, Ratio, TargetMetrics)
from peanalyzer.metrics.products import (aligned_products, contradictory_products, prepared_products,
                                        selective_observability_reasons)
from peanalyzer.provenance import software_provenance
from peanalyzer.routing import RoutingPolicy, policy_identity
from peanalyzer.schemas import Target
from peanalyzer.observability import population_observability
from peanalyzer.metrics.family import prepared_evidence, aligned_evidence, reaggregate
from peanalyzer.metrics.family_models import ProductEvidence
from peanalyzer.metrics.policy_requests import prepare_policies

RUNTIME_DIGEST = 'pinellolab/crispresso2@sha256:b7e7971a87769aa584d31d21e199a9abca5f641c4f889c2e807cb6324fc8ce0c'
LIMITATIONS = [
    'Copy metrics are routing-conditioned subpopulations, not unbiased target estimates.',
    'Insertion edit coverage can quarantine PE-bearing fragments without an equivalent WT quarantine; confident cohorts may be PE-depleted. No correction is applied.',
    'Target all-read metrics are the primary population view when eligible.',
    'Prepared exact classification requires inward-facing amplicon-end reads with a unique sequence-consistent overlap of at least 10 nt and complete reconstruction; internal fragments, gaps and disagreements are excluded.',
    'Backend preprocessing/alignment and product assessability impose additional metric-specific filters; no single stage defines every denominator.',
    'Exact and native PE fractions have different numerators and denominators; either may be higher. Direction alone does not establish editing quality.',
    'Backend unaligned causes remain unknown unless authoritative evidence establishes them. Biological origins are not inferred.',
    'Closed, correctly specified target panels and M3.1.2 geometry/placement qualification remain required; unseen panels are not biologically certified.',
    'Verification assumes immutable trusted archives; coordinated rewriting of all trusted artifacts and large-scale memory performance are not qualified.',
]


class GateError(ValueError):
    def __init__(self, code, message=''):
        self.code = code
        super().__init__(message or code)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def inventory(path, artifacts, label):
    if path.is_symlink() or not path.is_file():
        raise GateError('MISSING_REQUIRED_PROVENANCE', str(path))
    artifacts[label] = dict(sha256=sha256_file(path), size_bytes=path.stat().st_size)


def window_reasons(metrics, target):
    window = metrics.get('authoritative_reference_quantification_window')
    if window is None:
        return ['AUTHORITATIVE_QUANTIFICATION_WINDOW_MISSING']
    try:
        normalized = normalize_include_idxs(window, len(target.wt_sequence))
    except ValueError:
        return ['AUTHORITATIVE_QUANTIFICATION_WINDOW_INVALID']
    return [] if normalized else ['EMPTY_AUTHORITATIVE_QUANTIFICATION_WINDOW']


def load_backend(root, target, inputs, lineage_key, lineage_hash, runtime_digest, artifacts, label, *, comparator):
    """Verify a real Core handoff and re-parse named authoritative artifacts."""
    root = Path(root)
    if root.is_symlink() or any('.incomplete-' in p for p in root.resolve().parts):
        raise GateError('MISSING_INCOMPLETE_BACKEND_METRICS')
    execution = read_json(root / 'execution.json')
    if not isinstance(execution, dict):
        raise GateError('MISSING_REQUIRED_PROVENANCE')
    if execution.get('status') != 'completed' or execution.get('return_code') != 0:
        raise GateError(validated_failure_reason(execution['reason_code']) if 'reason_code' in execution else
                        ('BACKEND_EXECUTION_FAILED' if execution.get('return_code') not in (None, 0)
                         else 'MISSING_INCOMPLETE_BACKEND_METRICS'))
    if (not isinstance(execution.get('software'), dict)
            or not execution['software'].get('pipeline_version')
            or not execution.get('started_at') or not execution.get('ended_at')
            or not isinstance(execution.get('runtime_identity'), dict)
            or execution['runtime_identity'].get('image_digest') != runtime_digest):
        raise GateError('MISSING_REQUIRED_PROVENANCE')
    if execution.get(lineage_key) != lineage_hash or execution.get('inputs') != inputs:
        raise GateError('BACKEND_INPUT_LINEAGE_MISMATCH')
    name = 'unrouted' if comparator else 'confident'
    argv = execution.get('argv', [])
    expected = ['-r1', 'input_R1.fastq.gz', '-r2', 'input_R2.fastq.gz',
                '--amplicon_seq', target.wt_sequence, '--name', name, '--output_folder', 'output',
                '--write_detailed_allele_table', '--keep_intermediate', '--suppress_report', '--suppress_plots']
    for column, field in list(FIELDS.items())[2:]:
        value = getattr(target, field)
        if value is not None:
            expected.extend(['--' + column, str(value)])
    if not argv or argv[1:] != expected:
        raise GateError('BACKEND_CONFIGURATION_MISMATCH')
    inventory(root / 'execution.json', artifacts, label + '/execution.json')
    for mate in (1, 2):
        path = root / f'input_R{mate}.fastq.gz'
        entry = inputs['files'][f'r{mate}']
        if path.is_symlink() or sha256_file(path) != entry['sha256'] or path.stat().st_size != entry['size_bytes']:
            raise GateError('BACKEND_INPUT_LINEAGE_MISMATCH')
        inventory(path, artifacts, label + '/' + path.name)
    child = root / f'output/CRISPResso_on_{name}'
    if child.is_symlink() or child.parent.is_symlink():
        raise GateError('MISSING_REQUIRED_PROVENANCE')
    info = read_json(child / 'CRISPResso2_info.json')
    refs = info['results']['refs']
    if refs['Reference']['sequence'] != target.wt_sequence or refs['Prime-edited']['sequence'] != target.prime_edited_sequence:
        raise GateError('BACKEND_REFERENCE_MISMATCH')
    try:
        metrics = parse_child(child, routed_pairs=inputs['pairs'], one_input_record_per_pair=True,
                              preprocessing_preserves_records=False)
    except MetricContractError as exc:
        raise GateError(exc.code, str(exc)) from exc
    for filename in ['CRISPResso2_info.json', *(info['running_info'][key] for key in
                     ('mapping_stats_filename', 'quant_of_editing_freq_filename', 'allele_frequency_table_zip_filename'))]:
        inventory(child_file(child, filename), artifacts, label + '/child/' + filename)
    products = aligned_products(child, target)
    if (products.classification_input_reads != metrics['native']['aligned_reads']
            or products.exact_pe != metrics['exact_haplotype']['numerator']
            or products.exact_wt + products.exact_pe != metrics['exact_haplotype']['denominator']):
        raise GateError('BACKEND_PRODUCT_RECONCILIATION_FAILED')
    return metrics, products


def metric(name, family, scope, pop_id, count, *, copy=None, reasons=(), native=None, products=None):
    reasons = sorted(set(reasons))
    target_exact = scope == 'target_all_prepared' and family == 'precise'
    selective = selective_observability_reasons(products.exclusion_reason_counts) if target_exact and products else []
    n = native['numerator'] if family == 'native' and native else products.exact_pe if products else None
    d = native['denominator'] if family == 'native' and native else products.exact_wt + products.exact_pe if products else None
    if reasons:
        status = 'BLOCKED'
    elif selective:
        status, reasons = 'NOT_ASSESSABLE', selective
    elif d == 0:
        status = 'NOT_ASSESSABLE'
        reasons = ['ZERO_EXACT_DENOMINATOR' if family == 'precise' else 'ZERO_NATIVE_DENOMINATOR']
        if products:reasons+=sorted(k for k in products.exclusion_reason_counts if k.startswith(('STATE_DEPENDENT_','COPY_DEPENDENT_')))
    elif n is None or d is None:
        status, reasons = 'BLOCKED', ['MISSING_INCOMPLETE_BACKEND_METRICS']
    else:
        status = 'REPORTABLE'
    attrs = {k: native[k] for k in ('backend_input_reads', 'reads_after_preprocessing', 'aligned_reads',
             'unaligned_reads', 'preprocessing_count_delta', 'unaligned_reason_counts',
             'ordinary_classified_aligned_reads', 'ambiguous_aligned_reads', 'discarded_aligned_reads')} if native else {}
    return MetricRecord(metric_name=name, metric_family=family, population_scope=scope,
                        population_id=pop_id, population_input_reads=count, copy_id=copy,
                        routing_conditioned=copy is not None,
                        assessment_stage='prepared_pairs' if target_exact else 'backend_aligned_products',
                        status=status, numerator=n if status == 'REPORTABLE' else None,
                        denominator=d if status == 'REPORTABLE' else None, reason_codes=reasons,
                        confident_input_reads=count if copy else None,
                        backend_counts_role=('unavailable' if not native else
                                             'parallel_native_analysis' if target_exact else 'metric_filter'),
                        products=products,
                        population_denominator_exclusions=count-d if count is not None and d is not None and count>=d else None,
                        **attrs)


def combined_status(records):
    states = {r.status for r in records}
    return 'BLOCKED' if 'BLOCKED' in states else 'NOT_ASSESSABLE' if 'NOT_ASSESSABLE' in states else 'REPORTABLE'


def collect_metrics(*, analysis_root, sample_id, targets, analysis_id, comparator_root,
                    routing_root=None, copy_roots=None, runtime_digest=None, tolerance_policies=None):
    """Build M4 JSON from existing verified runs; never accepts cached metrics.json.

    One invocation describes one biological target and one prepared sample. The
    caller must supply its complete eligible target read population. Multi-target
    read selection is outside this API; sample/target applicability is explicit.
    Failure of copy routing does not remove reads from the target population.
    """
    targets = [Target.model_validate(t.model_dump() if isinstance(t, Target) else t) for t in targets]
    tolerance_policies=prepare_policies(tolerance_policies,targets)
    if not targets or not analysis_id or len({t.target_name for t in targets}) != 1:
        raise ValueError('one nonempty biological target and analysis identifier are required')
    if len({t.copy_name.casefold() for t in targets}) != len(targets):
        raise ValueError('duplicate copy identifier')
    targets = sorted(targets, key=lambda t: t.copy_name)
    definitions_hash = digest([t.model_dump() for t in targets])
    artifacts, global_reasons, routing_reasons, native_reasons = {}, [], [], []
    runtime_reasons = []
    verified, sample, routing, route_hash, products = None, None, None, None, None
    observability={}
    if runtime_digest != RUNTIME_DIGEST:
        runtime_reasons.append('MISSING_REQUIRED_PROVENANCE' if not runtime_digest else 'UNQUALIFIED_BACKEND_RUNTIME')
    try:
        report = geometry(targets)
    except (ValueError, KeyError) as exc:
        report = dict(status='BLOCKED', reasons=[dict(code='TARGET_CONFIGURATION_INVALID')])
        global_reasons.append('TARGET_CONFIGURATION_INVALID')
    if report['status'] == 'BLOCKED':
        routing_reasons += ['UNSUPPORTED_ROUTING_GEOMETRY'] + [r['code'] for r in report['reasons'] if r.get('severity') == 'BLOCKED']
    if contradictory_products(targets):
        global_reasons.append('CONTRADICTORY_EXACT_PRODUCT_DEFINITIONS')
    # All target-level options, not only spacer/extension, must be shared.
    shared = [field for field in list(FIELDS.values())[2:] if field != 'prime_edited_sequence']
    if any(len({getattr(t, field) for t in targets}) != 1 for field in shared):
        native_reasons.append('TARGET_BACKEND_CONFIGURATION_DIFFERS')
    try:
        preflight_guides(targets)
    except BackendError as exc:
        native_reasons.append(exc.code)
    try:
        verified = verify_analysis_output(Path(analysis_root))
        sample = verified.manifest['samples'][sample_id]
        inventory(verified.root / 'analysis_manifest.json', artifacts, 'prepared/analysis_manifest.json')
        paths = [verified.root / sample['files'][f'r{m}']['path'] for m in (1, 2)]
        products = prepared_products(paths, targets)
        observability['target']=population_observability(paths,targets)
        native_reasons.extend(observability['target']['backend_reason_counts'])
        if products.classification_input_reads != sample['pairs']:
            raise ValueError('prepared classification count mismatch')
        if products.contradictory_state:
            global_reasons.append('CONTRADICTORY_EXACT_CLASSIFICATION')
    except (OSError, ValueError, KeyError, TypeError):
        global_reasons.append('PREPARED_INPUT_VERIFICATION_FAILED')
        products = None
    population = digest(dict(prepared=verified.manifest_sha256 if verified else None,
                             sample=sample_id, target=definitions_hash, scope='target_all_prepared'))
    count = sample['pairs'] if sample else None
    product_evidence={}
    def unavailable_evidence(key, pop_id, size, scope, reasons):
        return ProductEvidence(population_id=pop_id,population_scope=scope,copy_id=None if key=='target' else key,
            assessment_stage='prepared_pairs' if key=='target' else 'backend_aligned_products',
            source_input_reads=size,classification_input_reads=0,targets=[t.model_dump() for t in targets],
            products=[],blocking_reasons=sorted(set(reasons or ['PRODUCT_EVIDENCE_UNAVAILABLE'])))
    if products is not None:
        try:
            product_evidence['target']=prepared_evidence(paths,targets,population_id=population,
                population_scope='target_all_prepared',copy_id=None,source_input_reads=count)
            product_evidence['target'].blocking_reasons=sorted(set(product_evidence['target'].blocking_reasons+global_reasons))
        except (OSError,ValueError,KeyError,TypeError):
            product_evidence['target']=unavailable_evidence('target',population,count,'target_all_prepared',global_reasons)
    else:product_evidence['target']=unavailable_evidence('target',population,count,'target_all_prepared',global_reasons)
    anchor_metrics, anchor_failures = {}, {}
    native_preconditions = global_reasons + native_reasons + runtime_reasons
    if verified and sample and not native_preconditions:
        for target in targets:
            try:
                root = Path(comparator_root) / target.copy_name
                if not root.exists():
                    raise GateError('MISSING_ANCHOR_RESULT')
                parsed, _ = load_backend(root, target, sample, 'analysis_manifest_sha256',
                                          verified.manifest_sha256, runtime_digest, artifacts,
                                          'anchors/' + target.copy_name, comparator=True)
                anchor_metrics[target.copy_name] = parsed
            except GateError as exc:
                anchor_failures[target.copy_name] = exc.code
            except (OSError, ValueError, KeyError, TypeError) as exc:
                anchor_failures[target.copy_name] = backend_failure_code(exc)
    native_reasons.extend(anchor_failures.values())
    try:
        comparison = (dict(status='BLOCKED', reasons=[], anchor_invariant=False, anchors={},
                           skipped_reason_codes=sorted(set(native_preconditions))) if native_preconditions
                      else evaluate_anchors(targets, anchor_metrics))
    except (ValueError, KeyError, TypeError):
        comparison = dict(status='BLOCKED', reasons=['COMPARATOR_NOT_QUALIFIED'], anchor_invariant=False, anchors={})
    if anchor_failures and 'MISSING_ANCHOR_RESULT' not in anchor_failures.values():
        comparison['reasons'] = [r for r in comparison['reasons'] if r != 'MISSING_ANCHOR_RESULT']
    native_reasons.extend(comparison['reasons'])
    for target in targets:
        if target.copy_name in anchor_metrics:
            native_reasons.extend(window_reasons(anchor_metrics[target.copy_name], target))
    # One common integer tuple, only after complete empirical equality; no averaging.
    common = (next(iter(anchor_metrics.values()))['native']
              if comparison['anchor_invariant'] and not native_reasons else None)
    if common and not comparison.get('partition_common'):
        common={**common,**{k:None for k in ('ordinary_classified_aligned_reads','ambiguous_aligned_reads','discarded_aligned_reads')}}
    target_native = metric('target_crispresso_native_pe', 'native', 'target_all_prepared', population, count,
                           reasons=global_reasons + native_reasons + runtime_reasons, native=common)
    target_exact = metric('total_precise_pe', 'precise', 'target_all_prepared', population, count,
                          reasons=global_reasons, native=common, products=products)
    if routing_root is None:
        routing_reasons.append('COPY_COHORT_UNAVAILABLE')
    elif not global_reasons and not routing_reasons:
        try:
            raw = read_json(Path(routing_root) / 'routing_manifest.json')
            if not isinstance(raw, dict) or raw.get('policy_identity') != policy_identity(RoutingPolicy()):
                raise GateError('STALE_OR_UNQUALIFIED_ROUTING_POLICY')
            routing = verify_routing_output(Path(routing_root))
            if (routing['analysis_manifest_sha256'] != verified.manifest_sha256 or routing['sample_id'] != sample_id
                    or digest(sorted(routing['targets'], key=lambda t: t['copy_name'])) != definitions_hash):
                raise GateError('ROUTED_INPUT_LINEAGE_MISMATCH')
            route_hash = sha256_file(Path(routing_root) / 'routing_manifest.json')
            for name in ('routing_manifest.json', 'routing_ledger.jsonl', 'geometry.json'):
                inventory(Path(routing_root) / name, artifacts, 'routing/' + name)
        except GateError as exc:
            routing, route_hash = None, None
            routing_reasons.append(exc.code)
        except (OSError, ValueError, KeyError, TypeError):
            routing, route_hash = None, None
            routing_reasons.append('ROUTED_HANDOFF_VERIFICATION_FAILED')
    copies = {}
    for target in targets:
        copy = target.copy_name
        reasons = global_reasons + routing_reasons + runtime_reasons
        cohort = routing['cohorts'][copy] if routing else None
        size = cohort['pairs'] if cohort else None
        pop_id = digest(dict(prepared_population=population, routing=route_hash, copy=copy, scope='confident_copy'))
        parsed, copy_products = None, None
        exact_observability_reasons=[]
        if cohort and size:
            paths=[Path(routing_root)/cohort['files'][f'r{m}']['path'] for m in (1,2)]
            observability[copy]=population_observability(paths,[target])
            reasons=reasons+list(observability[copy]['backend_reason_counts'])
            exact_observability_reasons=list(observability[copy]['exact_reason_counts'])+list(observability[copy]['reconstruction_ambiguity_reason_counts'])
        if cohort and not size:
            reasons = reasons + ['COPY_COHORT_UNAVAILABLE']
        if not reasons and cohort:
            try:
                root = (copy_roots or {}).get(copy)
                if root is None:
                    raise GateError('MISSING_INCOMPLETE_BACKEND_METRICS')
                parsed, copy_products = load_backend(root, target, cohort, 'routing_manifest_sha256',
                                                     route_hash, runtime_digest, artifacts, 'copies/' + copy,
                                                     comparator=False)
            except GateError as exc:
                reasons = reasons + [exc.code]
            except (OSError, ValueError, KeyError, TypeError) as exc:
                reasons = reasons + [backend_failure_code(exc)]
        attrs = parsed['native'] if parsed else None
        windows = window_reasons(parsed, target) if parsed else []
        native = metric(copy + '_crispresso_native_pe', 'native', 'confident_copy', pop_id, size,
                        copy=copy, reasons=reasons + windows, native=attrs)
        precise = metric(copy + '_precise_pe', 'precise', 'confident_copy', pop_id, size,
                         copy=copy, reasons=reasons+exact_observability_reasons, native=attrs, products=copy_products)
        copies[copy] = CopyMetrics(copy_id=copy, copy_metric_status=combined_status([native, precise]),
                                  native=native, precise=precise)
        if parsed and not reasons and not exact_observability_reasons:
            try:
                product_evidence[copy]=aligned_evidence(Path(root)/'output/CRISPResso_on_confident',target,targets=targets,
                    population_id=pop_id,population_scope='confident_copy',copy_id=copy,source_input_reads=size)
            except (OSError,ValueError,KeyError,TypeError):
                product_evidence[copy]=unavailable_evidence(copy,pop_id,size,'confident_copy',[])
        else:product_evidence[copy]=unavailable_evidence(copy,pop_id,size,'confident_copy',reasons+exact_observability_reasons)
    records = [target_native, target_exact, *(r for c in copies.values() for r in (c.native, c.precise))]
    assigned = sum(v['pairs'] for c, v in routing['cohorts'].items() if c != 'quarantine') if routing else None
    quarantine = routing['cohorts']['quarantine']['pairs'] if routing else None
    return MetricResult(target_id=targets[0].target_name, sample_id=sample_id, analysis_id=analysis_id,
        provenance=Provenance(software=software_provenance(), prepared_manifest_sha256=verified.manifest_sha256 if verified else None,
            prepared_sample=sample, target_definitions_sha256=definitions_hash, routing_manifest_sha256=route_hash,
            routing_policy_identity=routing['policy_identity'] if routing else None, crispresso_version='2.3.4',
            runtime_digest=runtime_digest, artifacts=artifacts),
        eligibility=Eligibility(target_metric_status=combined_status([target_native, target_exact]),
            routing_geometry_status=report['status'], comparator_status=target_native.status,
            anchor_invariant=comparison['anchor_invariant'],
            block_reason_codes=sorted({reason for r in records for reason in r.reason_codes})),
        target_metrics=TargetMetrics(target_crispresso_native_pe=target_native, total_precise_pe=target_exact),
        copies=copies, anchor_evidence=dict(comparison=comparison, failures=anchor_failures, backend_metrics=anchor_metrics,observability=observability),
        product_evidence=product_evidence,
        derived_metrics={key:reaggregate(evidence,tolerance_policies) for key,evidence in product_evidence.items()} if tolerance_policies else {},
        qc=QC(prepared_input_reads=count, routing_assigned_reads=assigned, routing_quarantined_reads=quarantine,
            routing_quarantine_fraction=Ratio(numerator=quarantine, denominator=count) if quarantine is not None else None,
            routing_quarantine_reasons={k:v for k,v in routing['categories'].items() if k != 'ASSIGNED_COPY'} if routing else {},
            target_backend_input_reads=common['backend_input_reads'] if common else None,
            target_backend_aligned_reads=common['aligned_reads'] if common else None,
            target_backend_unaligned_reads=common['unaligned_reads'] if common else None,
            target_backend_unaligned_fraction=Ratio(numerator=common['unaligned_reads'], denominator=common['reads_after_preprocessing']) if common else None,
            exact_assessable_reads=products.exact_wt+products.exact_pe if products else None,
            exact_product_exclusions=products.denominator_exclusions if products else None,
            per_copy_confident_counts={c:v['pairs'] for c,v in routing['cohorts'].items() if c!='quarantine'} if routing else {},
            limitations=LIMITATIONS))


def run_metrics(*, analysis_root, sample_id, targets, analysis_id, output, core,
                routing_root=None, runtime_digest=RUNTIME_DIGEST, tolerance_policies=None):
    """Execute conventional all-read anchors and verified copy Core; publish M4 JSON.

    Routing must already exist. Unsupported/missing copies stay explicit in the
    result. Execution failures never create a numeric zero. No resume/overwrite.
    """
    targets = [Target.model_validate(t.model_dump() if isinstance(t, Target) else t) for t in targets]
    tolerance_policies=prepare_policies(tolerance_policies,targets)
    output = Path(output).absolute()
    if output.exists():
        raise ValueError('M4 output must be new')
    output.mkdir(parents=True)
    runtime = {'image_digest': runtime_digest}
    # Pre-collection establishes all fail-closed input/geometry/configuration gates.
    initial = collect_metrics(analysis_root=analysis_root, sample_id=sample_id, targets=targets,
        analysis_id=analysis_id, comparator_root=output/'comparator', routing_root=routing_root,
        runtime_digest=runtime_digest)
    failures = {}
    def record_unstarted_failure(root, exc):
        # Preserve failures before a runner creates its execution manifest.
        # Existing completed/failed execution evidence must never be replaced.
        path = root/'execution.json'
        if not path.exists():
            root.mkdir(parents=True, exist_ok=True)
            with path.open('x') as handle:
                json.dump(dict(status='not_started', return_code=None,
                               reason_code=backend_failure_code(exc), error=str(exc)), handle, indent=2)
                handle.write('\n')
    allowed_missing = {'MISSING_ANCHOR_RESULT', 'ANCHOR_DEPENDENT_NATIVE_RESULT'}
    if set(initial.target_metrics.target_crispresso_native_pe.reason_codes) <= allowed_missing:
        try:
            comparison = run_comparator(analysis_root, sample_id, targets, output/'comparator', core, runtime_identity=runtime)
            if comparison['anchor_failures']:
                failures['anchors'] = comparison['anchor_failures']
        except (OSError, ValueError, KeyError, TypeError, BackendError) as exc:
            failures['comparator'] = str(exc)
            for target in targets:
                record_unstarted_failure(output/'comparator'/target.copy_name, exc)
    copy_roots = {}
    for copy, row in initial.copies.items():
        if row.native.reason_codes == ['MISSING_INCOMPLETE_BACKEND_METRICS']:
            copy_roots[copy] = output/'copies'/copy
            try:
                run_confident_core(Path(routing_root), copy, copy_roots[copy], core, runtime_identity=runtime)
            except (OSError, ValueError, KeyError, TypeError, BackendError) as exc:
                failures[copy] = str(exc)
                record_unstarted_failure(copy_roots[copy], exc)
    result = collect_metrics(analysis_root=analysis_root, sample_id=sample_id, targets=targets,
        analysis_id=analysis_id, comparator_root=output/'comparator', routing_root=routing_root,
        copy_roots=copy_roots, runtime_digest=runtime_digest)
    if tolerance_policies:
        result.derived_metrics={key:reaggregate(evidence,tolerance_policies) for key,evidence in result.product_evidence.items()}
    (output/'execution_failures.json').write_text(json.dumps(failures, indent=2)+'\n')
    # Exclusive publication only after schema validation of the complete result.
    with (output/'result.json').open('x') as handle:
        handle.write(result.model_dump_json(indent=2)+'\n')
    return result
