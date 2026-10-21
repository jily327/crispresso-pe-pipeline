"""Streaming demultiplexing API. No CLI, merging, target routing or PE analysis."""

import hashlib
import json
import logging
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from peanalyzer import __version__
from peanalyzer.barcodes import Catalog, assign_barcode_pair, bundled_catalog, extraction_rules, identify_read
from peanalyzer.barcodes import load_catalog
from peanalyzer.demux_output import SampleWriter, write_qc_tables
from peanalyzer.fastq import paired_fastq
from peanalyzer.schemas import Config
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


def reconcile(total: int, categories: dict, samples: dict, written: dict, matrix: Counter) -> dict:
    if set(categories) != set(CATEGORIES) or any(type(n) is not int or n < 0 for n in [total, *categories.values(), *samples.values(), *written.values(), *matrix.values()]):
        raise DemuxError("reconciliation failed: invalid category/count schema")
    checks = {
        "terminal_categories_equal_input": total == sum(categories.values()),
        "sample_counts_equal_assigned": sum(samples.values()) == categories["assigned_expected_pair"],
        "written_pairs_equal_sample_counts": samples == written,
        "matrix_equals_recognized_pairs": sum(matrix.values()) == categories["assigned_expected_pair"] + categories["unexpected_valid_barcode_pair"],
    }
    if not all(checks.values()):
        raise DemuxError(f"reconciliation failed: {checks}")
    return {"passed": True, "checks": checks}


def _end_qc(sequence, match, rule, bridge_enabled, qc):
    if match.status != "recognized":
        return
    qc["recognized"] += 1
    motif = sequence[rule.start:rule.start + match.length].decode("ascii").upper()
    for name, expected in (("prefix", rule.expected_prefix), ("suffix", rule.expected_suffix)):
        if expected:
            matches = motif.startswith(expected) if name == "prefix" else motif.endswith(expected)
            qc[f"{name}_match" if matches else f"{name}_mismatch"] += 1
    if bridge_enabled and rule.bridge:
        start = rule.start + match.length
        observed = sequence[start:start + len(rule.bridge)].decode("ascii").upper()
        status = "short" if len(observed) < len(rule.bridge) else "match" if observed == rule.bridge else "mismatch"
        qc[f"bridge_{status}"] += 1


def demultiplex(*, r1: Path, r2: Path, samples_path: Path, config: Config, output: Path, barcodes_path: Path | None = None) -> dict:
    """Create a new output directory; reject existing output and fail as a unit.

    All terminal counts refer to input pairs. On handled failures, remove only
    this invocation's newly created directory. The success JSON is written last.
    """
    r1, r2, samples_path, output = map(Path, (r1, r2, samples_path, output))
    if r1.resolve() == r2.resolve():
        raise DemuxError("R1 and R2 must be distinct input files")
    if output.exists():
        raise DemuxError(f"output already exists; choose a new directory: {output}")
    settings = config.demux
    if barcodes_path is None and settings.profile == "qi_hitom_v1":
        barcodes_path = bundled_catalog()
    # Snapshot before loading so metadata changes during processing are detected.
    sources = {"r1": r1, "r2": r2, "samples": samples_path}
    if barcodes_path:
        sources["barcodes"] = Path(barcodes_path)
    provenance = {name: file_provenance(path) for name, path in sources.items()}
    catalog = load_catalog(Path(barcodes_path)) if barcodes_path else Catalog([])
    samples = load_samples(samples_path, catalog, metadata_required=False)
    rules = extraction_rules(settings, catalog)
    expected = {(sample.forward_barcode_id, sample.reverse_barcode_id): sample.barcode_id for sample in samples}
    if len(expected) != len(samples):
        raise MetadataError("duplicate expected barcode pair")
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
    # mkdir is exclusive, so cleanup can never erase a preexisting user's result.
    output.mkdir(parents=True, exist_ok=False)
    writer = None
    succeeded = False
    try:
        qc_dir = output / "01_demux_QC"
        fastq_dir = output / "02_demultiplexed_fastq"
        qc_dir.mkdir()
        fastq_dir.mkdir()
        writer = SampleWriter(fastq_dir, list(sample_counts), settings.max_open_sample_pairs)
        for forward, reverse in paired_fastq(r1, r2):
            total += 1
            matches = {}
            for direction, record in (("forward", forward), ("reverse", reverse)):
                match = identify_read(record.sequence, rules[direction], catalog.ends[direction], settings.max_mismatches,
                                      reverse=direction == "reverse" and settings.reverse_barcode_orientation == "reverse_complement")
                matches[direction] = match
                if match.status == "recognized":
                    barcode_counts[direction, match.barcode_id] += 1
                    if match.distance:
                        corrected[direction, match.barcode_id] += 1
                _end_qc(record.sequence, match, rules[direction], settings.bridge_qc, end_qc[direction])
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
        reconciliation = reconcile(total, categories, sample_counts, writer.counts, matrix)
        for name, path in sources.items():
            stat = path.stat()
            if (stat.st_size, stat.st_mtime_ns) != (provenance[name]["size_bytes"], provenance[name]["mtime_ns"]):
                raise DemuxError(f"input changed during demultiplexing: {path}")
        write_qc_tables(qc_dir, catalog, matrix, barcode_counts, corrected, expected)
        resolved_config = config.model_dump(mode="json")
        # Persist effective profile values, not unset overrides: reloading the
        # resolved config must preserve bridge checks and extraction behavior.
        for direction, rule in rules.items():
            for setting, key in (("offset", "start"), ("length", "length"), ("bridge", "bridge")):
                resolved_config["demux"][f"{direction}_{setting}"] = getattr(rule, key)
        config_digest = hashlib.sha256(json.dumps(resolved_config, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        summary = {
            "schema_version": 1, "status": "completed", "pipeline_version": __version__,
            "started_at": started, "completed_at": datetime.now(timezone.utc).isoformat(),
            "total_input_read_pairs": total, **categories,
            "assignment_percentage": 100 * categories["assigned_expected_pair"] / total if total else None,
            "per_sample_assigned_read_pairs": sample_counts,
            "samples": [sample.model_dump(mode="json") for sample in samples],
            "extraction_profile": {"name": settings.profile, "rules": {key: rule.model_dump() for key, rule in rules.items()}},
            "barcode_catalog": {"source": str(barcodes_path) if barcodes_path else "explicit sample sequences", "resolved": catalog.ends},
            "mismatch_policy": {"method": "exact" if settings.max_mismatches == 0 else "hamming", "max_mismatches_per_end": settings.max_mismatches, "ties": "ambiguous", "sample_pair_rescue": False, "non_acgt_motifs": "unknown"},
            "barcode_bridge_qc": {key: dict(value) for key, value in end_qc.items()},
            "resolved_config": resolved_config, "resolved_config_sha256": config_digest,
            "input_provenance": provenance, "reconciliation": reconciliation,
            "warnings": (["empty input: assignment percentage is undefined"] if not total else []),
        }
        # A completion state is visible only after gzip close, QC and reconciliation.
        temporary = qc_dir / "demux_summary.json.tmp"
        temporary.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
        temporary.replace(qc_dir / "demux_summary.json")
        succeeded = True
        LOG.info("Completed %d read pairs; all count reconciliations passed", total)
        return summary
    finally:
        try:
            if writer is not None:
                writer.close()
        finally:
            if not succeeded:
                shutil.rmtree(output)
