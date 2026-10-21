# M3.1 routing and metric-contract qualification

> M3.1.1 audit remediation supersedes the placement, geometry and production-policy
> eligibility described here. See [M3.1.1 remediation](m311-remediation.md).
> Historical evidence below remains unchanged; do not infer merge approval.

**ROUTING GATE: PASS for the documented synthetic geometry and policy.** Default
multi-copy CRISPRessoPooled routing remains scientifically unqualified (M3 FAIL).
This milestone adds an explicit conservative router, input verification,
geometry preflight, direct per-copy Core handoff and metric-contract tests.
It does not implement final biological reports, aggregation or statistics.

Parent M3 commit: `e7e67ccef5792682fcf61344e3423f1a2f80d3e3`.
Unchanged main: `ae7e7f3e1f9144ea2092d9a6201a4d137a024214`.
Branch: `feat/m3.1-routing-quarantine`. Package version: 0.3.1.

## Denominators and backend attrition

**Every PE denominator is determined by multiple stages:**

1. Routing qualification/quarantine determines eligibility for copy-specific
   analysis. Quarantine is retained and is not a hidden discard from the
   copy-agnostic primary exact-haplotype cohort.
2. CRISPResso preprocessing and alignment acceptance determine which submitted
   records enter its aligned cohort.
3. The metric's product-class and assessability rules determine its denominator.

No one stage alone defines the final denominator. CRISPResso `Modified` is not
precise PE. Assignment to its `Prime-edited` reference is not exact intended PE.

`backend.metrics.parse_child` reads authoritative integer counters from
`running_info.alignment_stats` in each completed 2.3.4 `CRISPResso2_info.json`:

```text
aligned_reads   = N_CACHED_ALN + N_COMPUTED_ALN
unaligned_reads = N_CACHED_NOTALN + N_COMPUTED_NOTALN
N_TOT_READS     = aligned_reads + unaligned_reads
```

It reads the child file named by `running_info.mapping_stats_filename` and
requires its `READS AFTER PREPROCESSING == N_TOT_READS`, `READS ALIGNED ==
aligned_reads`, and identical cache/computation counters. When the handoff
guarantees one backend input record per pair, `READS IN INPUTS == routed_pairs`
is mandatory. Equality across preprocessing is a separate explicit contract;
it is not assumed for every future mode. Both losses and any count expansion
must remain visible. Missing, negative, malformed or inconsistent counters fail.

The native metric is exactly:

```text
numerator   = results.alignment_stats.counts_total['Prime-edited']
denominator = CRISPResso_mapping_statistics.txt: READS ALIGNED
```

The parser independently reconciles every reference's count and common
denominator with the child file named by `quant_of_editing_freq_filename`:
`Reads_aligned` and `Reads_aligned_all_amplicons`. Integer ratios are retained
using `Fraction`; display rounding is not an input. Nonexclusive/duplicated
reference accounting is rejected rather than silently producing a percentage.

The separate exact-haplotype metric counts full intended PE sequences over
full exact WT + full exact PE sequences. Allele ZIP counts must reconcile to
the aligned cohort. Partial coverage, extra substitutions, indels relative to
the intended haplotype and unresolved products are excluded explicitly. A
WT/PE state collision is excluded; a sequence shared by multiple copies within
the same state is counted once. PE and WT sets are not copy-assignment rules.

Both backend-derived metrics expose integer `backend_input_reads`,
`aligned_reads` and `unaligned_reads`, plus preprocessing count delta, aligned
product exclusions and exclusions relative to backend inputs. The pre-backend
copy-agnostic smoke test labels these counters as describing the separate
confident backend subcohort and records how many pairs were not submitted.
It does not call those subcohort counters the overall metric denominator.

Unless authoritative evidence establishes a cause, unaligned reads have reason
`unknown_backend_alignment_failure`. Short sequence coverage or a synthetic
class name alone is not used to invent `insufficient_length` or an alignment
score failure. Synthetic origin attribution is separate from failure causation.

### Historical M3 regression

The original generator and committed M3 evidence are unchanged. Newly committed
child mapping/quantification files and parsed results are in
[validation/m31/m3_baseline](validation/m31/m3_baseline/metrics.json).

| Child | Routed/input | N_TOT_READS | Aligned | Unaligned | Native PE | Exact PE / exact WT+PE |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| copy1 | 211 | 211 | 199 | 12 | 72/199 | 60/140 |
| copy2 | 139 | 139 | 131 | 8 | 48/131 | 40/90 |
| Combined diagnostic cohort | 350 | 350 | 330 | 20 | 120/330 | 100/230 |

