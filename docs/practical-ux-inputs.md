# Practical browser inputs and Results UX (0.9.0 candidate)

Base: `72e0f86a495e079cab2ae50d2796e7a3423c78af`. This is a candidate for independent
focused audit, not approval to merge. Existing science and M11C recovery semantics
are frozen. Version authority is `pyproject.toml`; installed runtime metadata,
frontend package.json/package-lock.json and generated bundle are synchronized.
Historical validation artifacts retain their historical versions.

## Browser FASTQ transfer

Samples offers native browser file inputs for R1/R2. A File body travels over the
existing token/Origin/Host-protected loopback API; no Windows path translation or
server-path request is accepted. Legacy `--setup-fastq` remains available.

`POST /api/v1/setup/uploads/fastq?filename=DISPLAY_NAME` accepts an octet-stream.
The original filename is display metadata only. The server uses a random owned
directory and fixed `input.fastq[.gz]` leaf, incrementally hashes/writes bounded
chunks, enforces a 64 GiB transport limit, validates through the existing FASTQ
reader, checks hash/size, and atomically renames before registering a capability.
Transport safeguards bound individual expanded lines to 1 MiB and expanded files
to 128 GiB; these resource limits do not define biological validity. Gzip/FASTQ
content must validate regardless of filename suffix. Pair synchronization remains
in existing Setup validation. One upload per server is received at a time.

Default storage: `~/.local/share/peanalyzer/uploads`, private mode 0700. Operators
may choose a stable private Linux path using `--upload-root`. No upload directory
is created just by Setup/Review. Partials from handled failures/disconnects are
removed through owned directory descriptors. Hard-kill orphan upload directories
may remain and require operator inspection; there is no automatic scavenger.
Completed uploads are retained, including replaced/discarded draft inputs, since
accepted analyses and recovery require original source paths. Never delete them
while a workspace depends on them. Receipt `upload.json` records display name,
byte count and SHA-256. External launcher inputs are never deletion targets.

A successful transfer changes the editable mate reference; failure leaves the
previous selection intact. It never submits Run. Source mutation after upload
is rejected against the received hash/size in addition to existing Review/Run
source checks. Same-account hostile filesystem writers are not an OS sandbox
threat model; this release does not change M11C's documented limitation.

## Excel workbook v1

Download `PEAnalyzer-samples-v1.xlsx` in Samples. Import replaces sample rows only
on success and after explicit user confirmation. The result is editable and must
still pass normal Validate & Review. No scientific execution occurs on import.

- Exactly `Samples`, optionally the official `Instructions` sheet with version
  marker `PEAnalyzer sample template v1`. Visible sheets/rows/columns only.
- Header row contains unique exact column names; whitespace at cell edges is
  trimmed. No unknown/misspelled headers.
- Required: `barcode_id`, `sample_name`, `editor`, `treatment`, `dpi`,
  `biological_replicate`. The backend requires numeric dpi; blank is not replaced
  by an invented biological value.
- Optional: `block_id`, `paired`, `forward_barcode_id`, `reverse_barcode_id`,
  `forward_barcode`, `reverse_barcode`.
- QI-HITOM shorthand such as `4A` identifies `F4`/`RA`; sequences come from the
  bundled authoritative catalog via its existing resolver. Unknown pairs fail;
  redundant IDs/sequences must agree. There is no second sequence lookup table.
- Custom profile uses explicit read-start forward/reverse sequences. Catalog IDs
  without a matching custom sequence definition are not guessed.
- Blank optional paired is false, matching the existing draft default. Accepted
  booleans: Excel true/false or case-insensitive text true/false. No yes/no/1/0
  inference. True requires block_id through the authoritative Sample model.
- Text and exact integer cells are accepted; preserve leading-zero IDs as text.
  Dates, fractional numbers, formulas, error cells and hyperlinks are rejected.
- Trailing empty rows are ignored; an empty row inside active data is an error.
- Maximum 1,000 rows, 2 MiB uploaded ZIP and 16 MiB expanded archive. Encrypted,
  macro-enabled, externally linked, merged, named-range, table/chart/image and
  hidden alternative structures are unsupported. No `.xls`/`.xlsm` support.

Pinned GUI dependencies are openpyxl 3.1.5, et_xmlfile 2.0.0, defusedxml 0.7.1.
They run inside Python; no Office/LibreOffice process is used. ZIP/XML bounds and
external-content rejection precede the reader. Existing Sample, Catalog and CSV
cross-row validation remain authoritative; full target/design checks stay in
Validate & Review. Errors identify worksheet row and field where possible.

## Identity and scientific parity

Current Setup science identity intentionally contains input **basename**, SHA-256
and size. Plan identity additionally contains analysis name and destination
identity. Execution provenance retains absolute paths. These contracts are not
changed to make transport IDs equal. Generated upload basenames normally differ
from legacy names; both scientific/plan digests can therefore differ. With equal
basenames, bytes and all other identity inputs, the existing digest can match.
The required parity oracle compares exact bytes/hashes/sizes, canonical sample
and catalog data, compiled configuration/targets/DAG and scientific outputs,
accounting only for documented source-name/path and execution provenance.

## Results and final verification

PE Samples shows both primary stored quantities without changing the selected
advanced series: Exact intended PE, and **CRISPResso Prime-edited reference
fraction**. The latter is `counts_total['Prime-edited'] / authoritative aligned
reads`, not Modified%. Exact intended PE remains exact PE / (exact WT + exact PE).
Counts, fractions and percentages are stored values, never recomputed in JS.
Definitions, population and verified source links are available beside values.
Null/blocked values remain unavailable. Copy-specific routed diagnostics have a
separate selector group and routing-conditioned explanation; stable IDs remain.

Run derives a display-only final-verification phase from existing FINAL_VALIDATION
/ VIEWER_VERIFICATION events or a RUNNING job with all scientific stages finished.
COMPLETED still requires the unchanged backend verification/registration path.
No new lifecycle state, cancellation rule or recovery action is introduced.

Optional path browsing/copy-path, extra runtime wording and biological-name
warnings are deferred. Existing M11C minor/info findings are not reopened.
