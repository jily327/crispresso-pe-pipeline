"""Artificial, deterministic routing ground truth; no experimental targets."""

import csv
import gzip
import hashlib
import json
import random
from pathlib import Path

from peanalyzer.schemas import Target, reverse_complement

DIAGNOSTIC_POSITIONS = (40, 80, 165, 205)  # zero-based
EDIT_POSITION = 122
GUIDE_START, GUIDE_END = 95, 115


def changed(base):
    return {"A": "C", "C": "G", "G": "T", "T": "A"}[base]


def design(*, guide_mismatch=False) -> dict:
    rng = random.Random(20261021)
    bases = []
    for _ in range(240):
        choices = [b for b in "ACGT" if len(bases) < 3 or bases[-3:] != [b] * 3]
        bases.append(rng.choice(choices))
    wt1 = "".join(bases)
    copy2 = list(wt1)
    positions = (*DIAGNOSTIC_POSITIONS, 100) if guide_mismatch else DIAGNOSTIC_POSITIONS
    for position in positions:
        copy2[position] = changed(copy2[position])
    wt2 = "".join(copy2)
    pe1, pe2 = list(wt1), list(wt2)
    pe1[EDIT_POSITION] = pe2[EDIT_POSITION] = changed(wt1[EDIT_POSITION])
    spacer = wt1[GUIDE_START:GUIDE_END]
    pe1, pe2 = "".join(pe1), "".join(pe2)
    extension = reverse_complement(pe1[105:145])
    targets = [Target(target_name="SYN", copy_name=copy, wt_sequence=wt, prime_edited_sequence=pe,
                      pegRNA_spacer=spacer, pegRNA_extension=extension)
               for copy, wt, pe in (("copy1", wt1, pe1), ("copy2", wt2, pe2))]
    description = {"version": "synthetic_homeologs_v1", "seed": 20261021, "length": 240,
                   "coordinate_convention": "zero-based", "diagnostic_positions": sorted(positions),
                   "intended_edit": {"position": EDIT_POSITION, "from": wt1[EDIT_POSITION], "to": pe1[EDIT_POSITION]},
                   "spacer_interval": [GUIDE_START, GUIDE_END], "guide_mismatch": guide_mismatch,
                   "targets": [target.model_dump() for target in targets]}
    description["design_sha256"] = hashlib.sha256(json.dumps(description, sort_keys=True).encode()).hexdigest()
    return description


def write_synthetic_run(directory: Path, *, guide_mismatch=False) -> tuple[list[Target], list[dict]]:
    directory.mkdir(parents=True, exist_ok=False)
    description = design(guide_mismatch=guide_mismatch)
    targets = [Target.model_validate(row) for row in description["targets"]]
    truth, sequences = [], []
    for target, amounts in zip(targets, ((80, 60, 12, 12, 12, 12, 10), (50, 40, 8, 8, 8, 8, 10))):
        for kind, count in zip(("WT", "precise_PE", "PE_extra_substitution", "indel", "ordinary_error", "diagnostic_error", "missing_diagnostics"), amounts):
            sequence = target.prime_edited_sequence if kind in ("precise_PE", "PE_extra_substitution") else target.wt_sequence
            if kind in ("PE_extra_substitution", "ordinary_error"):
                sequence = sequence[:55] + changed(sequence[55]) + sequence[56:]
            elif kind == "indel":
                sequence = sequence[:150] + sequence[151:]  # unintended 1-nt deletion away from diagnostics
            elif kind == "diagnostic_error":
                sequence = sequence[:40] + changed(sequence[40]) + sequence[41:]
            elif kind == "missing_diagnostics":
                sequence = sequence[115:155]  # no distinguishing sites, even in mismatch experiment
            for index in range(count):
                name = f"{target.copy_name}_{kind}_{index:04d}"
                truth.append({"read_id": name, "ground_truth_class": kind, "ground_truth_copy": target.amplicon_id,
                              "informative": kind != "missing_diagnostics", "fragment_length": len(sequence)})
                sequences.append(sequence)
    # Equal-score mosaic: two diagnostic alleles from each copy. No unique copy origin.
    shared = list(targets[0].wt_sequence)
    for pos in DIAGNOSTIC_POSITIONS[2:]:
        shared[pos] = targets[1].wt_sequence[pos]
    for index in range(20):
        truth.append({"read_id": f"compatible_both_{index:04d}", "ground_truth_class": "compatible_both",
                      "ground_truth_copy": "ambiguous", "informative": False, "fragment_length": len(shared)})
        sequences.append("".join(shared))
    # Motif/bridge prefixes are fixture data, separate from preparation control flow.
    prefixes = ("GCTTGCGTTGGAGTGAGTACGGTGTGC", "CTGTGTAGTGAGTTGGATGCTGGATGG")
    for mate in (1, 2):
        with gzip.open(directory / f"raw_R{mate}.fastq.gz", "wb") as handle:
            for row, sequence in zip(truth, sequences):
                length = min(150, len(sequence))
                read = sequence[:length] if mate == 1 else reverse_complement(sequence[-length:])
                read = prefixes[mate - 1] + read
                # Use CASAVA annotation: fastp retains the read identifier verbatim.
                handle.write(f"@{row['read_id']} {mate}:N:0:SYN\n{read}\n+\n{'I' * len(read)}\n".encode())
    with (directory / "synthetic_ground_truth.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(truth[0])); writer.writeheader(); writer.writerows(truth)
    (directory / "synthetic_design.json").write_text(json.dumps(description, indent=2, sort_keys=True) + "\n")
    (directory / "samples.csv").write_text("sample_name,barcode_id,forward_barcode_id,reverse_barcode_id\nsynthetic,1B,F1,RB\n")
    return targets, truth
