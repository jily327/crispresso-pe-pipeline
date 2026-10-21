import gzip

import pytest

from peanalyzer.analysis_fastq import PreparationConfig, PreparationError, prepare_analysis_fastqs
from peanalyzer.demux_verify import DemuxVerificationError, sha256_file
from test_demux_verify import completed


@pytest.mark.parametrize("trims", [None, (0, 0), (2, 5)])
def test_preparation_preserves_records_and_sources(completed, tmp_path, trims):
    before = {path: sha256_file(path) for path in completed.rglob("*.gz")}
    config = PreparationConfig() if trims is None else PreparationConfig(r1_analysis_trim_5p=trims[0], r2_analysis_trim_5p=trims[1])
    output = tmp_path / "analysis with spaces"
    report = prepare_analysis_fastqs(completed, output, config)
    expected_trims = trims or (27, 27)
    assert (report["r1_analysis_trim_5p"], report["r2_analysis_trim_5p"]) == expected_trims
    assert report["samples"]["1B"]["pairs"] == 1
    for sample, data in report["samples"].items():
        for mate, trim in enumerate(expected_trims, 1):
            source = completed / f"02_demultiplexed_fastq/{sample}_R{mate}.fastq.gz"
            original = gzip.decompress(source.read_bytes()).splitlines(keepends=True)
            actual = gzip.decompress((output / data["files"][f"r{mate}"]["path"]).read_bytes()).splitlines(keepends=True)
            assert len(actual) == len(original)
            for i in range(0, len(actual), 4):
                assert actual[i] == original[i] and actual[i+2] == original[i+2]
                assert actual[i+1] == original[i+1][trim:]
                assert actual[i+3] == original[i+3][trim:]
                assert len(actual[i+1].rstrip()) == len(actual[i+3].rstrip())
    assert {path: sha256_file(path) for path in before} == before


def test_short_reads_fail_without_published_analysis(completed, tmp_path):
    output = tmp_path / "analysis"
    with pytest.raises(PreparationError, match="exceed trim"):
        prepare_analysis_fastqs(completed, output, PreparationConfig(r1_analysis_trim_5p=1000, r2_analysis_trim_5p=1000))
    assert not output.exists() and not list(tmp_path.glob(".analysis.incomplete-*"))


def test_unverified_run_never_reaches_preparation(completed, tmp_path):
    (completed / "02_demultiplexed_fastq/1B_R1.fastq.gz").unlink()
    with pytest.raises(DemuxVerificationError):
        prepare_analysis_fastqs(completed, tmp_path / "analysis")
    assert not (tmp_path / "analysis").exists()


def test_refuses_to_write_inside_archive(completed):
    with pytest.raises(PreparationError, match="separate"):
        prepare_analysis_fastqs(completed, completed / "analysis")


def test_refuses_archive_via_symlink_parent(completed, tmp_path):
    alias = tmp_path / "archive_alias"
    alias.symlink_to(completed, target_is_directory=True)
    with pytest.raises(PreparationError, match="separate"):
        prepare_analysis_fastqs(completed, alias / "analysis")
