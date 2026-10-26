"""Read metadata without silently repairing malformed files or running CRISPResso."""

import csv
import itertools
import re
from pathlib import Path
from typing import TypeVar

import yaml
from pydantic import ValidationError

from peanalyzer.nuclease.targets import NucleaseTarget
from peanalyzer.schemas import BarcodeSample, Config, Model, Sample, Target, reverse_complement

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
    "nuclease_profile", "tigr_target_sequence", "tigr_window",
    "block_id", "nicking_guide", "pegRNA_scaffold", "quantification_window_coordinates",
    "quantification_window_size", "quantification_window_center",
    "prime_editing_pegRNA_scaffold_min_match_length",
    "forward_barcode_id", "reverse_barcode_id",
    "forward_barcode", "reverse_barcode",
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


def load_samples(path: Path, catalog=None, *, metadata_required: bool = True) -> list[BarcodeSample]:
    # Demux accepts a minimal routing sheet; validate retains full M1 metadata.
    # Sequence/ID presence is a per-row rule, not a required header spelling.
    required = tuple(c for c in SAMPLE_COLUMNS if c not in {"forward_barcode", "reverse_barcode"})
    model = Sample if metadata_required else BarcodeSample
    if not metadata_required:
        # Also accept full M1 sheets for demux, without inventing biological data.
        try:
            with path.open(encoding="utf-8-sig", newline="") as handle:
                headers = next(csv.reader(handle), [])
        except (OSError, UnicodeError, csv.Error) as exc:
            raise MetadataError(f"{path}: {exc}") from exc
        if set(headers) & (set(SAMPLE_COLUMNS) - set(BarcodeSample.model_fields)):
            model = Sample
        else:
            required = ("sample_name", "barcode_id")
    rows = _load_csv(path, model, required)
    if catalog is not None:
        rows = [catalog.resolve_sample(row) for row in rows]
    elif any(row.forward_barcode_id or row.reverse_barcode_id for row in rows):
        raise MetadataError(f"{path}: barcode IDs require a catalog (--barcodes)")
    for field in ("sample_name", "barcode_id"):
        values = [getattr(row, field) for row in rows]
        if len(set(values)) != len(values):
            raise MetadataError(f"{path}: duplicate {field}")
    sample_output_names([row.barcode_id for row in rows])
    pairs = [(row.forward_barcode, row.reverse_barcode) for row in rows]
    if len(set(pairs)) != len(pairs):
        raise MetadataError(f"{path}: duplicate forward/reverse barcode pair")
    return rows


def sample_output_names(sample_ids: list[str]) -> dict[str, tuple[str, str]]:
    """Identifiers are never sanitized; check actual filenames after casefolding."""
    names, seen = {}, set()
    for sample in sample_ids:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", sample):
            raise MetadataError(f"invalid output identifier {sample!r}; use a safe identifier, not a name requiring sanitization")
        filenames = tuple(f"{sample}_R{mate}.fastq.gz" for mate in (1, 2))
        for filename in filenames:
            key = filename.casefold()
            if key in seen:
                raise MetadataError(f"case-insensitive output filename collision: {filename}")
            seen.add(key)
        names[sample] = filenames
    return names


def load_targets(path: Path) -> list[Target]:
    # Dispatch at the CSV compatibility boundary; PE requirements remain exact.
    with path.open(newline="", encoding="utf-8-sig") as handle:
        records=list(csv.DictReader(handle))
    modes={r.get('analysis_mode','precise_edit') for r in records}
    if modes == {'indel_nuclease'}:
        rows = _load_csv(path, NucleaseTarget, ('analysis_mode','target_name','copy_name','wt_sequence'))
    elif modes <= {'precise_edit'}:
        rows = _load_csv(path, Target, TARGET_COLUMNS)
    else:
        raise MetadataError('MIXED_OR_UNKNOWN_ANALYSIS_MODE: use one scientific mode per target file')
    ids = [row.amplicon_id for row in rows]
    if len(set(ids)) != len(ids):
        raise MetadataError(f"{path}: duplicate target_name/copy_name")
    seen = set()
    for row in rows:
        seq = row.wt_sequence
        if seq in seen or reverse_complement(seq) in seen:
            raise MetadataError(f"{path}: duplicate or reverse-complement WT amplicon at {row.amplicon_id}")
        # v2.3.4 also rejects a self reverse-complementing reference.
        if row.analysis_mode == "precise_edit" and seq == reverse_complement(seq):
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
        if row.analysis_mode == "indel_nuclease":
            if sum(t.target_name == row.target_name for t in targets)>1:
                warnings.append("MULTICOPY_NUCLEASE_UNSUPPORTED: backend execution is blocked")
            continue
        if row.pegRNA_spacer not in row.wt_sequence:
            warnings.append(f"{row.amplicon_id}: spacer is not an exact forward WT substring; confirm strand/homeolog mismatches")
        if reverse_complement(row.pegRNA_extension) not in row.prime_edited_sequence:
            warnings.append(f"{row.amplicon_id}: reverse-complement extension is absent from intended PE; backend orientation/extension checks may fail")
    for left, right in itertools.combinations(targets, 2):
        if left.analysis_mode != "precise_edit" or right.analysis_mode != "precise_edit": continue
        a = {left.wt_sequence, left.prime_edited_sequence}
        b = {right.wt_sequence, right.prime_edited_sequence}
        if a & (b | {reverse_complement(seq) for seq in b}):
            warnings.append(f"reference collision across copies/targets: {left.amplicon_id}, {right.amplicon_id}")
    if len(targets) > 1 and all(t.analysis_mode == "precise_edit" for t in targets):
        warnings.append("multiple amplicons require validated copy routing; default Pooled routing does not guarantee unambiguous assignment")
    if config.statistics.mode != "none":
        column = config.statistics.block_column
        if any(row.paired for row in samples) and column != "block_id":
            raise MetadataError("paired metadata requires statistics.block_column: block_id for active statistics")
        if column and any(getattr(row, column) is None for row in samples):
            raise MetadataError(f"statistics requires a nonempty {column} for every sample")
        warnings.append("statistical design power, complete blocks and contrasts are not validated in Milestone 1")
    return warnings


def validate_metadata(samples_path: Path, targets_path: Path, config_path: Path, barcodes_path: Path | None = None) -> dict:
    config = load_config(config_path)
    from peanalyzer.barcodes import load_catalog
    samples = load_samples(samples_path, load_catalog(barcodes_path) if barcodes_path else None)
    targets = load_targets(targets_path)
    return {
        "schema_version": 1,
        "status": "valid_metadata",
        "sample_count": len(samples),
        "target_count": len({row.target_name for row in targets}),
        "copy_count": len(targets),
        "warnings": metadata_warnings(samples, targets, config),
        "resolved_config": config.model_dump(mode="json"),
        "analysis_modes": sorted({t.analysis_mode for t in targets}),
        "resolved_targets": [t.scientific_identity if t.analysis_mode == "indel_nuclease" else dict(analysis_mode="precise_edit", **t.model_dump(mode="json")) for t in targets],
        "nuclease_execution_supported": all(sum(t.target_name == r.target_name for t in targets)==1 for r in targets if r.analysis_mode=="indel_nuclease"),
        "scope": "metadata only; FASTQ, CRISPResso execution and biological validity are not checked",
    }
