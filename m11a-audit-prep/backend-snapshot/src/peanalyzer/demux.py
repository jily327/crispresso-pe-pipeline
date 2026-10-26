"""Streaming demultiplexing API. No CLI, merging, target routing or PE analysis."""

import hashlib
import json
import logging
import shutil
import tempfile
from importlib.resources import files
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from peanalyzer import __version__
from peanalyzer.barcodes import Catalog, assign_barcode_pair, bundled_catalog, extraction_rules, identify_read
from peanalyzer.barcodes import load_catalog, validate_catalog_matching
from peanalyzer.demux_output import SampleWriter, verify_matrix_file, write_heatmap, write_qc_tables
from peanalyzer.fastq import paired_fastq
from peanalyzer.provenance import software_provenance
from peanalyzer.schemas import Config, reverse_complement
from peanalyzer.validation import MetadataError, load_samples

LOG = logging.getLogger(__name__)
CATEGORIES = (
    "assigned_expected_pair", "unexpected_valid_barcode_pair", "ambiguous_barcode_match",
    "forward_only", "reverse_only", "no_barcode_match",
)


class DemuxError(ValueError):
    pass


def file_provenance(path: Path) -> dict:
    before = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise DemuxError(f"input changed while hashing: {path}")
    return {"path": str(path.resolve()), "size_bytes": after.st_size, "mtime_ns": after.st_mtime_ns, "sha256": digest.hexdigest()}


def reconcile(total: int, categories: dict, samples: dict, written: dict, matrix: Counter,
              expected: dict, mate_counts: dict) -> dict:
    if set(categories) != set(CATEGORIES) or any(type(n) is not int or n < 0 for n in [total, *categories.values(), *samples.values(), *written.values(), *matrix.values()]):
        raise DemuxError("reconciliation failed: invalid category/count schema")
    checks = {
        "terminal_categories_equal_input": total == sum(categories.values()),
        "sample_counts_equal_assigned": sum(samples.values()) == categories["assigned_expected_pair"],
        "written_pairs_equal_sample_counts": samples == written,
        "matrix_equals_recognized_pairs": sum(matrix.values()) == categories["assigned_expected_pair"] + categories["unexpected_valid_barcode_pair"],
        "expected_matrix_cells_equal_samples": {sample: matrix[pair] for pair, sample in expected.items()} == samples,
        "expected_matrix_sum_equals_assigned": sum(matrix[pair] for pair in expected) == categories["assigned_expected_pair"],
        "mate_records_equal_sample_counts": mate_counts == {sample: [count, count] for sample, count in samples.items()},
    }
    if not all(checks.values()):
        raise DemuxError(f"reconciliation failed: {checks}")
    return {"passed": True, "checks": checks}


def _end_qc(sequence, match, rule, bridge_enabled, qc, *, reverse=False):
    if match.status != "recognized":
        return
    qc["recognized"] += 1
    motif = sequence[rule.start:rule.start + match.length].decode("ascii").upper()
    if reverse:
        motif = reverse_complement(motif)
    for name, expected in (("prefix", rule.expected_prefix), ("suffix", rule.expected_suffix)):
        if expected:
            matches = motif.startswith(expected) if name == "prefix" else motif.endswith(expected)
            qc[f"{name}_match" if matches else f"{name}_mismatch"] += 1
    if bridge_enabled and rule.bridge:
        start = rule.start + match.length
        observed = sequence[start:start + len(rule.bridge)].decode("ascii").upper()
        status = "short" if len(observed) < len(rule.bridge) else "match" if observed == rule.bridge else "mismatch"
        qc[f"bridge_{status}"] += 1


