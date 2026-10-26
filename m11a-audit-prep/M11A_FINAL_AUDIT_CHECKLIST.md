# M11A final candidate audit checklist

This checklist is ready for a **stable implementation candidate**. It is not a
PASS for M11A. Pin authority to backend main
`40bd8ad8844fd07ce8a138b5520f7f0ec948030f` and design
`05cfc68b62215a4c52862e09f081eab1c75ba39f`. Read the active brief before applying
older design's execution actions: M11A ends at Review/validated preview.

## Intake and reproducibility

- [ ] Obtain implementer's declared stable branch and full SHA. Record main,
  candidate, parent/diff, package version, clean status, Python/dependency versions,
  OS/browser, frontend lockfile/build-tool versions and asset hashes.
- [ ] Inspect a detached/exported candidate outside the implementing checkout.
  Never modify its source, working branch or development refs. Record remote SHA
  again at finish. If it changes, label findings preliminary and re-pin evidence;
  no final PASS until stability is explicitly established.
- [ ] Map actual candidate routes/models/reducers to conceptual adapters in the
  matrix. Read server validation, async revision binding, active-mode projection,
  input path registration, destination checks and build/package resource loader.
- [ ] Review diff for scientific changes and unexpected execution dependencies.
  Separate existing contract behavior from candidate regressions. No broad M10
  reopening, no M11B execution implementation and no synthetic science rerun.
- [ ] Verify baseline oracle source hashes against pinned Git objects and rerun
  its 85 checks in an isolated environment if dependencies differ. Keep baseline
  results separate from candidate results; do not rewrite expected values to
  match the candidate.

## Run order and evidence

1. Run isolated positive/negative instrumentation canaries. Activate executor and
   process traps in the server, and file mutation monitoring around authorized
   roots. Record attempted calls even when caught; stop/discard the instrumented
   process after a trap. Do not run existing M10 workspace verification under
   the setup-only geometry restriction.
2. Apply Z01–Z10 before expensive browser testing. Open/setup/validate/preview
   both modes, raw and M2 sources, valid and invalid drafts, with Core absent.
   No workflow lock/session, scientific directory or report may be created.
3. Apply S/P/N cases through the real API and visible UI. Compare independent
   literals, strict errors and accepted controls. Confirm supported backend
   fields are not made falsely mandatory, unsupported controls are not silently
   enabled, and profile/runtime requirements are not misrepresented as observed
   qualification.
4. Apply R/M races using deterministic barriers. Immediately invalidate Review
   on edits; test late successes/errors, mode switches and Open Existing/New
   Analysis transitions. Abort alone is insufficient.
5. Apply I/O/V/U groups: scientific identity, filesystem safety, Review mapping,
   hidden/filtered/below-fold error navigation. Record screenshots plus network
   payloads and DOM assertions. A screenshot alone cannot prove ownership of
   geometry or current response identity.
6. Apply only the six G cases for M10 preservation, then the eight K packaging
   cases. Re-run high-value Z, N02/N03/N14, one PE indel and one stale-response
   attack against the installed artifact, not just the development server.
7. Fill each of 128 case records with PASS/FAIL/NOT RUN/NOT APPLICABLE, exact SHA,
   reproducer, expected/actual and evidence path. Expand parameterized cases
   explicitly; do not count the 85 baseline checks as candidate coverage.

## Required hidden-error UX checks

Filter out an invalid sample and invoke validation. Error summary must retain
its stable row identity, count and reason. Selecting it must reveal the row
(clear/adjust filter or otherwise expose it), navigate to the correct step,
scroll into view and focus a useful field. Repeat below viewport and across
steps with several errors. Correct one error and ensure remaining errors persist.
Press Review immediately after an edit: no previous-valid shortcut. A read-only
stale preview can be retained as clearly labeled history, never as current ready
state. Keyboard use must reach the error without relying only on color or hover.

## Narrow retained M10 regression

