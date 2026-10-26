"""Deterministic, invented FASTQ records; no reads copied from an experiment."""

import gzip
from pathlib import Path

from peanalyzer.barcodes import bundled_catalog, extraction_rules, load_catalog
from peanalyzer.schemas import DemuxConfig


def record(name: str, sequence: str, mate: int, *, crlf: bool = False) -> bytes:
    newline = b"\r\n" if crlf else b"\n"
    quality = "".join(chr(33 + i % 41) for i in range(len(sequence)))
    return newline.join(part.encode() for part in (f"@{name}/{mate} preserved header", sequence, f"+{name}/{mate} plus annotation", quality)) + newline


def mixed_records():
    catalog = load_catalog(bundled_catalog())
    rules = extraction_rules(DemuxConfig(), catalog)
    f, r = catalog.ends["forward"], catalog.ends["reverse"]
    # F1/F5 have distance two; this invented observation is distance one to both.
    tied = "GCTTGCTTT"
    pairs = [
        ("expected_1B", f["F1"], r["RB"], False),
        ("expected_2C", f["F2"], r["RC"], False),
        ("expected_6F", f["F6"], r["RF"], False),
        ("unexpected_F2_RA", f["F2"], r["RA"], False),
        ("forward_only", f["F1"], "AAAAAAAAA", False),
        ("reverse_only", "AAAAAAAAA", r["RC"], False),
        ("unknown_both", "AAAAAAAAA", "AAAAAAAAA", False),
        ("unique_error", "A" + f["F1"][1:], r["RB"], False),
        ("tied_error", tied, r["RB"], False),
        ("mutated_bridge", f["F1"], r["RB"], True),
    ]
    records = []
    for index, (name, forward, reverse, mutate) in enumerate(pairs):
        bridge_f, bridge_r = rules["forward"].bridge, rules["reverse"].bridge
        if mutate:
            bridge_f = "A" + bridge_f[1:]
            bridge_r = "A" + bridge_r[1:]
        # Mixed newline conventions, lowercase payload, varied quality and plus text.
        records.append((record(name, forward + bridge_f + "acgtNNACGT", 1, crlf=index % 2 == 0),
                        record(name, reverse + bridge_r + "tgcaNNACGT", 2, crlf=index % 2 == 0)))
    return records


def write_pairs(directory: Path, pairs, suffix=".fastq.gz"):
    paths = [directory / f"input_R{mate}{suffix}" for mate in (1, 2)]
    for index, path in enumerate(paths):
        data = b"".join(pair[index] for pair in pairs)
        path.write_bytes(gzip.compress(data, mtime=0) if suffix.endswith(".gz") else data)
    return paths
