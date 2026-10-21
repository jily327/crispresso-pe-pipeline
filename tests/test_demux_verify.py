import gzip
import json

import pytest

from peanalyzer.demux import demultiplex
from peanalyzer.demux_verify import DemuxVerificationError, sha256_file, verify_demux_output
from peanalyzer.schemas import Config
from synthetic import mixed_records, write_pairs


@pytest.fixture
def completed(tmp_path, example_dir):
    r1, r2 = write_pairs(tmp_path, mixed_records()[:2])
    output = tmp_path / "completed"
    demultiplex(r1=r1, r2=r2, samples_path=example_dir / "ev_only_1005_samples.csv", config=Config(schema_version=1), output=output)
    return output


def save(root, summary):
    (root / "01_demux_QC/demux_summary.json").write_text(json.dumps(summary))


def refresh(root, summary, relative):
    file = root / relative
    summary["output_files"][relative].update(sha256=sha256_file(file), size_bytes=file.stat().st_size)
    save(root, summary)


def test_completed_and_zero_sample_pass(completed):
    result = verify_demux_output(completed)
    assert sum(sample.pairs for sample in result.samples) == 2
    assert len(result.samples) == 12
    assert sum(sample.pairs == 0 for sample in result.samples) == 10


@pytest.mark.parametrize("case", ["flip", "append", "truncate", "delete", "mate_count", "mate_id", "status", "reconciliation",
                                  "missing_check", "matrix", "mapping", "size", "hash", "missing_csv", "schema", "inventory", "extra_file"])
def test_tamper_rejected(completed, case):
    summary = json.loads((completed / "01_demux_QC/demux_summary.json").read_text())
    relative = "02_demultiplexed_fastq/1B_R1.fastq.gz"
    file = completed / relative
    if case == "flip":
        data = bytearray(file.read_bytes()); data[15] ^= 1; file.write_bytes(data)
    elif case in ("append", "mate_count"):
        file.write_bytes(file.read_bytes() + gzip.compress(gzip.decompress(file.read_bytes())))
    elif case == "truncate":
        file.write_bytes(file.read_bytes()[:-6])
    elif case == "delete":
        file.unlink()
    elif case == "mate_id":
        file.write_bytes(gzip.compress(gzip.decompress(file.read_bytes()).replace(b"expected_1B", b"other_id")))
    elif case == "status": summary["status"] = "running"
    elif case == "reconciliation": summary["reconciliation"]["passed"] = False
    elif case == "missing_check": summary["reconciliation"]["checks"].pop("on_disk_matrix_matches_counts")
    elif case == "matrix":
        relative = "01_demux_QC/barcode_pair_matrix.csv"
        file = completed / relative
        file.write_text(file.read_text().replace("F1,0,1,", "F1,0,9,"))
    elif case == "mapping": summary["output_files"][relative]["sample_id"] = "2C"
    elif case == "size": summary["output_files"][relative]["size_bytes"] += 1
    elif case == "hash": summary["output_files"][relative]["sha256"] = "0" * 64
    elif case == "missing_csv": (completed / "01_demux_QC/barcode_counts.csv").unlink()
    elif case == "schema": summary["schema_version"] = 1
    elif case == "inventory": summary["output_files"]["../outside"] = summary["output_files"].pop(relative)
    else: (completed / "02_demultiplexed_fastq/extra.fastq.gz").write_bytes(gzip.compress(b""))
    # Refresh hashes for structural adversaries: prove rejection is independent of hashes.
    if case in ("mate_count", "mate_id", "truncate", "matrix"):
        refresh(completed, summary, relative)
    else:
        save(completed, summary)
    with pytest.raises(DemuxVerificationError):
        verify_demux_output(completed)


def test_staging_with_completed_summary_rejected(completed):
    staged = completed.with_name(".completed.incomplete-test")
    completed.rename(staged)
    with pytest.raises(DemuxVerificationError, match="staging"):
        verify_demux_output(staged)


def test_recount_rejects_both_mates_appended_with_refreshed_hashes(completed):
    summary = json.loads((completed / "01_demux_QC/demux_summary.json").read_text())
    for mate in (1, 2):
        name = f"02_demultiplexed_fastq/1B_R{mate}.fastq.gz"
        path = completed / name
        path.write_bytes(path.read_bytes() * 2)
        refresh(completed, summary, name)
    with pytest.raises(DemuxVerificationError, match="record count"):
        verify_demux_output(completed)
