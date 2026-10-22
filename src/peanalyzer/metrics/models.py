"""Versioned, strict JSON contract. Integer counts are the source of truth."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Count = Annotated[int, Field(strict=True, ge=0)]
Status = Literal["REPORTABLE", "BLOCKED", "NOT_ASSESSABLE"]
Scope = Literal["target_all_prepared", "confident_copy"]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Ratio(Model):
    numerator: Count
    denominator: Count

    @model_validator(mode="after")
    def bounded(self):
        if self.numerator > self.denominator:
            raise ValueError("fraction numerator exceeds denominator")
        return self


class ProductCounts(Model):
    exact_wt: Count = 0
    exact_pe: Count = 0
    pe_plus_extra_change: Count = 0
    other_nonexact_assessable: Count = 0
    unresolved_unassessable: Count = 0
    contradictory_state: Count = 0
    denominator_exclusions: Count = 0
    classification_input_reads: Count = 0

    @model_validator(mode="after")
    def partition(self):
        excluded = (self.pe_plus_extra_change + self.other_nonexact_assessable
                    + self.unresolved_unassessable + self.contradictory_state)
        if excluded != self.denominator_exclusions:
            raise ValueError("product exclusions do not reconcile")
        if self.exact_wt + self.exact_pe + excluded != self.classification_input_reads:
            raise ValueError("product partition does not reconcile")
        return self


class MetricRecord(Model):
    metric_name: str
    metric_family: Literal["native", "precise"]
    population_scope: Scope
    population_id: str
    population_input_reads: Count | None
    copy_id: str | None
    routing_conditioned: bool
    assessment_stage: Literal["backend_aligned_products", "prepared_pairs"]
    status: Status
    numerator: Count | None = None
    denominator: Count | None = None
    reason_codes: list[str] = Field(default_factory=list)
    confident_input_reads: Count | None = None
    backend_input_reads: Count | None = None
    reads_after_preprocessing: Count | None = None
    aligned_reads: Count | None = None
    unaligned_reads: Count | None = None
    backend_counts_role: Literal["metric_filter", "parallel_native_analysis", "unavailable"]
    preprocessing_count_delta: int | None = None
    unaligned_reason_counts: dict[str, Count] = Field(default_factory=dict)
    products: ProductCounts | None = None
    population_denominator_exclusions: Count | None = None

    @model_validator(mode="after")
    def coherent(self):
        if self.population_scope == "confident_copy":
            if not self.copy_id or not self.routing_conditioned:
                raise ValueError("copy metrics must identify their routed population")
        elif self.copy_id is not None or self.routing_conditioned:
            raise ValueError("target metrics cannot claim a routed-copy population")
        if self.status == "REPORTABLE":
            if (self.numerator is None or not self.denominator or self.reason_codes
                    or self.numerator > self.denominator or self.population_input_reads is None):
                raise ValueError("reportable metric needs positive denominator and verified population")
            if self.metric_family == "native" and self.denominator != self.aligned_reads:
                raise ValueError("native denominator must equal aligned reads")
            if self.metric_family == "precise" and (self.products is None or
                    self.numerator != self.products.exact_pe or
                    self.denominator != self.products.exact_wt + self.products.exact_pe):
                raise ValueError("precise denominator must equal exact WT plus PE")
        elif not self.reason_codes or self.numerator is not None or self.denominator is not None:
            raise ValueError("non-reportable metrics require reasons and null fraction")
        attrs = (self.backend_input_reads, self.reads_after_preprocessing, self.aligned_reads, self.unaligned_reads)
        if any(v is not None for v in attrs):
            if any(v is None for v in attrs) or self.reads_after_preprocessing != self.aligned_reads + self.unaligned_reads:
                raise ValueError("backend attrition counts do not reconcile")
            if self.preprocessing_count_delta != self.backend_input_reads - self.reads_after_preprocessing:
                raise ValueError("preprocessing delta does not reconcile")
            if sum(self.unaligned_reason_counts.values()) != self.unaligned_reads:
                raise ValueError("backend unaligned reasons do not reconcile")
            if self.population_scope == 'confident_copy' and self.backend_input_reads != self.confident_input_reads:
                raise ValueError("confident/backend input identity mismatch")
        if self.products:
            expected = self.population_input_reads if self.assessment_stage == 'prepared_pairs' else self.aligned_reads
            if self.products.classification_input_reads != expected:
                raise ValueError("exact classification population mismatch")
        return self


class TargetMetrics(Model):
    target_crispresso_native_pe: MetricRecord
    total_precise_pe: MetricRecord


class CopyMetrics(Model):
    copy_id: str
    copy_metric_status: Status
    native: MetricRecord
    precise: MetricRecord


class Eligibility(Model):
    target_metric_status: Status
    routing_geometry_status: Literal["SAFE", "WARN", "BLOCKED"]
    comparator_status: Status
    anchor_invariant: bool
    block_reason_codes: list[str]


class Artifact(Model):
    sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    size_bytes: Count


class Provenance(Model):
    software: dict
    prepared_manifest_sha256: str | None
    prepared_sample: dict | None
    target_definitions_sha256: str
    routing_manifest_sha256: str | None
    routing_policy_identity: dict | None
    crispresso_version: Literal["2.3.4"]
    runtime_digest: str | None
    artifacts: dict[str, Artifact]


class QC(Model):
    prepared_input_reads: Count | None
    routing_assigned_reads: Count | None
    routing_quarantined_reads: Count | None
    routing_quarantine_fraction: Ratio | None
    routing_quarantine_reasons: dict[str, Count]
    target_backend_input_reads: Count | None
    target_backend_aligned_reads: Count | None
    target_backend_unaligned_reads: Count | None
    target_backend_unaligned_fraction: Ratio | None
    exact_assessable_reads: Count | None
    exact_product_exclusions: Count | None
    per_copy_confident_counts: dict[str, Count]
    limitations: list[str]


class MetricResult(Model):
    schema_version: Literal[1] = 1
    metric_contract_version: Literal["m4-v1"] = "m4-v1"
    target_id: str
    sample_id: str
    analysis_id: str
    provenance: Provenance
    eligibility: Eligibility
    target_metrics: TargetMetrics
    copies: dict[str, CopyMetrics]
    qc: QC
    anchor_evidence: dict

    @model_validator(mode="after")
    def populations(self):
        for name, record in self.target_metrics:
            if record.population_scope != "target_all_prepared" or record.metric_name != name:
                raise ValueError("target metric identity mismatch")
            if record.metric_family != ('native' if name == 'target_crispresso_native_pe' else 'precise'):
                raise ValueError("target metric family mismatch")
        a, b = self.target_metrics.target_crispresso_native_pe, self.target_metrics.total_precise_pe
        if (a.population_id, a.population_input_reads) != (b.population_id, b.population_input_reads):
            raise ValueError("target metrics must share their source population")
        for name, copy in self.copies.items():
            if copy.copy_id != name:
                raise ValueError("copy inventory mismatch")
            for family, record in (('native', copy.native), ('precise', copy.precise)):
                if record.copy_id != name or record.population_scope != "confident_copy":
                    raise ValueError("copy population mismatch")
                expected_name = name + ('_crispresso_native_pe' if family == 'native' else '_precise_pe')
                if record.metric_family != family or record.metric_name != expected_name:
                    raise ValueError("copy metric family mismatch")
            if (copy.native.population_id, copy.native.population_input_reads) != (copy.precise.population_id, copy.precise.population_input_reads):
                raise ValueError("copy metric population mismatch")
        return self
