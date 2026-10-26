# M11A independent oracle fixtures

Backend authority: `40bd8ad8844fd07ce8a138b5520f7f0ec948030f`, package 0.8.0.
Design authority: `05cfc68b62215a4c52862e09f081eab1c75ba39f`.

**Observed: 85/85 focused baseline checks matched. Zero scientific executions;
zero subprocess calls.** Two intentional canaries attempted to cross a forbidden
boundary and were stopped before route_pair or executable probing. This is not
the application's full test suite, a backend qualification rerun, or a candidate
PASS. No broad M10 audit or historical routing regression was performed.

[oracle-fixtures.json](oracle-fixtures.json) holds literal synthetic model inputs;
[run_oracles.py](run_oracles.py) also constructs temporary sample CSV/FASTQ and
edge fixtures. [oracle-observations.json](oracle-observations.json) records every
expected value, observed value or exception, contract layer and match result.
Expectations are explicit constants derived from pinned contracts and hand-counted
loci, not values read from the candidate response. Temporary fixture creation by
the audit harness is distinct from forbidden application preview writes.

## PE expectations and limits

The supplied PE fixture has a 180-nt WT and an intended G→A substitution at
zero-based WT/PE position **87**. The exact independent annotation is:
`{"wt_position":87,"pe_position":87,"old":"G","new":"A","kind":"substitution"}`.
Additional literal intended products cover substitutions, insertion, deletion
and multiple differences. Each passes Target schema validation; this does **not**
assert copy-routing qualification. Indel geometry qualification was intercepted,
not executed. A candidate may reuse pure Python annotation helpers after review,
never route experimental/synthetic reads to produce a setup illustration.

WT/intended alphabet is A/C/G/T. RNA guide U normalizes to T. Identical WT and
intended reference, missing spacer/extension and invalid alphabet are rejected.
No compulsory nicking guide or universal 20-nt spacer length is invented. A
scaffold minimum match length requires a supplied scaffold. Copy identity is a
collection-level concern; duplicate/case-colliding names and duplicate or reverse
complement references cannot be rescued by frontend renaming.

A reverse-only spacer is accepted by the field model but rejected by pure
preflight with PE_GUIDE_ORIENTATION_UNSUPPORTED. A well-formed absent spacer
fails PE_GUIDE_REFERENCE_MISMATCH_UNSUPPORTED; incompatible extension fails
PE_EXTENSION_REFERENCE_INCOMPATIBLE. This distinction is deliberate: model,
preflight, annotation and routing gates are separate. A synthetic homeolog pair
with insufficient diagnostics yields BLOCKED in the pure substitution geometry
path. Do not turn that into numeric copy results or automatically erase otherwise
supported target-level metrics.

**Sentinel boundary:** the current PE Target retains legacy qwc `"0"`; the active
M11A brief's invalid explicit sentinel is enforced by the nuclease contract.
Never advertise PE's disabled-window sentinel as a real explicit coordinate.
Actual nuclease coordinate `"0-0"` is valid. This is a mode distinction, not a
proposal to change backend semantics.

## Nuclease exact goldens

All intervals below are **zero-based inclusive**. Use the exact 18-nt sequence
`ACGTTGCAAGTCGATCGA`. Forward WT is 20 Gs + that target + 22 Cs (60 nt). Reverse
WT contains its reverse complement at the same physical locus. The palindromic
control uses `ACGTTGCAATTGCAACGT` at that locus. In all cases the target interval
is `[20,37]` and physical nick boundaries are `[[24,25],[32,33]]`.

| Selection | Exact intervals | Explicit coordinate display |
|---|---|---|
| W1 | [[24,25],[32,33]] | 24-25_32-33 |
| W2 (default) | [[24,33]] | 24-33 |
| W3 | [[20,37]] | 20-37 |
| W4 | [[10,47]] | 10-47 |

Forward target-oriented nick labels are `["5|6","13|14"]`; reverse labels are
`["13|14","5|6"]`. Palindromic orientation is explicitly `palindromic` with null
target-oriented labels and null target-oriented between-cuts sequence. Do not
invent a direction. Physical geometry remains available. A palindrome is one
physical locus, not two matches merely because forward and reverse searches agree.

