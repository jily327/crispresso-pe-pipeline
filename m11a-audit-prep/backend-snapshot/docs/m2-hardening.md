# Milestone 2.1 audit hardening

This patch starts from `main` at `20338ef0c10608f3fc1ee007a61d05bc2b8dd012`.
Package version is 0.2.1. Config/metadata remain schema version 1; the demux
summary advances to schema version 2 to identify the stronger output contract.
No CRISPResso execution, copy routing, PE analysis or other M3 work is included.

## Findings and decisions

| Audit finding / requested scope | Resolution |
| --- | --- |
| HIGH-1: case-insensitive output collision | Validate actual R1/R2 filenames with `casefold()` before reading FASTQs, independently of the host filesystem. Only `barcode_id` enters sample filenames; `sample_name` is metadata. |
| Sanitized-name collisions | No lossy sanitizer is used. Unsafe names are rejected; whitespace is normalized before duplicate checking. Both normalized duplicates and case-only aliases fail. |
| Stale sample files | First open is exclusive `xb`. LRU reopen uses `r+b` only for a filename created by this writer, checks file identity, then seeks to the end. It cannot create a missing file or append to an unrelated preexisting one. |
| MEDIUM-1: partial outputs | Use a unique private sibling staging tree and rename the entire completed tree to its final path. CLI SIGTERM unwinds cleanup; SIGKILL can leave only an explicitly incomplete staging tree. |
| MEDIUM-2: unsafe mismatch tolerance | Compute minimum same-side Hamming distance over the entire resolved catalog, not just expected samples. Reject k >= d_min or k >= motif length. Warn when 2*k >= d_min. A singleton reports d_min=null and still enforces k < length. |
| MEDIUM-3: mixed-length misassignment | Require equal lengths within each direction, including catalog-free mode. F and R may have different lengths. Reject prefix examples such as ACGT / ACGTA before FASTQ processing. |
| MEDIUM-4: implicit catalog extension | Bundled and explicitly supplied catalogs are authoritative. A sample ID must exist on the right side; an explicit sequence must match it, or match an existing sequence when ID is omitted. Only custom profile + no catalog permits building identities from sample sequences. |
| MEDIUM-5: provenance | Record output SHA-256, software/Git/Python/dependency identity, CLI arguments/cwd, and catalog/profile hashes alongside existing input/config provenance. |
| LOW-1: reconciliation | Check each expected matrix cell against its sample count, expected-cell sum, both mate writer counters, closed-file inventory/identity, and the actual serialized matrix CSV. |
| LOW-3: reverse-complement QC | Evaluate motif prefix/suffix in catalog orientation. Bridge QC remains in raw-read orientation. Assignment and output sequence orientation are unchanged. |
| LOW-4: run warnings | Warn about zero/low assignment, high unexpected-pair fraction, and extraction extending past most reads. These are neutral diagnostics, not causal conclusions or failures. |
| LOW-6: plotting controls validity | Policy A: a rendering exception removes a partial PNG, records `visualization.status=failed` and a warning, and publishes validated authoritative output. |

The requested correctness findings are accepted. ID-plus-sequence disagreement
was already rejected; the new catalog fix covers the reproduced unknown-sequence
extension when the ID is omitted. The stricter equal-length policy is the task's
explicit alternative to the audit's proposed overlap heuristic. Existing tests
for supported exact/Hamming matching and raw record preservation remain; the old
variable-length execution test now asserts the intentionally required rejection.
The former combined QC/plot failure test still covers authoritative CSV failure,
and a separate test covers the new nonfatal rendering policy.

No change is made for audit observations outside this task: LRU capacity/tuning,
plus-line ID validation, zip-import packaging, stronger input-swap detection,
GUI APIs or speculative biological contamination models. The external audit did
not have the original FASTQs; that limitation does not contradict the separate
local real-data validation. No model-based contamination estimate is implemented.

## Matching and warning policy

Both Qi catalog sides have d_min=2. Exact matching (k=0) stays the production
default. k=1 remains permitted with overlapping-neighborhood warnings; tied
nearest candidates remain ambiguous. This does not guarantee correction of
multiple errors or prevent an error from becoming another valid motif. k>=2 is
rejected, never clamped. Catalog-free sheets have the same execution safety checks.

Run warnings use these transparent diagnostic thresholds over input pairs:

- Zero assigned expected pairs (also reported for empty input).
- Assigned fraction <10% for nonempty input.
- Unexpected valid pair fraction >10% for nonempty input.
- Offset + barcode length exceeds read length for >50% of reads on either end.

These thresholds do not reject runs or change counts, and do not identify a
biological cause. The existing EV-only unexpected fraction triggers a warning.
Empty input retains undefined assignment percentage and valid empty sample gzip
files. Prefix/suffix/bridge diagnostics never influence assignment.

## Publication and failure behavior

For `--output results/run1`, computation occurs in
`results/.run1.incomplete-<random-id>/`. Its permissions are private where the
platform supports them. All normal output subdirectories are nested within this
staging tree; `results/run1` does not exist during processing.

Publication order is: process all pairs; create any empty sample files; close
all writers successfully; verify file inventory and identities; reconcile
terminal/sample/matrix/mate counts; write and read back authoritative CSV data;
attempt the optional PNG; hash finalized compressed FASTQs and CSVs; write
`01_demux_QC/demux_summary.json` with completed status; rename the staging
directory to the final destination on the same filesystem.

