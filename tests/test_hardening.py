"""M2.1 audit regressions: output identity, publication and catalog safety."""

import gzip
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

import pytest

import peanalyzer.demux as engine
from peanalyzer.barcodes import Barcode, Catalog, bundled_catalog, load_catalog, validate_catalog_matching
from peanalyzer.demux import CATEGORIES, DemuxError, demultiplex, reconcile
from peanalyzer.demux_output import SampleWriter
from peanalyzer.schemas import Config, reverse_complement
from peanalyzer.validation import MetadataError, load_samples, sample_output_names
from synthetic import mixed_records, record, write_pairs


@pytest.fixture
def run_args(tmp_path, example_dir):
    r1, r2 = write_pairs(tmp_path, mixed_records())
    return dict(r1=r1, r2=r2, samples_path=example_dir / "ev_only_1005_samples.csv",
                config=Config(schema_version=1), output=tmp_path / "out")


@pytest.mark.parametrize("stems", [("s1", "S1"), ("sample", "Sample"), ("sample", " sample ")])
def test_output_collisions_fail_before_reading_fastq(run_args, write_csv, monkeypatch, stems):
    rows = [dict(sample_name=f"name{i}", barcode_id=stem, forward_barcode_id=f"F{i+1}", reverse_barcode_id="RB")
            for i, stem in enumerate(stems)]
    run_args["samples_path"] = write_csv("samples.csv", rows)
    original = engine.file_provenance
    def no_fastq(path):
        assert path not in (run_args["r1"], run_args["r2"]), "FASTQ read before metadata validation"
        return original(path)
    monkeypatch.setattr(engine, "file_provenance", no_fastq)
    with pytest.raises(MetadataError, match="collision|duplicate"):
        demultiplex(**run_args)
    assert not run_args["output"].exists()


@pytest.mark.parametrize("invalid", ["sample a", "sample/a", "sample:a"])
def test_names_that_would_need_sanitization_are_rejected(invalid):
    # No lossy sanitizer exists: these cannot silently alias sample_a.
    with pytest.raises(MetadataError, match="sanitization"):
        sample_output_names(["sample_a", invalid])


@pytest.mark.parametrize("mate", [1, 2])
def test_writer_refuses_stale_file_even_when_other_mate_is_new(tmp_path, mate):
    stale = tmp_path / f"A_R{mate}.fastq.gz"
    stale.write_bytes(b"unrelated stale data")
    writer = SampleWriter(tmp_path, ["A"], 1)
    with pytest.raises(FileExistsError):
        writer.ensure_empty_samples()
    writer.close()
    assert stale.read_bytes() == b"unrelated stale data"


def test_writer_refuses_case_collision_without_filesystem_help(tmp_path):
    with pytest.raises(MetadataError, match="collision"):
        SampleWriter(tmp_path, ["s1", "S1"], 1)
    assert not list(tmp_path.iterdir())


def test_lru_reopen_cannot_create_a_missing_file(tmp_path):
    writer = SampleWriter(tmp_path, ["A"], 1)
    writer.ensure_empty_samples()
    (tmp_path / "A_R1.fastq.gz").unlink()
    with pytest.raises(FileNotFoundError):
        writer.ensure_empty_samples()


def test_normal_completion_is_published_only_after_summary(run_args, monkeypatch):
    output = run_args["output"]
    original = Path.rename
    def inspect_publish(path, target):
        if target == output:
            assert path.name.startswith(".out.incomplete-")
            assert not output.exists()
            summary = json.loads((path / "01_demux_QC/demux_summary.json").read_text())
            assert summary["status"] == "completed" and summary["reconciliation"]["passed"]
            for name, metadata in summary["output_files"].items():
                assert hashlib.sha256((path / name).read_bytes()).hexdigest() == metadata["sha256"]
        return original(path, target)
    monkeypatch.setattr(Path, "rename", inspect_publish)
    report = demultiplex(**run_args)
    assert output.is_dir() and not list(output.parent.glob(".out.incomplete-*"))
    assert report["schema_version"] == 2


