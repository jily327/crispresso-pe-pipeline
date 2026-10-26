# M3.1.1 routing-boundary remediation

This is a focused correction of the independent audit checkpoint
`967e4519f59f7cf0838f2bbc540d37575844ceb2`, whose parent is M3
`e7e67ccef5792682fcf61344e3423f1a2f80d3e3`. Historical evidence under `m3/` and
`m31/` is unchanged. New execution evidence is in [validation/m311](validation/m311/README.md).
No production PE reporting, biological aggregation, statistics or M2 changes are
included. Re-audit is required before merge.

## Copy-level placement contract

For each mate and **every** competing copy, independently evaluate both WT and PE.
Each state must satisfy the recorded placement cap (16 equivalent alignments) and
read identity (0.8). A failing state contributes no placement; it cannot veto a
qualified state of the same copy. Retain every surviving equivalent placement,
not the highest-scoring state. Failure to obtain *any* viable placement for any
competing copy quarantines the pair (`COPY_HAS_NO_QUALIFIED_STATE_PLACEMENT`).
An alternative copy is never silently eliminated by placement failure.

Collapse state placements to their copy before inspecting copy evidence. At each
usable edit-independent diagnostic, all surviving placements, within and across
copies, must agree on the read coordinate, observed base, quality and coverage.
A repeated identical base at a different query coordinate is not equivalent
projection. Disagreement quarantines the pair. Edited/erased diagnostics do not
provide positive evidence or placement vetoes. Low-quality conflicts still veto
assignment. Alignment score, WT/PE score difference, MAPQ, AS−XS and primary
reference choice never supply positive copy evidence.

The manifest records exact parameters and identity
`m311-diagnostic-q30-sites2-cap16-identity08-v1`, with placement contract
`copy-collapsed-state-qc-v1`. Only Q30 / two sites / cap 16 / identity 0.8 is
qualified. Other policies can produce explicitly experimental routing artifacts,
but `run_confident_core` rejects them before invoking a backend. Existing M3.1
artifacts lack this identity and must be rerouted/requalified for the new handoff.
A matching policy identifies the validated algorithm, not blanket biological
qualification of a new panel.

## Geometry and indel qualification

For **each copy pair** and **each edit interval of either copy**, require at least
two usable edit-independent distinguishing sites under the qualified policy.
Also require a distinguishing site strictly before and strictly after the edit.
For a half-open WT interval `[s,e)`, upstream means `p<s` and downstream `p>=e`.
For insertion boundary `b`, require `p<b` and `p>b`. Adjacent changed alignment
columns coalesce into one coherent WT interval, including mixed gap/substitution
columns. Reports include pair-specific flanks, coordinates and nearest distances.
The baseline edit at 122 has upstream 40/80 and downstream 165/205; nearest
distances are 42 and 43 bases.

Missing sides yield `EDIT_NOT_FLANKED_BY_PAIR_DIAGNOSTICS`; insufficient counts
produce `INSUFFICIENT_PAIR_DIAGNOSTICS_FOR_ROUTING_POLICY`. Both BLOCK production
copy-specific admission. They do not declare the biological target invalid or
block all copy-agnostic research analyses. Each read still needs the normal
observed-diagnostic evidence policy; panel-level flanks alone cannot assign it.

No arbitrary maximum PE insertion/deletion length was introduced. Preflight runs
target-specific, symmetric perfect-WT/perfect-PE routing probes for every copy,
using inward-facing 100-nt, 150-nt and full-length mates. Any lost/cross-assigned
control blocks geometry with `PE_EDIT_GEOMETRY_ROUTING_UNQUALIFIED`. Nonunique
reference/edit alignments and inter-copy indels remain separately blocked.

The prespecified challenge grid has 36 designs: insertion/deletion lengths
1, 12, 28, 30, 40, 60; three independent deterministic insertion seeds/edit starts.
Inserted sequences are random sequence, not repetitive homopolymer constructs.
No failed design was removed, retried or selected for convenient alignment.
Each design has 12 routing trials (two copies × two states × three mate lengths).

