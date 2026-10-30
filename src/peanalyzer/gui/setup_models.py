"""Editable drafts and non-executable, backend-owned setup previews."""
from typing import Literal
from pydantic import Field, PrivateAttr
from peanalyzer.gui.models import Model, FieldValue

Step = Literal['samples', 'mode', 'target', 'configuration', 'review']


class SetupFile(Model):
    file_id: str
    label: str
    kind: Literal['fastq', 'demux', 'output_root']
    origin: Literal['launcher', 'upload'] = 'launcher'
    sha256: str | None = None
    size_bytes: str | None = None


class DraftSample(Model):
    sample_name: str = ''
    barcode_id: str = ''
    forward_barcode: str = ''
    reverse_barcode: str = ''
    editor: str = ''
    treatment: str = ''
    dpi: str = ''
    biological_replicate: str = ''
    paired: bool = False
    block_id: str = ''


class PETargetDraft(Model):
    analysis_mode: Literal['precise_edit'] = 'precise_edit'
    target_name: str = ''
    copy_name: str = ''
    wt_sequence: str = ''
    prime_edited_sequence: str = ''
    pegRNA_spacer: str = ''
    pegRNA_extension: str = ''
    nicking_guide: str = ''
    pegRNA_scaffold: str = ''


class NucleaseTargetDraft(Model):
    analysis_mode: Literal['indel_nuclease'] = 'indel_nuclease'
    target_name: str = ''
    copy_name: str = ''
    wt_sequence: str = ''
    profile: Literal['explicit', 'tigr_tas_v1'] = 'explicit'
    quantification_window_coordinates: str = ''
    tigr_target_sequence: str = ''
    tigr_window: Literal['W1', 'W2', 'W3', 'W4'] = 'W2'


class DraftContent(Model):
    analysis_name: str = ''
    input_mode: Literal['run', 'analyze'] = 'run'
    r1: str | None = None
    r2: str | None = None
    demux: str | None = None
    samples: list[DraftSample] = Field(default_factory=list)
    analysis_mode: Literal['precise_edit', 'indel_nuclease'] | None = None
    targets: list[PETargetDraft | NucleaseTargetDraft] = Field(default_factory=list)
    library_profile: Literal['qi_hitom_v1', 'custom'] = 'qi_hitom_v1'
    trim_r1: str = ''
    trim_r2: str = ''
    output_root: str | None = None
    workspace_name: str = ''


class DraftPatch(Model):
    revision: int = Field(ge=0)
    content: DraftContent


class DraftRevision(Model):
    revision: int = Field(ge=0)


class SetupIssue(Model):
    severity: Literal['ERROR', 'WARNING']
    code: str
    step: Step
    field: str
    message: str
    detail: str | None = None


class TargetPreview(Model):
    target_name: str
    copy_name: str
    wt_sequence: str
    intended_sequence: str | None
    annotation: list[FieldValue]
    scientific_configuration: list[FieldValue]
    configuration_notes: list[str] = Field(default_factory=list)


class PreviewStage(Model):
    stage_id: str
    kind: str
    label: str
    dependencies: list[str]
    output_path: str


class PlanPreview(Model):
    preview_contract: Literal['analysis-plan-preview-v1'] = 'analysis-plan-preview-v1'
    executable: Literal[False] = False
    analysis_name: str
    analysis_mode: Literal['precise_edit', 'indel_nuclease']
    source_mode: Literal['run', 'analyze']
    sample_count: str
    sample_ids: list[str]
    samples: list[FieldValue]
    inputs: list[FieldValue]
    target_name: str
    copy_count: str
    targets: list[TargetPreview]
    configuration: list[FieldValue]
    stages: list[PreviewStage]
    output_proposal: str | None
    scientific_identity_sha256: str
    plan_identity_sha256: str
    backend_identity: list[FieldValue]
    deferred: list[str]


class DraftValidation(Model):
    # Server-only compiler output; excluded from all HTTP/schema serialization.
    _compiled: dict | None = PrivateAttr(default=None)
    revision: int
    draft_digest: str
    status: Literal['VALID', 'INVALID']
    issues: list[SetupIssue]
    targets: list[TargetPreview]
    preview: PlanPreview | None


class DraftView(Model):
    draft_id: str
    revision: int
    content: DraftContent
    validation: DraftValidation | None = None


class SetupCapabilities(Model):
    contract: Literal['analysis-draft-v1'] = 'analysis-draft-v1'
    backend_base: str
    files: list[SetupFile]
    scientific_execution: Literal[False] = False
    scientific_execution_scope: Literal['setup_and_review_only'] = 'setup_and_review_only'
    recovery_available: bool = False
    statistics: Literal['descriptive_only'] = 'descriptive_only'
    run_available: bool = False


class WorkbookIssue(Model):
    row: int
    field: str
    code: str
    severity: Literal['ERROR']
    message: str


class WorkbookImport(Model):
    template_version: Literal['samples-xlsx-v1']
    samples: list[DraftSample]
    imported_count: int
    valid_count: int
    warnings: list[str]
    errors: list[WorkbookIssue]
