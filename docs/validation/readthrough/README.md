# 0.7.1 terminal read-through remediation (D1/D2)

This qualification starts at merged main
`67734b842d3295a9c40e2981724d981cc060fd80`. It changes routing identity and
reference-aware exact-product assessment only. M2 preparation, M4 backend
execution, M5 statistics, M6 presentation, and M7 orchestration are unchanged.
The result schemas and m5-v1 / m6-v1 / m7-v1 contracts remain unchanged.

## D1: identity and ambiguity are separate

`reference_span_identity()` counts matches divided by all columns in the
reference-bearing alignment span. Internal substitutions, insertions and
reference-only deletion columns are nonmatching columns. Unobserved reference
ends are omitted. Query-only bases are omitted **only** at reference coordinate
zero or reference length. Query-only sequence at an interior reference coordinate
still counts even when it precedes the first paired base. The threshold stays
0.8. The aligner, equivalence cap, diagnostic quality threshold, observed-edit
flanks and copy-evidence rules remain unchanged.

The independent ambiguity veto prevents stricter internal-deletion accounting
from creating apparent uniqueness by removing a competing placement. An
identity-rejected, cap-eligible placement is retained as an ambiguity witness
only when it contains internal reference-only deletion columns and at least 0.8
of its query bases inside the reference-bearing span match. Internal query
insertions and substitutions count against this query-support screen. Terminal
query-only bases outside the reference do not enter it. This is **not** a second
qualification score: with matches M, mismatches X, internal insertions I and
internal deletions D, identity is M/(M+X+I+D), while the ambiguity-only query
support is M/(M+X+I). Terminal query overhang is absent from both. A witness
cannot supply positive diagnostic evidence,
qualify a state/copy, or supply edit coverage. A witness vetoes only when its
projection at an edit-independent diagnostic differs from the qualified
placements (base, quality, query coordinate, or missing coverage). It uses the
existing `diagnostic placement differs across competing alignments` reason.

This preserves the WT 100-nt ambiguity in both copies of
`deletion_60_seed11`, `deletion_60_seed29`, and `deletion_60_seed47`.
The first candidate implementation without this veto admitted all three; that
candidate was rejected. The final historical geometry must remain 36 total,
13 allowed, 23 blocked. No biological reference, vendor, adapter, fixed read
length, or expected editing percentage is built into the veto.

## D2: exact whole biological products

`reconstruct_product()` evaluates every unique WT/PE/copy sequence together.
Inward amplicon-end mates retain their 5-prime anchors. An overlong mate must
contain the complete candidate exactly at its biological anchor. The other
mate must agree exactly over its entire candidate-overlapping portion. Only
query sequence beyond that whole candidate can be omitted. The resulting
biological mate portions must pass the existing unique-overlap reconstructor:
at least 10 nt overlap, no second qualifying overlap, no alternative border
of at least 4 nt, and no demonstrable repeated period fitting twice.

Distinct supported products, or an additional complete candidate occurrence
at a different position in either mate, fail closed. WT/PE and copy iteration
order cannot choose trimming. Existing state-dependent and copy-dependent
observability gates retain priority. Without unique exact candidate support,
the original pure-overlap method applies. No general trimming of imperfect
products is introduced. Partial products, internal errors, conflicting mates,
state collisions and repeated-placement ambiguity remain excluded.

The target precise denominator is exact WT plus exact intended PE among the
prepared pairs that pass these rules. Target native and confident-copy metrics
retain their existing populations. Routing, backend preprocessing/alignment,
and metric-specific assessability are separate filters; no one stage defines
every denominator. Native and exact fractions may differ in either direction.
Controls are never forced to zero and no origin/cause is inferred for their
apparent PE products.

## Authoritative inputs and metadata

`input-hashes.json` records streaming SHA-256 and byte sizes of all five
immutable uploaded files. No FASTQ is copied into Git. The target CSV hash is
`3112ba5418883cf40e8d8de09d5835376027745d5616a45a05231957f8198b24`.
Dataset A is **92,250 prepared pairs**; the prior audit's 73,250 statement was
an erroneous narrative, not a filter or subset.

`Azenta-samples.csv` and `AmpSeq-samples.csv` retain supplied barcode/sample
identities. Editor/treatment labels and leaf numbers transcribe those names;
NC, WT gDNA and NTC remain separately labelled controls. No paired design or
contrast is inferred. Both workflows call summarize only. The user explicitly
specified dpi 6 for all seven Azenta samples and ten AmpSeq EV samples; AmpSeq
WT/NTC dpi 0 is solely a schema bookkeeping placeholder, **not** a harvest-time
claim. `metadata-convention.json` records that convention. Leaf labels do not
establish experimental independence beyond the supplied metadata.

## Reproduction and independent checks

Use the existing qualified CRISPResso2 2.3.4 wrapper/runtime:
`pinellolab/crispresso2@sha256:b7e7971a87769aa584d31d21e199a9abca5f641c4f889c2e807cb6324fc8ce0c`.
`run-real.py DATASET OUTPUT` invokes M7 from raw FASTQs in a new workspace;
`--resume --forbid-execution` patches all execution APIs to raise while allowing
validators. `recount.py DATASET WORKFLOW OUTPUT_JSON` independently streams raw
records, matches the full catalog, reconciles every F/R cell and bridge counter,
checks exact demux/prepared record hashes and IDs, and derives exact haplotypes
by exhaustive candidate-coordinate consistency. Production classification is
called only afterwards for per-pair comparison. Manual percentages are not
implementation inputs or tuning targets.

