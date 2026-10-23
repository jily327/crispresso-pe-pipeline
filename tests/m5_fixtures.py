"""Deterministic synthetic M4 documents; no FASTQ or backend is accessed."""
import csv
import json
from pathlib import Path

import yaml

from peanalyzer.metrics import MetricResult
from peanalyzer.metrics.production import digest
from peanalyzer.remediation import panel


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def result_document(sample_id, target_name, numerator, denominator):
    targets = [t.model_dump() | {"target_name": target_name} for t in panel()]
    definitions = digest(targets)
    prepared = digest({"synthetic_sample": sample_id})
    routing = digest({"synthetic_routing": sample_id, "target": target_name})
    population = digest(dict(prepared=prepared, sample=sample_id, target=definitions, scope="target_all_prepared"))
    evidence, families = {}, {}

    def records(copy, n, d):
        scope = "confident_copy" if copy else "target_all_prepared"
        pop = digest(dict(prepared_population=population, routing=routing, copy=copy, scope=scope)) if copy else population
        common = dict(population_scope=scope, population_id=pop, population_input_reads=d, copy_id=copy,
            routing_conditioned=bool(copy), status="REPORTABLE", numerator=n, denominator=d, reason_codes=[],
            confident_input_reads=d if copy else None, backend_input_reads=d, reads_after_preprocessing=d,
            aligned_reads=d, unaligned_reads=0, preprocessing_count_delta=0, unaligned_reason_counts={},
            ordinary_classified_aligned_reads=d, ambiguous_aligned_reads=0, discarded_aligned_reads=0,
            backend_counts_role="metric_filter", population_denominator_exclusions=0)
        native = common | dict(metric_name=copy + "_crispresso_native_pe" if copy else "target_crispresso_native_pe",
                              metric_family="native", assessment_stage="backend_aligned_products", products=None)
        precise = common | dict(metric_name=copy + "_precise_pe" if copy else "total_precise_pe", metric_family="precise",
            assessment_stage="backend_aligned_products" if copy else "prepared_pairs",
            products=dict(exact_wt=d-n, exact_pe=n, classification_input_reads=d))
        products = []
        for count, state in ((d-n, "WT"), (n, "PE")):
            if count:
                products.append(dict(sequence=targets[0]["wt_sequence" if state == "WT" else "prime_edited_sequence"],
                    count=count, assessable=True, canonical_exact_wt=state == "WT", canonical_exact_pe=state == "PE"))
        key = copy or "target"
        evidence[key] = dict(population_id=pop, population_scope=scope, copy_id=copy,
            assessment_stage=precise["assessment_stage"], source_input_reads=d, classification_input_reads=d,
            targets=targets, products=products)
        families[key] = {}
        for tolerance in (0, 1):
            policy_id = f"policy{tolerance}"
            families[key][policy_id] = dict(metric_name=copy + "_pe_family" if copy else "total_pe_family",
                policy_id=policy_id, policy=dict(policy_id=policy_id, max_extra_substitutions=tolerance,
                    max_extra_indel_events=0, allowed_extra_substitution_positions=None),
                population_id=pop, population_scope=scope, copy_id=copy, status="REPORTABLE",
                numerator=n, denominator=d, wt_family=d-n, pe_family=n, family_ambiguous=0, excluded=0,
                classification_input_reads=d, reason_codes=[])
        return native, precise

    native, precise = records(None, numerator, denominator)
    copies = {}
    left_d, left_n = denominator // 2, numerator // 2
    for copy, n, d in (("copy1", left_n, left_d), ("copy2", numerator-left_n, denominator-left_d)):
        cn, cp = records(copy, n, d)
        copies[copy] = dict(copy_id=copy, copy_metric_status="REPORTABLE", native=cn, precise=cp)
    raw = dict(schema_version=1, metric_contract_version="m4-v1", target_id=target_name, sample_id=sample_id,
        analysis_id=f"synthetic-{sample_id}-{target_name}",
        provenance=dict(software={"fixture": "synthetic M5 count contract"}, prepared_manifest_sha256=prepared,
            prepared_sample={"pairs": denominator}, target_definitions_sha256=definitions,
            routing_manifest_sha256=routing, routing_policy_identity={}, crispresso_version="2.3.4", runtime_digest=None, artifacts={}),
        eligibility=dict(target_metric_status="REPORTABLE", routing_geometry_status="SAFE", comparator_status="REPORTABLE",
                         anchor_invariant=True, block_reason_codes=[]),
        target_metrics=dict(target_crispresso_native_pe=native, total_precise_pe=precise), copies=copies,
        qc=dict(prepared_input_reads=denominator, routing_assigned_reads=denominator, routing_quarantined_reads=0,
            routing_quarantine_fraction={"numerator": 0, "denominator": denominator}, routing_quarantine_reasons={},
            target_backend_input_reads=denominator, target_backend_aligned_reads=denominator, target_backend_unaligned_reads=0,
            target_backend_unaligned_fraction={"numerator": 0, "denominator": denominator}, exact_assessable_reads=denominator,
            exact_product_exclusions=0, per_copy_confident_counts={c: v["native"]["population_input_reads"] for c, v in copies.items()}, limitations=[]),
        anchor_evidence={}, product_evidence=evidence, derived_metrics=families)
    return MetricResult.model_validate(raw).model_dump(mode="json")


