"""Strict four-line FASTQ streaming, preserving original record bytes."""

import gzip
import zlib
from dataclasses import dataclass
from itertools import zip_longest
from pathlib import Path
from typing import Iterator


class FastqError(ValueError):
    pass


def line_content(line: bytes) -> bytes:
    return line.rstrip(b"\r\n")


@dataclass(frozen=True)
class FastqRecord:
    header: bytes
    sequence_line: bytes
    plus: bytes
    quality_line: bytes

    @property
    def sequence(self) -> bytes:
        return line_content(self.sequence_line)

    def to_bytes(self) -> bytes:
        return self.header + self.sequence_line + self.plus + self.quality_line

    def trimmed(self, count: int) -> "FastqRecord":
        if count >= len(self.sequence):
            raise FastqError("configured trimming would produce an empty read")
        return FastqRecord(self.header, self.sequence_line[count:], self.plus, self.quality_line[count:])


def read_fastq(path: Path) -> Iterator[FastqRecord]:
    opener = gzip.open if path.suffix.lower() == ".gz" else open
    number = 0
    try:
        with opener(path, "rb") as handle:
            while True:
                header = handle.readline()
                if not header:
                    break
                number += 1
                seq, plus, quality = (handle.readline() for _ in range(3))
                if not seq or not plus or not quality:
                    raise FastqError("truncated four-line record")
                if not header.startswith(b"@") or not line_content(header)[1:].split():
                    raise FastqError("missing @ read identifier")
                if not plus.startswith(b"+"):
                    raise FastqError("missing + line (wrapped FASTQ is unsupported)")
                sequence, scores = line_content(seq), line_content(quality)
                if not sequence or set(sequence.upper()) - set(b"ACGTRYSWKMBDHVN"):
                    raise FastqError("sequence must contain nonempty IUPAC DNA")
                if len(sequence) != len(scores):
                    raise FastqError("sequence and quality lengths differ")
                if any(score < 33 or score > 126 for score in scores):
                    raise FastqError("quality characters must be printable ASCII (33..126)")
                yield FastqRecord(header, seq, plus, quality)
    except (OSError, EOFError, zlib.error, FastqError) as exc:
        raise FastqError(f"{path}: record {number or 1}: {exc}") from exc


def read_id(record: FastqRecord, mate: int) -> bytes:
    parts = line_content(record.header)[1:].split()
    name = parts[0]
    if name.endswith((b"/1", b"/2")):
        if name[-1:] != str(mate).encode():
            raise FastqError(f"wrong mate suffix on R{mate}: {name!r}")
        name = name[:-2]
    if not name:
        raise FastqError(f"empty normalized read identifier on R{mate}")
    if len(parts) > 1 and parts[1].startswith((b"1:", b"2:")):
        if parts[1][:1] != str(mate).encode():
            raise FastqError(f"wrong CASAVA mate annotation on R{mate}: {parts[1]!r}")
    return name


def paired_fastq(r1: Path, r2: Path) -> Iterator[tuple[FastqRecord, FastqRecord]]:
    left, right = read_fastq(r1), read_fastq(r2)
    try:
        for index, (forward, reverse) in enumerate(zip_longest(left, right), 1):
            if forward is None or reverse is None:
                raise FastqError(f"pair {index}: R1/R2 record counts differ ({r1}, {r2})")
            try:
                if read_id(forward, 1) != read_id(reverse, 2):
                    raise FastqError(f"R1/R2 read IDs differ: {forward.header.rstrip()!r} vs {reverse.header.rstrip()!r}")
            except FastqError as exc:
                raise FastqError(f"pair {index}: {exc}") from exc
            yield forward, reverse
    finally:
        left.close()
        right.close()