@pytest.mark.parametrize("failure", ["close", "summary", "publish", "matrix_disk"])
def test_authoritative_failure_never_publishes(run_args, monkeypatch, failure):
    output = run_args["output"]
    if failure == "close":
        original = SampleWriter.close
        def close(writer):
            original(writer)
            raise OSError("injected close error")
        monkeypatch.setattr(SampleWriter, "close", close)
    elif failure == "summary":
        original = Path.write_text
        def write(path, *args, **kwargs):
            if path.name == "demux_summary.json.tmp":
                raise OSError("injected summary error")
            return original(path, *args, **kwargs)
        monkeypatch.setattr(Path, "write_text", write)
    elif failure == "publish":
        def rename(*args):
            raise OSError("injected rename error")
        monkeypatch.setattr(Path, "rename", rename)
    else:
        original = engine.write_qc_tables
        def tables(directory, *args):
            original(directory, *args)
            (directory / "barcode_pair_matrix.csv").write_text("corrupt\n")
        monkeypatch.setattr(engine, "write_qc_tables", tables)
    with pytest.raises(OSError):
        demultiplex(**run_args)
    assert not output.exists()
    assert not list(output.parent.glob(".out.incomplete-*"))


def test_destination_created_during_run_is_preserved(run_args, monkeypatch):
    original = engine.write_heatmap
    def race(*args):
        original(*args)
        run_args["output"].mkdir()
        (run_args["output"] / "unrelated").write_text("keep")
    monkeypatch.setattr(engine, "write_heatmap", race)
    with pytest.raises(DemuxError, match="publication"):
        demultiplex(**run_args)
    assert (run_args["output"] / "unrelated").read_text() == "keep"


@pytest.mark.parametrize("k", [2, 5, 50])
def test_unsafe_qi_mismatch_threshold_rejected_by_demux(run_args, monkeypatch, k):
    run_args["config"] = Config(schema_version=1, demux={"max_mismatches": k})
    def no_parse(*args):
        pytest.fail("unsafe catalog reached FASTQ parser")
    monkeypatch.setattr(engine, "paired_fastq", no_parse)
    with pytest.raises(MetadataError, match="minimum pairwise Hamming distance 2"):
        demultiplex(**run_args)


@pytest.mark.parametrize("k", [0, 1])
def test_qi_distance_is_reported_and_overlap_warned(run_args, k):
    run_args["config"] = Config(schema_version=1, demux={"max_mismatches": k})
    report = demultiplex(**run_args)
    assert all(side["minimum_hamming_distance"] == 2 for side in report["barcode_catalog"]["matching_safety"].values())
    assert any("neighborhoods overlap" in warning for warning in report["warnings"]) == bool(k)


def test_singleton_catalog_still_bounds_mismatch_threshold():
    catalog = Catalog([Barcode(direction=direction, barcode_id=direction, sequence="ACGT") for direction in ("forward", "reverse")])
    info, _ = validate_catalog_matching(catalog, 1)
    assert info["forward"]["minimum_hamming_distance"] is None
    with pytest.raises(MetadataError, match="barcode length"):
        validate_catalog_matching(catalog, 50)


@pytest.mark.parametrize("direction", ["forward", "reverse"])
@pytest.mark.parametrize("longer", ["ACGTA", "TTTTT"])
def test_prefix_overlaps_and_other_mixed_lengths_fail_in_demux(run_args, write_csv, direction, longer):
    rows = [dict(sample_name="a", barcode_id="A", forward_barcode="ACGT", reverse_barcode="ACGT"),
            dict(sample_name="b", barcode_id="B", forward_barcode="ACGT", reverse_barcode="ACGT")]
    rows[1][f"{direction}_barcode"] = longer
    run_args.update(samples_path=write_csv("samples.csv", rows), config=Config(schema_version=1, demux={"profile": "custom"}))
    with pytest.raises(MetadataError, match=f"{direction}: equal barcode lengths"):
        demultiplex(**run_args)


@pytest.mark.parametrize("with_id", [False, True])
def test_authoritative_catalog_rejects_unknown_or_conflicting_sequence(run_args, write_csv, with_id):
    row = dict(sample_name="a", barcode_id="A", forward_barcode="GCTTGCGTA", reverse_barcode_id="RB")
    if with_id:
        row["forward_barcode_id"] = "F1"
    run_args["samples_path"] = write_csv("samples.csv", [row])
    run_args["barcodes_path"] = bundled_catalog()
    with pytest.raises(MetadataError, match="unknown forward sequence|conflicting sequence"):
        demultiplex(**run_args)