def condition(treatment):
    return dict(editor="synthetic-editor", treatment=treatment, dpi=6)


def contrast(contrast_id="native", **overrides):
    return dict(contrast_id=contrast_id, family_id="primary", target_name="T1",
        metric_name="target_crispresso_native_pe", copy_name=None, policy_id=None,
        group_a=condition("A"), group_b=condition("B"), pairing_mode="unpaired", alternative="two-sided") | overrides


def dataset(root, *, paired=False, replicates=3, targets=("T1", "T2")):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    samples, paths = [], []
    for treatment in ("A", "B"):
        for i in range(replicates):
            name = f"{treatment}{i+1:03}"
            sample_id = "barcode-" + name
            sample = dict(sample_name=name, barcode_id=sample_id, forward_barcode="AAAA", reverse_barcode="CCCC",
                **condition(treatment), biological_replicate=str(i+1), block_id=f"block{i+1:03}" if paired else "",
                paired="true" if paired else "false")
            samples.append(sample)
            d = (10, 100, 20)[i % 3]
            fraction_tenths = (i % 3) if treatment == "A" else (8 + i % 3)
            n = d * fraction_tenths // 10
            for target in targets:
                path = root / f"{name}-{target}.json"
                write_json(path, result_document(sample_id, target, n, d))
                paths.append(path.name)
    write_samples(root / "samples.csv", samples)
    write_manifest(root / "metrics_manifest.csv", paths)
    spec = dict(schema_version=1, families=["primary", "secondary"], contrasts=[
        contrast(pairing_mode="block" if paired else "unpaired"),
        contrast("precise", metric_name="total_precise_pe", pairing_mode="block" if paired else "unpaired"),
        contrast("copy", metric_name="copy1_precise_pe", copy_name="copy1", pairing_mode="block" if paired else "unpaired"),
        contrast("family", metric_name="total_pe_family", policy_id="policy1", pairing_mode="block" if paired else "unpaired"),
        contrast("copy-family", metric_name="copy1_pe_family", copy_name="copy1", policy_id="policy0",
                 family_id="secondary", pairing_mode="block" if paired else "unpaired")])
    (root / "contrasts.yaml").write_text(yaml.safe_dump(spec, sort_keys=True))
    return dict(manifest_path=root / "metrics_manifest.csv", samples_path=root / "samples.csv", contrasts_path=root / "contrasts.yaml")


def write_samples(path, samples):
    with Path(path).open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(samples[0]))
        writer.writeheader()
        writer.writerows(samples)


def read_samples(path):
    with Path(path).open(newline="") as handle:
        return list(csv.DictReader(handle))


def write_manifest(path, paths):
    with Path(path).open("w", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["result_json"])
        writer.writerows([[p] for p in paths])


def change_record(path, status, name="target_crispresso_native_pe"):
    raw = json.loads(Path(path).read_text())
    raw["target_metrics"][name].update(status=status, numerator=None, denominator=None, reason_codes=["SYNTHETIC_" + status])
    write_json(path, raw)
