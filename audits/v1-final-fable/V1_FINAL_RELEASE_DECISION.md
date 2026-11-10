# PEAnalyzer v1.0.0 — Final Release Decision

Audited candidate: `main` @ `00b528e9c2ea7c1b14d8607c5c38ff46416054ae`, package version `1.0.0`. Identity was verified before the audit began and the artifact branch is cut from exactly this commit. No production file was modified.

## Verdict

**`PEANALYZER V1.0.0 FINAL AUDIT: PASS WITH CONDITIONS`**

This is not a statement that the software is proven correct. It is a statement about what a set of independent, deliberately hostile experiments could and could not break, in the environment described below.

## Confidence by dimension

| Dimension | Confidence | Basis |
|---|---|---|
| **Scientific correctness** | **High** for substitution-type PE (single and two-copy) and for nuclease indel quantification; **moderate** for rarer geometry branches | Designed-truth and independent-parse oracles matched every stored count (E03, E06, E07, E08, E33); null never became zero; copy ambiguity never became assignment. Read-through, repeat-period and insertion/deletion PE designs rest on earlier milestone evidence plus code review |
| **Cross-layer integrity** | **High** | Truth = metric JSON = statistics = HTTP view = workbook for every value traced; React performs no arithmetic; bundle reproducible from source |
| **Workflow / lifecycle safety** | **High** | No scenario produced a false `COMPLETED`, a double terminal state, or a registration after failure/cancel |
| **Destructive-operation safety** | **High** within the stated boundary | Every forgery without the local key was refused; nothing unowned was deleted |
| **Recovery usefulness** | **Low** | Cannot recover a run interrupted or failed inside the backend stage (F-01); mislabels two benign situations as tampering (F-01, F-04) |
| **Installed package** | **High** | Wheel built from a clean export is file-for-file identical to source (93/93); same code hash; static assets match their identity record and a fresh rebuild; source suite 1934 passed / 0 failed |
| **Windows / WSL desktop** | **Not established** | NOT VERIFIED — REAL WINDOWS DESKTOP REQUIRED. No recorded evidence from any party that the BAT entry point, Explorer reveal, Windows browser launch or Microsoft Excel has ever been exercised; launcher changed after the last qualification |

## Conditions

**C1 — before calling this an approved Windows desktop release (addresses F-02).** Perform and record one manual smoke test on real Windows + WSL2 Ubuntu-24.04 + Docker Desktop + Microsoft Excel covering: BAT cold start; browser auto-open; upload → Review → Run on a small pool; Explorer reveal; open, edit and close the workbook in Excel while Results is open; relaunch; restart Windows and attempt recovery. Until then, describe the Windows launcher as untested convenience tooling.

**C2 — before users rely on Recovery (addresses F-01, F-04).** Either fix (atomic publication of metrics output; non-accusatory classification; key outside `/tmp`) or, at minimum for 1.0.0, publish a release note stating plainly: *an analysis interrupted or failed during the CRISPResso stage cannot be resumed and must be re-run in a new workspace; "TAMPERED" in that situation does not mean your data were altered.* Correct `docs/m7-workflow.md` line 183.

**C3 — operating instructions that must accompany the release (addresses F-03, F-05, F-07).**
1. Remove samples with no or negligible reads from the sheet before running; one such sample stops the whole analysis.
2. The displayed runtime digest is a declaration. The laboratory is responsible for actually running the pinned image.
3. In nuclease mode, read `any_modification_fraction` alongside `indel_fraction`; compact equal-length replacement events are reported as substitutions.

None of the conditions concerns a wrong number. If C1 and C2 are unacceptable as release notes and must be fixed in code, that is a 1.0.1, not a reason to distrust results produced by 1.0.0.

## Why not "PASS — RELEASE READY"

Two things a reasonable user would assume work, do not, or are unknown: recovering an interrupted analysis, and the Windows entry point of a desktop release. Shipping without saying so would misrepresent the product.

## Why not "FAIL — RELEASE BLOCKED"

By the classification agreed for this audit, blocking requires a wrong or misrepresented scientific result, false verification, deletion outside proven ownership, a corrupted/cancelled result published as complete, or a serious security boundary failure. I tried to cause each and could not. Every defect found fails closed.

## Arguing against my own verdict

*The case that I am being too lenient.* A recovery feature that dead-ends in its main use case and then accuses the user of tampering is arguably "materially misleading UI", and a desktop release whose desktop has never been switched on is arguably not a release. A stricter auditor could reasonably say: fix F-01 and run C1 first, then tag 1.0.0. If the audience for this release is bench scientists using the BAT file with nobody to call, I would side with that stricter view.

*The case that I am being too harsh.* The M11C documentation does say that non-empty unmanifested content is refused, and the desktop documentation does say Windows was not tested. Read strictly, F-01 and F-02 are documented limitations and the verdict could be an unconditional pass. I rejected this because another active document says the opposite about forcing, the GUI's own classification invites the user down a path that cannot succeed, and "we wrote down that we did not test it" does not make an entry point tested.

*The case that my evidence is weaker than it looks.* All reads were perfect synthetic reads; real libraries have errors, chimeras, primer-dimers and uneven depth. The backend was a genuine 2.3.4 but not the pinned image. I drove the HTTP API, not a browser. Cancellation races are probabilistic and I ran each a handful of times. I used substitution edits only. I did not attempt a full coordinated provenance rewrite or a hostile same-account process. A defect living in any of those gaps would not have been seen. The appropriate next step for scientific confidence is one real dataset with known expected editing, run on the pinned image, compared by hand.

## Residual documented limitations (accepted, not defects)

One biological target per workflow; nuclease mode single-copy only; copy metrics are routing-conditioned and can be PE-depleted for insertion edits; verification detects corruption but is not authentication; workspace relocation unsupported; GUI statistics are descriptive only; lease and recovery key are per host/account; no automatic stale-lock removal; CRISPResso remains the sole variant caller.

## What would change this verdict

* To **RELEASE READY**: C1 executed successfully on real hardware; F-01 fixed with a non-empty-orphan regression test (or the limitation prominently released-noted and the misleading label corrected).
* To **RELEASE BLOCKED**: any reproducible case where a stored or displayed fraction disagrees with its own numerator/denominator or with the raw backend output; any case of `Verified` shown for content that fails `verify_workflow_output`; any deletion of a file not listed in an authenticated inventory.
