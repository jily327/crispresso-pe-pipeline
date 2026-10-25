"""Versioned presentation contracts. Scientific integers travel as decimal strings."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class Model(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class FieldValue(Model):
    name: str
    value: str | None


class ErrorDetail(Model):
    code: str
    message: str
    detail: str
    stage_id: str | None = None


class ErrorEnvelope(Model):
    error: ErrorDetail


class Capabilities(Model):
    api_version: Literal['viewer-v1'] = 'viewer-v1'
    package_version: str
    backend_base: str
    viewer_software: list[FieldValue]
    result_contracts: list[str]
    analysis_modes: list[str]
    screens: list[str]
    read_only: Literal[True] = True
    scientific_execution: Literal[False] = False
    native_html_viewing: Literal[False] = False
    nuclease_alleles: Literal[True] = True
    pe_alleles: Literal[False] = False


class Registration(Model):
    registration_id: str
    label: str


class OpenRequest(Model):
    registration_id: str


class Source(Model):
    artifact_id: str
    name: str
    sha256: str
    size_bytes: str
    kind: str
    downloadable: bool


class Value(Model):
    numerator: str | None
    denominator: str | None
    fraction: float | None
    percentage: str | None


class Observation(Value):
    observation_id: str
    series_id: str
    sample_id: str
    sample_name: str
    editor: str
    treatment: str
    dpi: str
    biological_replicate: str
    block_id: str | None
    paired: bool
    target: str
    copy_name: str | None
    policy_id: str | None
    policy: list[FieldValue]
    metric_name: str
    label: str
    population_id: str
    population_scope: str
    routing_conditioned: bool
    status: Literal['REPORTABLE', 'BLOCKED', 'NOT_ASSESSABLE']
    reasons: list[str]
    assessment_stage: str
    backend_counts_role: str
    denominator_label: str
    source: Source
    evidence: list[FieldValue]


class Group(Model):
    series_id: str
    metric_name: str
    label: str
    condition: str
    expected_n: str
    reportable_n: str
    mean: float | None
    mean_percentage: str | None
    minimum: float | None
    maximum: float | None
    median: float | None
    points: list[FieldValue]
    availability: list[FieldValue]
    source: Source


class Contrast(Model):
    contrast_id: str
    series_id: str
    metric_name: str
    group_a: str
    group_b: str
    effect: float | None
    p: float | None
    q: float | None
    expected_a: str
    expected_b: str
    used_a: str
    used_b: str
    family: str
    pairing_mode: str
    blocks: list[str]
    exclusions: list[FieldValue]
    status: str
    reasons: list[str]
    source: Source


class Population(Model):
    sample_id: str | None
    name: str
    role: str
    counts: list[FieldValue]
    source: Source


class Bin(Value):
    net_size: str


class ClassValue(Value):
    name: str


class NucleaseDetail(Model):
    sample_id: str
    target: str
    status: str
    window: list[FieldValue]
    classes: list[ClassValue]
    overlapping: list[ClassValue]
    bins: list[Bin]
    allele_count: str
    expected_configuration: list[FieldValue]
    resolved_configuration: list[FieldValue]
    source: Source


class Allele(Model):
    row_id: str
    reads: str
    product_class: str
    inserted_bp: str
    deleted_bp: str
    mutated_bp: str
    net_delta: str
    aligned_sequence: str
    reference_sequence: str
    original_percentage: str


class AllelePage(Model):
    items: list[Allele]
    offset: int
    limit: int
    total: str
    source: Source


class Stage(Model):
    stage_id: str
    label: str
    status: str
    history: Literal['executed', 'reused']
    signature: str
    started_at: str
    ended_at: str


class WorkspaceView(Model):
    api_version: Literal['viewer-v1'] = 'viewer-v1'
    workspace_id: str
    label: str
    verified: Literal[True] = True
    snapshot_id: str
    mode: Literal['precise_edit', 'indel_nuclease']
    targets: list[str]
    contracts: list[str]
    observations: list[Observation]
    groups: list[Group]
    contrasts: list[Contrast]
    populations: list[Population]
    nuclease: list[NucleaseDetail]
    provenance: list[FieldValue]
    stages: list[Stage]
    artifacts: list[Source]
    native_html: Literal['Available for download only', 'Not produced']


class ObservationPage(Model):
    items: list[Observation]
    offset: int
    limit: int
    total: str
