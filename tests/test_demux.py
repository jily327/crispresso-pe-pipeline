import csv
import gzip
import json
import subprocess
import sys
from collections import Counter

import pytest
from PIL import Image

from peanalyzer.barcodes import bundled_catalog
from peanalyzer.demux import CATEGORIES, DemuxError, demultiplex, reconcile
from peanalyzer.fastq import FastqError
from peanalyzer.schemas import Config
from synthetic import mixed_records, record, write_pairs


@pytest.mark.parametrize("mismatches,counts,indices", [
    (0, [4, 1, 0, 1, 3, 1], {"1B": [0, 9], "2C": [1], "6F": [2]}),
    (1, [5, 1, 1, 1, 1, 1], {"1B": [0, 7, 9], "2C": [1], "6F": [2]}),
])
def test_mixed_fixture_outputs_and_reconciliation(tmp_path, example_dir, mismatches, counts, indices):
    records = mixed_records()
    r1, r2 = write_pairs(tmp_path, records)
    output = tmp_path / "results"
    report = demultiplex(r1=r1, r2=r2, samples_path=example_dir / "ev_only_1005_samples.csv",
                         config=Config(schema_version=1, demux={"max_mismatches": mismatches}), output=output)
    assert report["total_input_read_pairs"] == 10
    assert [report[category] for category in CATEGORIES] == counts
    assert report["reconciliation"]["passed"] is True
    assert all(report["reconciliation"]["checks"].values())
    assert report["assignment_percentage"] == counts[0] * 10
    assert sum(report["per_sample_assigned_read_pairs"].values()) == counts[0]
    assert report["barcode_bridge_qc"]["forward"]["bridge_mismatch"] == 1
    assert report["barcode_bridge_qc"]["reverse"]["bridge_mismatch"] == 1
    for name, metadata in report["input_provenance"].items():
        assert len(metadata["sha256"]) == 64, name
    assert len(list((output / "02_demultiplexed_fastq").glob("*.gz"))) == 24
    all_headers = []
    for sample, count in report["per_sample_assigned_read_pairs"].items():
        selected = indices.get(sample, [])
        assert count == len(selected)
        for mate in (1, 2):
            path = output / "02_demultiplexed_fastq" / f"{sample}_R{mate}.fastq.gz"
            actual = gzip.decompress(path.read_bytes())
            assert actual == b"".join(records[index][mate - 1] for index in selected)
            if mate == 1:
                all_headers.extend(actual.splitlines()[::4])
    assert len(all_headers) == len(set(all_headers)) == counts[0]
    qc = output / "01_demux_QC"
    with (qc / "barcode_pair_matrix.csv").open() as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 12
    assert len(rows[0]) == 9
    matrix = {row["forward_barcode_id"]: row for row in rows}
    assert int(matrix["F2"]["RA"]) == 1  # unexpected is retained
    assert int(matrix["F12"]["RH"]) == 0  # zero cells are retained
    assert sum(int(value) for row in rows for key, value in row.items() if key != "forward_barcode_id") == counts[0] + counts[1]
    with (qc / "barcode_counts.csv").open() as handle:
        barcode_rows = list(csv.DictReader(handle))
    assert len(barcode_rows) == 20
    f1 = next(row for row in barcode_rows if row["barcode_id"] == "F1")
    assert int(f1["corrected_read_pairs"]) == mismatches
    assert sum(int(row["recognized_read_pairs"]) for row in barcode_rows if row["direction"] == "forward") == 6 + mismatches
    assert sum(int(row["recognized_read_pairs"]) for row in barcode_rows if row["direction"] == "reverse") == 8
    assert json.loads((qc / "demux_summary.json").read_text()) == report
    with Image.open(qc / "barcode_pair_heatmap.png") as image:
        assert image.format == "PNG"
        assert image.width > 0 and image.height > 0
        image.verify()


@pytest.mark.parametrize("suffix", [".fastq", ".fq", ".fq.gz"])
def test_plain_and_compressed_demux(tmp_path, example_dir, suffix):
    r1, r2 = write_pairs(tmp_path, mixed_records()[:1], suffix)
    report = demultiplex(r1=r1, r2=r2, samples_path=example_dir / "ev_only_1005_samples.csv", config=Config(schema_version=1), output=tmp_path / "out")
    assert report["assigned_expected_pair"] == 1


