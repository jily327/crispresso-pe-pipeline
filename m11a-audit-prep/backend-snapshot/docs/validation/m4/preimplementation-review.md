# Review of the authoritative M3.1.2 boundary

Fetched origin before implementation. `origin/main` was exactly
`550df70f9f9627c7218b9f047d0b6bf3023b8d25`. Created
`feat/m4-production-metrics` directly there; `git merge-base HEAD main` returned
that exact SHA. No previous milestone commit was amended or rewritten.

Read the required README, architecture, M3.1 routing, M3.1.1 remediation,
M3.1.2 validation README, complete routing/geometry/Core/comparator sources,
the M3.1/M3.1.1/M3.1.2 unit and integration tests, backend metrics parser,
prepared verifier and qualification code. Inspected committed comparator,
confident-Core, historical Pooled, original-125, indel, ndarray and partial-Core
evidence. Historical roadmap prose is superseded by the later remediation
contracts; it is not an instruction to revert qualified behavior.

Reconstructed contracts before M4 design:

- One shared experimental spacer/extension/nick/scaffold per biological target.
  No copy-specific guide rewriting. Forward-spacer representation is the qualified
  backend convention; mismatch/reverse-only representations remain unsupported.
- Biopython placements retain all qualified WT/PE states for every copy, with
  state-specific QC, then collapse to copy. Scores do not assign a copy.
  Policy is Q30, two distinguishing sites, cap 16, identity 0.8.
- Exact current identity is
  `m312-diagnostic-q30-sites2-cap16-identity08-observed-flanks-v1`, placement
  `copy-collapsed-state-qc-v1`, edit coverage `observed-pair-flanks-v1`.
- Panel geometry requires edit-independent flanks. M3.1.2 also requires observed
  qualified flanks for every potentially covered edit on the same molecule;
  mates can supply opposite flanks, but an unsequenced mate gap is not coverage.
- Handoff re-verifies prepared input lineage, synchronized byte preservation,
  hashes/inventory, policy, geometry, ledger category/compatible-copy semantics,
  exhaustive IDs and cohort counts. It rejects older policy identities.
- Comparator uses all verified prepared pairs once per anchor, not confident
  cohorts. It preserves actual guide/configuration and requires identical input,
  aligned, unaligned, native numerator and denominator. Intended edits/coordinates
  must be comparable; authoritative diagnostic-window overlap blocks.
- Authoritative windows accept plain integer lists or exact ndarray wrappers;
  malformed encodings fail closed. Empty valid arrays are accepted by the old
  parser, as the M4 request explicitly anticipated. M4 adds a production gate.
- Five running alignment counters, mapping and quantification artifacts reconcile.
  Backend input equals routed pairs under the contracted handoff. Preprocessing
  identity is a separate explicit contract, not universal.
- Exact target classification inspects original paired ends, with full combined
  product coverage; backend exact primitives inspect full allele sequences.
  Same-state products deduplicate; WT/PE collisions cannot establish exact state.

Committed evidence agrees with the task's regressions: 125=75+50, confident
45/30, zero changed original-125 decisions; 36 indel designs, 13 allowed/23
blocked; target native 120/330 (M3) and 30/105 (M3.1), confident native 18/42
and 12/28; exact combined 100/230 and 20/50, all-pair M3.1 exact 20/55.
No behavioral conflict requiring a stop was found. The insertion population
limitation is carried explicitly into M4 without changing the observed-flank rule.

Before new M4 tests were introduced, the full baseline with all four integration
switches enabled reproduced **468 passed, zero skips**, including 14 actual
CRISPResso tests. The captured baseline runner output accompanies this review.
