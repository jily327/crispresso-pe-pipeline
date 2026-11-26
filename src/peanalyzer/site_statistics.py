"""Project authenticated two-site counts into biological observations."""
from os.path import relpath
from pathlib import Path

from peanalyzer.aggregation import AggregationError, canonical, sha256, strict_json, subset
from peanalyzer.statistical_models import BiologicalSample, Observation
from peanalyzer.site_series import ARTIFACT, CONTRACT, METHODS, OUTCOMES


def _count(value):
    if type(value) is not int or value < 0:
        raise AggregationError("Invalid integer in two-site population")
    return value


def _ratios(row, method, input_pairs):
    counts = row["counts"]
    states = {"WT", "A_only", "B_only", "AB"}
    backend = method == "core_alleles"
    if backend:
        states |= {"other_mixed", "unassessable"}
    if set(counts) != states or sum(map(_count, counts.values())) > input_pairs:
        raise AggregationError("Two-site state inventory exceeds population or differs from contract")
    total = sum(counts.values()) - counts.get("unassessable", 0)
    if _count(row["joint_assessable" if backend else "assessable"]) != total:
        raise AggregationError("Joint site denominator differs from state partition")
    a, b, ab = counts["A_only"], counts["B_only"], counts["AB"]
    joint_counts = {"A_only": a, "B_only": b, "double_edit": ab}
    if not backend:
        joint_counts["any_edit"] = a + b + ab
    if method == "full_templates":
        joint_counts.update(site_A=a + ab, site_B=b + ab)
    ratios = {"WT": (counts["WT"], total)}
    for outcome in OUTCOMES.keys() - {"WT"}:
        value = row[outcome]
        n, d = _count(value["numerator"]), _count(value["denominator"])
        if (not n <= d <= input_pairs or isinstance(value["fraction"], bool)
                or value["fraction"] != (n / d if d else None)):
            raise AggregationError("Two-site integer ratio mismatch")
        if outcome in joint_counts and (n, d) != (joint_counts[outcome], total):
            raise AggregationError("Two-site reported ratio disagrees with joint state counts")
        if backend and outcome == "any_edit" and not (d == total and a + b + ab <= n <= a + b + ab + counts["other_mixed"]):
            raise AggregationError("Backend any-edit ratio differs from joint states")
        ratios[outcome] = (n, d)
    return ratios


