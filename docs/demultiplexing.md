# Milestone 2.1: Hi-TOM paired-end demultiplexing

This layer assigns samples from inline barcodes and produces barcode QC. It does
not merge reads, identify targets/homeologs, invoke CRISPResso, compute editing
efficiency, perform statistics or generate the final HTML report.

## Verified layout and defaults

The user inspected a Qi-Lab/Azenta dataset, `EV_only_1005_R1.fastq.gz` and
`EV_only_1005_R2.fastq.gz`, with 108,232 synchronized read pairs. The verified
layout is:

```text
R1: 5' [GCTT + four variable bases + T] [GGAGTGAGTACGGTGTGC] [amplicon...] 3'
R2: 5' [CTGT + four variable bases + T] [GAGTTGGATGCTGGATGG] [amplicon...] 3'
```

Both full motifs are 9 nt at sequence offset 0. For example, R1
`GCTTGTAGTGGAGTGAGTACGGTGTGC...` is F2 then the forward bridge; R2
`CTGTACGCTGAGTTGGATGCTGGATGG...` is RC then the reverse bridge. There is no
arbitrary-position search and no matching on just the four variable bases.

The named `qi_hitom_v1` profile is stored in
`src/peanalyzer/profiles/qi_hitom_v1.yaml`. Its motifs are stored once, as data,
in `src/peanalyzer/barcode_sets/qi_hitom_v1.csv`. Both resources are included in
source distributions and wheels. These observations describe this protocol/run,
not every future sequencing protocol.

No barcode or bridge is trimmed by default. Matching uses uppercase sequence
views; the original record bytes, including case, line endings, headers, plus
annotations and quality characters, are retained in sample FASTQs. Bridge and
prefix/suffix checks are diagnostics; assignment uses the entire barcode motif.
A mutated bridge never excludes an otherwise assigned pair.

## Catalog and sample schemas

Catalog CSV columns are exactly `direction,barcode_id,sequence`:

```csv
direction,barcode_id,sequence
forward,F1,GCTTGCGTT
reverse,RB,CTGTGTAGT
```

The bundled catalog contains all 12 forward (F1–F12) and 8 reverse (RA–RH) motifs
provided by the user. `direction` must be `forward` or `reverse`; IDs use the
existing safe identifier grammar and are globally unique. Sequences are nonempty
ACGT (case-normalized), unique within each direction. Each catalog must contain
both directions. ID prefixes are not parsed: adding F13/RI or other names requires
only data changes. Use the **full** run catalog, including barcodes absent from
expected sample combinations, to recognize unexpected valid combinations.

Minimal demux sample sheet:

```csv
sample_name,barcode_id,forward_barcode_id,reverse_barcode_id
ePPEmax-v2-EV_leaf1,1B,F1,RB
ePPEmax-v2-EV_leaf2,2C,F2,RC
```

`barcode_id` is the sample output stem (e.g. `1B`), distinct from the two catalog
IDs. All sample names, output stems and resolved F/R pairs must be unique.
Output filenames must also be unique after `casefold()`, on every platform.
Identifiers are validated, never lossily sanitized; surrounding CSV whitespace
is normalized before the uniqueness checks. `sample_name` is not a filename.
Forward/reverse IDs must exist on the correct catalog side. Optional
`forward_barcode`/`reverse_barcode` columns may provide explicit sequences. If ID
and sequence are both supplied, disagreement is an error. Empty optional cells
mean absent. Both the bundled catalog and a supplied `--barcodes` catalog are
authoritative: an explicit sequence without an ID must match an existing entry.
Unknown sequences cannot extend that catalog. Only `profile: custom` with no
`--barcodes` builds a catalog from explicit sample sequences, using deterministic
`forward_<sequence>` / `reverse_<sequence>` IDs. These modes never mix implicitly.

Full Milestone 1 sample sheets remain supported. If any biological metadata
columns are present, the full biological schema is required. The minimal sheet
does not invent dpi, treatment, replicate, pairing or block values; the controls
in the supplied example are preserved as named samples without assumptions.
The `validate` command retains full metadata/target validation and accepts
`--barcodes` for full sheets using catalog IDs; `demux` validates minimal sheets
itself and requires no targets.csv.

## Extraction and matching

`config.yaml` retains `schema_version: 1` with additive demux settings. Package
version 0.2 changes the default `trim_barcodes` from the earlier proposed true
to **false**, as explicitly requested for the verified protocol. An existing
explicit `trim_barcodes: true` is still honored. Other M1 metadata rules remain.