def test_known_explicit_sequences_use_authoritative_identity(write_csv):
    catalog = load_catalog(bundled_catalog())
    samples = write_csv("samples.csv", [dict(sample_name="a", barcode_id="A", forward_barcode="GCTTGCGTT", reverse_barcode="CTGTGTAGT")])
    row = load_samples(samples, catalog, metadata_required=False)[0]
    assert (row.forward_barcode_id, row.reverse_barcode_id) == ("F1", "RB")
    assert len(catalog.ends["forward"]) == 12


def test_per_sample_matrix_mismatch_fails_even_when_totals_agree():
    categories = dict.fromkeys(CATEGORIES, 0)
    categories["assigned_expected_pair"] = 3
    samples = {"A": 1, "B": 2}
    matrix = Counter({("F1", "R"): 2, ("F2", "R"): 1})
    with pytest.raises(DemuxError, match="expected_matrix_cells_equal_samples.*False"):
        reconcile(3, categories, samples, samples, matrix, {("F1", "R"): "A", ("F2", "R"): "B"}, {"A": [1, 1], "B": [2, 2]})


def test_expected_matrix_total_and_mate_counts_are_independently_checked():
    categories = dict.fromkeys(CATEGORIES, 0)
    categories.update(assigned_expected_pair=1, unexpected_valid_barcode_pair=1)
    with pytest.raises(DemuxError, match="expected_matrix_sum_equals_assigned.*False"):
        reconcile(2, categories, {"A": 1}, {"A": 1}, Counter({("F", "R"): 2}), {("F", "R"): "A"}, {"A": [1, 1]})
    with pytest.raises(DemuxError, match="mate_records_equal_sample_counts.*False"):
        reconcile(2, categories, {"A": 1}, {"A": 1}, Counter({("F", "R"): 1, ("F2", "R"): 1}), {("F", "R"): "A"}, {"A": [1, 0]})


def test_all_output_hashes_and_counts_verify_including_lru_and_empty_samples(run_args):
    run_args["config"] = Config(schema_version=1, demux={"max_open_sample_pairs": 1})
    report = demultiplex(**run_args)
    assert len(report["output_files"]) == 26
    for name, metadata in report["output_files"].items():
        data = (run_args["output"] / name).read_bytes()
        assert metadata["sha256"] == hashlib.sha256(data).hexdigest()
        assert metadata["size_bytes"] == len(data)
        if "records" in metadata:
            assert len(gzip.decompress(data).splitlines()) // 4 == metadata["records"]
            assert metadata["records"] == report["per_sample_assigned_read_pairs"][metadata["sample_id"]]
    software = report["software"]
    assert software["python_version"] and software["dependencies"]["pydantic"]
    assert "git_commit" in software and "git_dirty" in software
    assert report["invocation"]["argv"] is None  # direct API invocation
    assert report["extraction_profile"]["source_sha256"]
    assert report["barcode_catalog"]["resolved_sha256"]


@pytest.mark.parametrize("checkout", [False, True])
def test_missing_git_is_nonfatal_and_wheel_never_uses_callers_git(tmp_path, monkeypatch, checkout):
    import peanalyzer.provenance as provenance
    module = tmp_path / "src/peanalyzer/provenance.py"
    monkeypatch.setattr(provenance, "__file__", str(module))
    if checkout:
        (tmp_path / ".git").mkdir()
    def unavailable(*args, **kwargs):
        assert checkout, "installed wheel must not probe the caller's Git checkout"
        raise FileNotFoundError("git unavailable")
    monkeypatch.setattr(provenance.subprocess, "check_output", unavailable)
    report = provenance.software_provenance()
    assert report["git_commit"] is None and report["git_dirty"] is None
    assert report["pipeline_version"] == "0.4.0"


def test_reverse_complement_motif_qc_keeps_bridge_in_raw_orientation(run_args, tmp_path):
    catalog = load_catalog(bundled_catalog())
    f = catalog.ends["forward"]["F1"]
    r = reverse_complement(catalog.ends["reverse"]["RB"])
    pairs = [(record("x", f + "GGAGTGAGTACGGTGTGCACGT", 1), record("x", r + "GAGTTGGATGCTGGATGGACGT", 2))]
    run_args["r1"], run_args["r2"] = write_pairs(tmp_path, pairs)
    run_args["config"] = Config(schema_version=1, demux={"reverse_barcode_orientation": "reverse_complement"})
    report = demultiplex(**run_args)
    assert report["assigned_expected_pair"] == 1
    qc = report["barcode_bridge_qc"]["reverse"]
    assert qc["prefix_match"] == qc["suffix_match"] == qc["bridge_match"] == 1
    assert qc["prefix_mismatch"] == qc["suffix_mismatch"] == 0
    assert gzip.decompress((run_args["output"] / "02_demultiplexed_fastq/1B_R2.fastq.gz").read_bytes()) == pairs[0][1]