| Intended edit | Length | Before WT /18 | Before PE /18 | After WT /18 | After PE /18 | Allowed /3 |
|---|---:|---:|---:|---:|---:|---:|
| insertion | 1 | 18 | 18 | 18 | 18 | 3 |
| insertion | 12 | 18 | 18 | 18 | 18 | 3 |
| insertion | 28 | 18 | 18 | 18 | 18 | 2 |
| insertion | 30 | 18 | 14 | 18 | 18 | 3 |
| insertion | 40 | 18 | 14 | 18 | 18 | 1 |
| insertion | 60 | 18 | 10 | 18 | 18 | 0 |
| deletion | 1 | 18 | 18 | 18 | 18 | 1 |
| deletion | 12 | 18 | 18 | 18 | 18 | 0 |
| deletion | 28 | 12 | 18 | 12 | 18 | 0 |
| deletion | 30 | 12 | 18 | 12 | 18 | 0 |
| deletion | 40 | 5 | 0 | 6 | 2 | 0 |
| deletion | 60 | 0 | 18 | 12 | 18 | 0 |

These are raw diagnostic routing trials, including BLOCKED panels; counts are not
production retention estimates. Every allowed design retains 6/6 WT and 6/6 PE
with zero cross-assignment. Overall 13 designs are allowed and 23 BLOCKED.
Residual deletion asymmetry is explicitly **not solved** by guessing placements;
all affected designs are blocked. Some symmetrically routed designs are also
blocked because reference/edit alignment is nonunique. Thus size alone does not
define support. Per-design reasons, exact inserted sequences and every outcome
are recorded in `indels_before.json` and `indels_after.json`. The before router
and geometry were loaded from the unmodified audit checkpoint. These deterministic
fixtures are not claimed to be the auditor's undisclosed exact input sequences.

## Chimeras, difficult reads, and historical behavior

48 single-switch challenges cover flanked, upstream-only, downstream-only, and
three-copy geometry, both switching directions, WT/PE backgrounds, and breakpoints
100/140. All 32 challenges under supported geometry quarantine as conflicting
diagnostics. All 16 one-sided challenges are blocked by geometry before production
admission; their raw diagnostic-only assignments are retained in the evidence.
No challenged chimera is admitted to a production copy cohort.

36 matched difficult reads cover both copies and WT/PE versions of one/two
diagnostic errors, restricted one/two-site coverage, low-quality evidence,
low-quality conflict, mosaics, mate conflict and terminal truncation. The restricted
fragments span the edit, so WT/PE pairs have distinct sequence evidence. Diagnostic
errors use a third allele rather than duplicate mosaic sequences. All 36 underlying
sequence/quality pairs are distinct. Both states show the same category per class:
8 assigned correctly, 28 quarantined, zero cross-assignments.

The **original 125-read fixture is unchanged**: 75 assigned (45 copy1, 30 copy2),
50 quarantined, zero cross-assignments and no unexpected informative loss.
Quarantine remains 20 high-quality conflicts, 15 insufficient support, 5 low-quality
only, 5 low-quality conflicts, 5 mate conflicts. Every historical decision is
compared by read ID in the evidence collection. No historical count is rewritten.
Historical truth aliases and intentional abundance replicates remain for backwards
regression; the byte-identical different-class aliases are explicitly enumerated
in `historical_duplicate_classes.json`. They are not independent evidence.

Two old geometry expectations necessarily change: editing the first diagnostic
(position 40) leaves that edit without an upstream independent flank, and the old
third-copy example differs from copy1 only upstream. Both now BLOCK admission.
Tests retain their raw routing checks. For the separate edited-diagnostic 50-read
fixture, raw routing still gives 40 assignments and 10 quarantines, but the previous
production geometry acceptance is intentionally withdrawn. Its ten restricted-site
reads (copy1: three WT and three PE; copy2: two WT and two PE) now use
`NO_DIAGNOSTIC_COVERAGE` rather than `EDIT_DEPENDENT_DIAGNOSTIC_LOSS`, because the
edited site no longer supplies routing observations or a placement veto. Every
changed read ID is listed in `edited_diagnostic_boundary.json`; none enters a
confident cohort. The original 125-read panel remains eligible.

## Ledger integrity

