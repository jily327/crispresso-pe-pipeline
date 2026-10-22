"""Opt-in tests run the real external 2.3.4 tool, never mocked subprocesses."""

import os
from pathlib import Path

import pytest

from peanalyzer.backend.pooled import resolve_executable
from peanalyzer.backend.routing_validation import run_synthetic_experiment

pytestmark = [pytest.mark.crispresso_integration,
              pytest.mark.skipif(os.environ.get("M3_INTEGRATION") != "1", reason="set M3_INTEGRATION=1 with CRISPResso2 2.3.4 installed")]


@pytest.fixture(scope="module")
def experiments(tmp_path_factory):
    root = Path(os.environ["M3_RESULTS_DIR"]) if "M3_RESULTS_DIR" in os.environ else tmp_path_factory.mktemp("crispresso-real")
    root.mkdir(parents=True, exist_ok=True)
    core = resolve_executable(os.environ.get("M3_CORE_EXECUTABLE", "CRISPResso"))
    pooled = resolve_executable(os.environ.get("M3_POOLED_EXECUTABLE", "CRISPRessoPooled"))
    results = {}
    for name, mismatch in (("baseline", False), ("guide_mismatch", True)):
        results[name] = run_synthetic_experiment(root / name, core=core, pooled=pooled,
            samtools=os.environ.get("M3_SAMTOOLS_EXECUTABLE", "samtools"),
            child_core_command=os.environ.get("M3_CHILD_CORE_COMMAND"), guide_mismatch=mismatch)
    return results


def test_real_pooled_informative_homeolog_routes(experiments):
    result = experiments["baseline"]
    assert result["total_synthetic_reads"] == 350
    assert result["informative_reads"] == result["correct_informative_routes"] == 310
    assert result["incorrect_cross_routes"] == 0
    assert result["cross_routed_read_ids"] == []


def test_default_ambiguous_routing_fails_scientific_gate(experiments):
    result = experiments["baseline"]
    assert result["deliberately_noninformative_reads"] == 40
    assert result["noninformative_reads_assigned_to_copies"] == result["score_tied_routed_reads"] == 40
    assert result["unassigned_reads"] == result["multiply_routed_reads"] == 0
    assert result["routing_gate"] == "FAIL"  # regression documents unsafe upstream default


def test_distinct_copy_specific_wt_pe_references(experiments):
    for copy, count in (("SYN__copy1", 60), ("SYN__copy2", 40)):
        result = experiments["baseline"]["reference_smoke"][copy]
        assert result["wt_reference_verified"] and result["pe_reference_verified"]
        assert result["precise_pe_routed_correctly"] == count
        assert result["exact_synthetic_pe_allele_reads_assigned_to_pe_reference"] == count


def test_faithful_experimental_spacer_mismatch(experiments):
    # Expected rejection observed in the faithful first experiment, not a rescue.
    result = experiments["guide_mismatch"]
    assert result["status"] == "rejected" and result["return_code"] == 255
    assert result["error_code"] == "PE_GUIDE_REFERENCE_MISMATCH_UNSUPPORTED"
    assert result["guide_sequences_unchanged"]
    assert not result["backend_sequence_check_override"] and not result["downstream_analysis_permitted"]