def test_bridge_diagnostics_can_be_disabled_without_changing_assignment(tmp_path, example_dir):
    r1, r2 = write_pairs(tmp_path, mixed_records()[-1:])
    report = demultiplex(r1=r1, r2=r2, samples_path=example_dir / "ev_only_1005_samples.csv", config=Config(schema_version=1, demux={"bridge_qc": False}), output=tmp_path / "out")
    assert report["assigned_expected_pair"] == 1
    assert not any(key.startswith("bridge_") for key in report["barcode_bridge_qc"]["forward"])


@pytest.mark.parametrize("trim_bridge,removed", [(False, 9), (True, 27)])
def test_only_explicit_trimming_changes_sequence_and_quality(tmp_path, example_dir, trim_bridge, removed):
    records = mixed_records()[:1]
    r1, r2 = write_pairs(tmp_path, records)
    output = tmp_path / "out"
    demultiplex(r1=r1, r2=r2, samples_path=example_dir / "ev_only_1005_samples.csv", config=Config(schema_version=1, demux={"trim_barcodes": True, "trim_bridges": trim_bridge}), output=output)
    for mate in (1, 2):
        lines = records[0][mate - 1].splitlines(keepends=True)
        expected = lines[0] + lines[1][removed:] + lines[2] + lines[3][removed:]
        assert gzip.decompress((output / "02_demultiplexed_fastq" / f"1B_R{mate}.fastq.gz").read_bytes()) == expected


def test_lru_reopen_never_truncates_or_duplicates_records(tmp_path, example_dir):
    records = mixed_records()
    selection = [records[0], records[1], records[9]]
    r1, r2 = write_pairs(tmp_path, selection)
    output = tmp_path / "out"
    demultiplex(r1=r1, r2=r2, samples_path=example_dir / "ev_only_1005_samples.csv", config=Config(schema_version=1, demux={"max_open_sample_pairs": 1}), output=output)
    for mate in (1, 2):
        actual = gzip.decompress((output / "02_demultiplexed_fastq" / f"1B_R{mate}.fastq.gz").read_bytes())
        assert actual == records[0][mate - 1] + records[9][mate - 1]


def test_gzip_bytes_are_reproducible(tmp_path, example_dir):
    r1, r2 = write_pairs(tmp_path, mixed_records()[:1])
    for name in ("first", "second"):
        demultiplex(r1=r1, r2=r2, samples_path=example_dir / "ev_only_1005_samples.csv", config=Config(schema_version=1), output=tmp_path / name)
    for mate in (1, 2):
        filename = f"02_demultiplexed_fastq/1B_R{mate}.fastq.gz"
        assert (tmp_path / "first" / filename).read_bytes() == (tmp_path / "second" / filename).read_bytes()


def test_custom_explicit_sequences_offsets_and_reverse_orientation(tmp_path, write_csv):
    rows = [{"sample_name": "custom", "barcode_id": "A", "forward_barcode": "ACG", "reverse_barcode": "ATGCC"}]
    samples = write_csv("samples.csv", rows)
    records = [(record("x", "TTACGTTTT", 1), record("x", "AGGCATTTTT", 2))]
    r1, r2 = write_pairs(tmp_path, records)
    config = Config(schema_version=1, demux={"profile": "custom", "forward_offset": 2, "reverse_offset": 1, "reverse_barcode_orientation": "reverse_complement"})
    output = tmp_path / "out"
    report = demultiplex(r1=r1, r2=r2, samples_path=samples, config=config, output=output)
    assert report["assigned_expected_pair"] == 1
    assert gzip.decompress((output / "02_demultiplexed_fastq/A_R2.fastq.gz").read_bytes()) == records[0][1]


def test_variable_length_custom_barcodes(tmp_path, write_csv):
    samples = write_csv("samples.csv", [
        {"sample_name": "a", "barcode_id": "A", "forward_barcode": "ACG", "reverse_barcode": "TTAA"},
        {"sample_name": "b", "barcode_id": "B", "forward_barcode": "GGGGG", "reverse_barcode": "CC"},
    ])
    records = [(record("x", "ACGTTTTTT", 1), record("x", "TTAATTTT", 2)),
               (record("y", "GGGGGTTTT", 1), record("y", "CCTTTTTT", 2))]
    r1, r2 = write_pairs(tmp_path, records)
    report = demultiplex(r1=r1, r2=r2, samples_path=samples, config=Config(schema_version=1, demux={"profile": "custom"}), output=tmp_path / "out")
    assert report["per_sample_assigned_read_pairs"] == {"A": 1, "B": 1}