Unaligned fraction: **20/350 = 5.714285…%**. The combined row reconciles a
diagnostic experiment; it does not endorse the original unsafe routing.

Among the 330 aligned reads, exact-denominator exclusions are **60 WT-derived,
20 PE-derived, and 20 origin-unresolved**, established from independent synthetic
truth and actual allele-sequence multiplicities. A separate 20 backend-unaligned
reads are WT-derived in this synthetic fixture. Thus all 350 backend inputs
exclude 80 WT-derived + 20 PE-derived + 20 unresolved reads from the 230-read
exact denominator. The 60/20 comparison refers to aligned imperfect products,
not an omission of backend attrition. Real data receive observable product
classes unless an origin can actually be established.

Here the exact fraction 100/230 (43.478…%) exceeds the native fraction 120/330
(36.363…%). **Exact-haplotype PE is not a conservative lower bound.** Both its
numerator and denominator differ. In the new confident cohort below, it is
lower. Neither direction alone demonstrates better or worse editing quality.

## Verified boundaries

`verify_analysis_output(path)` requires a completed schema-1 preparation
manifest, a non-staging final directory, reverified source M2 identity, exact
sample/mate inventory, paths, sizes, hashes, valid synchronized FASTQs and actual
record counts. It independently compares every prepared record to the source
record after the recorded trim, including header, plus line, sequence and quality.
Zero-read samples pass. It does not merely glob FASTQs or trust writer counters.

`route_analysis` calls that verifier before consuming data. The new production
handoff `run_confident_core` accepts a routing directory and copy identity, not
arbitrary FASTQ paths. `verify_routing_output` reverifies analysis identity,
cohort hashes/counts, ledger membership, unique/exhaustive IDs and preservation
of original prepared record bytes. Quarantine cannot be supplied as a copy.
Preflight and critical integrity failures stop execution. Publication uses a
new staging directory and a completed manifest; failed Core manifests remain
explicitly failed. The older `run_pooled_diagnostic` API remains diagnostic-only.

This closes L4 without changing M2 production modules or expanding M2's threat
model to coordinated rewriting of all trusted metadata (L6 remains out of scope).
Archives must not be concurrently modified. Verification currently retains
read-ID/cohort evidence in memory; large-scale performance is not qualified.

## Target geometry and guide semantics

`geometry(targets, coding=..., primers=...)` requires one biological target and
one shared experimental spacer/extension/nicking-guide/scaffold across its copy
rows. Duplicate guide fields remain a compatibility representation of target-level
metadata; unequal values are rejected. No copy-specific spacer is synthesized.

Biopython **1.85 PairwiseAligner** derives all pairwise WT alignments and diagnostic
alleles, WT→PE substitutions/insertions/deletions, diagnostic/edit distances,
edit-erased diagnostics and changes in similarity to other WT copies. Coordinates
are zero-based, anchored to the lexically first copy's WT; intervals are half-open.
Explicit alignment maps connect each copy's WT/PE coordinates to that anchor.
Repeated/nonunique reference alignments and inter-copy indel geometry are blocked
until separately qualified. Intended edits and read indels are represented by
alignment gaps, not guessed from string length differences.

Every preflight returns SAFE/WARN/BLOCKED and reason codes. Zero distinguishable
copies or no remaining edit-independent diagnostics block copy-specific analysis.
Shared sequences can still support a copy-agnostic exact state call. Coding
annotations are produced only for supplied forward-reference frame offsets 0–2;
codons/amino acids and synonymous/nonsynonymous differences are derived. No frame
is guessed. Primer intervals are compared through reference-coordinate maps;
variation says copy-specific PCR *may* be feasible, not preferable or validated.

Guide occurrence and diagnostic overlap with its window are reported separately
from backend compatibility. A diagnostic inside a spacer is not itself a blocking
rule. An absent experimental spacer is `PE_GUIDE_REFERENCE_MISMATCH_UNSUPPORTED`.
The actual reverse-only-spacer experiment exits with the upstream 3′→5′ error;
preflight now reports `PE_GUIDE_ORIENTATION_UNSUPPORTED` for this configuration.
This closes L3 within the validated orientation convention: spacer forward in WT,
reverse-complement extension in intended PE. No guide rewriting or sequence-check
override is used. Reverse-only occurrence is not asserted to establish biological
guide invalidity; it is an unsupported backend representation here.

Quantification-window overlap is reported, with explicit coordinates preferred.
Pinned-default estimates include spacer and extension-flap windows and any exact
nicking-guide site. Final authoritative indices are retained from the child's
`results.refs.Reference.include_idxs`; backend end exclusions can differ from
the preflight estimate. A diagnostic in a window warns that misrouting can create
generic `Modified` events. It does not prove inflation of precise PE.