def test_plot_failure_warns_and_preserves_authoritative_results(run_args, monkeypatch):
    def fail(directory, *args):
        (directory / "barcode_pair_heatmap.png").write_bytes(b"partial png")
        raise RuntimeError("injected renderer failure")
    monkeypatch.setattr(engine, "write_heatmap", fail)
    report = demultiplex(**run_args)
    assert report["status"] == "completed" and report["reconciliation"]["passed"]
    assert report["assigned_expected_pair"] == 4
    assert report["visualization"] == {"status": "failed", "error_type": "RuntimeError"}
    assert any("visualization failed" in w for w in report["warnings"])
    assert not (run_args["output"] / "01_demux_QC/barcode_pair_heatmap.png").exists()
    assert len(list((run_args["output"] / "02_demultiplexed_fastq").glob("*.gz"))) == 24


def test_extreme_offset_warns_without_failing_valid_accounting(run_args):
    run_args["config"] = Config(schema_version=1, demux={"forward_offset": 100000, "reverse_offset": 100000})
    report = demultiplex(**run_args)
    assert report["no_barcode_match"] == report["total_input_read_pairs"] == 10
    assert report["short_barcode_reads"] == {"forward": 10, "reverse": 10}
    assert any("zero assigned" in w for w in report["warnings"])
    assert any("low assigned fraction" in w for w in report["warnings"])
    assert sum("most reads" in w for w in report["warnings"]) == 2


def test_high_unexpected_fraction_warning_is_noncausal(run_args, tmp_path):
    run_args["r1"], run_args["r2"] = write_pairs(tmp_path, [mixed_records()[3]] * 9 + [mixed_records()[0]])
    report = demultiplex(**run_args)
    assert report["unexpected_valid_barcode_pair"] == 9
    assert any("high unexpected valid barcode pair fraction" in w for w in report["warnings"])
    assert all("chimera" not in w.lower() for w in report["warnings"])


@pytest.mark.skipif(os.name != "posix", reason="POSIX process signal integration")
@pytest.mark.parametrize("signum", [signal.SIGTERM, getattr(signal, "SIGKILL", 9)])
def test_cli_signal_keeps_incomplete_data_out_of_final_path(run_args, example_dir, tmp_path, signum):
    # Deterministic handshake after a pair is written; no huge fixture or timing race.
    ready = tmp_path / "ready"
    script = '''
import signal, sys
from pathlib import Path
import peanalyzer.demux as engine
from peanalyzer.cli import main
original = engine.paired_fastq
def wait_after_first(*args):
    for pair in original(*args):
        yield pair
        Path(sys.argv[1]).touch()
        signal.pause()
engine.paired_fastq = wait_after_first
raise SystemExit(main(sys.argv[2:]))
'''
    argv = [sys.executable, "-c", script, str(ready), "demux", "--r1", str(run_args["r1"]), "--r2", str(run_args["r2"]),
            "--samples", str(run_args["samples_path"]), "--config", str(example_dir / "qi_hitom_config.yaml"), "--output", str(run_args["output"])]
    process = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        deadline = time.monotonic() + 15
        while not ready.exists() and process.poll() is None and time.monotonic() < deadline:
            time.sleep(.02)
        assert ready.exists(), "child did not reach the in-progress handshake"
        assert not run_args["output"].exists()
        process.send_signal(signum)
        stdout, stderr = process.communicate(timeout=10)
        assert process.returncode == (143 if signum == signal.SIGTERM else -signal.SIGKILL), stderr
        assert not stdout and not run_args["output"].exists()
        remnants = list(tmp_path.glob(".out.incomplete-*"))
        if signum == signal.SIGTERM:
            assert not remnants
        else:
            assert len(remnants) == 1
            assert not (remnants[0] / "01_demux_QC/demux_summary.json").exists()
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate(timeout=10)
