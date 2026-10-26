"""Strict recovery presentation and confirmation contracts; no path authority."""
from typing import Literal
from pydantic import Field, field_validator
from peanalyzer.gui.models import Model, ErrorDetail, FieldValue
from peanalyzer.workflow_models import Hash

class RecoverySelection(Model):
    revision: int = Field(ge=0)
    force: list[str] = Field(default_factory=list)

class RecoveryRequest(Model):
    revision: int = Field(ge=0)
    recovery_plan_sha256: Hash
    confirmed: Literal[True]

    @field_validator('confirmed', mode='before')
    @classmethod
    def explicit_confirmation(cls, value):
        if value is not True:raise ValueError('Explicit boolean confirmation is required')
        return value

class RecoveryOpen(Model):
    registration_id: str

class RecoveryStage(Model):
    stage_id: str
    stage_kind: str
    action: Literal['REUSE','RUN','RERUN','BLOCKED']
    output_path: str
    reason_codes: list[str]

class RecoveryView(Model):
    recovery_contract: Literal['analysis-recovery-v1']='analysis-recovery-v1'
    recovery_id: str
    revision: int
    workspace_label: str
    classification: Literal['COMPLETED','RESUMABLE','RESUMABLE_WITH_FORCE','STALE_INPUT','SOFTWARE_CHANGED','TAMPERED','ACTIVE','UNSUPPORTED','INVALID_WORKSPACE']
    recovery_plan_sha256: Hash | None = None
    scientific_identity_sha256: Hash | None = None
    workflow_identity_sha256: Hash | None = None
    analysis_mode: str | None = None
    force_families: list[str]
    selected_force: list[str]
    closure: list[str] = Field(default_factory=list)
    removal_paths: list[str] = Field(default_factory=list)
    stages: list[RecoveryStage] = Field(default_factory=list)
    reasons: list[ErrorDetail] = Field(default_factory=list)
    software: list[FieldValue] = Field(default_factory=list)
    backend: list[FieldValue] = Field(default_factory=list)
    executable: bool = False