For future/custom protocols, select `demux.profile: custom` and supply a catalog
with `--barcodes`, or explicit sequences in the sample sheet. Configuration:

- `forward_offset`, `reverse_offset`: zero-based, nonnegative starts (default 0).
- `forward_length`, `reverse_length`: positive extraction lengths. Explicit
  lengths must agree with every catalog entry on that side. If unset in custom
  mode, infer the single motif length on each side. Equal lengths within each
  direction are required, including in catalog-free mode; F and R may differ.
- `reverse_barcode_orientation`: `as_read` (default) or `reverse_complement`.
  Only the extracted R2 motif is reverse-complemented for comparison; output
  reads and bridges stay in raw-read orientation.
- `forward_bridge`, `reverse_bridge`: optional expected DNA in raw-read
  orientation; explicit null disables that bridge. These override profile data.
- `max_mismatches`: nonnegative Hamming threshold **per end**, default 0.
  Execution rejects k >= the minimum same-side pairwise Hamming distance or
  barcode length. When 2*k >= that distance, it warns about overlapping
  neighborhoods. A singleton has no pairwise distance but still requires k < length.
- `bridge_qc`: true by default. Diagnostics are recorded after recognized motifs.
- `trim_barcodes`: false; true removes sequence/quality through offset+motif.
- `trim_bridges`: false; true additionally removes the configured bridge length,
  requires `trim_barcodes: true` and bridges on both ends. This is fixed-position
  trimming even for a mutated bridge; a resulting empty read fails the run.
- `max_open_sample_pairs`: positive limit, default 32, for output handle reuse.
- `ambiguous_policy`: only `unassigned`; no rescue mode is implemented.

Omitted fields use profile defaults; explicit fields override them. The resolved
rules are written to the summary. Bridge sequences and motif structures are not
Python control-flow constants.

Each end is matched independently against **all** catalog entries on that side.
Choose a uniquely nearest equal-length sequence within the threshold. A tie at
the best distance is ambiguous, even if only one candidate would make an expected
sample pair. An exact match wins over a more distant in-threshold candidate.
Motifs containing unresolved/non-ACGT bases (including N) or lacking sufficient
read length are unknown, never rescued as mismatches. No barcode indel matching
or quality-weighted correction is implemented. Quality strings are validated
and preserved, but their scores do not affect barcode identity.

Several Qi motifs differ by two bases. For example, F1 `GCTTGCGTT` and F5
`GCTTGCTCT` are both one mismatch from `GCTTGCTTT`. With tolerance 1 this
observation must remain ambiguous. Both Qi catalog sides have minimum Hamming
distance 2: k=0 is the production default, k=1 is permitted with a risk warning,
and k>=2 is rejected. Ties being ambiguous does not eliminate misassignment from
multiple errors. Mixed-length catalogs, including `ACGT` / `ACGTA`, are rejected
before reading FASTQs; variable-length matching requires a future explicit mode.

## Terminal categories (precedence matters)

| Precedence | Category | Rule |
| --- | --- | --- |
| 1 | `ambiguous_barcode_match` | At least one end has a tied nearest match, regardless of the other end |
| 2 | `assigned_expected_pair` | Both ends uniquely recognized and their pair maps to one sample |
| 3 | `unexpected_valid_barcode_pair` | Both ends uniquely recognized, but no expected sample pair exists |
| 4 | `forward_only` | Forward uniquely recognized, reverse unknown |
| 5 | `reverse_only` | Reverse uniquely recognized, forward unknown |
| 6 | `no_barcode_match` | Both ends unknown |

Every pair gets exactly one category. Only category 2 is written to sample FASTQs.
F2+RA, for example, is unexpected for the supplied sample sheet and is never
reassigned to F2+RC. Unexpected valid pairs may have several biological or
technical causes; the software does not label them as proven PCR chimeras.

## FASTQ and run lifecycle

The parser streams `.fastq`, `.fq`, `.fastq.gz` and `.fq.gz` in synchronous pairs.
Four-line, nonempty IUPAC-DNA sequences and equal-length printable ASCII quality
strings are required. Wrapped FASTQ, truncated records, corrupt gzip, invalid
quality or unequal mate counts fail with file/record context. Read IDs compare
the first header token, allowing corresponding `/1` and `/2` suffixes and CASAVA
mate annotations. Wrong mate annotations fail. Nothing is skipped, reordered,
deduplicated or silently repaired. Repeated input IDs are not deduplicated;
each synchronized input pair is a separate observation.

