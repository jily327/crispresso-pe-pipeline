"""Catalog resolution and independent end identification, without sample rescue."""

from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Literal

import yaml
from pydantic import field_validator

from peanalyzer.schemas import BarcodeSample, DemuxConfig, Identifier, Model, NonnegativeInt, PositiveInt, reverse_complement, sequence
from peanalyzer.validation import MetadataError, UniqueKeyLoader, _load_csv


def bundled_catalog() -> Path:
    return Path(str(files("peanalyzer").joinpath("barcode_sets/qi_hitom_v1.csv")))


class Barcode(Model):
    direction: Literal["forward", "reverse"]
    barcode_id: Identifier
    sequence: str

    @field_validator("sequence")
    @classmethod
    def check_sequence(cls, value: str) -> str:
        return sequence(value)


class Catalog:
    def __init__(self, entries: list[Barcode]):
        self.ends: dict[str, dict[str, str]] = {"forward": {}, "reverse": {}}
        self.ids: set[str] = set()
        for entry in entries:
            self.add(entry)

    def add(self, entry: Barcode) -> None:
        end = self.ends[entry.direction]
        if entry.barcode_id in self.ids or entry.sequence in end.values():
            raise MetadataError(f"duplicate catalog ID or {entry.direction} sequence: {entry.barcode_id}")
        end[entry.barcode_id] = entry.sequence
        self.ids.add(entry.barcode_id)

    def resolve_sample(self, sample: BarcodeSample) -> BarcodeSample:
        data = sample.model_dump()
        for direction in self.ends:
            seq_key, id_key = f"{direction}_barcode", f"{direction}_barcode_id"
            seq, barcode_id = data[seq_key], data[id_key]
            end = self.ends[direction]
            if barcode_id is not None:
                if barcode_id not in end:
                    raise MetadataError(f"{sample.sample_name}: unknown {direction} barcode ID {barcode_id}")
                if seq is not None and seq != end[barcode_id]:
                    raise MetadataError(f"{sample.sample_name}: conflicting sequence for {barcode_id}")
                seq = end[barcode_id]
            else:
                barcode_id = next((key for key, value in end.items() if value == seq), None)
                if barcode_id is None:
                    barcode_id = f"{direction}_{seq}"
                    self.add(Barcode(direction=direction, barcode_id=barcode_id, sequence=seq))
            data[seq_key], data[id_key] = seq, barcode_id
        return type(sample).model_validate(data)


def load_catalog(path: Path) -> Catalog:
    entries = _load_csv(path, Barcode, ("direction", "barcode_id", "sequence"))
    catalog = Catalog(entries)
    if not all(catalog.ends.values()):
        raise MetadataError(f"{path}: catalog requires both forward and reverse barcodes")
    return catalog


class ExtractionRule(Model):
    start: NonnegativeInt = 0
    length: PositiveInt | None = None
    expected_prefix: str | None = None
    expected_suffix: str | None = None
    bridge: str | None = None


def extraction_rules(config: DemuxConfig, catalog: Catalog) -> dict[str, ExtractionRule]:
    data = {"forward": {}, "reverse": {}}
    if config.profile != "custom":
        resource = files("peanalyzer").joinpath(f"profiles/{config.profile}.yaml")
        data = yaml.load(resource.read_text(), Loader=UniqueKeyLoader)
    rules = {}
    for direction, values in data.items():
        values = dict(values)
        for setting, key in (("offset", "start"), ("length", "length"), ("bridge", "bridge")):
            field = f"{direction}_{setting}"
            if field in config.model_fields_set:
                values[key] = getattr(config, field)
        rule = ExtractionRule.model_validate(values)
        if rule.length and any(len(seq) != rule.length for seq in catalog.ends[direction].values()):
            raise MetadataError(f"{direction} catalog lengths disagree with extraction length {rule.length}; use a custom profile")
        if config.trim_bridges and not rule.bridge:
            raise MetadataError(f"trim_bridges requires a configured {direction} bridge")
        rules[direction] = rule
    return rules


def extract_barcode(read: bytes, rule: ExtractionRule, length: int) -> str:
    """Extract only at the specified offset; a short read cannot become a match."""
    return read[rule.start:rule.start + length].decode("ascii").upper()


@dataclass(frozen=True)
class BarcodeMatch:
    status: Literal["recognized", "ambiguous", "unknown"]
    barcode_id: str | None = None
    distance: int | None = None
    length: int | None = None
    candidates: tuple[str, ...] = ()


def identify_barcode(observed: dict[int, str], catalog: dict[str, str], max_mismatches: int) -> BarcodeMatch:
    """Unique nearest equal-length motif within tolerance; ties never use samples."""
    best = []
    best_distance = max_mismatches + 1
    for barcode_id, seq in catalog.items():
        motif = observed.get(len(seq), "")
        if len(motif) != len(seq) or set(motif) - set("ACGT"):
            continue
        distance = sum(a != b for a, b in zip(motif, seq))
        if distance < best_distance:
            best, best_distance = [(barcode_id, len(seq))], distance
        elif distance == best_distance:
            best.append((barcode_id, len(seq)))
    if not best or best_distance > max_mismatches:
        return BarcodeMatch("unknown")
    candidates = tuple(sorted(barcode_id for barcode_id, _ in best))
    if len(best) > 1:
        return BarcodeMatch("ambiguous", distance=best_distance, candidates=candidates)
    return BarcodeMatch("recognized", best[0][0], best_distance, best[0][1], candidates)


def identify_read(read: bytes, rule: ExtractionRule, catalog: dict[str, str], max_mismatches: int, *, reverse: bool = False) -> BarcodeMatch:
    observed = {length: extract_barcode(read, rule, length) for length in {len(seq) for seq in catalog.values()}}
    if reverse:
        observed = {length: reverse_complement(seq) for length, seq in observed.items()}
    return identify_barcode(observed, catalog, max_mismatches)


def assign_barcode_pair(forward: BarcodeMatch, reverse: BarcodeMatch, expected: dict[tuple[str, str], str]) -> tuple[str, str | None]:
    if "ambiguous" in (forward.status, reverse.status):
        return "ambiguous_barcode_match", None
    if forward.status == reverse.status == "recognized":
        sample = expected.get((forward.barcode_id, reverse.barcode_id))
        return ("assigned_expected_pair", sample) if sample else ("unexpected_valid_barcode_pair", None)
    if forward.status == "recognized":
        return "forward_only", None
    if reverse.status == "recognized":
        return "reverse_only", None
    return "no_barcode_match", None