def test_short_motif_is_unknown_not_dropped(tmp_path, example_dir):
    records = [(record("x", "GCTT", 1), mixed_records()[0][1].replace(b"expected_1B", b"x"))]
    r1, r2 = write_pairs(tmp_path, records)
    report = demultiplex(r1=r1, r2=r2, samples_path=example_dir / "ev_only_1005_samples.csv", config=Config(schema_version=1), output=tmp_path / "out")
    assert report["reverse_only"] == 1
    assert report["total_input_read_pairs"] == 1


def test_empty_input_has_explicit_undefined_percentage_and_empty_fastqs(tmp_path, example_dir):
    r1, r2 = write_pairs(tmp_path, [])
    output = tmp_path / "out"
    report = demultiplex(r1=r1, r2=r2, samples_path=example_dir / "ev_only_1005_samples.csv", config=Config(schema_version=1), output=output)
    assert report["assignment_percentage"] is None
    assert report["warnings"]
    assert report["reconciliation"]["passed"]
    assert all(gzip.decompress(path.read_bytes()) == b"" for path in (output / "02_demultiplexed_fastq").glob("*.gz"))


@pytest.mark.parametrize("kind", ["total", "sample", "writer", "matrix", "negative", "extra_category"])
def test_reconciliation_must_fail_on_inconsistent_accounting(kind):
    categories = dict.fromkeys(CATEGORIES, 0)
    categories["assigned_expected_pair"] = 1
    total, samples, written, matrix = 1, {"A": 1}, {"A": 1}, Counter({("F", "R"): 1})
    if kind == "total":
        total = 2
    elif kind == "sample":
        samples["A"] = 0
    elif kind == "writer":
        written["A"] = 2
    elif kind == "matrix":
        matrix["F", "R"] = 0
    elif kind == "negative":
        categories["no_barcode_match"] = -1
    else:
        categories["extra"] = 0
    with pytest.raises(DemuxError, match="reconciliation failed"):
        reconcile(total, categories, samples, written, matrix)


@pytest.mark.parametrize("failure", ["read_id", "reconciliation", "writer_loss", "writer_duplicate", "heatmap"])
def test_run_failure_leaves_no_success_or_partial_sample_outputs(tmp_path, example_dir, monkeypatch, failure):
    import peanalyzer.demux as module
    records = mixed_records()[:2]
    if failure == "read_id":
        records[1] = (records[1][0], records[1][1].replace(b"expected_2C", b"WRONG_ID"))
    elif failure == "reconciliation":
        def fail(*args):
            raise DemuxError("reconciliation failed: injected mismatch")
        monkeypatch.setattr(module, "reconcile", fail)
    elif failure == "writer_loss":
        monkeypatch.setattr(module.SampleWriter, "write", lambda *args: None)
    elif failure == "writer_duplicate":
        original = module.SampleWriter.write
        def twice(*args):
            original(*args)
            original(*args)
        monkeypatch.setattr(module.SampleWriter, "write", twice)
    else:
        def fail(*args):
            raise OSError("heatmap write failed")
        monkeypatch.setattr(module, "write_qc_tables", fail)
    r1, r2 = write_pairs(tmp_path, records)
    output = tmp_path / "out"
    with pytest.raises((DemuxError, FastqError, OSError)):
        demultiplex(r1=r1, r2=r2, samples_path=example_dir / "ev_only_1005_samples.csv", config=Config(schema_version=1), output=output)
    assert not output.exists()


def test_preexisting_output_is_never_overwritten(tmp_path, example_dir):
    r1, r2 = write_pairs(tmp_path, mixed_records()[:1])
    output = tmp_path / "out"
    output.mkdir()
    sentinel = output / "user_file.txt"
    sentinel.write_text("keep")
    with pytest.raises(DemuxError, match="already exists"):
        demultiplex(r1=r1, r2=r2, samples_path=example_dir / "ev_only_1005_samples.csv", config=Config(schema_version=1), output=output)
    assert sentinel.read_text() == "keep"


