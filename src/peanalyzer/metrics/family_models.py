"""Additive aggregate product evidence and explicit PE-family policies."""
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

Count=Annotated[int,Field(strict=True,ge=0)]


class FamilyModel(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)


class FamilyPolicy(FamilyModel):
    policy_id: str = Field(min_length=1)
    max_extra_substitutions: Count = 0
    max_extra_indel_events: Annotated[int,Field(strict=True,ge=0,le=0)] = 0
    allowed_extra_substitution_positions: list[Count] | None = None

    @model_validator(mode='after')
    def normalized(self):
        if type(self.max_extra_indel_events) is not int:
            raise ValueError('indel tolerance must be integer zero')
        if self.allowed_extra_substitution_positions is not None:
            self.allowed_extra_substitution_positions=sorted(set(self.allowed_extra_substitution_positions))
        return self


class ObservedProduct(FamilyModel):
    sequence: str | None
    count: Count
    assessable: bool
    reason_codes: list[str] = Field(default_factory=list)
    canonical_exact_wt: bool = False
    canonical_exact_pe: bool = False
    intended_state: Literal['WT','PE','neither','ambiguous'] = 'neither'
    candidates: list[dict] = Field(default_factory=list)
    observed_mates: list[str] | None = None
    eligible_copies: list[str] = Field(default_factory=list)


class ProductEvidence(FamilyModel):
    evidence_version: Literal[1] = 1
    population_id: str
    population_scope: Literal['target_all_prepared','confident_copy']
    copy_id: str | None
    assessment_stage: Literal['prepared_pairs','backend_aligned_products']
    source_input_reads: Count | None
    classification_input_reads: Count
    targets: list[dict]
    products: list[ObservedProduct]
    blocking_reasons: list[str] = Field(default_factory=list)
    coordinate_contract: Literal['zero_based_anchor_wt_forward'] = 'zero_based_anchor_wt_forward'

    @model_validator(mode='after')
    def partition(self):
        if sum(p.count for p in self.products)!=self.classification_input_reads:
            raise ValueError('aggregate product evidence does not reconcile')
        if any(p.count==0 for p in self.products): raise ValueError('empty product row')
        if self.population_scope=='confident_copy' and not self.copy_id:
            raise ValueError('copy evidence must identify the confident population')
        return self


class FamilyMetric(FamilyModel):
    metric_name: str
    policy_id: str
    policy: dict
    population_id: str
    population_scope: Literal['target_all_prepared','confident_copy']
    copy_id: str | None
    status: Literal['REPORTABLE','BLOCKED','NOT_ASSESSABLE']
    numerator: Count | None
    denominator: Count | None
    wt_family: Count
    pe_family: Count
    family_ambiguous: Count
    excluded: Count
    classification_input_reads: Count
    reason_codes: list[str]

    @model_validator(mode='after')
    def coherent(self):
        if self.wt_family+self.pe_family+self.family_ambiguous+self.excluded!=self.classification_input_reads:
            raise ValueError('family partition does not reconcile')
        if self.status=='REPORTABLE':
            if (self.reason_codes or self.numerator!=self.pe_family or
                    self.denominator!=self.wt_family+self.pe_family or not self.denominator):
                raise ValueError('invalid reportable family fraction')
        elif self.numerator is not None or self.denominator is not None or not self.reason_codes:
            raise ValueError('nonreportable family needs null fraction and reasons')
        return self
