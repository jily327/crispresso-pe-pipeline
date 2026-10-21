"""Authoritative, versioned metadata models. No analysis runs on model creation."""

import re
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Identifier = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")]
NonnegativeInt = Annotated[int, Field(ge=0)]
PositiveInt = Annotated[int, Field(gt=0)]
Fraction = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
Nonempty = Annotated[str, Field(min_length=1)]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)


def sequence(value: str, *, rna: bool = False) -> str:
    """Normalize case and RNA U; reject gaps, ambiguity codes and internal spaces."""
    value = value.strip().upper()
    if rna:
        value = value.replace("U", "T")
    if not re.fullmatch(r"[ACGT]+", value):
        raise ValueError("sequence must contain only A/C/G/T" + (" (U accepted for RNA)" if rna else ""))
    return value


def reverse_complement(value: str) -> str:
    return value.translate(str.maketrans("ACGT", "TGCA"))[::-1]


class BarcodeSample(Model):
    sample_name: Identifier
    barcode_id: Identifier
    forward_barcode: str | None = None
    reverse_barcode: str | None = None
    forward_barcode_id: Identifier | None = None
    reverse_barcode_id: Identifier | None = None

    @field_validator("forward_barcode", "reverse_barcode")
    @classmethod
    def validate_dna(cls, value: str | None) -> str | None:
        return None if value is None else sequence(value)

    @model_validator(mode="after")
    def check_definitions(self) -> Self:
        for direction in ("forward", "reverse"):
            if getattr(self, f"{direction}_barcode") is None and getattr(self, f"{direction}_barcode_id") is None:
                raise ValueError(f"{direction} barcode sequence or catalog ID is required")
        return self


class Sample(BarcodeSample):
    editor: Nonempty
    treatment: Nonempty
    dpi: NonnegativeInt
    biological_replicate: Identifier
    block_id: Identifier | None = None
    paired: bool

    @model_validator(mode="after")
    def check_block(self) -> Self:
        if self.paired and self.block_id is None:
            raise ValueError("paired samples require block_id")
        return self


class Target(Model):
    target_name: Identifier
    copy_name: Identifier
    wt_sequence: str
    prime_edited_sequence: str
    pegRNA_spacer: str
    pegRNA_extension: str
    nicking_guide: str | None = None
    pegRNA_scaffold: str | None = None
    quantification_window_coordinates: str | None = None
    quantification_window_size: NonnegativeInt | None = None
    quantification_window_center: int | None = None
    prime_editing_pegRNA_scaffold_min_match_length: PositiveInt | None = None

    @field_validator("target_name", "copy_name")
    @classmethod
    def reserve_separator(cls, value: str) -> str:
        if "__" in value:
            raise ValueError("double underscore is reserved for generated amplicon IDs")
        return value

    @field_validator("wt_sequence", "prime_edited_sequence")
    @classmethod
    def validate_dna(cls, value: str) -> str:
        return sequence(value)

    @field_validator("pegRNA_spacer", "pegRNA_extension", "nicking_guide", "pegRNA_scaffold")
    @classmethod
    def validate_rna(cls, value: str | None) -> str | None:
        return None if value is None else sequence(value, rna=True)

    @model_validator(mode="after")
    def check_references(self) -> Self:
        if self.wt_sequence == self.prime_edited_sequence:
            raise ValueError("WT and intended prime-edited reference must differ")
        if self.prime_editing_pegRNA_scaffold_min_match_length is not None:
            if self.pegRNA_scaffold is None:
                raise ValueError("scaffold minimum match length requires pegRNA_scaffold")
            if self.prime_editing_pegRNA_scaffold_min_match_length > len(self.pegRNA_scaffold):
                raise ValueError("scaffold minimum match length exceeds scaffold length")
        coordinates = self.quantification_window_coordinates
        if coordinates is not None and coordinates != "0":
            if not re.fullmatch(r"\d+-\d+(?:_\d+-\d+)*", coordinates):
                raise ValueError("window coordinates must be 0 or inclusive start-end ranges joined by _")
            previous_end = -1
            for interval in coordinates.split("_"):
                start, end = map(int, interval.split("-"))
                if start > end or start <= previous_end or end >= len(self.wt_sequence):
                    raise ValueError("window ranges must be ordered, disjoint and within the WT reference")
                previous_end = end
        return self

    @property
    def amplicon_id(self) -> str:
        return f"{self.target_name}__{self.copy_name}"


