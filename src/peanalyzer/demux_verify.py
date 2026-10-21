"""Read-only M2.1 completion contract, including an independent disk recount."""

import csv
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from peanalyzer.fastq import FastqError, paired_fastq
from peanalyzer.schemas import BarcodeSample, Sample
from peanalyzer.validation import sample_output_names

CHECKS = frozenset((
    "terminal_categories_equal_input", "sample_counts_equal_assigned",
    "written_pairs_equal_sample_counts", "matrix_equals_recognized_pairs",
    "expected_matrix_cells_equal_samples", "expected_matrix_sum_equals_assigned",
    "mate_records_equal_sample_counts", "on_disk_matrix_matches_counts",
))
CATEGORIES = ("assigned_expected_pair", "unexpected_valid_barcode_pair", "forward_only",
              "reverse_only", "no_barcode_match", "ambiguous_barcode_match")


class DemuxVerificationError(ValueError):
    pass


def sha256_file(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def read_json(path: Path) -> dict:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON field: {key}")
            result[key] = value
        return result
    return json.loads(path.read_text(), object_pairs_hook=unique)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise DemuxVerificationError(message)


def _count(value) -> int:
    _require(type(value) is int and value >= 0, "counts/sizes must be nonnegative integers")
    return value


@dataclass(frozen=True)
class VerifiedSample:
    sample_id: str
    pairs: int
    r1: Path
    r2: Path
    r1_sha256: str
    r2_sha256: str


@dataclass(frozen=True)
class VerifiedDemuxRun:
    root: Path
    summary_sha256: str
    samples: tuple[VerifiedSample, ...]
    summary: dict


def verify_demux_output(path: Path) -> VerifiedDemuxRun:
    """Never repair a result. Checksums and one independent FASTQ parse per mate.

    Hashing compressed bytes is a separate streaming pass from decompression;
    no reads are retained in memory and no writer counters are trusted.
    """
    try:
        return _verify(Path(path))
    except DemuxVerificationError:
        raise
    except (OSError, ValueError, KeyError, IndexError, TypeError, AttributeError, FastqError) as exc:
        raise DemuxVerificationError(f"invalid completed demux output: {exc}") from exc


def _verify(path: Path) -> VerifiedDemuxRun:
    _require(not path.is_symlink(), "published run root cannot be a symlink")
    root = path.resolve(strict=True)
    _require(not any(".incomplete-" in part for part in (*path.parts, *root.parts)), "incomplete staging path is not consumable")
    summary_path = root / "01_demux_QC/demux_summary.json"
    _require(not summary_path.is_symlink(), "summary cannot be a symlink")
    before = sha256_file(summary_path)
    summary = read_json(summary_path)
    _require(type(summary["schema_version"]) is int and summary["schema_version"] == 2, "unsupported demux summary schema")
    _require(summary["status"] == "completed", "demux is not completed")
    reconciliation = summary["reconciliation"]
    _require(reconciliation["passed"] is True, "reconciliation failed")
    _require(CHECKS <= reconciliation["checks"].keys() and
             all(value is True for value in reconciliation["checks"].values()), "missing or failed reconciliation checks")
    rows = [(Sample if "editor" in row else BarcodeSample).model_validate(row) for row in summary["samples"]]
    _require(bool(rows), "missing samples")
    names = sample_output_names([row.barcode_id for row in rows])
    expected_pairs = {(row.forward_barcode_id, row.reverse_barcode_id): row.barcode_id for row in rows}
    _require(len(expected_pairs) == len(rows), "duplicate sample barcode pairs")
    counts = summary["per_sample_assigned_read_pairs"]
    _require(set(counts) == set(names), "sample identity/count mapping mismatch")
    assigned = _count(summary["assigned_expected_pair"])
    _require(sum(_count(n) for n in counts.values()) == assigned, "assigned sample sum mismatch")
    _require(sum(_count(summary[key]) for key in CATEGORIES) == _count(summary["total_input_read_pairs"]), "terminal count mismatch")
    inventory = summary["output_files"]
    expected_paths = {f"02_demultiplexed_fastq/{name}" for pair in names.values() for name in pair}
    expected_paths |= {"01_demux_QC/barcode_counts.csv", "01_demux_QC/barcode_pair_matrix.csv"}
    _require(set(inventory) == expected_paths, "authoritative file inventory mismatch")
    for relative, metadata in inventory.items():
        file = root / relative
        _require(not any(parent.is_symlink() for parent in (file, *file.parents) if parent != root.parent), "authoritative files cannot traverse symlinks")
        _require(file.is_file(), f"missing authoritative file: {relative}")
        _require(file.stat().st_size == _count(metadata["size_bytes"]), f"wrong file size: {relative}")
        _require(sha256_file(file) == metadata["sha256"], f"wrong file hash: {relative}")
    actual = {p.name for p in (root / "02_demultiplexed_fastq").iterdir()}
    _require(actual == {name for pair in names.values() for name in pair}, "extra/missing sample FASTQ")
    verified = []
    for row in rows:
        sample = row.barcode_id
        paths = [root / "02_demultiplexed_fastq" / name for name in names[sample]]
        hashes = []
        for mate, file in enumerate(paths, 1):
            metadata = inventory[file.relative_to(root).as_posix()]
            _require(metadata["sample_id"] == sample and type(metadata["mate"]) is int and metadata["mate"] == mate,
                     "filename/sample mapping mismatch")
            _require(_count(metadata["records"]) == counts[sample], "manifest mate count mismatch")
            hashes.append(metadata["sha256"])
        observed = sum(1 for _ in paired_fastq(*paths))
        _require(observed == counts[sample], f"on-disk record count mismatch: {sample}")
        verified.append(VerifiedSample(sample, observed, *paths, *hashes))
    catalog = summary["barcode_catalog"]["resolved"]
    with (root / "01_demux_QC/barcode_pair_matrix.csv").open(newline="") as handle:
        matrix_rows = list(csv.reader(handle))
    forward, reverse = [row[0] for row in matrix_rows[1:]], matrix_rows[0][1:]
    # JSON is serialized with sorted keys; CSV retains catalog insertion order.
    _require(matrix_rows[0][0] == "forward_barcode_id" and
             len(set(forward)) == len(forward) == len(catalog["forward"]) and
             len(set(reverse)) == len(reverse) == len(catalog["reverse"]) and
             set(forward) == set(catalog["forward"]) and set(reverse) == set(catalog["reverse"]), "matrix identities mismatch")
    matrix = {}
    for f, values in zip(forward, matrix_rows[1:]):
        _require(len(values) == len(reverse) + 1, "ragged matrix")
        for r, n in zip(reverse, values[1:]):
            _require(n.isdecimal(), "invalid matrix count")
            matrix[f, r] = int(n)
    _require(sum(matrix.values()) == assigned + summary["unexpected_valid_barcode_pair"], "matrix total mismatch")
    for row in rows:
        f, r = row.forward_barcode_id, row.reverse_barcode_id
        _require(catalog["forward"][f] == row.forward_barcode and catalog["reverse"][r] == row.reverse_barcode, "sample/catalog mismatch")
        _require(matrix[f, r] == counts[row.barcode_id], "expected matrix cell mismatch")
    _require(sum(matrix[pair] for pair in expected_pairs) == assigned, "expected matrix sum mismatch")
    _require(sha256_file(summary_path) == before, "summary changed during verification")
    return VerifiedDemuxRun(root, before, tuple(verified), summary)
