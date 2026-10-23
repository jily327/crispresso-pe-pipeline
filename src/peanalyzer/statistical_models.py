"""Strict M5 biological observation, design and statistical result contracts."""
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator, model_validator

from peanalyzer.metrics.models import Count, Scope, Status
from peanalyzer.schemas import Identifier, Nonempty, NonnegativeInt

Probability = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
Effect = Annotated[float, Field(ge=-1, le=1, allow_inf_nan=False)]
Hash = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    @field_validator("schema_version", mode="before", check_fields=False)
    @classmethod
    def integer_schema_version(cls, value):
        if type(value) is not int:
            raise ValueError("schema_version must be an integer")
        return value


class Condition(Model):
    editor: Nonempty
    treatment: Nonempty
    dpi: NonnegativeInt

    @field_validator("editor", "treatment")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("condition values must not be blank")
        return value


class BiologicalSample(Condition):
    sample_name: Identifier
    biological_replicate: Identifier
    block_id: Identifier | None
    paired: bool


class Selector(Model):
    target_name: Identifier
    metric_name: Nonempty
    copy_name: Identifier | None = None
    policy_id: str | None = None


class Series(Selector):
    population_scope: Scope
    routing_conditioned: bool
    policy_definition: dict[str, JsonValue] | None = None

    @model_validator(mode="after")
    def identity(self):
        if self.routing_conditioned != (self.population_scope == "confident_copy"):
            raise ValueError("routing flag and population scope disagree")
        if (self.copy_name is not None) != self.routing_conditioned:
            raise ValueError("copy identity and population scope disagree")
        if (self.policy_id is None) != (self.policy_definition is None):
            raise ValueError("policy identity requires its exact definition")
        return self


class Observation(Series, BiologicalSample):
    sample_id: Identifier
    population_id: Nonempty
    status: Status
    numerator: Count | None
    denominator: Count | None
    fraction: Probability | None
    reason_codes: list[Nonempty]
    analysis_id: Nonempty
    metric_contract_version: Literal["m4-v1"]
    source_result: Nonempty

    @model_validator(mode="after")
    def ratio(self):
        if self.status == "REPORTABLE":
            if (self.numerator is None or not self.denominator or self.reason_codes
                    or self.numerator > self.denominator
                    or self.fraction != self.numerator / self.denominator):
                raise ValueError("reportable observation requires unchanged counts and derived fraction")
        elif (not self.reason_codes or self.numerator is not None
              or self.denominator is not None or self.fraction is not None):
            raise ValueError("nonreportable observation requires reasons and null counts/fraction")
        return self


class SampleAssessment(BiologicalSample):
    status: Literal["REPORTABLE", "BLOCKED", "NOT_ASSESSABLE", "MISSING_METRIC"]
    reason_codes: list[Nonempty]


    @model_validator(mode="after")
    def reportability(self):
        if bool(self.reason_codes) != (self.status != "REPORTABLE"):
            raise ValueError("sample assessment status and reasons disagree")
        return self


class SampleFraction(Model):
    sample_name: Identifier
    numerator: Count
    denominator: Annotated[int, Field(gt=0)]
    fraction: Probability

    @model_validator(mode="after")
    def ratio(self):
        if self.numerator > self.denominator or self.fraction != self.numerator / self.denominator:
            raise ValueError("invalid sample fraction")
        return self


class GroupSummary(Series):
    condition: Condition
    expected_sample_count: Count
    expected_sample_ids: list[Identifier]
    reportable_count: Count
    blocked_count: Count
    not_assessable_count: Count
    missing_metric_count: Count
    sample_assessments: list[SampleAssessment]
    reportable_sample_ids: list[Identifier]
    source_fractions: list[SampleFraction]
    mean_biological_sample_fraction: Probability | None
    median_biological_sample_fraction: Probability | None
    minimum_biological_sample_fraction: Probability | None
    maximum_biological_sample_fraction: Probability | None
    pooled_read_fraction: Probability | None
    pooled_read_fraction_label: Literal["POOLED READ-WEIGHTED DESCRIPTIVE FRACTION"] = "POOLED READ-WEIGHTED DESCRIPTIVE FRACTION"

    @model_validator(mode="after")
    def counts(self):
        if self.expected_sample_count != len(self.expected_sample_ids) or len(set(self.expected_sample_ids)) != self.expected_sample_count:
            raise ValueError("expected sample inventory does not reconcile")
        if self.expected_sample_count != self.reportable_count + self.blocked_count + self.not_assessable_count + self.missing_metric_count:
            raise ValueError("summary status counts do not reconcile")
        if self.reportable_sample_ids != [r.sample_name for r in self.source_fractions] or self.reportable_count != len(self.source_fractions):
            raise ValueError("reportable sample inventory does not reconcile")
        if [s.sample_name for s in self.sample_assessments] != self.expected_sample_ids:
            raise ValueError("sample assessments and expected inventory disagree")
        for status, count in (("REPORTABLE", self.reportable_count), ("BLOCKED", self.blocked_count),
                              ("NOT_ASSESSABLE", self.not_assessable_count), ("MISSING_METRIC", self.missing_metric_count)):
            if sum(s.status == status for s in self.sample_assessments) != count:
                raise ValueError("sample assessments and status counts disagree")
        values = (self.mean_biological_sample_fraction, self.median_biological_sample_fraction,
                  self.minimum_biological_sample_fraction, self.maximum_biological_sample_fraction, self.pooled_read_fraction)
        if any((v is None) != (self.reportable_count == 0) for v in values):
            raise ValueError("empty summaries require null descriptive fractions")
        return self


