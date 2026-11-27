# Presentation and canonical eligibility audit ledger

## SCI-05

The supplied `gate.py` was run against an unmodified archive of `2f567b88628eeb287bacc9febf3b65b3a00bfc7a` using CRISPResso2 2.3.4. It generated ten regular WT pairs, five intended double-edit pairs and one WT pair with physical mate lengths 154/119. The M4 canonical result withheld its numerator and denominator with `STATE_DEPENDENT_PRODUCT_OBSERVABILITY`. The companion reported 5/15 and `ASSESSED`. The latter result is the reproduced defect. [Frozen output](sci05-before.json)

The authoritative M4 record now supplies the canonical population identity, numerator, denominator, eligibility and reasons to the companion. Standalone paired-site classification can report four-state template counts and joint or marginal site measurements. It withholds the canonical ratio until an authoritative M4 record exists. Separate four-template AB and paired-Q30 AB frequencies keep their own population definitions.

The earlier Practical suite recorded zero passes and three skips after it was interrupted. The earlier six Run lifecycle passes do not establish final-remediation backend parity. [Earlier Chromium record](../../v110/browser-regression.json)

## Installed SCI-05 regression

The original auditor's input generator and unchanged `gate.py` ran in a fresh directory with the wheel's Docker wrapper. For the 16 acquired pairs, M4 retained ten exact WT, five exact intended, and one excluded pair as evidence. The matched observability trial found one valid WT overlap and two intended-product overlaps. M4 withheld the canonical fraction with `STATE_DEPENDENT_PRODUCT_OBSERVABILITY`. The companion carried the same population ID, withheld numerator and denominator, and retained the same reason. The group contained zero reportable biological samples for this metric.

A separate check inspected the verified GUI projection and reopened the generated XLSX. The canonical cells, catalog rows, TSV and HTML rows matched M4. The two independent measurement definitions each had 10 WT, 0 A-only, 0 B-only and 5 AB in 15 eligible pairs. The native executions and original counts remain available with their own execution, extraction, parity and runtime statuses. [Installed regression and source hashes](sci05-after.json) · [Surface check](check_scientific_surfaces.py)

## Installed Chromium regressions

The application, backend wrapper and frontend assets came from wheel SHA-256 `5b3cc36ac797cfb9923c02e90a2b860ccfe5ec20dee4d869f8e0f289a882c556`, built from `81c21c8b7dc536a6e2d1a22d446008407f625415`. The browser harness and evidence commits followed this freeze. Each attempt records its harness revision and commands. The wheel stayed byte-identical across attempts. [Commands, source identities, input hashes and individual outcomes](installed-browser-evidence.json) · [Qualification runner](qualify_browser.py)

| Installed suite | Passed | Coverage |
| --- | ---: | --- |
| Run | 6 | Real PE and nuclease runs, stale Review, reconnect, cancel and child cleanup, concurrent submission, backend failure |
| Recovery | 8 | PE and nuclease resume, forced recovery, stale preview, completed open, cancellation, detached child cleanup and server SIGKILL |
| Setup and read-only viewer | 20 | Workspace verification, native report download, site and nuclease views, integrity handling, keyboard, accessibility and reflow |
| Practical | 3 | Browser FASTQ and Excel import, PE and nuclease execution, final verification, workbook integrity and invalid replacement |

The initial installed Practical run passed the invalid-input case. Its PE fixture exceeded the historical 90-second wait while the metrics stage was running. The following nuclease submission encountered the active worker lease. After the browser harness used the explicit qualification job timeout, all three cases ran to completion. The successful PE test took 3.1 minutes. The same assertions for counts, review, final verification, workbook integrity and accessibility remained enabled.

The first viewer fixture check expected suppressed native reports. Both wheel-generated fixtures produced original CRISPResso reports. The updated API checks downloaded every reported HTML artifact, compared its bytes with its bound file and compared its SHA-256 with the verified source identity. Both PE and nuclease fixtures passed. The subsequent browser run found a second harness conflict. The global trial guard intercepted the read-only verifier when it replayed the existing PE routing evidence. Ten tests passed and ten failed. The guard now allows routing recomputation only within the existing-workspace verifier and rejects it during Setup and elsewhere. Scientific stage execution, backend launches, probes and input or workspace changes remain test failures.

The final read-only suite passed all 20 tests with 13 existing-workspace verification calls and zero scientific executor or backend-probe calls. The verifier replayed 176 routing decisions during integrity checks. Workspace files, original inputs and proposed Setup outputs retained their recorded bytes and modification times.
