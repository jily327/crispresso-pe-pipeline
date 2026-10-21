"""Read metadata without silently repairing malformed files or running CRISPResso."""

import csv
import itertools
import re
from pathlib import Path
from typing import TypeVar

import yaml
from pydantic import ValidationError

from peanalyzer.schemas import Config, Model, Sample, Target, reverse_complement

SAMPLE_COLUMNS = (
    "sample_name", "barcode_id", "forward_barcode", "reverse_barcode", "editor",
    "treatment", "dpi", "biological_replicate", "block_id", "paired",
)
TARGET_COLUMNS = (
    "target_name", "copy_name", "wt_sequence", "prime_edited_sequence",
    "pegRNA_spacer", "pegRNA_extension", "nicking_guide", "pegRNA_scaffold",
)
INTEGER_COLUMNS = {
    "dpi", "quantification_window_size", "quantification_window_center",
    "prime_editing_pegRNA_scaffold_min_match_length",
}
NULLABLE_COLUMNS = {
    "block_id", "nicking_guide", "pegRNA_scaffold", "quantification_window_coordinates",
    "quantification_window_size", "quantification_window_center",
    "prime_editing_pegRNA_scaffold_min_match_length",
}
Row = TypeVar("Row", bound=Model)


class MetadataError(ValueError):
    """Invalid metadata, with a filename and row where available."""


class UniqueKeyLoader(yaml.SafeLoader):
    """Safe YAML with duplicate keys rejected rather than silently overwritten."""

    def construct_mapping(self, node, deep=False):
        self.flatten_mapping(node)
        mapping = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if not isinstance(key, str):
                raise MetadataError("YAML mapping keys must be strings")
            if key in mapping:
                raise MetadataError(f"duplicate YAML key: {key}")
            mapping[key] = self.construct_object(value_node, deep=deep)
        return mapping


def load_config(path: Path) -> Config:
    try:
        with path.open(encoding="utf-8-sig") as handle:
            data = yaml.load(handle, Loader=UniqueKeyLoader)
        return Config.model_validate(data)
    except (OSError, UnicodeError, yaml.YAMLError, ValidationError, MetadataError) as exc:
        raise MetadataError(f"{path}: {exc}") from exc


def _csv_value(column: str, value: str) -> object:
    value = value.strip()
    if not value and column in NULLABLE_COLUMNS:
        return None
    if column in INTEGER_COLUMNS:
        if not re.fullmatch(r"-?\d+", value):
            raise MetadataError(f"{column} must be an integer")
        return int(value)
    if column == "paired":
        if value.lower() not in {"true", "false"}:
            raise MetadataError("paired must be true or false")
        return value.lower() == "true"
    return value


def _load_csv(path: Path, model: type[Row], required: tuple[str, ...]) -> list[Row]:
    rows = []
    try:
        with path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.reader(handle, strict=True)
            header = next(reader, [])
            if len(set(header)) != len(header):
                raise MetadataError("duplicate CSV column names")
            missing = set(required) - set(header)
            unknown = set(header) - set(model.model_fields)
            if missing or unknown:
                raise MetadataError(f"missing columns: {sorted(missing)}; unknown columns: {sorted(unknown)}")
            for values in reader:
                if len(values) != len(header):
                    raise MetadataError(f"row {reader.line_num}: expected {len(header)} cells, got {len(values)}")
                try:
                    row = {key: _csv_value(key, value) for key, value in zip(header, values)}
                    rows.append(model.model_validate(row))
                except (ValidationError, MetadataError) as exc:
                    raise MetadataError(f"row {reader.line_num}: {exc}") from exc
        if not rows:
            raise MetadataError("at least one data row is required")
    except (OSError, UnicodeError, csv.Error, MetadataError) as exc:
        raise MetadataError(f"{path}: {exc}") from exc
    return rows