W4 left clipping: target starts at 0 in a 40-nt WT → `[[0,27]]`.
W4 right clipping: target starts at 42 in a 60-nt WT → `[[32,59]]`.
No match → TIGR_TARGET_MISSING; multiple physical matches →
TIGR_TARGET_NOT_UNIQUE; target length other than 18 → TIGR_TARGET_LENGTH.
Non-DNA target rejects. The profile is exactly `tigr_tas_v1`, not a generic
inference from an editor label. Default W2 is not the only supported window.

| Explicit qwc | Pinned outcome on 60-nt WT |
|---|---|
| 10-20 | [[10,20]] |
| 0-0 | [[0,0]] |
| 0-59 / 59-59 | Valid boundaries |
| 1-3_8-10 | Ordered disjoint intervals accepted |
| 010-020 | Normalized to [[10,20]] |
| 0 / empty / -1-3 | NUCLEASE_WINDOW_REQUIRED |
| 20-10 / 59-60 | NUCLEASE_WINDOW_INVALID |
| 1-4_4-8 / 8-10_1-3 | Overlap or ordering invalid; no silent sorting |

Explicit qwc and TIGR profile are mutually exclusive. Nuclease target rejects PE
extra fields and legacy insertion mode; the qualified expected argument map has
58 fields and uses current insertion quantification. These are **expected
configuration**, not observed runtime arguments. No Core/version probe was run.
The strict single-copy production gate is separate from accepting individual
rows. Frontend must display backend coordinates and retain their coordinate
convention rather than recalculate them from target strings.

## Input and sample oracles

One pool R1/R2 pair can contain multiple biological samples. Stable M4/M5 sample
identity is barcode_id. Distinct rows may share one forward or reverse barcode;
the whole F/R pair must be unique. sample_name also must be globally unique in
the actual loader, with filename casefold collisions rejected. Repeated condition
metadata is valid for distinct biological replicates. Duplicate biological
replicate within condition/target passes metadata loading but is rejected later
by aggregation; it cannot be certified as end-to-end ready by metadata alone.

The observed paired_fastq reader rejects swapped /1 /2 marked mates. Unmarked,
synchronized swapped mates cannot be identified by that reader. It also reads
the same unmarked file as both mates without detecting file identity; demux has
a separate same-resolved-path gate. Candidate file validation must not rely on
FASTQ syntax alone for R1≠R2. Same inode/hardlink aliases should not bypass this
safety intent. Distinct same-basename files are not the same input.

Trim helper controls: explicit (8,8) returns (8,8); supplying just one trim fails;
the synthetic qi_hitom layout returns (13,12). Resolving lengths does not prove
all reads survive trimming. A relevant prepared read with length≤trim would
fail preparation; preview must detect/read-only report this without executing
preparation. For raw pools, assignment is unknown without demux: distinguish
conservative all-input screening from actual prepared-population evidence.

## Determinism and Review comparison

Observed nuclease default W2 and explicit W2 scientific identities are equal;
W3 differs. Two samples × two targets yield 14 run nodes or 13 analyze nodes,
regardless of copy count. This pure graph check is not permission to execute
multi-target production, which the current scope gate rejects. Caller must
normalize and sort sample/target identities; dag itself does not do that.

For candidate tests capture canonical backend scientific payload and SHA-256,
then change one factor at a time. Field semantics and source byte provenance
are separate: reorder equivalent CSV rows → same normalized graph, potentially
different file hashes. A report title affects report/overall plan identity but
not target biology. UI tab/filter/zoom is not an input. Target's excluded default
analysis_mode must be reintroduced through scientific_target when constructing
scientific identity. Never hash the frontend's independently reconstructed plan.

Use two independent Review checks: (1) real backend goldens prove correctness;
(2) controlled schema-valid distinctive server values prove UI fidelity. Inspect
coordinates, sample IDs/count, target/copy count, mode/profile/window, qualified
requirements, scientific digest and stage edges. A marked-response UI test is
not proof of backend correctness, and a backend-only test is not proof the UI
uses those values. Keep model validation and display provenance visible.

## Reproduction

Use a clean environment containing the pinned project's dependencies. The
script imports only the exported pinned backend snapshot and asserts its origin:

```sh
PYTHONDONTWRITEBYTECODE=1 MPLCONFIGDIR=/tmp/m11a-audit-mpl \
  /workspace/validation/m101/venv/bin/python \
  /workspace/m11a-independent-audit-prep/run_oracles.py
```