def site_observations(result, sample, result_path, manifest_directory, snapshots, methods_by_target):
    artifact = result.provenance.artifacts.get(ARTIFACT)
    if artifact is None:
        return []
    path = result_path.with_name(ARTIFACT)
    if path.is_symlink() or not path.is_file():
        raise AggregationError("Missing or aliased declared two-site artifact")
    data = path.read_bytes()
    checksum = sha256(data)
    if len(data) != artifact.size_bytes or checksum != artifact.sha256:
        raise AggregationError("Two-site artifact digest or size mismatch")
    raw = strict_json(data)
    if (raw["contract"] != CONTRACT or raw["sample_id"] != result.sample_id
            or raw["target_name"] != result.target_id
            or raw["prepared_manifest_sha256"] != result.provenance.prepared_manifest_sha256
            or _count(raw["input_pairs"]) != result.qc.prepared_input_reads):
        raise AggregationError("Two-site source differs from its declaring metric result")
    from peanalyzer.canonical_site_metric import verify_canonical_binding
    try:
        verify_canonical_binding(raw, result.target_metrics.total_precise_pe, required=(path.parent / 'native_runs.json').is_file())
    except ValueError as exc:
        raise AggregationError(str(exc)) from exc
    snapshots[path] = checksum
    source = Path(relpath(path, manifest_directory)).as_posix()
    observed = []
    blocked = raw["status"] == "BLOCKED"
    if raw["status"] not in ("ASSESSED", "NO_CALLABLE_SITE_PAIRS", "EMPTY_NEGATIVE_CONTROL", "EMPTY_SAMPLE", "BLOCKED"):
        raise AggregationError("Unknown two-site assessment status")
    if blocked and not raw.get("reason_codes"):
        raise AggregationError("Blocked two-site assessment requires a reason")
    if not blocked:
        from peanalyzer.haplotypes import FLANK, MARKER_LENGTH, MIN_PHRED
        if (raw["site_min_phred"], raw["copy_marker_length"], raw["site_flank_length"]) != (MIN_PHRED, MARKER_LENGTH, FLANK):
            raise AggregationError("Two-site assay parameters differ from the declared method")
        evidence = result.product_evidence.get("target")
        if not evidence:
            raise AggregationError("Two-site source requires authenticated target definitions")
        copies = {t["copy_name"]: {"WT": t["wt_sequence"], "PE": t["prime_edited_sequence"]} for t in evidence.targets}
        coordinates = {c: [i for i, (wt, pe) in enumerate(zip(t["WT"], t["PE"], strict=True)) if wt != pe]
                       for c, t in copies.items()}
        if (sha256(canonical(copies).encode()) != raw["reference_panel_sha256"]
                or coordinates != raw["site_coordinates_0based"] or any(len(v) != 2 for v in coordinates.values())):
            raise AggregationError("Two-site reference panel or original coordinates differ from M4 evidence")
        signature = canonical({k: raw[k] for k in ("site_coordinates_0based", "copy_marker_starts_0based",
            "reference_panel_sha256", "site_min_phred", "copy_marker_length", "site_flank_length","analysis_trim_5p")})
        if methods_by_target.setdefault(result.target_id, signature) != signature:
            raise AggregationError("Two-site assay or reference panel differs across biological samples")
    base = subset(sample, BiologicalSample).model_dump()
    for method in METHODS:
        backend = method == "core_alleles"
        if backend and not raw.get("backend"):
            continue
        group = None if blocked else raw["backend" if backend else method]
        if backend and group is not None:
            if group["status"] not in ("BLOCKED", "NOT_ASSESSABLE", "REPORTABLE"):
                raise AggregationError("Unknown site backend status")
            if group["status"] == "BLOCKED" and not group.get("reason_codes"):
                raise AggregationError("Blocked site backend requires a reason")
            if group["status"] != "BLOCKED" and (group["version"] != "2.3.4" or group["input_pairs"] != raw["input_pairs"]):
                raise AggregationError("Site backend version or read population mismatch")
        reasons = raw.get("reason_codes", []) if blocked else (group.get("reason_codes", []) if backend else [])
        if group is not None and not reasons and not backend:
            if set(group["copies"]) != set(result.copies):
                raise AggregationError("Two-site copy inventory differs from the metric result")
            # Unresolved origin remains in the combined denominator. Check partition
            # completeness without promoting an ambiguous read to a named copy.
            parts = [*group["copies"].values(), group["unresolved_copy"]]
            _ratios(group["unresolved_copy"], method, raw["input_pairs"])
            for state, count in group["combined"]["counts"].items():
                if sum(_count(v["counts"][state]) for v in parts) != count:
                    raise AggregationError("Two-site copy partitions differ from combined counts")
            for marginal in ("site_A", "site_B"):
                for key in ("numerator", "denominator"):
                    if sum(_count(v[marginal][key]) for v in parts) != group["combined"][marginal][key]:
                        raise AggregationError("Two-site marginal copy partitions differ from combined counts")
        populations = [None] if backend else [None, *sorted(result.copies)]
        for copy in populations:
            row = None if group is None or reasons else (group["combined"] if copy is None else group["copies"][copy])
            values = _ratios(row, method, raw["input_pairs"]) if row is not None else {}
            for outcome in OUTCOMES:
                n, d = values.get(outcome, (None, None))
                status = "BLOCKED" if blocked or reasons else "REPORTABLE" if d else "NOT_ASSESSABLE"
                observed.append(Observation(**base, sample_id=result.sample_id, target_name=result.target_id,
                    metric_name=f"intended_sites.{method}.{outcome}", copy_name=copy, routing_conditioned=copy is not None,
                    population_scope="target_all_prepared" if copy is None else "confident_copy",
                    population_id=sha256(canonical([checksum, method, copy]).encode()),
                    policy_id=None, policy_definition=None, status=status, numerator=n if d else None,
                    denominator=d if d else None, fraction=n/d if d else None,
                    reason_codes=[] if d else (reasons or ["ZERO_SITE_DENOMINATOR"]),
                    analysis_id=result.analysis_id, metric_contract_version=CONTRACT, source_result=source))
    return observed


def verify_workflow_site_observations(plan, result, metric_paths):
    """Compare stored site observations with the independently bound M4 companion."""
    from peanalyzer.metrics.models import MetricResult
    from peanalyzer.schemas import Sample
    from peanalyzer.workflow_sites import two_substitutions

    actual = [o for o in result.observations if o.metric_contract_version == CONTRACT]
    eligible = {name for name in plan.expected_targets
                if two_substitutions([t for t in plan.targets if t.target_name == name])}
    if not actual and not eligible:
        return
    samples = {s["barcode_id"]: Sample.model_validate(s) for s in plan.samples}
    directory = Path(plan.output) / "metrics"
    expected, methods, snapshots = [], {}, {}
    for (sample, target), path in metric_paths.items():
        if target in eligible:
            metric = MetricResult.model_validate(strict_json(path.read_bytes()))
            expected.extend(site_observations(metric, samples[sample], path, directory, snapshots, methods))
    if sorted(map(canonical, actual)) != sorted(map(canonical, expected)):
        raise AggregationError("Stored two-site biological observations differ from declared evidence")
    if any(sha256(p.read_bytes()) != value for p, value in snapshots.items()):
        raise AggregationError("Intended-site artifact changed during verification")
