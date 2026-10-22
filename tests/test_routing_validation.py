import pytest

from peanalyzer.backend.pooled import BackendError
from peanalyzer.backend.routing_validation import read_sam_routes
from peanalyzer.backend.synthetic import DIAGNOSTIC_POSITIONS, design, write_synthetic_run


def test_sam_parser_preserves_ties_and_duplicate_alignments(tmp_path):
    path = tmp_path / "routes.sam"
    path.write_text("@HD\tVN:1.6\n" +
                    "read/1\t0\tAMPL_A\t1\t1\t4M\t*\t0\t0\tACGT\tIIII\tAS:i:0\tXS:i:0\n" +
                    "read/1\t256\tAMPL_B\t1\t0\t4M\t*\t0\t0\tACGT\tIIII\tAS:i:0\n" +
                    "missing\t4\t*\t0\t0\t*\t*\t0\t0\tACGT\tIIII\n")
    routes = read_sam_routes(path, {"AMPL_A": "copy1", "AMPL_B": "copy2"})
    assert len(routes["read"]) == 2
    assert routes["read"][0]["alignment_score"] == routes["read"][0]["alternative_score"] == 0
    assert routes["read"][1]["flag"] == 256
    assert "missing" not in routes


@pytest.mark.parametrize("line", ["not SAM", "x\t0\tunknown\t1\t1\t4M\t*\t0\t0\tACGT\tIIII"])
def test_malformed_routing_artifact_rejected(tmp_path, line):
    path = tmp_path / "bad.sam"; path.write_text(line + "\n")
    with pytest.raises(BackendError): read_sam_routes(path, {})


def test_synthetic_design_has_independent_ground_truth(tmp_path):
    targets, truth = write_synthetic_run(tmp_path / "synthetic")
    assert len(truth) == 350 and sum(row["informative"] for row in truth) == 310
    assert [i for i, (a, b) in enumerate(zip(targets[0].wt_sequence, targets[1].wt_sequence)) if a != b] == list(DIAGNOSTIC_POSITIONS)
    assert len(targets[0].wt_sequence) == len(targets[1].wt_sequence) == 240
    assert any(row["fragment_length"] == 40 for row in truth)
    assert len({row["read_id"] for row in truth}) == len(truth)
    assert design() == design()