class DemuxConfig(Model):
    profile: Literal["qi_hitom_v1", "custom"] = "qi_hitom_v1"
    forward_offset: NonnegativeInt = 0
    reverse_offset: NonnegativeInt = 0
    forward_length: PositiveInt | None = None
    reverse_length: PositiveInt | None = None
    forward_bridge: str | None = None
    reverse_bridge: str | None = None
    reverse_barcode_orientation: Literal["as_read", "reverse_complement"] = "as_read"
    max_mismatches: NonnegativeInt = 0
    trim_barcodes: bool = False
    trim_bridges: bool = False
    bridge_qc: bool = True
    max_open_sample_pairs: PositiveInt = 32
    ambiguous_policy: Literal["unassigned"] = "unassigned"

    @field_validator("forward_bridge", "reverse_bridge")
    @classmethod
    def check_bridge(cls, value: str | None) -> str | None:
        return None if value is None else sequence(value)

    @model_validator(mode="after")
    def check_trimming(self) -> Self:
        if self.trim_bridges and not self.trim_barcodes:
            raise ValueError("trim_bridges requires trim_barcodes")
        return self


class CrispressoConfig(Model):
    pooled_executable: Nonempty = "CRISPRessoPooled"
    core_executable: Nonempty = "CRISPResso"
    version: Literal["2.3.4"] = "2.3.4"
    min_reads_to_use_region: NonnegativeInt = 100
    copy_assignment_policy: Literal["require_validated"] = "require_validated"


class QuantificationConfig(Model):
    primary_metric: Literal["precise_full_amplicon", "pe_reference_assigned"] = "precise_full_amplicon"
    denominator: Literal["nonambiguous_nondiscarded_aligned"] = "nonambiguous_nondiscarded_aligned"


class QCConfig(Model):
    min_analyzable_reads: PositiveInt = 100
    min_copy_fraction: Fraction = 0.1
    max_ambiguous_fraction: Fraction = 0.1
    discriminating_variant_edit_distance: NonnegativeInt = 5


class StatisticsConfig(Model):
    mode: Literal["none", "simple", "factorial"] = "none"
    factors: list[Literal["editor", "treatment", "dpi"]] = Field(default_factory=list)
    block_column: Literal["block_id", "biological_replicate"] | None = None
    include_interaction: bool = False
    min_biological_replicates: Annotated[int, Field(ge=2)] = 3

    @model_validator(mode="after")
    def check_design(self) -> Self:
        if len(set(self.factors)) != len(self.factors):
            raise ValueError("statistical factors must be unique")
        if self.mode != "none" and not self.factors:
            raise ValueError("active statistical mode requires factors")
        if self.include_interaction and (self.mode != "factorial" or len(self.factors) < 2):
            raise ValueError("interaction requires factorial mode with at least two factors")
        if self.mode == "none" and (self.factors or self.block_column is not None):
            raise ValueError("mode none cannot specify factors or a block column")
        return self


class Config(Model):
    schema_version: Literal[1]
    n_processes: PositiveInt = 1
    demux: DemuxConfig = Field(default_factory=DemuxConfig)
    crispresso: CrispressoConfig = Field(default_factory=CrispressoConfig)
    quantification: QuantificationConfig = Field(default_factory=QuantificationConfig)
    qc: QCConfig = Field(default_factory=QCConfig)
    statistics: StatisticsConfig = Field(default_factory=StatisticsConfig)

    @field_validator("schema_version", mode="before")
    @classmethod
    def check_version_type(cls, value: object) -> object:
        if type(value) is not int:
            raise ValueError("schema_version must be the integer 1")
        return value