def _json_hash(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _run_warnings(total, categories, short_motifs):
    warnings = []
    if not total:
        return ["empty input: assignment percentage is undefined", "zero assigned expected pairs"]
    if not categories["assigned_expected_pair"]:
        warnings.append("zero assigned expected pairs; check sample sheet, catalog and extraction settings")
    if categories["assigned_expected_pair"] / total < 0.1:
        warnings.append("low assigned fraction (<10% of input pairs); review run inputs and extraction settings")
    if categories["unexpected_valid_barcode_pair"] / total > 0.1:
        warnings.append("high unexpected valid barcode pair fraction (>10% of input pairs); no cause is inferred")
    for direction, count in short_motifs.items():
        if count / total > 0.5:
            warnings.append(f"{direction}: extraction offset plus barcode length exceeds read length for most reads ({count}/{total})")
    return warnings


def demultiplex(*, r1: Path, r2: Path, samples_path: Path, config: Config, output: Path,
                barcodes_path: Path | None = None, command_argv: list[str] | None = None) -> dict:
    """Publish a completed directory by renaming a private sibling staging tree.

    All terminal counts refer to input pairs. On handled failures, remove only
    this invocation's staging directory. Hard-kill leftovers remain incomplete.
    """
    r1, r2, samples_path, output = map(Path, (r1, r2, samples_path, output))
    if r1.resolve() == r2.resolve():
        raise DemuxError("R1 and R2 must be distinct input files")
    if output.exists() or output.is_symlink():
        raise DemuxError(f"output already exists; choose a new directory: {output}")
    settings = config.demux
    if barcodes_path is None and settings.profile == "qi_hitom_v1":
        barcodes_path = bundled_catalog()
    # Snapshot before loading so metadata changes during processing are detected.
    sources = {"samples": samples_path}
    if barcodes_path:
        sources["barcodes"] = Path(barcodes_path)
    provenance = {name: file_provenance(path) for name, path in sources.items()}
    catalog = load_catalog(Path(barcodes_path)) if barcodes_path else Catalog([], authoritative=False)
    samples = load_samples(samples_path, catalog, metadata_required=False)
    catalog_safety, warnings = validate_catalog_matching(catalog, settings.max_mismatches)
    rules = extraction_rules(settings, catalog)
    expected = {(sample.forward_barcode_id, sample.reverse_barcode_id): sample.barcode_id for sample in samples}
    if len(expected) != len(samples):
        raise MetadataError("duplicate expected barcode pair")
    # Metadata safety checks must complete before even hashing FASTQ data.
    sources.update(r1=r1, r2=r2)
    provenance.update({name: file_provenance(path) for name, path in (("r1", r1), ("r2", r2))})
    profile_sha256 = None
    if settings.profile != "custom":
        profile_sha256 = hashlib.sha256(files("peanalyzer").joinpath(f"profiles/{settings.profile}.yaml").read_bytes()).hexdigest()
    software = software_provenance()
    started = datetime.now(timezone.utc).isoformat()
    categories = dict.fromkeys(CATEGORIES, 0)
    sample_counts = {sample.barcode_id: 0 for sample in samples}
    matrix, barcode_counts, corrected = Counter(), Counter(), Counter()
    end_qc = {}
    for direction, rule in rules.items():
        keys = ["recognized"]
        for name in ("prefix", "suffix"):
            if getattr(rule, f"expected_{name}"):
                keys.extend([f"{name}_match", f"{name}_mismatch"])
        if settings.bridge_qc and rule.bridge:
            keys.extend(["bridge_match", "bridge_mismatch", "bridge_short"])
        end_qc[direction] = Counter(dict.fromkeys(keys, 0))
    total = 0
    short_motifs = dict.fromkeys(rules, 0)
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{output.name}.incomplete-", dir=output.parent))
    writer = None
    succeeded = False
    try:
        qc_dir = staging / "01_demux_QC"
        fastq_dir = staging / "02_demultiplexed_fastq"
        qc_dir.mkdir()
        fastq_dir.mkdir()
        writer = SampleWriter(fastq_dir, list(sample_counts), settings.max_open_sample_pairs)
        for forward, reverse in paired_fastq(r1, r2):
            total += 1
            matches = {}
            for direction, record in (("forward", forward), ("reverse", reverse)):
                if len(record.sequence) < rules[direction].start + catalog_safety[direction]["barcode_length"]:
                    short_motifs[direction] += 1
                match = identify_read(record.sequence, rules[direction], catalog.ends[direction], settings.max_mismatches,
                                      reverse=direction == "reverse" and settings.reverse_barcode_orientation == "reverse_complement")
                matches[direction] = match
                if match.status == "recognized":
                    barcode_counts[direction, match.barcode_id] += 1
                    if match.distance:
                        corrected[direction, match.barcode_id] += 1
                _end_qc(record.sequence, match, rules[direction], settings.bridge_qc, end_qc[direction],
                        reverse=direction == "reverse" and settings.reverse_barcode_orientation == "reverse_complement")
            f, r = matches["forward"], matches["reverse"]
            category, sample_id = assign_barcode_pair(f, r, expected)
            categories[category] += 1
            if f.status == r.status == "recognized":
                matrix[f.barcode_id, r.barcode_id] += 1
            if category == "assigned_expected_pair":
                records = [forward, reverse]
                if settings.trim_barcodes:
                    for index, (direction, match) in enumerate((("forward", f), ("reverse", r))):
                        rule = rules[direction]
                        count = rule.start + match.length + (len(rule.bridge) if settings.trim_bridges else 0)
                        records[index] = records[index].trimmed(count)
                writer.write(sample_id, *records)
                sample_counts[sample_id] += 1
            if total % 100000 == 0:
                LOG.info("Processed %d read pairs", total)
        writer.ensure_empty_samples()
        writer.verify_files()
        reconciliation = reconcile(total, categories, sample_counts, writer.counts, matrix, expected, writer.record_counts)
        for name, path in sources.items():
            stat = path.stat()
            if (stat.st_size, stat.st_mtime_ns) != (provenance[name]["size_bytes"], provenance[name]["mtime_ns"]):
                raise DemuxError(f"input changed during demultiplexing: {path}")
        write_qc_tables(qc_dir, catalog, matrix, barcode_counts, corrected, expected)
        verify_matrix_file(qc_dir, catalog, matrix)
        reconciliation["checks"]["on_disk_matrix_matches_counts"] = True
        visualization = {"status": "completed", "path": "01_demux_QC/barcode_pair_heatmap.png"}
        try:
            write_heatmap(qc_dir, catalog, matrix, expected)
        except Exception as exc:
            # Rendering is optional. Interrupts/SystemExit still cancel the run.
            (qc_dir / "barcode_pair_heatmap.png").unlink(missing_ok=True)
            visualization = {"status": "failed", "error_type": type(exc).__name__}
            warnings.append(f"heatmap visualization failed ({type(exc).__name__}); authoritative outputs are complete")
        output_files = {}
        for sample, filenames in writer.names.items():
            for mate, filename in enumerate(filenames, 1):
                path = fastq_dir / filename
                metadata = file_provenance(path)
                output_files[path.relative_to(staging).as_posix()] = {
                    "sha256": metadata["sha256"], "size_bytes": metadata["size_bytes"],
                    "sample_id": sample, "mate": mate, "records": writer.record_counts[sample][mate - 1]}
        for filename in ("barcode_counts.csv", "barcode_pair_matrix.csv"):
            path = qc_dir / filename
            metadata = file_provenance(path)
            output_files[path.relative_to(staging).as_posix()] = {key: metadata[key] for key in ("sha256", "size_bytes")}
        warnings.extend(_run_warnings(total, categories, short_motifs))
        resolved_config = config.model_dump(mode="json")
        # Persist effective profile values, not unset overrides: reloading the
        # resolved config must preserve bridge checks and extraction behavior.
        for direction, rule in rules.items():
            for setting, key in (("offset", "start"), ("length", "length"), ("bridge", "bridge")):
                resolved_config["demux"][f"{direction}_{setting}"] = getattr(rule, key)
        config_digest = _json_hash(resolved_config)
        profile_rules = {key: rule.model_dump() for key, rule in rules.items()}
        summary = {
            "schema_version": 2, "status": "completed", "pipeline_version": __version__,
            "started_at": started, "completed_at": datetime.now(timezone.utc).isoformat(),
            "total_input_read_pairs": total, **categories,
            "assignment_percentage": 100 * categories["assigned_expected_pair"] / total if total else None,
            "per_sample_assigned_read_pairs": sample_counts,
            "samples": [sample.model_dump(mode="json") for sample in samples],
            "extraction_profile": {"name": settings.profile, "rules": profile_rules,
                                   "source_sha256": profile_sha256, "resolved_sha256": _json_hash(profile_rules)},
            "barcode_catalog": {"source": str(barcodes_path) if barcodes_path else "explicit sample sequences",
                                "authoritative": catalog.authoritative, "resolved": catalog.ends,
                                "resolved_sha256": _json_hash(catalog.ends), "matching_safety": catalog_safety},
            "mismatch_policy": {"method": "exact" if settings.max_mismatches == 0 else "hamming", "max_mismatches_per_end": settings.max_mismatches, "ties": "ambiguous", "sample_pair_rescue": False, "non_acgt_motifs": "unknown"},
            "barcode_bridge_qc": {key: dict(value) for key, value in end_qc.items()},
            "resolved_config": resolved_config, "resolved_config_sha256": config_digest,
            "input_provenance": provenance, "reconciliation": reconciliation,
            "output_files": output_files, "software": software,
            "invocation": {"argv": command_argv, "cwd": str(Path.cwd())},
            "visualization": visualization, "short_barcode_reads": short_motifs, "warnings": warnings,
        }
        # A completion state is visible only after gzip close, QC and reconciliation.
        temporary = qc_dir / "demux_summary.json.tmp"
        temporary.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
        temporary.replace(qc_dir / "demux_summary.json")
        if output.exists() or output.is_symlink():
            raise DemuxError(f"output already exists at publication: {output}")
        staging.rename(output)
        succeeded = True
        for warning in warnings:
            LOG.warning("%s", warning)
        LOG.info("Completed %d read pairs; all count reconciliations passed", total)
        return summary
    finally:
        try:
            if writer is not None:
                writer.close()
        finally:
            if not succeeded and staging.exists():
                shutil.rmtree(staging)