def test_demux_cli_with_custom_catalog_argument(tmp_path, example_dir):
    r1, r2 = write_pairs(tmp_path, mixed_records())
    output = tmp_path / "out"
    result = subprocess.run([sys.executable, "-m", "peanalyzer", "demux", "--r1", str(r1), "--r2", str(r2),
                             "--samples", str(example_dir / "ev_only_1005_samples.csv"), "--barcodes", str(bundled_catalog()),
                             "--config", str(example_dir / "qi_hitom_config.yaml"), "--output", str(output)], text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["assigned_expected_pair"] == 4
    assert "reconciliations passed" in result.stderr
    assert gzip.decompress((output / "02_demultiplexed_fastq/1B_R1.fastq.gz").read_bytes()) == mixed_records()[0][0] + mixed_records()[9][0]


def test_demux_cli_error_has_nonzero_exit(tmp_path, example_dir):
    result = subprocess.run([sys.executable, "-m", "peanalyzer", "demux", "--r1", str(tmp_path / "missing_R1.fq"), "--r2", str(tmp_path / "missing_R2.fq"),
                             "--samples", str(example_dir / "ev_only_1005_samples.csv"), "--config", str(example_dir / "qi_hitom_config.yaml"),
                             "--output", str(tmp_path / "out")], text=True, capture_output=True)
    assert result.returncode == 2
    assert "Demultiplexing failed" in result.stderr
    assert "Traceback" not in result.stderr
    assert not result.stdout


def test_resolved_config_round_trip_preserves_profile_checks(tmp_path, example_dir):
    r1, r2 = write_pairs(tmp_path, mixed_records()[-1:])
    first = demultiplex(r1=r1, r2=r2, samples_path=example_dir / "ev_only_1005_samples.csv", config=Config(schema_version=1), output=tmp_path / "first")
    second = demultiplex(r1=r1, r2=r2, samples_path=example_dir / "ev_only_1005_samples.csv", config=Config.model_validate(first["resolved_config"]), output=tmp_path / "second")
    assert first["barcode_bridge_qc"] == second["barcode_bridge_qc"]
    assert first["extraction_profile"] == second["extraction_profile"]
    assert first["resolved_config_sha256"] == second["resolved_config_sha256"]


def test_explicit_custom_catalog_runs_with_new_ids(tmp_path, write_csv):
    catalog = write_csv("catalog.csv", [
        {"direction": "forward", "barcode_id": "F13", "sequence": "GCTTAAAAT"},
        {"direction": "reverse", "barcode_id": "RI", "sequence": "CTGTAAAAT"},
    ])
    samples = write_csv("samples.csv", [{"sample_name": "new", "barcode_id": "13I", "forward_barcode_id": "F13", "reverse_barcode_id": "RI"}])
    pair = (record("x", "GCTTAAAATACGT", 1), record("x", "CTGTAAAATACGT", 2))
    r1, r2 = write_pairs(tmp_path, [pair])
    output = tmp_path / "out"
    report = demultiplex(r1=r1, r2=r2, samples_path=samples, barcodes_path=catalog, config=Config(schema_version=1), output=output)
    assert report["per_sample_assigned_read_pairs"] == {"13I": 1}
    assert report["barcode_bridge_qc"]["forward"]["bridge_short"] == 1
    assert gzip.decompress((output / "02_demultiplexed_fastq/13I_R1.fastq.gz").read_bytes()) == pair[0]


def test_changed_input_prevents_completed_state(tmp_path, example_dir, monkeypatch):
    import peanalyzer.demux as module
    r1, r2 = write_pairs(tmp_path, mixed_records()[:1])
    original = module.paired_fastq
    def changing_input(*args):
        yield from original(*args)
        r1.write_bytes(r1.read_bytes() + b"changed")
    monkeypatch.setattr(module, "paired_fastq", changing_input)
    output = tmp_path / "out"
    with pytest.raises(DemuxError, match="input changed"):
        demultiplex(r1=r1, r2=r2, samples_path=example_dir / "ev_only_1005_samples.csv", config=Config(schema_version=1), output=output)
    assert not output.exists()
