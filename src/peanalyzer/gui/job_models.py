"""Versioned job presentation contracts; no process or filesystem capabilities."""
from typing import Literal
from pydantic import Field
from peanalyzer.gui.models import Model, ErrorDetail, FieldValue
from peanalyzer.gui.setup_models import SetupIssue, PreviewStage
from peanalyzer.workflow_models import Hash

JobState = Literal['STARTING','RUNNING','CANCELLING','CANCELLED','FAILED','COMPLETED']
StageState = Literal['PENDING','RUNNING','COMPLETED','SKIPPED_SCIENTIFIC_GATE','FAILED','CANCELLED']


class JobSubmission(Model):
    draft_id: str
    revision: int = Field(ge=0)
    plan_identity_sha256: Hash
    scientific_identity_sha256: Hash


class JobStage(PreviewStage):
    status: StageState = 'PENDING'
    reason_codes: list[str] = Field(default_factory=list)


class JobEvent(Model):
    sequence: int
    timestamp: str
    state: JobState
    status: str
    stage_id: str | None = None
    stage_kind: str | None = None
    reason_codes: list[str] = Field(default_factory=list)
    code: str | None = None


class JobEvents(Model):
    items: list[JobEvent]
    next_sequence: int
    has_more: bool


class JobView(Model):
    job_contract: Literal['analysis-job-v1'] = 'analysis-job-v1'
    job_id: str
    draft_id: str
    revision: int
    state: JobState
    analysis_name: str
    analysis_mode: Literal['precise_edit','indel_nuclease']
    target_name: str
    output_proposal: str
    plan_identity_sha256: Hash
    scientific_identity_sha256: Hash
    execution_spec_sha256: Hash
    input_metadata: list[FieldValue]
    warnings: list[SetupIssue]
    stages: list[JobStage]
    current_stage_id: str | None = None
    finished_stages: int = 0
    total_stages: int
    started_at: str
    ended_at: str | None = None
    elapsed_seconds: float = 0.0
    cancellable: bool = True
    error: ErrorDetail | None = None
    workspace_id: str | None = None
    latest_sequence: int = 0
