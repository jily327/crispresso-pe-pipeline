import gzip

import pytest

from peanalyzer.fastq import FastqError, paired_fastq, read_fastq
from synthetic import record, write_pairs


@pytest.mark.parametrize("suffix", [".fq", ".fastq", ".fq.gz", ".fastq.gz"])
def test_supported_inputs_preserve_bytes(tmp_path, suffix):
    pair = (record("read", "acgtnACGT", 1, crlf=True), record("read", "TGCA", 2))
    paths = write_pairs(tmp_path, [pair], suffix)
    parsed = list(paired_fastq(*paths))
    assert [r.to_bytes() for r in parsed[0]] == list(pair)


@pytest.mark.parametrize("bad", [
    b"@x\nACG\n+\n", b"x\nACG\n+\nIII\n", b"@\nACG\n+\nIII\n",
    b"@x\nACG\n-\nIII\n", b"@x\nACG\n+\nII\n", b"@x\nACG\n+\nI I\n",
    b"@x\nAC-\n+\nIII\n", b"@x\n\n+\n\n", b"@x\nACG\nTG\n+\nIIIII\n",
])
def test_bad_fastq_fails_with_record_context(tmp_path, bad):
    path = tmp_path / "bad.fastq"
    path.write_bytes(bad)
    with pytest.raises(FastqError, match="record 1"):
        list(read_fastq(path))


@pytest.mark.parametrize("case", ["mismatch", "short_r2", "short_r1", "wrong_suffix", "wrong_casava"])
def test_pair_errors_are_not_repaired(tmp_path, case):
    forward, reverse = record("x", "ACGT", 1), record("x", "TGCA", 2)
    if case == "mismatch":
        reverse = record("y", "TGCA", 2)
    elif case == "short_r2":
        reverse = b""
    elif case == "short_r1":
        forward = b""
    elif case == "wrong_suffix":
        reverse = record("x", "TGCA", 1)
    else:
        reverse = reverse.replace(b"@x/2 preserved header", b"@x 1:N:0:ABC")
    paths = write_pairs(tmp_path, [(forward, reverse)])
    with pytest.raises(FastqError, match="pair 1"):
        list(paired_fastq(*paths))


def test_casava_ids_and_final_line_without_newline(tmp_path):
    forward = record("x", "ACGT", 1).replace(b"@x/1 preserved header", b"@x 1:N:0:ABC")
    reverse = record("x", "ACGT", 2).replace(b"@x/2 preserved header", b"@x 2:N:0:ABC").rstrip(b"\n")
    paths = write_pairs(tmp_path, [(forward, reverse)])
    pair = list(paired_fastq(*paths))[0]
    assert pair[1].to_bytes() == reverse


def test_parser_streams_valid_record_before_later_error(tmp_path):
    path = tmp_path / "stream.fastq"
    first = record("x", "ACGT", 1)
    path.write_bytes(first + b"@bad\n")
    reader = read_fastq(path)
    assert next(reader).to_bytes() == first
    with pytest.raises(FastqError, match="record 2"):
        next(reader)


def test_corrupt_gzip_rejected(tmp_path):
    path = tmp_path / "corrupt.fq.gz"
    path.write_bytes(gzip.compress(record("x", "ACGT", 1))[:-5])
    with pytest.raises(FastqError):
        list(read_fastq(path))


def test_empty_normalized_identifier_rejected(tmp_path):
    paths = write_pairs(tmp_path, [(record("", "ACGT", 1), record("", "ACGT", 2))])
    with pytest.raises(FastqError, match="empty normalized read identifier"):
        list(paired_fastq(*paths))
