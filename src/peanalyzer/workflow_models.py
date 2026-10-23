"""Strict, non-scientific M7 workspace and completion contracts."""
from datetime import datetime, timedelta
from pathlib import PurePosixPath
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator, model_validator
from peanalyzer.schemas import Identifier, Target

Hash = Annotated[str, Field(pattern=r'^[0-9a-f]{64}$')]
RelativePath = Annotated[str, Field(pattern=r'^[A-Za-z0-9_][A-Za-z0-9_.-]*(/[A-Za-z0-9_][A-Za-z0-9_.-]*)*$')]
Kind = Literal['raw_inputs', 'external_demux', 'demux', 'analysis', 'routing', 'metrics', 'metrics_manifest', 'statistics', 'report']
Status = Literal['COMPLETED', 'SKIPPED_SCIENTIFIC_GATE']


class Model(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    @field_validator('started_at', 'ended_at', check_fields=False)
    @classmethod
    def utc_timestamp(cls, value):
        if datetime.fromisoformat(value).utcoffset() != timedelta(0):
            raise ValueError('timestamp must be timezone-aware UTC')
        return value

    @field_validator('schema_version', mode='before', check_fields=False)
    @classmethod
    def integer_version(cls, value):
        if type(value) is not int:
            raise ValueError('schema_version must be an integer')
        return value


class Artifact(Model):
    path: RelativePath
    sha256: Hash
    size_bytes: Annotated[int, Field(ge=0)]


class InputArtifact(Model):
    source_path: str
    sha256: Hash
    size_bytes: Annotated[int, Field(ge=0)]
    snapshot: RelativePath | None = None


class Software(Model):
    pipeline_version: str
    git_commit: str | None
    git_dirty: bool | None
    python_version: str
    dependencies: dict[str, str | None]
    package_code_sha256: Hash


class Backend(Model):
    executable: str
    executable_sha256: Hash
    version: Literal['2.3.4']
    runtime_digest: Annotated[str, Field(min_length=1)]


class Node(Model):
    stage_id: str
    stage_kind: Kind
    dependencies: list[str]
    output_path: RelativePath
    sample_id: Identifier | None = None
    target_name: Identifier | None = None


def dag(mode, samples, targets):
    """The supported fixed DAG; no implicit scheduling or biological decisions."""
    source = 'raw_inputs' if mode == 'run' else 'external_demux'
    nodes = [Node(stage_id=source, stage_kind=source, dependencies=[], output_path=f'workflow/sources/{source}.json')]
    if mode == 'run':
        nodes.append(Node(stage_id='demux', stage_kind='demux', dependencies=[source], output_path='demux'))
    nodes.append(Node(stage_id='analysis', stage_kind='analysis', dependencies=['demux' if mode == 'run' else source], output_path='analysis'))
    for kind in ('routing', 'metrics'):
        for sample in samples:
            for target in targets:
                nodes.append(Node(stage_id=f'{kind}::{sample}::{target}', stage_kind=kind,
                    dependencies=['analysis'] if kind == 'routing' else ['analysis', f'routing::{sample}::{target}'],
                    output_path=f'{kind}/{sample}/{target}', sample_id=sample, target_name=target))
    nodes.extend([
        Node(stage_id='metrics_manifest', stage_kind='metrics_manifest',
             dependencies=[n.stage_id for n in nodes if n.stage_kind == 'metrics'], output_path='metrics/manifest.csv'),
        Node(stage_id='statistics', stage_kind='statistics', dependencies=['metrics_manifest'], output_path='statistics'),
        Node(stage_id='report', stage_kind='report', dependencies=['statistics'], output_path='report')])
    return nodes


class Plan(Model):
    schema_version: Literal[1] = 1
    workflow_contract_version: Literal['m7-v1'] = 'm7-v1'
    mode: Literal['run', 'analyze']
    output: str
    expected_samples: list[Identifier]
    expected_targets: list[Identifier]
    samples: list[dict[str, JsonValue]]
    targets: list[Target]
    nodes: list[Node]
    inputs: dict[str, InputArtifact]
    normalized_options: dict[str, JsonValue]
    software_identity: Software
    backend_identity: Backend

    @model_validator(mode='after')
    def graph(self):
        for values in (self.expected_samples, self.expected_targets):
            if not values or values != sorted(set(values)) or len({v.casefold() for v in values}) != len(values):
                raise ValueError('inventory must be nonempty, sorted, unique and filesystem-distinct')
        if sorted(s['barcode_id'] for s in self.samples) != self.expected_samples:
            raise ValueError('sample inventory mismatch')
        if sorted({t.target_name for t in self.targets}) != self.expected_targets:
            raise ValueError('target inventory mismatch')
        if self.nodes != dag(self.mode, self.expected_samples, self.expected_targets):
            raise ValueError('invalid DAG: dependencies, stage identities or owned paths differ')
        seen = set()
        for node in self.nodes:
            if node.stage_id in seen or not set(node.dependencies) <= seen:
                raise ValueError('duplicate stage, cycle or missing dependency')
            seen.add(node.stage_id)
        return self


class Dependency(Model):
    manifest: Artifact
    stage_signature_sha256: Hash
    output_identity_sha256: Hash


class StageManifest(Model):
    schema_version: Literal[1] = 1
    workflow_contract_version: Literal['m7-v1'] = 'm7-v1'
    node: Node
    status: Status
    stage_signature_sha256: Hash
    dependencies: dict[str, Dependency]
    input_artifacts: dict[str, InputArtifact]
    output_artifacts: list[Artifact]
    normalized_parameters: dict[str, JsonValue]
    software_identity: Software
    backend_identity: Backend | None
    api_call: str
    started_at: str
    ended_at: str
    validation: list[str]
    reason_codes: list[str]

    @model_validator(mode='after')
    def inventory(self):
        if set(self.dependencies) != set(self.node.dependencies):
            raise ValueError('dependency inventory mismatch')
        paths = [a.path for a in self.output_artifacts]
        if not paths or paths != sorted(set(paths)):
            raise ValueError('output artifacts must be nonempty, sorted and unique')
        root = PurePosixPath(self.node.output_path)
        if any(not PurePosixPath(p).is_relative_to(root) for p in paths):
            raise ValueError('artifact outside owned stage output')
        if self.status == 'SKIPPED_SCIENTIFIC_GATE' and (self.node.stage_kind != 'routing' or not self.reason_codes):
            raise ValueError('only routing can be skipped at an explicit scientific gate')
        if self.node.stage_kind != 'metrics' and self.backend_identity is not None:
            raise ValueError('backend identity belongs to metrics')
        return self


class Session(Model):
    session_id: Identifier
    mode: Literal['run', 'analyze']
    resume: bool
    force: list[str]
    started_at: str
    ended_at: str
    executed_stages: list[str]
    reused_stages: list[str]
    failed_stage: str | None
    argv: list[str]
    cwd: str


class WorkflowManifest(Model):
    schema_version: Literal[1] = 1
    workflow_contract_version: Literal['m7-v1'] = 'm7-v1'
    status: Literal['COMPLETED']
    mode: Literal['run', 'analyze']
    software_identity: Software
    plan: Artifact
    input_inventory: dict[str, InputArtifact]
    stage_inventory: dict[str, Artifact]
    session: Session
    statistics_result: Artifact
    report_manifest: Artifact
    limitations: list[str]
