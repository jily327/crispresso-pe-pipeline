# M11C.2 checkpoint qualification

Implementation candidate: `b4aee11b1f4ba56791a5d36629a14c3e154ae4d8`.
Starting protected feature: `7df52db461b719ee0370c8e4b2416d7f6382a4af`.
Unchanged main: `a1f2fbb5794dfa7be3d5bc614db3baf30f6fb503`.
Package version remains **0.8.0**.

This continuation qualifies the published implementation; it does not reimplement
M11C.2. No production, frontend, or test bytes changed during this continuation.
Documentation/evidence commits descend linearly from the candidate. Source tests
measure the exact candidate checkout; installed tests measure its freshly built
wheel. The published evidence commit has the same production package payload.

## Evidence authority

The previous untracked evidence directory was unavailable. `CHECKPOINT_HANDOFF.txt`
is the supplied authority for already-completed gates: frontend 48, source browser
32, and 92-member direct/clean-checkout/sdist-to-wheel parity. These expensive
completed gates were not rerun. `qualification.json` separates those adopted
results from terminal results observed in this continuation. No interrupted
partial-suite count is represented as a completed suite.

The complete source and installed-wheel suites each include all integration
scenarios; they are serialized, not overlapped with browser scientific jobs.
Integration results are derived from collected pytest markers and matched to
terminal JUnit cases, not guessed from module names. The source inventory is
1,910 = 1,876 retained + 34 M11C.2 cases, including 88 integrations.

## Remediation scope

Only these production files differ from M11C.1:

- `src/peanalyzer/workflow_integrity.py` (new)
- `src/peanalyzer/workflow.py`
- `src/peanalyzer/workflow_recovery.py`
- `src/peanalyzer/gui/recovery.py`
- `src/peanalyzer/gui/jobs.py`
- `src/peanalyzer/gui/supervision.py`

`production.diff` contains the exact diff. `static-checks.json` verifies all 62
frozen science/resource files and all 65 independent audit-preparation files.
The frozen audit source remains commit
`78125e5d3ff20e68921e03843bd44fa5d9de2150`; no audit expectation was rewritten.

## R7 and ownership

HMAC-SHA256 authenticates the original plan, stage manifests (including the
frontier), and completion marker against a private account key outside the
workspace. Receipt identity binds path/device/inode. Workspace JSON agreement
alone never authenticates ownership. Existing recursive content checks still
reject foreign entries before deletion.

The full suites exercise all seven frontier attacks (reason, inventory add/remove,
path, hash, status, parameters), completion inventory/stage hash/final hash/plan/
status attacks, future-stage plan changes, forged ownership with VICTIM.txt,
forged matching receipt records, directory replacement, and missing/forged/copied
receipts or unavailable keys. Rejection occurs before execution or invalidation;
workspace snapshots, including the victim, remain unchanged.

Intact interruptions resume. Genuine source drift remains STALE_INPUT. Genuine
backend drift requires the existing metrics force family where appropriate.
Unanchored legacy recovery refuses with UNANCHORED_RECOVERY_OWNERSHIP; completed
legacy scientific results still pass the existing portable verifier where valid.

## Lifecycle and signaling

CONTAINMENT_ERROR remains diagnostic history while RUNNING is cancellable and
CANCELLING remains active. Lifecycle traces cover transient success, cancellation,
real stage failure and persistent uncertainty. Each emits one terminal result;
clean success/cancellation has no stale final error. The terminal guard rejects
all later terminal transitions and observations. Failed/cancelled jobs never
register completed scientific results.

Persistent census uncertainty stops already-known births, commits authoritative
failure after the scientific child exits, and retains the guardian/lease until
positive containment. C7 fault tests cover census, pidfd opening/delivery, TERM
and KILL failures. Successful signal delivery is once per birth/phase; failed
attempts retry no faster than 250 ms. Tests include TERM/KILL retry, exit before
retry, PID reuse and one-success accounting. The early-child PID fixture uses
atomic publication; the retained 80 cancellation cases exercise the real cleanup
records. W2 foreign-content and G6 REUSED semantics remain covered.

The independent frozen force-closure oracle checks every family subset for run
and analyze: **192 allowed / 64 blocked / 0 mismatches**.

## Scientific parity

Full-suite native Core 2.3.4 fixtures independently regenerate PE **2/24**, nuclease
**8/20**, and ambiguous PE native **BLOCKED/null**, precise **12/24**. Every mode
compares fresh/resumed/forced scientific projections and deterministic FASTQ,
routing and report payloads. Root-specific provenance and authenticated recovery
receipts are not claimed byte-identical across roots or installations. Serialized
source and wheel evidence records exact projection hashes and product counts.

## Operational notes and limitations

Source/wheel/process/browser scientific runs are serialized around the shared
host/account lease. This environment initially had less than 32 MB free; obsolete
rebuildable virtual environments were removed before exhaustion. Historical
scientific results and evidence were retained. This was infrastructure maintenance,
not a product change.

Recovery authentication is local to the signing account/host. The private key in
/tmp is not published. Losing it, moving workspaces/hosts, or a crash between
metadata and receipt publication can require a fresh workspace. No retroactive
trust is claimed. A process with code execution as the signing account/root is
outside this trust boundary; authenticated rollback is not prevented by a trusted
monotonic counter. The existing same-account filesystem writer race and Linux/WSL
process-support boundaries remain documented in docs/m11c-recovery.md.

No PR, merge, rebase, force push, science change, or redesign is part of this
qualification. The checkpoint branch is retained. Only after all remaining gates
pass may the feature branch fast-forward to the final evidence-bearing descendant.

## Qualification checkpoint — source complete

Source: **1,910 passed, 0 failures/errors/skips**, including **88 integrations**,
**34 M11C.2 cases**, and **80 cancellation-stress cases**. Wheel Python and
installed-wheel browser gates remain pending. **Do not promote yet.**