No local unpublished ALS-W reference/annotation input was found. The supplied
211-nt/frame/position/codon claims were not hardcoded, confirmed or committed.

## Diagnostic-evidence routing

Both mates align against **every copy's WT and intended PE** using the established
Biopython aligner, not a replacement aligner. R2 is reverse-complemented with its
quality positions reversed for evidence inspection; output records stay unchanged.
Scoring is match +2, mismatch −3, gap-open −6, gap-extension −1, with uncovered
reference ends free for read placement. Every equally scoring placement up to a
recorded cap of 16 is inspected. Nonunique diagnostic coordinates across placements
or haplotypes quarantine the pair. Read/reference identity below 0.8 also rejects
placement; that threshold never chooses one copy over another.

WT and PE placements collapse to copy identity. Any diagnostic altered/removed
by intended editing is excluded from positive copy evidence in *both* states.
Thus the intended edit cannot masquerade as copy origin. Every usable site's
ledger records observed alleles, qualities, mate coverage/agreement, compatible
copies and edit overlap.

Default policy: **Q30**, at least **two distinguishing sites against every other
copy**, all observed non-edit diagnostic alleles consistent with the candidate.
Q20/Q30/Q40 are tested. Low-quality alleles cannot provide positive support, but
contradictory low-quality alleles veto assignment: discarding them could convert
a known mosaic into a false unique winner. High-quality conflicts and mate
disagreements also quarantine; majority voting does not rescue a 3:1 mosaic.

Terminal categories include ASSIGNED_COPY, NO_DIAGNOSTIC_COVERAGE,
LOW_QUALITY_DIAGNOSTICS_ONLY, LOW_QUALITY_CONFLICT, MULTIPLE_COMPATIBLE_COPIES,
INSUFFICIENT_DIAGNOSTIC_SUPPORT, CONFLICTING_DIAGNOSTIC_EVIDENCE, MATE_CONFLICT,
ALIGNMENT_FAILURE and EDIT_DEPENDENT_DIAGNOSTIC_LOSS. Mosaic/chimeric truth falls
under conflicting evidence; real PCR chimerism is not claimed from that label.

No MAPQ, primary hit, AS−XS margin or random tie-break chooses a copy. Biopython
does not supply MAPQ/AS/XS, so those fields are null rather than fabricated.
All haplotype alignment scores are retained as diagnostics. Historical Bowtie2
AS−XS and MAPQ distributions are committed for comparison. Reference reversal
leaves every new ledger decision unchanged; the router has no Bowtie2 RNG.
All pairs partition exactly once into confident copy FASTQs or quarantine.

## Synthetic results and qualification scope

The new fixture retains the artificial 240-bp references and 40/80/165/205
diagnostics with edit 122 G→T, but adds variable qualities and difficult evidence.
Full sequences and independent truth are in [the evidence bundle](validation/m31/README.md).
Copy1/copy2 abundances are unequal (75/50 input pairs). Each ordinary challenge
class has 3/2 reads; WT and precise PE have 12/8 each.

| Truth class | Total | Confident | Quarantined |
| --- | ---: | ---: | ---: |
| WT | 20 | 20 | 0 |
| precise PE | 20 | 20 | 0 |
| PE + extra substitution | 5 | 5 | 0 |
| PE + low-quality unrelated sequencing error | 5 | 5 | 0 |
| unintended indel | 5 | 5 | 0 |
| Q20 diagnostics | 5 | 0 | 5 |
| Q30 diagnostics | 5 | 5 | 0 |
| Q40 diagnostics | 5 | 5 | 0 |
| one diagnostic error | 5 | 0 | 5 |
| two diagnostic errors | 5 | 0 | 5 |
| one observed diagnostic | 5 | 0 | 5 |
| two observed diagnostics | 5 | 5 | 0 |
| terminal truncation (30 nt per end) | 5 | 5 | 0 |
| 3:1 mosaic | 5 | 0 | 5 |
| 2:2 mosaic | 5 | 0 | 5 |
| low-quality conflicting allele | 5 | 0 | 5 |
| mate conflict | 5 | 0 | 5 |
| restricted-site WT | 5 | 0 | 5 |
| restricted-site PE | 5 | 0 | 5 |

| Truth copy | Assigned copy1 | Assigned copy2 | Quarantine |
| --- | ---: | ---: | ---: |
| copy1 | 45 | 0 | 30 |
| copy2 | 0 | 30 | 20 |

