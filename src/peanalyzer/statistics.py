"""Exact biological replicate permutation tests and explicit-family BH correction."""
import itertools
import math
from fractions import Fraction
from pathlib import Path

import yaml

from peanalyzer.aggregation import (
    AggregationError, canonical, collect_observations, publish,
    series_key, sha256, subset,
)
from peanalyzer.statistical_models import (
    ContrastSpecification, ExcludedBlock, MultipleTestingFamily,
    Series, StatisticsResult,
)
from peanalyzer.validation import UniqueKeyLoader

MAX_PERMUTATIONS = 100_000
MIN_BIOLOGICAL_REPLICATES = 2


def _limit(maximum):
    if type(maximum) is not int or not 1 <= maximum <= MAX_PERMUTATIONS:
        raise AggregationError(f"max_permutations must be an integer from 1 to {MAX_PERMUTATIONS}")


def exact_unpaired(group_a, group_b, *, maximum=MAX_PERMUTATIONS):
    """Return (rational effect, space, extreme count); inputs are sample fractions.

    The public orchestration API handles insufficient replicates/large spaces as
    typed nonreportable results. This low-level enumerator rejects those calls.
    """
    _limit(maximum)
    a, b = [Fraction(v) for v in group_a], [Fraction(v) for v in group_b]
    if min(len(a), len(b)) < MIN_BIOLOGICAL_REPLICATES:
        raise AggregationError("INSUFFICIENT_BIOLOGICAL_REPLICATES")
    if any(not 0 <= v <= 1 for v in a + b):
        raise AggregationError("sample fractions must be between zero and one")
    size = math.comb(len(a) + len(b), len(a))
    if size > maximum:
        raise AggregationError("PERMUTATION_SPACE_TOO_LARGE")
    observed = sum(b) / len(b) - sum(a) / len(a)
    pooled, extreme = a + b, 0
    total = sum(pooled)
    for indices in itertools.combinations(range(len(pooled)), len(a)):
        sum_a = sum(pooled[i] for i in indices)
        statistic = (total - sum_a) / len(b) - sum_a / len(a)
        extreme += abs(statistic) >= abs(observed)
    return observed, size, extreme


def exact_paired(differences, *, maximum=MAX_PERMUTATIONS):
    """Enumerate all block sign flips with exact rational tail comparisons."""
    _limit(maximum)
    differences = [Fraction(v) for v in differences]
    if len(differences) < MIN_BIOLOGICAL_REPLICATES:
        raise AggregationError("INSUFFICIENT_BIOLOGICAL_REPLICATES")
    if any(not -1 <= v <= 1 for v in differences):
        raise AggregationError("block differences must be between minus one and one")
    size = 2 ** len(differences)
    if size > maximum:
        raise AggregationError("PERMUTATION_SPACE_TOO_LARGE")
    observed, extreme = sum(differences) / len(differences), 0
    for signs in itertools.product((-1, 1), repeat=len(differences)):
        statistic = sum(sign * value for sign, value in zip(signs, differences)) / len(differences)
        extreme += abs(statistic) >= abs(observed)
    return observed, size, extreme


def benjamini_hochberg(p_values):
    """Adjust only supplied valid p-values; IDs provide deterministic tie order."""
    if any(type(p) not in (int, float, Fraction) or not math.isfinite(p) or not 0 <= p <= 1 for p in p_values.values()):
        raise AggregationError("BH requires finite probabilities")
    ordered = sorted(p_values, key=lambda key: (p_values[key], key))
    adjusted, running = {}, Fraction(1)
    for rank in range(len(ordered), 0, -1):
        name = ordered[rank - 1]
        running = min(running, Fraction(p_values[name]) * len(ordered) / rank)
        adjusted[name] = float(running)
    return {name: adjusted[name] for name in sorted(adjusted)}


def load_contrasts(path):
    try:
        data = Path(path).read_bytes()
        raw = yaml.load(data.decode("utf-8-sig"), Loader=UniqueKeyLoader)
        if not isinstance(raw, dict) or type(raw.get("schema_version")) is not int:
            raise AggregationError("contrast specification requires integer schema_version")
        return ContrastSpecification.model_validate(raw), sha256(data)
    except (OSError, UnicodeError, ValueError, yaml.YAMLError) as exc:
        raise AggregationError(f"invalid contrast specification: {exc}") from exc