The shown interpreter is the environment used for these observations, not a
portable prerequisite. Substitute a qualified interpreter when handing off.
The script writes only its local oracle evidence and temporary synthetic inputs;
it does not change repository files. Error excerpts below are expected negative
outcomes, not failed checks. Full exact diagnostics remain in JSON.

## Observed check inventory

| ID | Contract layer | Expected / observed outcome | Matched |
|---|---|---|---|
| PE_SNP | Target schema only; indel routing qualification NOT run | {"mode":"precise_edit","nick":null,"qwc":"70-105"} | yes |
| PE_SUBSTITUTIONS | Target schema only; indel routing qualification NOT run | {"mode":"precise_edit","nick":null,"qwc":"70-105"} | yes |
| PE_INSERTION | Target schema only; indel routing qualification NOT run | {"mode":"precise_edit","nick":null,"qwc":"70-105"} | yes |
| PE_DELETION | Target schema only; indel routing qualification NOT run | {"mode":"precise_edit","nick":null,"qwc":"70-105"} | yes |
| PE_MULTIPLE | Target schema only; indel routing qualification NOT run | {"mode":"precise_edit","nick":null,"qwc":"70-105"} | yes |
| PE_DNA_N | Target rejection | "sequence must contain" (expected rejection/trap) | yes |
| PE_IDENTICAL | Target rejection | "must differ" (expected rejection/trap) | yes |
| PE_BAD_SPACER | Target rejection | "sequence must contain" (expected rejection/trap) | yes |
| PE_MISSING_SPACER | Target rejection | "valid string" (expected rejection/trap) | yes |
| PE_MISSING_EXTENSION | Target rejection | "valid string" (expected rejection/trap) | yes |
| PE_RESERVED_COPY | Target rejection | "reserved" (expected rejection/trap) | yes |
| PE_SCAFFOLD_LENGTH | Target rejection | "requires pegRNA_scaffold" (expected rejection/trap) | yes |
| PE_OPTIONAL_NICK | Target | {"mode":"precise_edit","nick":null,"qwc":"70-105"} | yes |
| PE_SENTINEL_ZERO | legacy PE Target only | {"mode":"precise_edit","nick":null,"qwc":"0"} | yes |
| PE_RNA_U | RNA normalization | "GGCGCTGGTTTGCGACTCCG" | yes |
| PE_REVERSE_MODEL | schema accepts reverse-only spacer | {"mode":"precise_edit","nick":null,"qwc":"70-105"} | yes |
| PE_REVERSE_PREFLIGHT | pure PE preflight | "PE_GUIDE_ORIENTATION_UNSUPPORTED" (expected rejection/trap) | yes |
| PE_ABSENT_GUIDE | pure PE preflight | "PE_GUIDE_REFERENCE_MISMATCH_UNSUPPORTED" (expected rejection/trap) | yes |
| PE_EXTENSION_ABSENT | pure target validation | "PE_EXTENSION_REFERENCE_INCOMPATIBLE" (expected rejection/trap) | yes |
| PE_SNP_ANNOTATION | geometry substitution-only branch | [{"wt_position":87,"pe_position":87,"old":"G","new":"A","kind":"substitution"}] | yes |
| PE_DUPLICATE_COPY | CSV collection / geometry identity | "duplicate" (expected rejection/trap) | yes |
| PE_DUPLICATE_WT | CSV collection / geometry identity | "duplicate" (expected rejection/trap) | yes |
| PE_CASEFOLD_COPY | CSV collection / geometry identity | "duplicate" (expected rejection/trap) | yes |
| PE_HOMELOG_TOO_FEW_DIAGNOSTICS | pure substitution geometry | "BLOCKED" | yes |
| TRAP_GEOMETRY_INDEL | geometry has hidden scientific trial | "TRAPPED_EXPERIMENTAL_ROUTE_PAIR" (expected rejection/trap) | yes |
| TRAP_BUILD_PLAN | builder probes despite no output writing | "TRAPPED_EXECUTABLE_PROBE" (expected rejection/trap) | yes |
| SAMPLE_SHARED_REVERSE | load_samples | 2 | yes |
| SAMPLE_DUPLICATE_CONDITION | different biological replicates | 2 | yes |
| SAMPLE_DUP_ID | load_samples collection | "duplicate barcode_id" (expected rejection/trap) | yes |
| SAMPLE_DUP_LABEL | load_samples collection | "duplicate sample_name" (expected rejection/trap) | yes |
| SAMPLE_DUP_PAIR | load_samples collection | "duplicate forward/reverse barcode pair" (expected rejection/trap) | yes |
| SAMPLE_CASEFOLD | load_samples collection | "collision" (expected rejection/trap) | yes |
| SAMPLE_BLANK_EDITOR | load_samples collection | "at least 1 character" (expected rejection/trap) | yes |
| SAMPLE_BLANK_DPI | load_samples collection | "dpi must be an integer" (expected rejection/trap) | yes |
| SAMPLE_PAIRED_BLOCK | load_samples collection | "require block_id" (expected rejection/trap) | yes |
| SAMPLE_DUP_BIO_REP_METADATA | metadata accepts; downstream M5 rejects per condition/target | 2 | yes |
| FASTQ_SYNCHRONIZED | paired_fastq read-only | 1 | yes |
| FASTQ_SWAPPED_MARKED | paired_fastq | "wrong mate suffix" (expected rejection/trap) | yes |
| FASTQ_UNMARKED_IDENTICAL_INPUT | iterator alone DOES NOT reject same file; separate identity gate required | 1 | yes |
| FASTQ_SWAPPED_UNMARKED | file roles cannot be proved from unmarked matching IDs | 1 | yes |
| TRIM_ONE_ONLY | resolve_trims | "supply both" (expected rejection/trap) | yes |
| TRIM_EXPLICIT | resolve_trims does not inspect read length | [8,8] | yes |
| TRIM_AUTOMATIC | recorded library layout only | [13,12] | yes |
| NUC_QWC_10-20 | NucleaseTarget explicit | [[10,20]] | yes |
| NUC_QWC_0-0 | NucleaseTarget explicit | [[0,0]] | yes |
| NUC_QWC_0-59 | NucleaseTarget explicit | [[0,59]] | yes |
| NUC_QWC_59-59 | NucleaseTarget explicit | [[59,59]] | yes |
| NUC_QWC_1-3_8-10 | NucleaseTarget explicit | [[1,3],[8,10]] | yes |
| NUC_QWC_010-020 | NucleaseTarget explicit | [[10,20]] | yes |
| NUC_BAD_QWC_'0' | NucleaseTarget explicit | "NUCLEASE_WINDOW_REQUIRED" (expected rejection/trap) | yes |
| NUC_BAD_QWC_'20-10' | NucleaseTarget explicit | "NUCLEASE_WINDOW_INVALID" (expected rejection/trap) | yes |
| NUC_BAD_QWC_'59-60' | NucleaseTarget explicit | "NUCLEASE_WINDOW_INVALID" (expected rejection/trap) | yes |
| NUC_BAD_QWC_'1-4_4-8' | NucleaseTarget explicit | "NUCLEASE_WINDOW_INVALID" (expected rejection/trap) | yes |
| NUC_BAD_QWC_'8-10_1-3' | NucleaseTarget explicit | "NUCLEASE_WINDOW_INVALID" (expected rejection/trap) | yes |
| NUC_BAD_QWC_'-1-3' | NucleaseTarget explicit | "NUCLEASE_WINDOW_REQUIRED" (expected rejection/trap) | yes |
| NUC_BAD_QWC_'' | NucleaseTarget explicit | "NUCLEASE_WINDOW_REQUIRED" (expected rejection/trap) | yes |
| TIGR_forward_W1 | exact independent physical-locus golden | {"orientation":"forward","target_interval":[20,37],"physical_nick_boundaries":[[24,25],[32,33]],"target_oriented_nick_labels":["5\|6","13\|14"],"intervals":[[24,25],[32,33]],"selected_window":"W1"} | yes |
| TIGR_forward_W2 | exact independent physical-locus golden | {"orientation":"forward","target_interval":[20,37],"physical_nick_boundaries":[[24,25],[32,33]],"target_oriented_nick_labels":["5\|6","13\|14"],"intervals":[[24,33]],"selected_window":"W2"} | yes |
| TIGR_forward_W3 | exact independent physical-locus golden | {"orientation":"forward","target_interval":[20,37],"physical_nick_boundaries":[[24,25],[32,33]],"target_oriented_nick_labels":["5\|6","13\|14"],"intervals":[[20,37]],"selected_window":"W3"} | yes |
| TIGR_forward_W4 | exact independent physical-locus golden | {"orientation":"forward","target_interval":[20,37],"physical_nick_boundaries":[[24,25],[32,33]],"target_oriented_nick_labels":["5\|6","13\|14"],"intervals":[[10,47]],"selected_window":"W4"} | yes |
| TIGR_reverse_W1 | exact independent physical-locus golden | {"orientation":"reverse","target_interval":[20,37],"physical_nick_boundaries":[[24,25],[32,33]],"target_oriented_nick_labels":["13\|14","5\|6"],"intervals":[[24,25],[32,33]],"selected_window":"W1"} | yes |
| TIGR_reverse_W2 | exact independent physical-locus golden | {"orientation":"reverse","target_interval":[20,37],"physical_nick_boundaries":[[24,25],[32,33]],"target_oriented_nick_labels":["13\|14","5\|6"],"intervals":[[24,33]],"selected_window":"W2"} | yes |
| TIGR_reverse_W3 | exact independent physical-locus golden | {"orientation":"reverse","target_interval":[20,37],"physical_nick_boundaries":[[24,25],[32,33]],"target_oriented_nick_labels":["13\|14","5\|6"],"intervals":[[20,37]],"selected_window":"W3"} | yes |
| TIGR_reverse_W4 | exact independent physical-locus golden | {"orientation":"reverse","target_interval":[20,37],"physical_nick_boundaries":[[24,25],[32,33]],"target_oriented_nick_labels":["13\|14","5\|6"],"intervals":[[10,47]],"selected_window":"W4"} | yes |
| TIGR_palindromic_W1 | exact independent physical-locus golden | {"orientation":"palindromic","target_interval":[20,37],"physical_nick_boundaries":[[24,25],[32,33]],"target_oriented_nick_labels":null,"intervals":[[24,25],[32,33]],"selected_window":"W1"} | yes |
| TIGR_palindromic_W2 | exact independent physical-locus golden | {"orientation":"palindromic","target_interval":[20,37],"physical_nick_boundaries":[[24,25],[32,33]],"target_oriented_nick_labels":null,"intervals":[[24,33]],"selected_window":"W2"} | yes |
| TIGR_palindromic_W3 | exact independent physical-locus golden | {"orientation":"palindromic","target_interval":[20,37],"physical_nick_boundaries":[[24,25],[32,33]],"target_oriented_nick_labels":null,"intervals":[[20,37]],"selected_window":"W3"} | yes |
| TIGR_palindromic_W4 | exact independent physical-locus golden | {"orientation":"palindromic","target_interval":[20,37],"physical_nick_boundaries":[[24,25],[32,33]],"target_oriented_nick_labels":null,"intervals":[[10,47]],"selected_window":"W4"} | yes |
| TIGR_DEFAULT_W2 | omitted selection | [[24,33]] | yes |
| TIGR_W4_LEFT_CLIP | edge fixture | [[0,27]] | yes |
| TIGR_W4_RIGHT_CLIP | edge fixture | [[32,59]] | yes |
| TIGR_MISSING | NucleaseTarget rejection | "TIGR_TARGET_MISSING" (expected rejection/trap) | yes |
| TIGR_MULTIPLE | NucleaseTarget rejection | "TIGR_TARGET_NOT_UNIQUE" (expected rejection/trap) | yes |
| TIGR_SHORT | NucleaseTarget rejection | "TIGR_TARGET_LENGTH" (expected rejection/trap) | yes |
| TIGR_BAD_DNA | NucleaseTarget rejection | "sequence must contain" (expected rejection/trap) | yes |
| TIGR_BOTH | NucleaseTarget rejection | "not both" (expected rejection/trap) | yes |
| TIGR_LEGACY | NucleaseTarget rejection | "current" (expected rejection/trap) | yes |
| TIGR_PE_CONTAMINATION | NucleaseTarget rejection | "Extra inputs" (expected rejection/trap) | yes |
| QUALIFIED_ARGUMENT_COUNT | expected map, not executed/verified runtime | 58 | yes |
| DAG_RUN_2X2 | two samples/two targets independent of copy count | 14 | yes |
| DAG_ANALYZE_2X2 | external source, no demux node | 13 | yes |
| IDENTITY_W2_DEFAULT | backend scientific identity canonicalization | true | yes |
| IDENTITY_WINDOW_CHANGE | backend scientific identity | true | yes |
| PATH_DOTDOT_HELPER | no_symlinks normalizes traversal; not a registration allowlist | true | yes |
| PATH_OWNED_REJECTS | owned relative artifact boundary | "UNSAFE_PATH" (expected rejection/trap) | yes |