Existing destinations are refused, including symlinks, and checked again before
publication. Never edit an in-progress run's staging directory or race another
process creating its final destination. Directory rename provides atomic
visibility on normal local filesystems; it is not an fsync-based guarantee
against power loss or a promise about unusual network filesystems.

Handled exceptions, SIGINT and CLI SIGTERM remove this invocation's staging
tree. The CLI restores the previous SIGTERM handler and exits 143 on SIGTERM.
Direct API users own their signal policy; a default-terminated process may leave
staging behind, but does not publish it. SIGKILL cannot execute cleanup. Leftover
staging is never accepted, even if it contains a completed summary written just
before the process died. It may be inspected or removed manually, not resumed.

FASTQ/CSV/hash/summary/close errors prevent publication. Matplotlib exceptions
are handled only around rendering: a partial PNG is removed and the exception
type is recorded without read content. Interrupts and `SystemExit` still cancel
the run. If removal of a partial PNG itself fails, publication fails too.

## Downstream completion contract

Future M3 **must not glob FASTQs to decide whether a run is complete**. It must:

1. Select a published final run root, never a `.incomplete-*` tree.
2. Load `01_demux_QC/demux_summary.json` and require `schema_version == 2`,
   `status == "completed"`, `reconciliation.passed is true`, and every required
   `reconciliation.checks` value is true.
3. Require all eight reconciliation checks: `terminal_categories_equal_input`,
   `sample_counts_equal_assigned`, `written_pairs_equal_sample_counts`,
   `matrix_equals_recognized_pairs`, `expected_matrix_cells_equal_samples`,
   `expected_matrix_sum_equals_assigned`, `mate_records_equal_sample_counts`,
   and `on_disk_matrix_matches_counts`.
4. Derive the exact expected sample filenames from validated `samples` and
   `per_sample_assigned_read_pairs`; require both mates per sample in
   `output_files`, with matching sample/mate IDs and assigned record counts.
   Require the two authoritative CSV entries too. Do not accept extra/missing
   biological sample files, unsafe relative paths or symlinks outside the run.
5. Verify every authoritative file's current byte size and SHA-256 against
   `output_files`. Hash the compressed FASTQ bytes, not their decoded text.
   Reject missing, modified or mismatched files. Treat the completed run as
   immutable; prepared downstream inputs must go elsewhere.

The PNG and `visualization.status` do not determine biological validity.
Old schema-version-1 M2 output does not satisfy this stronger contract; rerun it
or perform an explicit, separately designed migration before M3 consumption.
No such migration or M3 consumer is implemented here. Checksums detect changes
relative to the trusted manifest; they are not a digital signature. The manifest
does not hash itself.

## Provenance

The summary adds:

- `software`: package version, Git commit and dirty state when this module lives
  in a checkout, Python version/executable, and installed versions of Pydantic,
  PyYAML, matplotlib and relevant numerical/rendering dependencies. Missing Git
  or a wheel outside a checkout yields null Git fields; it never takes the SHA
  from an unrelated caller working directory. Unavailable dependency versions
  are null.
- `invocation`: CLI entrypoint and argument vector plus cwd (paths are resolved
  using that cwd). For `python -m`, the entrypoint is the executed `__main__.py`;
  Python identity is recorded separately. Explicit `main(argv)` calls record a
  canonical `peanalyzer` argv. Direct API calls have null argv unless supplied.
- `output_files`: run-relative paths, SHA-256 and compressed byte sizes for every
  sample mate, including empty files; also sample ID, mate and successful writer
  record count. Both authoritative CSVs have hashes and sizes.
- `barcode_catalog`: authoritative-mode flag, resolved catalog hash and per-side
  matching-safety statistics. File-backed catalogs retain their source hash in
  `input_provenance.barcodes`; catalog-free identity is the resolved catalog hash.
- `extraction_profile`: packaged profile source hash (null for custom), effective
  rules and their canonical JSON hash.
- `visualization`: completed PNG path or failure status/exception type;
  `short_barcode_reads` and expanded warnings.

Existing input SHA-256/size/mtime, metadata and resolved configuration/hash remain.
Canonical JSON hashes use sorted keys and compact separators. Output hashes use
a streaming pass over closed compressed files; production does not decompress
huge FASTQs merely to recount them. Per-mate counters advance only after a full
write succeeds. This detects the scoped filename/stale-file failures and count
drift; it is not a second biological classifier. No raw reads enter logs.

## Validation

The baseline's 177 tests passed before editing. Independent pre-patch probes
reproduced acceptance of `s1`/`S1`, appending to a stale FASTQ, the ACGT/ACGTA
exact misassignment, unknown sample-sequence catalog extension and k=50.
Regression tests cover these cases, successful/failed staged publication,
SIGTERM/SIGKILL, optional rendering failure, output hashes, per-cell and mate
reconciliation, reverse-complement QC and software provenance fallback.

The real-data regression uses the original EV-only paired FASTQs outside Git,
the bundled Qi catalog, exact matching and the existing sample sheet. Its
independent audit compares every assigned four-line record to input, recounts
all 96 matrix cells and checks both mate IDs. Expected counts and sample totals
are listed in [demultiplexing.md](demultiplexing.md#synthetic-evidence-and-manual-real-data-comparison).
No raw data or validation scratch outputs are included in the package or commit.