Use previously committed synthetic complete workspaces appropriate to the pinned
M10 viewer; do not launch workflows to regenerate them. Record fixture identity.
Verify open/Overview/result tabs and existing snapshot integrity behavior. Tamper
only with a disposable copy to ensure the viewer retains its rejection behavior.
Capture viewer snapshot/identity before and after creating an invalid setup
 draft. New Analysis state and pending responses must not overwrite the open
workspace's data; opening an existing workspace must not overwrite a draft's
scientific inputs. These six cases are sufficient for this preparation scope;
new evidence, not curiosity, would justify wider investigation.

## Packaging chain and offline runtime

- [ ] In a disposable clean checkout at stable SHA, identify the actual frontend
  package manager lockfile/build command and existing Python packaging policy.
  Build assets using that locked toolchain; record source/build manifest, asset
  list and hashes. Do not assume hard-coded filenames or require a new packaging
  architecture merely for this audit.
- [ ] Build wheel and sdist using project configuration. Inspect both archives
  for setup/viewer Python modules, schemas/resources, HTML and JS/CSS assets.
  Check no stale M10-only bundle or source/build identity mismatch. Include
  source resources required to rebuild according to project policy.
- [ ] Unpack the sdist outside the checkout and build a fresh wheel from it.
  If frontend rebuilding is required, use the documented build environment;
  Node may be a build dependency but never a runtime requirement. Record whether
  shipped assets or an actual rebuild supplied the resulting bundle.
- [ ] Install each wheel into clean environments outside the source checkout.
  Assert package import originates in site-packages; unset PYTHONPATH and avoid
  editable installations. Record package version and resource paths. Compare
  corresponding asset identity and scientific preview payloads, allowing only
  documented build/provenance envelope differences, never stale UI semantics.
- [ ] Runtime: remove Node/npm and CRISPResso from the executable search path or
  use an isolated environment with neither installed. Show which checks prove
  absence. Launch the packaged GUI; New Analysis and retained viewer must load,
  including refresh/deep links/static resources supported by the product.
  No asset build, CDN fetch or external Core probe may be needed at runtime.
- [ ] Instrument installed server as well as source. Repeat representative
  valid/invalid targets, W1–W4/default W2/explicit 0-0/sentinel 0, PE indel preview,
  and race/zero-write checks. Compare API payload to visible Review. Source-only
  success does not qualify the distributed package.
- [ ] Document fresh install commands, build logs, hashes and origin evidence.
  Unexpected environment failures are NOT RUN/blocked evidence, not product
  PASS or automatic product failure. No backend science execution is necessary
  to qualify this setup-only milestone.

## Severity and final decision

Use the matrix rubric. A broad try/except that hides a forbidden attempt does
not reduce severity. No final PASS if a BLOCKING or unresolved material MAJOR
finding remains; report exact conditions and evidence, without changing code.
MINOR/INFO observations must not expand implementation scope by themselves.
A candidate still changing can receive preliminary findings only.

Final audit report should identify stable SHA, scope, observed case/assertion
counts, failures/not-run items, environment and source/wheel/sdist evidence.
Separate backend authority from candidate outcomes and test-harness limitations.
Confirm no repository modifications/commits/pushes/PR/merge. Never claim runtime
qualification or scientific results from a deterministic draft preview.

## Prepared evidence index

- [Backend map](M11A_BACKEND_CONTRACT_AUDIT.md): 64 exact symbols and boundary risks.
- [Matrix](M11A_ADVERSARIAL_TEST_MATRIX.md): 128 candidate cases and attack protocols.
- [Oracles](M11A_ORACLE_FIXTURES.md): 85 observed baseline checks with independent goldens.
- [Machine-readable cases](case-inventory.json): candidate status remains NOT RUN.
- [Literal fixtures](oracle-fixtures.json) and [observations](oracle-observations.json).
- [Tripwire helper](zero_execution_traps.py): audit-process instrumentation, not application code.
- [Source inventory](source-inventory.json): pinned authority and inspected source hashes.
- `backend-snapshot/` and `design-snapshot/`: unchanged Git exports used for this preparation.
