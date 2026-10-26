"""Strict artifact inventory for the M6 presentation contract."""
from pathlib import PurePosixPath
from typing import Literal

from pydantic import JsonValue, field_validator, model_validator

from peanalyzer.statistical_models import Hash, Model


DEFAULT_TITLE = "Prime-editing amplicon analysis report"


class ReportingError(ValueError):
    """Invalid input or unsuccessful atomic report publication."""


class ReportArtifact(Model):
    path: str
    sha256: Hash
    media_type: Literal["text/html", "application/json", "text/tab-separated-values", "image/svg+xml"]
    artifact_kind: Literal["html", "source", "table", "figure"]
    figure_id: str | None = None
    figure_type: Literal["samples", "contrasts"] | None = None
    target_name: str | None = None
    metric_name: str | None = None
    population_scope: str | None = None
    routing_conditioned: bool | None = None
    copy_name: str | None = None
    policy_id: str | None = None
    policy_definition: dict[str, JsonValue] | None = None
    family_id: str | None = None

    @field_validator("path")
    @classmethod
    def portable(cls, value):
        path = PurePosixPath(value)
        if (not value or path.is_absolute() or ".." in path.parts or "\\" in value
                or ":" in value or str(path) != value):
            raise ValueError("artifact paths must be canonical relative POSIX paths")
        return value

    @model_validator(mode="after")
    def kind_matches(self):
        suffix, media = {"html": (".html", "text/html"), "source": (".json", "application/json"),
                         "table": (".tsv", "text/tab-separated-values"),
                         "figure": (".svg", "image/svg+xml")}[self.artifact_kind]
        if not self.path.endswith(suffix) or self.media_type != media:
            raise ValueError("artifact extension, kind and media type disagree")
        if self.artifact_kind == "figure":
            if not self.figure_id or not self.figure_type or self.path != f"figures/{self.figure_id}.svg":
                raise ValueError("figure identity and path disagree")
            if self.figure_type == "samples" and (self.target_name is None or self.metric_name is None
                    or self.population_scope is None or self.routing_conditioned is None or self.family_id is not None):
                raise ValueError("sample figures require their population identity")
            if self.figure_type == "samples" and ((self.policy_id is None) != (self.policy_definition is None)):
                raise ValueError("sample figures require the exact policy definition with policy identity")
            if self.figure_type == "contrasts" and self.family_id is None:
                raise ValueError("contrast figures require a family identity")
        elif any(getattr(self, name) is not None for name in (
                "figure_id", "figure_type", "target_name", "metric_name", "population_scope",
                "routing_conditioned", "copy_name", "policy_id", "policy_definition", "family_id")):
            raise ValueError("only figures carry figure metadata")
        return self


class ReportManifest(Model):
    schema_version: Literal[1]
    report_contract_version: Literal["m6-v1"]
    package_version: str
    source_statistics_contract_version: Literal["m5-v1"]
    source_result_sha256: Hash
    title: str
    artifacts: list[ReportArtifact]

    @model_validator(mode="after")
    def inventory(self):
        paths = [a.path for a in self.artifacts]
        if paths != sorted(set(paths)):
            raise ValueError("artifact paths must be unique and sorted")
        required = {"report.html": "html", "source/result.json": "source",
                    **{f"tables/{name}.tsv": "table" for name in ("observations", "group_summaries", "contrasts")}}
        actual = {a.path: a for a in self.artifacts}
        if not required.keys() <= actual.keys() or any(actual[p].artifact_kind != k for p, k in required.items()):
            raise ValueError("missing required report artifacts")
        if any(p not in required and a.artifact_kind != "figure" for p, a in actual.items()):
            raise ValueError("unexpected artifact")
        if actual["source/result.json"].sha256 != self.source_result_sha256:
            raise ValueError("source artifact hash disagrees")
        return self