def _contrast(request, summary_a, summary_b, maximum):
    a, b = summary_a.sample_assessments, summary_b.sample_assessments
    fractions_a = {s.sample_name: Fraction(s.numerator, s.denominator) for s in summary_a.source_fractions}
    fractions_b = {s.sample_name: Fraction(s.numerator, s.denominator) for s in summary_b.source_fractions}
    used_a, used_b, complete, excluded, reasons = [], [], [], [], []
    status, space, effect, count, extreme = "REPORTABLE", None, None, None, None
    if request.pairing_mode == "unpaired":
        blocks = [s.block_id for s in a + b if s.block_id is not None]
        if any(s.paired for s in a + b) or len(set(blocks)) != len(blocks):
            status, reasons = "BLOCKED", ["UNPAIRED_DESIGN_CONFLICT"]
        else:
            used_a, used_b = sorted(fractions_a), sorted(fractions_b)
            space = math.comb(len(used_a) + len(used_b), len(used_a))
    else:
        if any(not s.paired or s.block_id is None for s in a + b):
            status, reasons = "BLOCKED", ["PAIRED_DESIGN_REQUIRES_BLOCK_ID_AND_PAIRED_TRUE"]
        blocks = sorted({s.block_id for s in a + b if s.block_id is not None})
        for block in blocks:
            left, right = [s for s in a if s.block_id == block], [s for s in b if s.block_id == block]
            block_reasons = []
            if len(left) > 1 or len(right) > 1:
                status = "BLOCKED"
                reasons.append("DUPLICATE_BLOCK_GROUP_OBSERVATIONS")
                block_reasons.append("DUPLICATE_BLOCK_GROUP_OBSERVATIONS")
            if not left:
                block_reasons.append("MISSING_GROUP_A")
            if not right:
                block_reasons.append("MISSING_GROUP_B")
            if any(s.status != "REPORTABLE" for s in left + right):
                block_reasons.append("NONREPORTABLE_BLOCK_OBSERVATION")
                block_reasons += [reason for s in left + right for reason in s.reason_codes]
            if block_reasons:
                excluded.append(ExcludedBlock(block_id=block, group_a_sample_ids=[s.sample_name for s in left],
                    group_b_sample_ids=[s.sample_name for s in right], reason_codes=sorted(set(block_reasons))))
            else:
                complete.append(block)
                used_a.append(left[0].sample_name)
                used_b.append(right[0].sample_name)
        if status == "BLOCKED":
            # No samples are used for inference when the design itself is invalid.
            used_a, used_b, complete = [], [], []
        else:
            space = 2 ** len(complete)
    if status == "REPORTABLE":
        if min(len(used_a), len(used_b)) < MIN_BIOLOGICAL_REPLICATES:
            status, reasons = "NOT_ASSESSABLE", ["INSUFFICIENT_BIOLOGICAL_REPLICATES"]
        elif space > maximum:
            status, reasons = "NOT_ASSESSABLE", ["PERMUTATION_SPACE_TOO_LARGE"]
        else:
            if request.pairing_mode == "unpaired":
                effect, count, extreme = exact_unpaired([fractions_a[s] for s in used_a],
                                                       [fractions_b[s] for s in used_b], maximum=maximum)
            else:
                effect, count, extreme = exact_paired([fractions_b[right] - fractions_a[left]
                                                      for left, right in zip(used_a, used_b)], maximum=maximum)
    return dict(**request.model_dump(), **{k: v for k, v in subset(summary_a, Series).model_dump().items()
                                         if k not in type(request).model_fields},
        expected_group_a=[s.model_dump() for s in a], expected_group_b=[s.model_dump() for s in b],
        expected_group_a_count=len(a), expected_group_b_count=len(b),
        used_group_a_sample_ids=used_a, used_group_b_sample_ids=used_b,
        used_group_a_count=len(used_a), used_group_b_count=len(used_b),
        complete_blocks=complete, excluded_blocks=[r.model_dump() for r in excluded],
        status=status, reason_codes=sorted(set(reasons)),
        difference_in_biological_sample_fraction=float(effect) if effect is not None else None,
        p_value=extreme / count if count else None, q_value=None, valid_tests_in_family=0,
        permutation_space_size=space, permutation_count=count, extreme_count=extreme)


def calculate_contrasts(result, specification, *, max_permutations=MAX_PERMUTATIONS):
    """Return a new result; preserve all observations and explicit sample attrition."""
    _limit(max_permutations)
    result = StatisticsResult.model_validate(result.model_dump())
    specification = ContrastSpecification.model_validate(specification.model_dump())
    groups = {(series_key(s), canonical(s.condition)): s for s in result.group_summaries}
    contrasts = []
    for request in sorted(specification.contrasts, key=lambda c: c.contrast_id):
        key = series_key(request)
        left, right = groups.get((key, canonical(request.group_a))), groups.get((key, canonical(request.group_b)))
        if left is None or right is None:
            raise AggregationError(f"unknown/empty condition or metric population in contrast: {request.contrast_id}")
        contrasts.append(_contrast(request, left, right, max_permutations))
    families = []
    for family in sorted(specification.families):
        members = [c for c in contrasts if c["family_id"] == family]
        valid = {c["contrast_id"]: Fraction(c["extreme_count"], c["permutation_count"])
                 for c in members if c["status"] == "REPORTABLE"}
        adjusted = benjamini_hochberg(valid)
        for contrast in members:
            contrast["valid_tests_in_family"] = len(valid)
            contrast["q_value"] = adjusted.get(contrast["contrast_id"])
        families.append(MultipleTestingFamily(family_id=family, contrast_ids=sorted(c["contrast_id"] for c in members),
                                             valid_contrast_ids=sorted(valid), valid_test_count=len(valid)))
    data = result.model_dump()
    data.update(contrasts=contrasts, multiple_testing_families=[f.model_dump() for f in families])
    data["provenance"].update(contrast_specification_path=None,
        contrast_specification_hash=sha256(canonical(specification).encode("utf-8")))
    data["provenance"]["invocation_parameters"].update(command="stats", max_permutations=max_permutations,
                                                      minimum_biological_replicates=MIN_BIOLOGICAL_REPLICATES,
                                                      contrast_specification_hash_basis="normalized_typed_specification")
    return StatisticsResult.model_validate(data)


def stats(*, manifest_path, samples_path, contrasts_path, output=None, max_permutations=MAX_PERMUTATIONS):
    specification, spec_hash = load_contrasts(contrasts_path)
    result = calculate_contrasts(collect_observations(manifest_path, samples_path), specification,
                                 max_permutations=max_permutations)
    result.provenance.contrast_specification_path = str(Path(contrasts_path).resolve())
    result.provenance.contrast_specification_hash = spec_hash
    result.provenance.invocation_parameters["contrast_specification_hash_basis"] = "source_file_bytes"
    if sha256(Path(contrasts_path).read_bytes()) != spec_hash:
        raise AggregationError("contrast specification changed during analysis")
    if output is not None:
        publish(result, output)
    return result
