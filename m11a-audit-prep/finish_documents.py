from pathlib import Path
import json
P=Path(__file__).resolve().parent
matrix='''# M11A adversarial audit matrix

This is a prepared test plan, **not candidate test results**. Authority is merged
main `40bd8ad8844fd07ce8a138b5520f7f0ec948030f` (0.8.0), with final design at
`05cfc68b62215a4c52862e09f081eab1c75ba39f`. The current M11A brief restricts the
five setup steps to backend-owned preview. The full design's later execution
features are out of scope.

There are **128 uniquely identified candidate cases** in
[case-inventory.json](case-inventory.json). Parameterized controls may produce
more individual assertions. All are NOT RUN against a stable M11A candidate.
The separate 85 observed baseline checks are documented in
[M11A_ORACLE_FIXTURES.md](M11A_ORACLE_FIXTURES.md).

## Bind the candidate without inventing an API

At stable candidate intake, record the actual draft schema, validation handler,
preview handler, input registration/file-selection boundary, response model,
frontend store/reducer and request cancellation code, with commit/line references.
`validate(draft)` and `preview(draft)` below are conceptual audit adapter names,
not claims that those endpoints already exist. A read-only complete-draft POST is
acceptable; an HTTP 200 by itself does not imply validity. Assert typed response
state and the absence of a current valid plan on invalid inputs.

For every case preserve input bytes and hashes, draft revision, response payload,
UI observations, executor-attempt log, filesystem diff and candidate SHA. Use only
synthetic fixtures and explicitly authorized local paths. Do not replay a real
experimental dataset merely to test a form.

## Zero execution: instrument the API process

Install [zero_execution_traps.py](zero_execution_traps.py) **inside the candidate
Python process**, after imports and before each setup action. Patching the test's
HTTP client cannot intercept the server. The exact-symbol inventory covers
workflow planning/execution/resume/invalidation, demux/barcode classification,
preparation, PE routing (including route_pair), comparator/Core, PE and nuclease
metrics, aggregation/statistics and report rendering. Process traps include
subprocess, os spawn/exec/fork/system, and asyncio subprocess entry points.

Pure Pydantic model checks, CSV/YAML loading, authorized read-only FASTQ
inspection, hashing, pure nuclease geometry and existing reference annotation
helpers remain permitted. Geometry's intended-indel branch is not pure: it calls
route_pair for synthetic qualification. An indel draft must not use that branch
merely to draw an annotation. A safely reported unavailable annotation is better
than fabricated qualification, but check candidate scope before accepting an
omitted required feature.

The helper patches module aliases and profiles original Python function code to
catch previously captured aliases/default arguments. Run a positive pure-model
control and a deliberate forbidden-call canary in separate processes before
candidate testing. Any attempted call is a failure even if the application
catches the trap. Discard that audit process after the first forbidden attempt:
Python may disable a profile hook when it raises. This is an audit instrument,
not a hostile-code sandbox; native extensions and a separately started server
need independent OS process/file monitoring. For older Python, existing worker
threads may not inherit profiling: use a fresh server or instrument them
explicitly. Source checkout and installed wheel both need testing because
software_provenance may run git only in the former.

Start the candidate server outside the request-scoped subprocess trap, then
observe each setup request, initial capabilities fetch and delayed/background
work. Capture process creation for the whole session too: bootstrap must not
probe CRISPResso merely to enable New Analysis. A precomputed package version is
not evidence of an installed, qualified Core executable. No demux dry-run is
permitted to compute preview assignment counts.

## Exact revision-race protocol

Use controllable HTTP response barriers or deferred promises, not sleep-based
ordering. Record both frontend draft identity and submitted content identity.
A response can be applied only to the exact current draft/revision/content it
validated. Cancellation is an optimization, never proof that an old response
cannot arrive. An equivalent monotonic token or immutable draft-key mechanism
is acceptable; literal field names are not prescribed.

1. **Late validation:** enter valid draft D at revision r; hold validation A.
   Change a scientific field to invalid content at r+1. Immediately assert old
   validity/Review is stale. Deliver A's success: r+1 stays invalid/unvalidated.
   Reverse success/error order too: a stale error must not replace newer success.
2. **Late preview across mode:** hold PE preview A; switch to nuclease, establish
   its current validation B; deliver A. No PE copy, intended product, guide,
   scientific identity or stage graph appears as current nuclease Review.
3. **Review-visible edit:** obtain valid Review, edit WT/qwc in another step.
   Before any network response, current Review must disappear or become clearly
   stale and unusable. A stale card may remain as history only if never presented
   as the current valid plan. Direct Review navigation must await current checks.
4. **File/sample change:** replace a registered FASTQ with same-name/same-size
   different bytes or change a barcode row. Old identity is invalid; current
   preview uses freshly established content identity. A UI revision alone does
   not detect external file mutation: recheck at the validation/preview boundary.
5. **A→B→A and tab lifetimes:** returning to equal visible text does not authorize
   an old response for a different file inventory, mode epoch or draft instance.
   Unmount/remount and Open Existing transitions must not resurrect a pending
   response into another draft. Test both success and error envelopes.

API response metadata may carry request/revision tokens, separate from the
canonical scientific payload. Do not put timestamps/request IDs into the
scientific digest. A server may reject an obsolete request or return a response
bound to its submitted snapshot; the frontend must still refuse stale display.

## Active-mode isolation

Save distinct PE and nuclease drafts with unmistakable sentinels. Cycle both
ways and inspect **the actual request and backend normalized payload**, not just
hidden inputs. Retaining inactive local drafts is allowed. Inactive fields must
not reach the active strict target model or alter its scientific identity.
Inject PE extras directly into a nuclease target request and require rejection
under its extra-forbid model. Also switch explicit qwc ↔ TIGR: inactive qwc or
selected W1–W4 must not override the currently selected contract. No automatic
reverse-complement rescue, per-copy guide invention or target reconstruction.

## No-write and path audit protocol

Before and after every setup action, snapshot the scientific destination, its
parent, all input roots, any open existing workspace, and sibling lock/staging
locations. Record relative entries, lstat type/mode, size, mtime_ns, symlink target
and streamed SHA-256 for regular files. Do not follow symlinks; ignore atime,
which reads may legitimately change. For missing destinations record absence.
Use a dedicated scratch parent so unrelated activity cannot mask changes.

Also log or deny writes, mkdir, unlink, rename/replace, chmod/truncate and lock
creation in these locations; snapshots alone miss a create-then-delete probe.
Python audit hooks or OS syscall tracing can complement monkeypatches. Confirm
hook effectiveness with a canary in a separate scratch directory before the
real test. Authorized GUI draft/cache writes must be explicitly located outside
scientific input/output and existing viewer roots, with a documented allowlist.
Do not whitelist all of /tmp or the whole workspace.

Test relative ../, absolute injected child paths, symlink ancestors/leaves and
opaque-handle forgery at the server boundary. Resolve authorized local roots and
reject path escapes before reading; the existing no_symlinks helper normalizes
.. and is not itself an approved-root policy. Test read-only destinations as an
unprivileged user: root permission bypass is not a passing writability test.
Existing empty/nonempty/PEAnalyzer roots are invalid for a **new** run under the
current workflow contract, never an implicit resume. Validation must not touch
any root, even an invalid one. Do not run execute_workflow to discover this: it
can create a parent and lock before it finishes planning.

## Outcome and severity interpretation

Input classification is separate from finding severity. BLOCKING INVALID means
that draft cannot produce a current valid scientific preview. VALID WITH WARNING
means accepted under the real contract with an explicit unresolved limitation.
PRESENTATION-ONLY means display changes do not change the scientific payload.
A valid control with no required warning is marked VALID; do not fabricate
warnings solely to fit three labels. Read assignment cannot be claimed before
demux, and missing biological metadata cannot be invented.

| Finding severity | Decision rule |
|---|---|
| BLOCKING | Science/probe execution; scientific workspace mutation; unsafe filesystem access; stale response accepted as current; invalid draft promoted to valid scientific plan; active-mode contamination; independent frontend geometry that disagrees with Python. |
| MAJOR | Material sample/target/window mapping error; Review differs from authoritative preview; scientifically meaningful identity edit missed, without a stronger BLOCKING invariant already violated. |
| MINOR | Recoverable discoverability/focus/label issue with correct backend rejection and no invalid current plan. Escalate if it hides a blocking error or permits invalid preview. |
| INFO | Evidence/documentation limitation or supported behavior that is surprising but preserves correctness. |

Per-row severities below are starting points, not a cap. A row marked MAJOR
becomes BLOCKING when it produces a valid-looking plan for invalid inputs.
Reproduce against a fixed SHA, give expected/actual and precise evidence, and
separate audit harness failure from product failure. These are hypotheses until
applied; no findings are asserted against an unseen M11A implementation.

'''
(P/'M11A_ADVERSARIAL_TEST_MATRIX.md').write_text(matrix+(P/'matrix-tables.md').read_text())

oracle='''# M11A independent oracle fixtures

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
PYTHONDONTWRITEBYTECODE=1 MPLCONFIGDIR=/tmp/m11a-audit-mpl \\
  /workspace/validation/m101/venv/bin/python \\
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
'''
data=json.loads((P/'oracle-observations.json').read_text())
def esc(v):return str(v).replace('|','\\|').replace('\n',' ')
for r in data['observations']:
 val=json.dumps(r['expected'],ensure_ascii=False,separators=(',',':'))
 oracle+=f"| {r['id']} | {esc(r['contract'])} | {esc(val)}{' (expected rejection/trap)' if r['error'] else ''} | {'yes' if r['matched'] else 'NO'} |\n"
(P/'M11A_ORACLE_FIXTURES.md').write_text(oracle)

checklist='''# M11A final candidate audit checklist

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
'''
(P/'M11A_FINAL_AUDIT_CHECKLIST.md').write_text(checklist)
print('Wrote three remaining primary documents')
