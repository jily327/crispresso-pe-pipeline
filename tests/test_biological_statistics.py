"""Cross-mode regression of biological replicate statistics and stored projections."""
import csv
import json
import math

import pytest
import yaml

from m5_fixtures import dataset, result_document, write_json
from peanalyzer.aggregation import AggregationError
from peanalyzer.reporting import build_report_spec, load_result, render_html, write_tables
from peanalyzer.schemas import StatisticsConfig
from peanalyzer.statistics import stats
from test_m8 import measurements


@pytest.mark.parametrize("paired", [False, True])
def test_two_replicates_and_configured_threshold(tmp_path, paired):
    inputs = dataset(tmp_path, replicates=2, targets=("T1",), paired=paired)
    for name, num, den in (("A001", 1, 10), ("A002", 90, 100)):
        write_json(tmp_path / f"{name}-T1.json", result_document("barcode-" + name, "T1", num, den))
    default = stats(**inputs)
    assert StatisticsConfig().min_biological_replicates == 2
    assert all(c.status == "REPORTABLE" for c in default.contrasts)
    output = tmp_path / "stats"
    result = stats(**inputs, min_biological_replicates=3, output=output)
    assert result.group_summaries == default.group_summaries
    assert all(c.reason_codes == ["INSUFFICIENT_BIOLOGICAL_REPLICATES"] for c in result.contrasts)
    assert all(c.p_value is c.q_value is None for c in result.contrasts)
    assert all(not f.valid_test_count for f in result.multiple_testing_families)
    assert result.provenance.invocation_parameters["minimum_biological_replicates"] == 3
    group = next(g for g in result.group_summaries if g.metric_name == "total_precise_pe" and g.condition.treatment == "A")
    expected_sd = math.sqrt(0.32)
    assert group.mean_biological_sample_fraction == 0.5
    assert group.sample_sd_biological_sample_fraction == pytest.approx(expected_sd)
    assert group.pooled_read_fraction == 91 / 110
    data = (output / "result.json").read_bytes()
    spec = build_report_spec(load_result(data))
    figures = {item["figure_id"]: "" for item in spec["series"]}
    html = render_html(spec, "0" * 64, figures)
    assert "56.57%" in html and "Executed minimum biological replicates: 3" in html
    write_tables(spec, tmp_path / "tables")
    for table in (output / "group_summaries.tsv", tmp_path / "tables/group_summaries.tsv"):
        with table.open() as stream:
            row = next(row for row in csv.DictReader(stream, delimiter="\t") if row["metric_name"] == "total_precise_pe"
                       and json.loads(row["condition"])["treatment"] == "A")
        assert float(row["sample_sd_biological_sample_fraction"]) == pytest.approx(expected_sd)
        assert row["descriptive_statistics_version"] == "biological-sample-sd-v1"


def test_one_replicate_historical_contract_and_invalid_threshold(tmp_path):
    inputs = dataset(tmp_path, replicates=1, targets=("T1",))
    fresh = stats(**inputs)
    assert fresh.group_summaries and all(g.sample_sd_biological_sample_fraction is None for g in fresh.group_summaries)
    legacy = fresh.model_dump()
    for group in legacy["group_summaries"]:
        del group["sample_sd_biological_sample_fraction"], group["descriptive_statistics_version"]
    spec = build_report_spec(load_result(json.dumps(legacy)))
    assert spec["group_summaries"] and all("sample_sd_biological_sample_fraction" not in g for g in spec["group_summaries"])
    for invalid in (True, 1, 2.5):
        with pytest.raises(AggregationError, match="min_biological_replicates"):
            stats(**inputs, min_biological_replicates=invalid)


def test_nuclease_same_threshold_and_zero_sd(measurements):
    options, contrasts = measurements
    result = stats(**options, contrasts_path=contrasts, min_biological_replicates=3)
    assert all(group.sample_sd_biological_sample_fraction == 0 for group in result.group_summaries)
    assert all(row.reason_codes == ["INSUFFICIENT_BIOLOGICAL_REPLICATES"] for row in result.contrasts)


def test_workflow_config_reaches_executed_statistics(tmp_path, monkeypatch):
    from m7_fixtures import fixture
    from peanalyzer import workflow

    options = fixture(tmp_path / "inputs", samples=4)
    options["contrasts"] = tmp_path / "inputs/contrasts.yaml"
    cfg = yaml.safe_load(options["config"].read_text())
    cfg["statistics"] = {"min_biological_replicates": 4}
    options["config"].write_text(yaml.safe_dump(cfg))
    fake_core = tmp_path / "test-core"
    fake_core.write_text('#!/bin/sh\necho "CRISPResso 2.3.4"\n')
    fake_core.chmod(0o755)
    options["crispresso"] = str(fake_core)
    plan = workflow.build_workflow_plan(**options)
    node = next(n for n in plan.nodes if n.stage_kind == "statistics")
    assert workflow.parameters_for(plan, node)["min_biological_replicates"] == 4
    calls = []
    monkeypatch.setattr(workflow, "stats", lambda **kwargs: calls.append(kwargs))
    workflow.execute_stage(plan, node, {}, [])
    assert len(calls) == 1 and calls[0]["min_biological_replicates"] == 4
