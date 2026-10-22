"""Offline collection of immutable M4 measurements into biological observations."""
import csv
import hashlib
import io
import json
import os
import platform
import shutil
import statistics as descriptive
import tempfile
from collections import defaultdict
from fractions import Fraction
from pathlib import Path

from pydantic import ValidationError

from peanalyzer import __version__
from peanalyzer.metrics import MetricResult, FamilyPolicy
from peanalyzer.metrics.production import digest
from peanalyzer.schemas import Sample, Target
from peanalyzer.statistical_models import (
    BiologicalSample, Condition, ContrastResult, GroupSummary, InputResult, Observation, Provenance,
    SampleAssessment, SampleFraction, Selector, Series, StatisticsResult,
)
from peanalyzer.validation import SAMPLE_COLUMNS, _load_csv


class AggregationError(ValueError):
    """Invalid biological input or an inconsistent authoritative measurement."""


def canonical(value):
    """Lossless deterministic identity for structured conditions and series."""
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def strict_json(data):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise AggregationError(f"duplicate JSON key: {key}")
            result[key] = value
        return result
    def invalid(value):
        raise AggregationError(f"nonfinite JSON value: {value}")
    return json.loads(data, object_pairs_hook=unique, parse_constant=invalid)


def subset(model, cls):
    return cls.model_validate({key: getattr(model, key) for key in cls.model_fields})


def series_key(row):
    return canonical(subset(row, Selector))


def condition_key(row):
    return canonical(subset(row, Condition))


def _validate_populations(result):
    """Check identity links, not sequence interpretation or metric calculation."""
    provenance = result.provenance
    population = digest(dict(prepared=provenance.prepared_manifest_sha256,
                             sample=result.sample_id, target=provenance.target_definitions_sha256,
                             scope="target_all_prepared"))
    populations = {"target": (population, result.target_metrics.total_precise_pe)}
    for copy, records in result.copies.items():
        pop_id = digest(dict(prepared_population=population, routing=provenance.routing_manifest_sha256,
                             copy=copy, scope="confident_copy"))
        populations[copy] = (pop_id, records.precise)
    if "target" in result.copies:
        raise AggregationError("reserved target/copy population key collision")
    records = [r for _, r in result.target_metrics]
    records += [r for copy in result.copies.values() for r in (copy.native, copy.precise)]
    for record in records:
        expected, _ = populations[record.copy_id or "target"]
        if record.population_id != expected:
            raise AggregationError("inconsistent sample/target population identity")
        if record.status == "REPORTABLE" and record.denominator > record.population_input_reads:
            raise AggregationError("metric denominator exceeds source population")
    target_count = result.target_metrics.total_precise_pe.population_input_reads
    if provenance.prepared_sample is not None:
        count = provenance.prepared_sample.get("pairs")
        if type(count) is not int or count < 0 or count != target_count:
            raise AggregationError("prepared sample population identity mismatch")
    if result.qc.prepared_input_reads != target_count:
        raise AggregationError("QC/prepared population identity mismatch")
    copy_counts = [c.precise.population_input_reads for c in result.copies.values()]
    if target_count is not None and sum(n for n in copy_counts if n is not None) > target_count:
        raise AggregationError("confident copy populations exceed whole-target population")
    for key, evidence in result.product_evidence.items():
        if key not in populations:
            raise AggregationError("unknown product evidence population")
        pop_id, record = populations[key]
        if (evidence.population_id, evidence.population_scope, evidence.copy_id, evidence.source_input_reads,
            evidence.assessment_stage) != (pop_id, record.population_scope, record.copy_id,
                                          record.population_input_reads, record.assessment_stage):
            raise AggregationError("product evidence population identity mismatch")
        if (evidence.classification_input_reads and evidence.source_input_reads is None
                or evidence.source_input_reads is not None
                and evidence.classification_input_reads > evidence.source_input_reads):
            raise AggregationError("product evidence classification exceeds source population")
        targets = sorted((Target.model_validate(t) for t in evidence.targets), key=lambda t: t.copy_name)
        if (not targets or any(t.target_name != result.target_id for t in targets)
                or [t.copy_name for t in targets] != sorted(result.copies)
                or digest([t.model_dump() for t in targets]) != provenance.target_definitions_sha256):
            raise AggregationError("conflicting target definition identity")
    for key, policies in result.derived_metrics.items():
        if key not in populations or key not in result.product_evidence:
            raise AggregationError("family metric has no matching product evidence")
        pop_id, record = populations[key]
        for family in policies.values():
            name = "total_pe_family" if key == "target" else key + "_pe_family"
            if (family.population_id, family.population_scope, family.copy_id, family.metric_name,
                family.classification_input_reads) != (pop_id, record.population_scope, record.copy_id, name,
                                                       result.product_evidence[key].classification_input_reads):
                raise AggregationError("family metric population identity mismatch")


def _policy_definition(record):
    try:
        policy = FamilyPolicy.model_validate(record.policy)
    except ValidationError:
        if record.status == "REPORTABLE":
            raise AggregationError("reportable family metric has an invalid policy") from None
        return record.policy
    if policy.policy_id != record.policy_id:
        raise AggregationError("family policy identity mismatch")
    return policy.model_dump(mode="json")