**125 input = 75 assigned + 50 quarantined; zero confident cross-assignments.**
Quarantine: 20 conflicting diagnostics, 15 insufficient support, 5 low-quality-only,
5 low-quality conflicts and 5 mate conflicts. Quality sensitivity has no false
mosaic/mate-conflict assignment at Q20, Q30 or Q40. Threshold-dependent retention
is reported by class, not optimized to maximize a pass percentage.

Matched full-coverage WT/PE retention is 20/20 each. A separate edit-overlap
fixture changes diagnostic 40 in both PE references: its full-coverage WT/PE
retention remains 20/20 each using remaining diagnostics; restricted-site WT and
PE both retain 0/5. The loss is controlled symmetrically by ignoring the altered
site in both states. A one-diagnostic target whose edit destroys all copy evidence
is explicitly BLOCKED. This does not qualify arbitrary chimeric or edited-reference
geometries; new panels require their own evidence and bias tests.

An explicitly single-copy assay panel collapses compatible WT/PE placements to
that copy after the same placement checks; no nonexistent second copy is assumed.
As with multi-copy panels, panel completeness/PCR specificity is an experimental
assumption. Ordinary tests cover one and three copies as well as the two-copy run.

Only confident cohorts enter direct Core (no multi-copy Pooled routing):

| Copy | Backend input | Aligned | Unaligned | Native PE | Exact PE |
| --- | ---: | ---: | ---: | ---: | ---: |
| copy1 | 45 | 42 | 3 | 18/42 | 12/30 |
| copy2 | 30 | 28 | 2 | 12/28 | 8/20 |

Aligned exact exclusions: 10 WT-derived + 10 PE-derived. Another 5 backend-unaligned
reads are WT-derived by synthetic truth; their backend failure cause stays unknown.
Native 30/70 (42.857…%) exceeds exact 20/50 (40%) in this same confident cohort.

The separate copy-agnostic exact smoke test examines the *actual original mates*,
requiring matching amplicon ends, complete combined coverage and no disagreement.
It includes quarantine independently of copy identity and obtains **20/(35+20) =
20/55** across all 125 pairs. Its 70 exclusions comprise 35 WT-derived, 15 PE-derived
and 20 unresolved synthetic origins. It does not use synthetic truth to decide
exactness. Internal fragments and uncovered gaps are unassessable. A full-sample
CRISPResso-native primary result is not invented by summing confident subcohorts;
that contract remains a task for production metric implementation.

## Reproduction and limits

```sh
python -m pip install -r requirements-dev.lock
python -m pip install --no-build-isolation --no-deps -e .
python -m pytest -q -m 'not crispresso_integration'
python -m build --no-isolation
M3_INTEGRATION=1 M31_INTEGRATION=1 python -m pytest -q -m crispresso_integration
```

Core/Pooled 2.3.4 are external. Tests accept `M3_CORE_EXECUTABLE`,
`M3_POOLED_EXECUTABLE`, `M3_SAMTOOLS_EXECUTABLE`, `M3_CHILD_CORE_COMMAND`,
`M3_RESULTS_DIR`, `M31_RESULTS_DIR`, and `M31_RUNTIME_IMAGE`. Use new output roots.
The recorded environment uses the same official image digest as M3, Bowtie2 2.5.5,
samtools 1.23.1 and fastp 1.3.3. New Core manifests include the declared runtime
digest, exact argv, hashes, software/Git identity, timestamps and return status;
image inspection and runtime probes accompany the evidence. Docker is not an
application requirement. Failed orientation runs remain explicitly failed.

Normal unit tests cover prepared tampering, gate PASS/FAIL, score ties, missing
coverage, low quality, conflicts, lost informative reads, wrong-copy assignments,
mate conflict, edited diagnostics, indistinguishable copies, >2 copies, permutation,
geometry, native/allele counter parity and non-record-preserving preprocessing.
The historical and new real-backend tests run separately from unit tests.

Qualification applies to the tested closed, correctly specified amplicon panel.
It does not prove PCR specificity, eliminate coincident sequencing errors, or
qualify arbitrary repeats, structural copy differences, unseen edit products or
new reference panels. Inter-copy indels, nonunique geometry, guide mismatch and
reverse-only spacer representation remain explicit blockers.
Memory/performance optimization and production paired-fragment assessability are
not completed. No real FASTQ/BAM or unpublished reference is committed.

After independent review: **SAFE TO PROCEED TO PRODUCTION PE METRICS** as the next
implementation milestone using qualified targets and these explicit denominators;
this is not certification of biological results on an unvalidated target.