Reads are not loaded as a dataset. Input SHA-256 hashes are computed in streaming
chunks in an initial pass; processing takes a second pass. Size and mtime are
checked for input changes. Metadata, catalog/matrix counters and a bounded set
of output handles remain in memory. A least-recently-used writer exclusively creates each file first (`xb`), then
reopens only files created by this run (`r+b`, identity checked) using concatenated
gzip members, preserving order and data. Stale or replaced files cause failure. Gzip timestamps and
filenames are fixed so repeated processing gives identical sample gzip bytes
with the same settings. All expected samples receive paired output files,
including valid empty gzip files for samples with zero reads.

An existing output directory is rejected, even if empty. Use a new destination;
there is no resume/overwrite option. Work stays in a unique sibling directory
`.<output-name>.incomplete-<random-id>` until writers close, reconciliation and
authoritative QC succeed, output hashes are recorded, and the completed summary
is written. A single same-filesystem directory rename publishes the final result.
Handled failures and CLI SIGTERM clean staging. SIGKILL may leave staging behind;
it cannot be cleaned up by the killed process. Never consume an incomplete tree,
even if it contains a summary written just before interruption.

A heatmap rendering exception completes authoritative outputs with an explicit
visualization warning (policy A); it does not erase biological results. CSV,
FASTQ, close, hash and summary failures still prevent publication.
See [the M2.1 completion contract](m2-hardening.md#downstream-completion-contract).

## Outputs and accounting

```text
results/
  01_demux_QC/
    barcode_counts.csv
    barcode_pair_matrix.csv
    barcode_pair_heatmap.png
    demux_summary.json
  02_demultiplexed_fastq/
    1B_R1.fastq.gz
    1B_R2.fastq.gz
    ...
```

`barcode_pair_matrix.csv` is authoritative: first column `forward_barcode_id`,
one row per forward catalog ID and one column per reverse ID, in catalog order.
Both ends must be uniquely recognized to contribute. Every cell, including zero
and unexpected combinations, is written. The PNG is a linear-count convenience
visualization with orange outlines on expected combinations. No low-frequency
cells are suppressed and no biological cause is inferred.

`barcode_counts.csv` contains `direction,barcode_id,sequence,recognized_read_pairs,
exact_read_pairs,corrected_read_pairs`. A recognized end contributes even if the
other end is unknown or ambiguous; these per-end counts are not terminal pair
categories. Corrected counts require nonzero distance and uniquely best matches.

The schema-version-2 summary contains total input pairs, all six categories, assignment percentage
(0–100; null for empty input), per-sample counts, resolved sample definitions,
profile/rules, catalog source and resolved motifs, mismatch/tie policy, resolved
configuration, input paths/sizes/mtimes/SHA-256, pipeline version, UTC times and
explicit reconciliation checks. It also records software/dependency identity,
Git SHA/dirty state when available, CLI argv/cwd, profile/catalog hashes and every
final sample FASTQ SHA-256/size/mate record count (including empty files). Raw QC
CSVs are hashed too. See [provenance details](m2-hardening.md#provenance). Prefix/suffix and bridge diagnostics are per
recognized end. Configured bridge counters partition recognized ends into
`bridge_match`, `bridge_mismatch`, `bridge_short`; disabled checks have no counters.

The run fails if any of these checks fails:

```text
total_input_read_pairs = sum(the six terminal category counts)
sum(per_sample_assigned_read_pairs) = assigned_expected_pair
writer's per-sample pair counts = per_sample_assigned_read_pairs
sum(barcode_pair_matrix cells) = assigned_expected_pair + unexpected_valid_barcode_pair
for each expected pair: matrix[F, R] = sample count = written R1 records = written R2 records
sum(expected matrix cells) = assigned_expected_pair
on-disk matrix CSV = reconciled matrix (all cells, including zeros)
```

`reconciliation.passed` is true only after all checks. Output file inventory and
identities are verified after close. The matrix CSV is read back; production
does not decompress and reparse FASTQs merely to recount them. Tests also inspect
actual decompressed FASTQ bytes to detect duplicate assignment and read loss.

## CLI and Python API

From a checkout, the explicit catalog form is:

```sh
peanalyzer demux --r1 /data/EV_only_1005_R1.fastq.gz \
  --r2 /data/EV_only_1005_R2.fastq.gz \
  --samples examples/ev_only_1005_samples.csv \
  --barcodes src/peanalyzer/barcode_sets/qi_hitom_v1.csv \
  --config examples/qi_hitom_config.yaml --output results/ev_only_1005
```

Omit `--barcodes` to use the installed bundled catalog with `qi_hitom_v1`.
Paths are relative to the invoking working directory. Exit 0 means completed;
invalid inputs and authoritative-output errors return 2 without a published
result. CLI SIGTERM returns 143; heatmap failure returns 0 with a warning.
JSON is printed to stdout; progress/errors go to stderr.

```python
from pathlib import Path
from peanalyzer.demux import demultiplex
from peanalyzer.validation import load_config

summary = demultiplex(
    r1=Path("/data/R1.fq.gz"), r2=Path("/data/R2.fq.gz"),
    samples_path=Path("examples/ev_only_1005_samples.csv"),
    config=load_config(Path("examples/qi_hitom_config.yaml")),
    output=Path("results/new_run"),
)
assert summary["reconciliation"]["passed"]
```

The API takes paths and typed settings, not argparse or GUI objects. Extraction,
identification, assignment, parsing, accounting and writing are independently
testable functions/classes. Milestone 2 processes serially; `n_processes` remains
reserved for future pipeline stages.

## Synthetic evidence and manual real-data comparison

`tests/synthetic.py` constructs ten invented read pairs with deterministic headers,
varying quality, mixed LF/CRLF, lowercase payload and plus-line annotations.
It includes expected 1B/2C/6F, unexpected F2+RA, each unknown-end case, a unique
one-base error, a tied one-base error and a mutated bridge. No real reads are
included. Expected results:

| Category | Exact | Hamming <=1 |
| --- | ---: | ---: |
| assigned_expected_pair | 4 | 5 |
| unexpected_valid_barcode_pair | 1 | 1 |
| ambiguous_barcode_match | 0 | 1 |
| forward_only | 1 | 1 |
| reverse_only | 3 | 1 |
| no_barcode_match | 1 | 1 |
| total | 10 | 10 |

Exact per-sample counts: 1B=2, 2C=1, 6F=1; tolerance 1: 1B=3, 2C=1, 6F=1.
All other expected samples have zero. Both modes reconcile. Tests inspect sample
contents, complete matrices, PNG validity, error cleanup, trimming, custom
catalogs/extraction, LRU reopening, gzip corruption and count-failure injection.

The following began as **user-supplied expectations**. They were subsequently
reproduced after the M2 commit, with every assigned record compared byte-for-byte
and every matrix cell independently recounted. Raw data and local validation
artifacts remain outside Git. When the original FASTQs are available, rerun the
command above and compare integer counts to these regression targets. Do not
commit FASTQs; they are gitignored and are never unit-test dependencies.

| Category | Observed pairs | Supplied percentage |
| --- | ---: | ---: |
| total_input_read_pairs | 108232 | 100% |
| assigned_expected_pair | 85878 | 79.346% |
| unexpected_valid_barcode_pair | 18493 | 17.086% |
| ambiguous_barcode_match | 0 (implied by exact unique motifs) | 0% |
| forward_only | 2387 | 2.205% |
| reverse_only | 1416 | 1.308% |
| no_barcode_match | 58 | 0.054% |

These categories sum to 108232. Compare integer counts; the supplied percentages
are rounded observations, not exact arithmetic targets.

| Sample stem | Pair | Observed assigned pairs |
| --- | --- | ---: |
| 1B | F1+RB | 6991 |
| 2C | F2+RC | 9045 |
| 3D | F3+RD | 6942 |
| 4E | F4+RE | 6879 |
| 5A | F5+RA | 9589 |
| 1C | F1+RC | 7673 |
| 2D | F2+RD | 9164 |
| 3E | F3+RE | 6238 |
| 4A | F4+RA | 8050 |
| 5B | F5+RB | 7538 |
| 6F | F6+RF | 6532 |
| 7G | F7+RG | 1237 |

The sample counts sum to 85878. If an actual comparison differs, first check
input hashes, complete catalog, sample sheet, extraction offsets/orientation,
exact matching and trimming settings; retain the observed differences. Never
alter the classifier to force agreement. The tests' ten-read counts differ
deliberately because they describe invented inputs, not the observed experiment.

Known limits: four-line FASTQ only, Hamming substitutions only, no barcode-quality
weighting, no automatic protocol discovery, no read deduplication, no retention
of rejected category FASTQs and no resume. Matrix
memory/plot size scale with catalog dimensions; the read stream itself is bounded.
Sample assignment validation does not validate target/homeolog assignment.

Next is Milestone 3: pin/install the CRISPResso toolchain, explicitly prepare
analysis inputs from preserved demux outputs, generate per-copy Pooled TSV/argv,
capture provenance, and test the documented homeolog-routing limitation with
synthetic WT/PE, tied copies and erased diagnostic variants before enabling
copy-specific results. No part of that backend is implemented here.
