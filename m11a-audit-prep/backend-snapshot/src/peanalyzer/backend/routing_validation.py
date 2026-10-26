"""Synthetic-only ground-truth audit; never a production homeolog router."""

import csv
import io
import json
import shutil
import subprocess
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

from peanalyzer.analysis_fastq import prepare_analysis_fastqs
from peanalyzer.backend.pooled import BackendError, Executable, run_pooled_diagnostic, utc_now
from peanalyzer.backend.metrics import parse_child
from peanalyzer.backend.synthetic import write_synthetic_run
from peanalyzer.demux import demultiplex
from peanalyzer.demux_verify import read_json, sha256_file
from peanalyzer.fastq import read_fastq, read_id
from peanalyzer.provenance import software_provenance
from peanalyzer.schemas import Config, Target


def read_sam_routes(path: Path, reference_names: dict) -> dict:
    routes = defaultdict(list)
    with path.open() as handle:
        for line in handle:
            if line.startswith("@"):
                continue
            fields = line.rstrip("\n").split("\t")
            if len(fields) < 11:
                raise BackendError("INVALID_ROUTING_ARTIFACT", "malformed SAM record")
            identifier, flag, reference = fields[0], int(fields[1]), fields[2]
            if identifier.endswith(("/1", "/2")):
                identifier = identifier[:-2]
            if flag & 4:
                continue
            if reference not in reference_names:
                raise BackendError("INVALID_ROUTING_ARTIFACT", f"unknown reference {reference}")
            tags = {field.split(":", 2)[0]: field.split(":", 2)[2] for field in fields[11:]}
            routes[identifier].append({"copy": reference_names[reference], "flag": flag, "mapq": int(fields[4]),
                                       "alignment_score": int(tags["AS"]) if "AS" in tags else None,
                                       "alternative_score": int(tags["XS"]) if "XS" in tags else None})
    return dict(routes)


def reference_smoke(pooled_root: Path, pooled_info: dict, targets: list[Target], truth: list[dict], routes: dict) -> dict:
    results = {}
    by_name = {t.amplicon_id: t for t in targets}
    if set(pooled_info["results"]["all_region_display_names"].values()) != set(by_name):
        raise BackendError("MISSING_CHILD_ARTIFACT", "Pooled reference inventory differs from targets")
    for run, display in pooled_info["results"]["all_region_display_names"].items():
        target = by_name[display]
        folder = pooled_info["results"]["good_region_folders"].get(run)
        if not folder or Path(folder).name != folder:
            raise BackendError("MISSING_CHILD_ARTIFACT", display)
        child = pooled_root / folder
        data = read_json(child / "CRISPResso2_info.json")
        if data["running_info"]["version"] != "2.3.4" or not data["running_info"].get("end_time_string"):
            raise BackendError("INVALID_CHILD_ARTIFACT", display)
        refs = data["results"]["refs"]
        if refs["Reference"]["sequence"] != target.wt_sequence or refs["Prime-edited"]["sequence"] != target.prime_edited_sequence:
            raise BackendError("PE_REFERENCE_MISMATCH", display)
        expected_ids = [r["read_id"] for r in truth if r["ground_truth_copy"] == display and r["ground_truth_class"] == "precise_PE"]
        routed = sum(len(routes.get(identifier, [])) == 1 and routes[identifier][0]["copy"] == display for identifier in expected_ids)
        with zipfile.ZipFile(child / data["running_info"]["allele_frequency_table_zip_filename"]) as archive:
            with archive.open(data["running_info"]["allele_frequency_table_filename"]) as handle:
                rows = list(csv.DictReader(io.TextIOWrapper(handle), delimiter="\t"))
        matched = sum(int(row["#Reads"]) for row in rows if row["Reference_Name"] == "Prime-edited" and
                      row["Aligned_Sequence"].replace("-", "") == target.prime_edited_sequence)
        results[display] = {"wt_reference_verified": True, "pe_reference_verified": True,
                            "precise_pe_truth_reads": len(expected_ids), "precise_pe_routed_correctly": routed,
                            "exact_synthetic_pe_allele_reads_assigned_to_pe_reference": matched,
                            "scope": "synthetic reference smoke test, not a production efficiency metric"}
        result = parse_child(child, routed_pairs=sum(r['copy']==display for hits in routes.values() for r in hits),
                             one_input_record_per_pair=True, preprocessing_preserves_records=True)
        results[display]['alignment_reconciliation'] = result
    return results