def collect_observations(manifest_path, samples_path):
    """Return a validated summary result. M4 sample_id joins barcode_id exactly.

    Result paths are relative to the manifest's directory. No directory scan,
    backend execution, count pooling or technical-replicate selection occurs.
    """
    manifest_path, samples_path = Path(manifest_path).resolve(), Path(samples_path).resolve()
    try:
        manifest_bytes, samples_bytes = manifest_path.read_bytes(), samples_path.read_bytes()
        required = tuple(c for c in SAMPLE_COLUMNS if c not in {"forward_barcode", "reverse_barcode"})
        samples = _load_csv(samples_path, Sample, required)
        for field in ("sample_name", "barcode_id"):
            values = [getattr(s, field) for s in samples]
            if len(values) != len(set(values)):
                raise AggregationError(f"duplicate metadata {field}")
        metadata = {s.barcode_id: s for s in samples}
        reader = csv.reader(io.StringIO(manifest_bytes.decode("utf-8-sig")), strict=True)
        if next(reader, []) != ["result_json"]:
            raise AggregationError("manifest must have exactly one column: result_json")
        paths = []
        for row in reader:
            if len(row) != 1 or not row[0].strip():
                raise AggregationError(f"invalid manifest row {reader.line_num}")
            paths.append((manifest_path.parent / row[0].strip()).resolve())
        if not paths:
            raise AggregationError("manifest must contain at least one result")
        if len(paths) != len(set(paths)):
            raise AggregationError("duplicate resolved result path in manifest")
        observations, inputs, seen, replicates, target_definitions, definition_targets, policies = [], [], set(), set(), {}, {}, {}
        snapshots = {manifest_path: sha256(manifest_bytes), samples_path: sha256(samples_bytes)}
        for path in sorted(paths):
            data = path.read_bytes()
            raw = strict_json(data)
            if not isinstance(raw, dict) or type(raw.get("schema_version")) is not int or raw.get("schema_version") != 1 or raw.get("metric_contract_version") != "m4-v1":
                raise AggregationError(f"unsupported or missing M4 schema/metric contract: {path}")
            result = MetricResult.model_validate(raw)
            _validate_populations(result)
            if result.sample_id not in metadata:
                raise AggregationError(f"M4 sample absent from metadata barcode_id: {result.sample_id}")
            sample = metadata[result.sample_id]
            identity = (sample.sample_name, result.target_id)
            if identity in seen:
                raise AggregationError(f"duplicate analysis for sample x target: {identity}")
            seen.add(identity)
            replicate = (condition_key(sample), result.target_id, sample.biological_replicate)
            if replicate in replicates:
                raise AggregationError("duplicate biological_replicate within condition and target")
            replicates.add(replicate)
            definitions = result.provenance.target_definitions_sha256
            if target_definitions.setdefault(result.target_id, definitions) != definitions or definition_targets.setdefault(definitions, result.target_id) != result.target_id:
                raise AggregationError("conflicting target identity across analyses")
            source = Path(os.path.relpath(path, manifest_path.parent)).as_posix()
            snapshots[path] = sha256(data)
            inputs.append(InputResult(source_result=source, sha256=sha256(data), sample_id=result.sample_id,
                                      target_name=result.target_id, analysis_id=result.analysis_id))
            records = [(r, None) for _, r in result.target_metrics]
            records += [(r, None) for c in result.copies.values() for r in (c.native, c.precise)]
            records += [(r, _policy_definition(r)) for group in result.derived_metrics.values() for r in group.values()]
            local_series = set()
            for record, policy in records:
                if policy is not None:
                    if policies.setdefault(record.policy_id, canonical(policy)) != canonical(policy):
                        raise AggregationError(f"family policy definition collision: {record.policy_id}")
                observation = Observation(**subset(sample, BiologicalSample).model_dump(),
                    sample_id=result.sample_id, target_name=result.target_id, metric_name=record.metric_name,
                    population_scope=record.population_scope, population_id=record.population_id,
                    copy_name=record.copy_id, routing_conditioned=record.population_scope == "confident_copy",
                    policy_id=record.policy_id if policy is not None else None, policy_definition=policy,
                    status=record.status, numerator=record.numerator, denominator=record.denominator,
                    fraction=record.numerator / record.denominator if record.status == "REPORTABLE" else None,
                    reason_codes=record.reason_codes, analysis_id=result.analysis_id,
                    metric_contract_version=result.metric_contract_version, source_result=source)
                key = series_key(observation)
                if key in local_series:
                    raise AggregationError("duplicate metric/policy analytical series within one analysis")
                local_series.add(key)
                observations.append(observation)
        # Inputs must be immutable during collection, including metadata parsed by its shared loader.
        for path, expected in snapshots.items():
            if sha256(path.read_bytes()) != expected:
                raise AggregationError(f"input changed during collection: {path}")
        observations.sort(key=lambda r: (series_key(r), condition_key(r), r.sample_name))
        return StatisticsResult(
            schema_version=1, statistics_contract_version="m5-v1",
            provenance=Provenance(package_version=__version__, source_metric_contract_versions=["m4-v1"],
                input_results=sorted(inputs, key=lambda r: (r.sample_id, r.target_name)),
                samples_path=str(samples_path), manifest_path=str(manifest_path),
                contrast_specification_path=None, contrast_specification_hash=None,
                invocation_parameters={"command": "summarize", "sample_identity_column": "barcode_id",
                                       "result_paths_relative_to": "manifest_directory"},
                python=platform.python_version(), platform=platform.platform()),
            input_manifest_hash=sha256(manifest_bytes), sample_metadata_hash=sha256(samples_bytes),
            observations=observations, group_summaries=summarize_groups(observations), contrasts=[],
            multiple_testing_families=[], unused_metadata_sample_ids=sorted(
                s.sample_name for s in samples if s.sample_name not in {name for name, _ in seen}))
    except (OSError, UnicodeError, csv.Error, ValueError, TypeError) as exc:
        if isinstance(exc, AggregationError):
            raise
        raise AggregationError(str(exc)) from exc