def load_samples(path: Path) -> list[Sample]:
    rows = _load_csv(path, Sample, SAMPLE_COLUMNS)
    for field in ("sample_name", "barcode_id"):
        values = [getattr(row, field) for row in rows]
        if len(set(values)) != len(values):
            raise MetadataError(f"{path}: duplicate {field}")
    pairs = [(row.forward_barcode, row.reverse_barcode) for row in rows]
    if len(set(pairs)) != len(pairs):
        raise MetadataError(f"{path}: duplicate forward/reverse barcode pair")
    return rows


def load_targets(path: Path) -> list[Target]:
    rows = _load_csv(path, Target, TARGET_COLUMNS)
    ids = [row.amplicon_id for row in rows]
    if len(set(ids)) != len(ids):
        raise MetadataError(f"{path}: duplicate target_name/copy_name")
    seen = set()
    for row in rows:
        seq = row.wt_sequence
        if seq in seen or reverse_complement(seq) in seen:
            raise MetadataError(f"{path}: duplicate or reverse-complement WT amplicon at {row.amplicon_id}")
        # v2.3.4 also rejects a self reverse-complementing reference.
        if seq == reverse_complement(seq):
            raise MetadataError(f"{path}: palindromic WT unsupported by CRISPRessoPooled 2.3.4: {row.amplicon_id}")
        seen.add(seq)
    return rows


def metadata_warnings(samples: list[Sample], targets: list[Target], config: Config) -> list[str]:
    """Conservative metadata diagnostics; these do not certify biological validity."""
    warnings = []
    for left, right in itertools.combinations(samples, 2):
        # A shorter barcode can match a prefix of a longer one. Runtime ties must
        # be quarantined even if both allowed mismatch balls overlap only partly.
        overlaps = []
        for field in ("forward_barcode", "reverse_barcode"):
            a, b = getattr(left, field), getattr(right, field)
            if field == "reverse_barcode" and config.demux.reverse_barcode_orientation == "reverse_complement":
                a, b = reverse_complement(a), reverse_complement(b)
            overlaps.append(sum(x != y for x, y in zip(a, b)) <= 2 * config.demux.max_mismatches)
        if all(overlaps):
            warnings.append(f"barcode matching may be ambiguous: {left.sample_name}, {right.sample_name}")
    for row in targets:
        if row.pegRNA_spacer not in row.wt_sequence:
            warnings.append(f"{row.amplicon_id}: spacer is not an exact forward WT substring; confirm strand/homeolog mismatches")
        if reverse_complement(row.pegRNA_extension) not in row.prime_edited_sequence:
            warnings.append(f"{row.amplicon_id}: reverse-complement extension is absent from intended PE; backend orientation/extension checks may fail")
    for left, right in itertools.combinations(targets, 2):
        a = {left.wt_sequence, left.prime_edited_sequence}
        b = {right.wt_sequence, right.prime_edited_sequence}
        if a & (b | {reverse_complement(seq) for seq in b}):
            warnings.append(f"reference collision across copies/targets: {left.amplicon_id}, {right.amplicon_id}")
    if len(targets) > 1:
        warnings.append("multiple amplicons require validated copy routing; default Pooled routing does not guarantee unambiguous assignment")
    if config.statistics.mode != "none":
        column = config.statistics.block_column
        if any(row.paired for row in samples) and column != "block_id":
            raise MetadataError("paired metadata requires statistics.block_column: block_id for active statistics")
        if column and any(getattr(row, column) is None for row in samples):
            raise MetadataError(f"statistics requires a nonempty {column} for every sample")
        warnings.append("statistical design power, complete blocks and contrasts are not validated in Milestone 1")
    return warnings


def validate_metadata(samples_path: Path, targets_path: Path, config_path: Path) -> dict:
    config = load_config(config_path)
    samples = load_samples(samples_path)
    targets = load_targets(targets_path)
    return {
        "schema_version": 1,
        "status": "valid_metadata",
        "sample_count": len(samples),
        "target_count": len({row.target_name for row in targets}),
        "copy_count": len(targets),
        "warnings": metadata_warnings(samples, targets, config),
        "resolved_config": config.model_dump(mode="json"),
        "scope": "metadata only; FASTQ, CRISPResso execution and biological validity are not checked",
    }