`route-oracle.py` replays the starting-main router against every prepared pair,
and independently removes only established complete-product tails on a
stratified sample of exact WT/PE/copy/length combinations. It compares original
and normalized routing decisions and retains compact baseline ledgers outside
Git. The summary includes all tested strata and read-ID hashes, not FASTQ data.

`check-stale.py` uses a disposable 0.7.0 synthetic workspace. Its normal resume
must fail with `STALE_STAGE_IDENTITY`, then existing `--force all` recomputes it.
There is no special-case version logic and historical 0.7.0 evidence is untouched.
Software version, code digest and Git provenance naturally change stage identity.
A later commit/install also changes source provenance; reuse across that change
requires the existing invalidation rules.

Full suites use the existing `docs/validation/m7/run-tests.sh`, including all
63 historical integration scenarios (62 pre-M7 plus one M7; 62 execute the
backend and one is preflight-only). The wheel suite
runs outside the checkout and imports from site-packages. Final machine-readable
evidence and exact counts are collected alongside this document.

## Limits

This is a conservative exact-reference boundary contract, not a general adapter
trimmer or reference-free assembler. It assumes correctly specified complete
references and inward amplicon-end reads. Novel products with tails may remain
unassessable. Whole-reference repetitions are rejected even if one occurrence
appears more plausible. Qualification does not establish a mechanism for vendor
length differences, control PE signal or unexpected barcode pairs. No automatic
biological interpretation or correction is applied. The M7 single-target
execution limit remains; unrelated M4/M5/M6/M7 findings are not remediated.

## Observed regression and scientific impact

The full source and independently installed wheel suites each passed **1,095**
cases: all 1,036 prior cases retained plus 59 new targeted cases, with zero
failures/errors/skips. Each includes 63 integration scenarios: 62 executing the
backend and one preflight-only scenario. The 145 M5/M5.1 cases and 72 M6/M6.1
cases pass unchanged. All 475 historical exact classifications, all 432 trials
across the 36 geometry designs, and the original 125 routing classifications
are unchanged. All 42 historical M4 scientific result comparisons match; their
only text difference is the explicit 0.7.1 read-through statement at
`qc.limitations[3]`, individually recorded in the evidence.

The independent exact oracle agrees on every expected prepared pair in both
source and wheel: 92,250 Azenta and 85,878 AmpSeq. Independent raw recounts also
match every terminal count, sample count, matrix cell and bridge counter, and
verify unchanged demux records and exact 27-base prepared transformations.
All 232 Azenta and 144 AmpSeq complete exact-product normalization trials
preserve routing decisions. Twelve additional partial-reference-tail probes
preserve exact classification and assignment.

Baseline routing replay independently reproduces zero Azenta assignments and
all published AmpSeq per-copy counts. Final Azenta assignments are 8,095 to
chr01g24880 and 9,504 to chr11g18980; 74,651 pairs remain quarantined. AmpSeq gains
32 assignments and loses one, for 64,677 assigned and 21,201 quarantined. All
per-read category transitions, including quarantine-category changes, are
inventoried in the routing evidence. The lost assignment contains a 42-base
internal deletion: its chr01 WT alignment identity becomes 168/211 = 0.7962
instead of 168/196 = 0.8571. It fails the unchanged 0.8 threshold; the ambiguity
witness cannot rescue positive qualification. This is an explicitly disclosed
conservative consequence of the required internal-deletion penalty, not an
unexplained loss or a threshold change.

For AmpSeq, the raw length class with a mate at least 290 nt independently
recounts to the audit's 1,091 pairs. Assignments increase from 0 to 7; 1,084 remain
quarantined. None meets the complete exact-product normalization probe's entry
criterion. An additional alignment-coordinate boundary probe confirms invariant
routing for three newly assigned pairs; four have competing full-reference
boundary proposals and are explicitly **not established** for that extra probe.
No boundary is selected for those four and no production behavior is changed to
make the probe pass. Copy-diagnostic assignment is not proof of an exact product
or a unique complete-product boundary.

Azenta's original target-native integer results match the supporting audit
exactly. Every target-precise result is compared with the independently derived
exact WT/PE integer counts, not fitted to historical percentages. Real exclusions
remain observable/unresolved product exclusions; no WT-derived or PE-derived
origin is claimed. Nonzero control signal is retained without causal attribution.

The AmpSeq process disappeared mid-run without a handled-failure record. After
confirming no workflow or backend child remained, the task-owned stale lock was
removed and existing `resume --force metrics` recovery used. Its fresh raw demux,
preparation and routing lineage was retained and verified; all metrics and their
descendants were rebuilt. No M7 implementation or stale-lock policy changed.

See [RESULTS.md](RESULTS.md) for all 19 target-precise integer results and native
comparators, and `qualification-gate.json` for the completed gate inventory.