def summarize_groups(observations):
    """Give each biological sample one vote; retain missing metric inventories."""
    members, series, rows = defaultdict(dict), {}, defaultdict(dict)
    for row in observations:
        condition, key = condition_key(row), series_key(row)
        members[(row.target_name, condition)][row.sample_name] = subset(row, BiologicalSample)
        series[key] = subset(row, Series)
        rows[(key, condition)][row.sample_name] = row
    summaries = []
    for key, definition in sorted(series.items()):
        for (target, condition), samples in sorted(members.items()):
            if target != definition.target_name:
                continue
            actual = rows[(key, condition)]
            assessments, fractions = [], []
            for name, sample in sorted(samples.items()):
                row = actual.get(name)
                assessments.append(SampleAssessment(**sample.model_dump(),
                    status=row.status if row else "MISSING_METRIC",
                    reason_codes=row.reason_codes if row else ["METRIC_NOT_PRESENT"]))
                if row and row.status == "REPORTABLE":
                    fractions.append(SampleFraction(sample_name=name, numerator=row.numerator,
                                                    denominator=row.denominator, fraction=row.fraction))
            values = [Fraction(r.numerator, r.denominator) for r in fractions]
            summaries.append(GroupSummary(**definition.model_dump(), condition=Condition.model_validate_json(condition),
                expected_sample_count=len(samples), expected_sample_ids=sorted(samples),
                reportable_count=len(fractions), blocked_count=sum(r.status == "BLOCKED" for r in assessments),
                not_assessable_count=sum(r.status == "NOT_ASSESSABLE" for r in assessments),
                missing_metric_count=sum(r.status == "MISSING_METRIC" for r in assessments),
                sample_assessments=assessments, reportable_sample_ids=[r.sample_name for r in fractions],
                source_fractions=fractions,
                mean_biological_sample_fraction=float(sum(values) / len(values)) if values else None,
                median_biological_sample_fraction=float(descriptive.median(values)) if values else None,
                minimum_biological_sample_fraction=float(min(values)) if values else None,
                maximum_biological_sample_fraction=float(max(values)) if values else None,
                pooled_read_fraction=sum(r.numerator for r in fractions) / sum(r.denominator for r in fractions) if values else None))
    return summaries


def publish(result, output):
    """Publish authoritative JSON and derived TSVs by a single sibling rename."""
    result = StatisticsResult.model_validate(result.model_dump())
    output = Path(output).absolute()
    if output.exists() or output.is_symlink():
        raise AggregationError(f"output already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    lock = output.with_name(f".{output.name}.m5-lock")
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise AggregationError(f"output publication already in progress: {output}") from exc
    os.close(descriptor)
    stage = None
    try:
        stage = Path(tempfile.mkdtemp(prefix=f".{output.name}.incomplete-", dir=output.parent))
        (stage / "result.json").write_text(json.dumps(result.model_dump(mode="json"), indent=2, sort_keys=True, allow_nan=False) + "\n")
        for filename, model, values in (("observations", Observation, result.observations),
                ("group_summaries", GroupSummary, result.group_summaries),
                ("contrasts", ContrastResult, result.contrasts)):
            with (stage / f"{filename}.tsv").open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(model.model_fields), delimiter="\t", lineterminator="\n")
                writer.writeheader()
                for value in values:
                    writer.writerow({k: canonical(v) if isinstance(v, (list, dict)) else "" if v is None else v
                                     for k, v in value.model_dump(mode="json").items()})
        if output.exists() or output.is_symlink():
            raise AggregationError(f"output already exists: {output}")
        stage.rename(output)
    finally:
        if stage is not None and stage.exists():
            shutil.rmtree(stage)
        lock.unlink()


def summarize(*, manifest_path, samples_path, output=None):
    result = collect_observations(manifest_path, samples_path)
    if output is not None:
        publish(result, output)
    return result