Verification requires assigned rows to identify a real copy and exactly that
compatible copy; quarantine rows must have null assignment. Replaying the evidence
decision verifies category/compatible-copy semantics. Ledger category totals must
match the manifest; ledger copy totals must match cohort FASTQ counts. Existing
unique/exhaustive ID, exact byte-preservation, input lineage and file-hash checks
remain. Attacks include conflicting-category with a non-null copy, unknown copies,
inconsistent/missing compatibility, forged counts, duplicate/missing IDs, unknown
category and forged policy identity. No new per-read FASTQ memory duplication was
introduced. As before, the verifier holds existing record/ID maps in memory;
large-scale performance and coordinated rewriting of every trusted artifact are
not qualified.

## Qualification-only conventional Core comparator

`backend.comparator.run_comparator` uses all verified prepared pairs, independent
of routing, and invokes actual Core 2.3.4 once with **each** copy's WT/PE anchor.
The one actual experimental pegRNA spacer/extension is preserved for all copies.
The comparator requires the same representable intended edit, comparable edit
coordinates, all anchor results, and conservative exclusion of diagnostics inside
**authoritative backend** `Reference.include_idxs`. Preflight conditions alone are
not a proof: empirical anchor invariance is required. Exact input, aligned,
unaligned, Prime-edited numerator and native denominator must all agree. A missing
anchor or differing integer BLOCKS the comparator; no preferred anchor is selected.
Synthetic results do not establish sufficiency for unseen targets.

| Population | Anchor | Input | Aligned | Unaligned | Native PE |
|---|---|---:|---:|---:|---:|
| M3 all prepared reads | copy1 | 350 | 330 | 20 | 120/330 |
| M3 all prepared reads | copy2 | 350 | 330 | 20 | 120/330 |
| M3.1 all prepared reads | copy1 | 125 | 105 | 20 | 30/105 |
| M3.1 all prepared reads | copy2 | 125 | 105 | 20 | 30/105 |
| M3.1 confident copy1 cohort | copy1 | 45 | 42 | 3 | 18/42 |
| M3.1 confident copy2 cohort | copy2 | 30 | 28 | 2 | 12/28 |

Both all-read experiments are empirically anchor invariant. M3 matches combined
historical Pooled native 120/330. The old Pooled per-copy reconciliation remains
211→199+12 and 139→131+8, totaling 350→330+20. The confident M3.1 cohort combines
to 75→70+5 and native 30/70 (42.8571%). Its 50 quarantined pairs were not submitted.
All-read M3.1 native is 30/105 (28.5714%). Their difference includes population
selection; it must not be presented as merely a native-versus-exact definition gap.

For every actual child, `aligned=N_CACHED_ALN+N_COMPUTED_ALN`,
`unaligned=N_CACHED_NOTALN+N_COMPUTED_NOTALN`, and `N_TOT_READS=aligned+unaligned`
are checked against mapping and quantification tables. No causes are invented for
backend unaligned reads. Native numerator remains
`results.alignment_stats.counts_total['Prime-edited']`; denominator is authoritative
READS ALIGNED. Exact PE remains `exact PE/(exact WT+exact PE)`, never a conservative
lower bound. Confident exact is separately 20/50; original all-pair exact is 20/55.
These have separately labelled populations.

Future names remain distinct: all-read `target_crispresso_native_pe` and
`total_precise_pe`; confident-copy `copyN_crispresso_native_pe` and
`copyN_precise_pe`; QC `routing_quarantine_fraction`, `backend_unaligned_reads`,
and exact-product exclusions. This remediation implements qualification evidence,
not production reports for those metrics.

## Limits and next review

Perfect-read probes qualify their specified geometries, not arbitrary reads,
unseen editing outcomes, arbitrary repeats, structural copy changes or a biologically
incomplete panel. Sparse/uncovered diagnostics, coincident errors and unobservable
multiple template switches cannot establish biological origin. Flanking diagnostics
are necessary support, not a general proof that every conceivable chimera is
recognizable. Some indel targets remain BLOCKED and need a separate scientifically
validated placement architecture before use. No sequencing experiment, copy-specific
PCR design, biological statistics or final report is certified here.

The remediation is ready for a **targeted independent re-audit**, not merge.

Validation: source suite **404 passed**, fresh installed-wheel suite **404 passed**;
each executed **12 actual CRISPResso integration tests**, with zero failures and
zero skips. Source distribution and wheel builds succeeded. See `gate.json` and
the two captured runner logs for the completed qualification checks.