class Contrast(Selector):
    contrast_id: Identifier
    family_id: Identifier
    group_a: Condition
    group_b: Condition
    pairing_mode: Literal["unpaired", "block"]
    alternative: Literal["two-sided"]

    @model_validator(mode="after")
    def distinct_groups(self):
        if self.group_a == self.group_b:
            raise ValueError("contrast conditions must be distinct")
        return self


class ContrastSpecification(Model):
    schema_version: Literal[1]
    families: Annotated[list[Identifier], Field(min_length=1)]
    contrasts: Annotated[list[Contrast], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_declarations(self):
        ids = [c.contrast_id for c in self.contrasts]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate contrast_id")
        if len(self.families) != len(set(self.families)):
            raise ValueError("duplicate multiple-testing family specification")
        if any(c.family_id not in self.families for c in self.contrasts):
            raise ValueError("contrast references an undeclared family_id")
        return self


class ExcludedBlock(Model):
    block_id: Identifier
    group_a_sample_ids: list[Identifier]
    group_b_sample_ids: list[Identifier]
    reason_codes: list[Nonempty]


class ContrastResult(Contrast, Series):
    expected_group_a: list[SampleAssessment]
    expected_group_b: list[SampleAssessment]
    expected_group_a_count: Count
    expected_group_b_count: Count
    used_group_a_sample_ids: list[Identifier]
    used_group_b_sample_ids: list[Identifier]
    used_group_a_count: Count
    used_group_b_count: Count
    complete_blocks: list[Identifier]
    excluded_blocks: list[ExcludedBlock]
    status: Status
    reason_codes: list[Nonempty]
    difference_in_biological_sample_fraction: Effect | None
    p_value: Probability | None
    q_value: Probability | None
    valid_tests_in_family: Count
    permutation_space_size: Count | None
    permutation_count: Count | None
    extreme_count: Count | None

    @model_validator(mode="after")
    def coherent(self):
        for group in ("a", "b"):
            expected = getattr(self, f"expected_group_{group}")
            used = getattr(self, f"used_group_{group}_sample_ids")
            if (getattr(self, f"expected_group_{group}_count") != len(expected)
                    or len({s.sample_name for s in expected}) != len(expected)
                    or getattr(self, f"used_group_{group}_count") != len(used)
                    or len(set(used)) != len(used)
                    or not set(used) <= {s.sample_name for s in expected if s.status == "REPORTABLE"}):
                raise ValueError("contrast sample inventory does not reconcile")
        if self.status == "REPORTABLE":
            if (self.reason_codes or self.difference_in_biological_sample_fraction is None
                    or self.p_value is None or self.q_value is None
                    or not self.permutation_count or self.permutation_count != self.permutation_space_size
                    or not self.extreme_count or self.extreme_count > self.permutation_count
                    or self.p_value != self.extreme_count / self.permutation_count
                    or not self.p_value <= self.q_value <= 1 or self.valid_tests_in_family < 1
                    or min(self.used_group_a_count, self.used_group_b_count) < 2):
                raise ValueError("reportable contrast requires exact enumeration, effect and valid p/q")
            if self.pairing_mode == "block" and len(self.complete_blocks) < 2:
                raise ValueError("paired inference requires at least two complete blocks")
        elif (not self.reason_codes or any(v is not None for v in (
                self.p_value, self.q_value, self.difference_in_biological_sample_fraction,
                self.permutation_count, self.extreme_count))):
            raise ValueError("nonreportable contrast requires reasons and null inference")
        return self


class MultipleTestingFamily(Model):
    family_id: Identifier
    method: Literal["Benjamini-Hochberg"] = "Benjamini-Hochberg"
    contrast_ids: list[Identifier]
    valid_contrast_ids: list[Identifier]
    valid_test_count: Count


class InputResult(Model):
    source_result: Nonempty
    sha256: Hash
    sample_id: Identifier
    target_name: Identifier
    analysis_id: Nonempty


class Provenance(Model):
    package_version: Nonempty
    statistics_contract_version: Literal["m5-v1"] = "m5-v1"
    source_metric_contract_versions: list[Literal["m4-v1"]]
    input_results: list[InputResult]
    samples_path: Nonempty
    manifest_path: Nonempty
    contrast_specification_path: str | None
    contrast_specification_hash: Hash | None
    invocation_parameters: dict[str, JsonValue]
    python: Nonempty
    platform: Nonempty


class StatisticsResult(Model):
    schema_version: Literal[1]
    statistics_contract_version: Literal["m5-v1"]
    provenance: Provenance
    input_manifest_hash: Hash
    sample_metadata_hash: Hash
    observations: list[Observation]
    group_summaries: list[GroupSummary]
    contrasts: list[ContrastResult]
    multiple_testing_families: list[MultipleTestingFamily]
    unused_metadata_sample_ids: list[Identifier]

    @model_validator(mode="after")
    def families(self):
        ids = [c.contrast_id for c in self.contrasts]
        families = [f.family_id for f in self.multiple_testing_families]
        if len(set(ids)) != len(ids) or len(set(families)) != len(families):
            raise ValueError("duplicate contrast/family identity in result")
        if any(c.family_id not in families for c in self.contrasts):
            raise ValueError("undeclared multiple-testing family in result")
        for family in self.multiple_testing_families:
            members = [c for c in self.contrasts if c.family_id == family.family_id]
            valid = [c.contrast_id for c in members if c.status == "REPORTABLE"]
            if (family.contrast_ids != sorted(c.contrast_id for c in members)
                    or family.valid_contrast_ids != sorted(valid) or family.valid_test_count != len(valid)
                    or any(c.valid_tests_in_family != len(valid) for c in members)):
                raise ValueError("multiple-testing family inventory does not reconcile")
        return self