def analyze_routing(*, pooled_root: Path, sam: Path, targets: list[Target], truth: list[dict], design: dict, output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    info = read_json(pooled_root / "CRISPResso2Pooled_info.json")
    display_names = info["results"]["all_region_display_names"]
    routes = read_sam_routes(sam, {"AMPL_" + run: name for run, name in display_names.items()})
    by_id = {row["read_id"]: row for row in truth}
    if len(by_id) != len(truth) or set(routes) - set(by_id):
        raise BackendError("ROUTING_TRUTH_MISMATCH", "duplicate truth or unknown routed read IDs")
    # Confirm that BAM routing really propagated into the FASTQs consumed by Core.
    delivered = defaultdict(list)
    for run, display in display_names.items():
        for record in read_fastq(pooled_root / f"AMPL_{run}.fastq.gz"):
            delivered[read_id(record, 1).decode()].append(display)
    if {key: sorted(value) for key, value in delivered.items()} != {key: sorted(r["copy"] for r in value) for key, value in routes.items()}:
        raise BackendError("ROUTING_HANDOFF_MISMATCH", "BAM and per-copy FASTQs disagree")
    matrix, by_class, counts = Counter(), Counter(), Counter()
    rows, cross_routes = [], []
    for row in truth:
        hits = routes.get(row["read_id"], [])
        routed = hits[0]["copy"] if len(hits) == 1 else "unassigned" if not hits else "multiple"
        informative = row["informative"] is True or row["informative"] == "True"
        group = row["ground_truth_copy"] if informative else "noninformative"
        matrix[group, routed] += 1
        by_class[row["ground_truth_class"], routed] += 1
        counts["informative_reads" if informative else "deliberately_noninformative_reads"] += 1
        if not hits:
            counts["unassigned_reads"] += 1
        if len(hits) > 1:
            counts["multiply_routed_reads"] += 1
        if informative:
            if routed == row["ground_truth_copy"]:
                counts["correct_informative_routes"] += 1
            elif hits:
                counts["incorrect_cross_routes"] += 1
                cross_routes.append(row["read_id"])
        elif hits:
            counts["noninformative_reads_assigned_to_copies"] += 1
        tied = len(hits) == 1 and hits[0]["alignment_score"] is not None and hits[0]["alignment_score"] == hits[0]["alternative_score"]
        counts["score_tied_routed_reads"] += int(tied)
        rows.append({**row, "routed_copy": routed, "alignment_count": len(hits), "score_tied": tied,
                     "mapq": hits[0]["mapq"] if len(hits) == 1 else "", "AS": hits[0]["alignment_score"] if len(hits) == 1 else "",
                     "XS": hits[0]["alternative_score"] if len(hits) == 1 else ""})
    for key in ("unassigned_reads", "multiply_routed_reads", "incorrect_cross_routes", "noninformative_reads_assigned_to_copies"):
        counts.setdefault(key, 0)
    summary = {"schema_version": 1, "total_synthetic_reads": len(truth), **counts,
               "explicit_backend_ambiguous_read_count": None,
               "ambiguity_policy": {"expand_ambiguous_alignments": False, "assign_ambiguous_alignments_to_first_reference": False,
                                    "pooled_routing": "default Bowtie2 primary-hit routing; no wrapper filtering"},
               "design_sha256": design["design_sha256"], "cross_routed_read_ids": cross_routes,
               "per_copy_routed_counts": {copy: sum(matrix[group, copy] for group in {k[0] for k in matrix}) for copy in display_names.values()},
               "artifacts": {"bam_sha256": sha256_file(pooled_root / "CRISPResso_AMPLICONS_ALIGNED.bam"), "sam_sha256": sha256_file(sam),
                             "pooled_info_sha256": sha256_file(pooled_root / "CRISPResso2Pooled_info.json")},
               "routing_gate": "FAIL" if counts["incorrect_cross_routes"] or counts["noninformative_reads_assigned_to_copies"] or counts["multiply_routed_reads"]
               or counts["score_tied_routed_reads"] or not counts["informative_reads"]
               or counts["correct_informative_routes"] != counts["informative_reads"] else "PASS"}
    summary["reference_smoke"] = reference_smoke(pooled_root, info, targets, truth, routes)
    with (output / "synthetic_routing_results.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    columns = [*display_names.values(), "unassigned", "multiple"]
    for name, data in (("routing_confusion_matrix.csv", matrix), ("routing_by_class.csv", by_class)):
        with (output / name).open("w", newline="") as handle:
            writer = csv.writer(handle); writer.writerow(["ground_truth", *columns])
            for group in sorted({key[0] for key in data}):
                writer.writerow([group, *(data[group, column] for column in columns)])
    (output / "routing_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    return summary


def run_synthetic_experiment(output: Path, *, core: Executable, pooled: Executable, samtools: str,
                             child_core_command: str | None = None, guide_mismatch=False) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    targets, truth = write_synthetic_run(output / "synthetic", guide_mismatch=guide_mismatch)
    demultiplex(r1=output / "synthetic/raw_R1.fastq.gz", r2=output / "synthetic/raw_R2.fastq.gz",
                samples_path=output / "synthetic/samples.csv", config=Config(schema_version=1), output=output / "demux")
    prepare_analysis_fastqs(output / "demux", output / "analysis")
    try:
        run_pooled_diagnostic(r1=output / "analysis/03_analysis_fastq/1B_R1.analysis.fastq.gz",
                          r2=output / "analysis/03_analysis_fastq/1B_R2.analysis.fastq.gz", targets=targets,
                          output=output / "backend", core=core, pooled=pooled, child_core_command=child_core_command,
                          diagnostic_test_unsupported_guide=guide_mismatch)
    except BackendError as exc:
        if not guide_mismatch or exc.code != "PE_GUIDE_REFERENCE_MISMATCH_UNSUPPORTED":
            raise
        execution = read_json(output / "backend/execution.json")
        observation = {"status": "rejected", "error_code": exc.code, "return_code": execution["return_code"],
                       "guide_sequences_unchanged": targets[0].pegRNA_spacer == targets[1].pegRNA_spacer,
                       "backend_sequence_check_override": False,
                       "error_text": "The given prime editing pegRNA spacer is not found in the reference sequence",
                       "stderr_sha256": sha256_file(output / "backend/stderr.log"),
                       "design_sha256": read_json(output / "synthetic/synthetic_design.json")["design_sha256"],
                       "downstream_analysis_permitted": False}
        (output / "guide_mismatch_result.json").write_text(json.dumps(observation, indent=2, sort_keys=True) + "\n")
        return observation
    root = output / "backend/output/CRISPRessoPooled_on_diagnostic"
    executable = shutil.which(samtools)
    if executable is None:
        raise BackendError("EXECUTABLE_MISSING", samtools)
    probe_argv, probe_start = [executable, "--version"], utc_now()
    probe = subprocess.run(probe_argv, capture_output=True, text=True, errors="replace", check=False)
    version_probe = {"argv": probe_argv, "started_at": probe_start, "ended_at": utc_now(),
                     "return_code": probe.returncode, "stdout": probe.stdout, "stderr": probe.stderr}
    if probe.returncode:
        raise BackendError("VERSION_PROBE_FAILED", f"samtools exit {probe.returncode}")
    argv = [executable, "view", str(root / "CRISPResso_AMPLICONS_ALIGNED.bam")]
    start = utc_now()
    with (output / "routing.sam").open("w") as stdout, (output / "samtools.stderr.log").open("w") as stderr:
        result = subprocess.run(argv, stdout=stdout, stderr=stderr, check=False)
    (output / "samtools_execution.json").write_text(json.dumps({"argv": argv, "started_at": start, "ended_at": utc_now(),
        "software": software_provenance(), "version_probe": version_probe, "executable_path": executable,
        "input_path": str(root / "CRISPResso_AMPLICONS_ALIGNED.bam"), "output_path": str(output / "routing.sam"),
        "backend_manifest_sha256": sha256_file(output / "backend/execution.json"),
        "return_code": result.returncode, "input_sha256": sha256_file(root / "CRISPResso_AMPLICONS_ALIGNED.bam"),
        "output_sha256": sha256_file(output / "routing.sam")}, indent=2) + "\n")
    if result.returncode:
        raise BackendError("ROUTING_ARTIFACT_EXTRACTION_FAILED", str(result.returncode))
    return analyze_routing(pooled_root=root, sam=output / "routing.sam", targets=targets, truth=truth,
                           design=read_json(output / "synthetic/synthetic_design.json"), output=output / "05_routing_QC")
