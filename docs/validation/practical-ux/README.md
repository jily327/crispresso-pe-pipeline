# Practical UX qualification — in progress

Base: `72e0f86a495e079cab2ae50d2796e7a3423c78af`.
Branch: `feat/practical-ux-inputs`. Package: 0.8.0 → 0.9.0.

The initial durable implementation checkpoint passed 116 focused Python cases,
169 retained GUI/Setup/Run/M11C.2 cases, and 56 frontend cases (zero failures,
errors or skips in those successful runs). A final reader ZIP-part restriction
was additionally checked against all 35 workbook cases plus the version case.
Generated frontend assets pass the existing identity gate.

The source hashes in frozen-core.json prove scientific Python modules outside
GUI and the explicitly frozen GUI execution/jobs/worker/recovery models remain
byte-identical to the base. Full source/wheel, browser and real native-Core
transport-parity qualification are still pending. This is not an audit pass.

Transient development findings were test harness/expectation defects: the first
20-sample spreadsheet used non-catalog letters; a mocked download returned no
Promise; and a retained denominator-label assertion needed its new explicit
Denominator prefix. No scientific rule was changed to satisfy those tests.

## Parity/browser checkpoint

Two compiler identity cases and two native-Core integration cases pass. The
legacy/manual and uploaded/XLSX routes have equal scientific inputs and outputs
for PE and nuclease; current identities deliberately include input basenames.
Same-basename equivalent inputs also have identical plan/scientific digests.

Browser tests use actual File inputs and the real native backend. A test-only
worker pauses the authoritative FINAL_VALIDATION event before continuing; it
never changes production job semantics. An earlier reader-thread pause was a
harness defect (delayed containment acknowledgement), replaced with a producer
pause. Other browser harness corrections concerned response-body lifetime and
asserting two equal primary metric counts instead of one.

Full release qualification will run only after this test checkpoint is pushed.

## Complete source gate

All 1,972 source cases passed (0 failures/errors/skips), including all 1,910
retained cases and 62 new cases. Integration inventory: 88 retained + 2 new = 90.
The fresh wheel builds and imports 0.9.0 from site-packages; its 89 packaged
application/resource files match source bytes. Full wheel and retained browser
qualification remain pending. PE/nuclease 0.8.0 baseline science matches 0.9.0;
the only compared SVG change is the package-version creator credit.

## Complete source browser gate

35/35 pass: viewer/Setup 18, Run 6, Recovery 8, new practical inputs 3.
Zero failures, skipped or flaky cases. The viewer recorded zero scientific calls
and unchanged input/workspace bytes and mtimes. The frozen byte inventory now
also includes unchanged supervision, process safety, setup validation and viewer
verification modules (64 files total).

The first wheel test workspace, extracted from the sdist, lacked a historical
nuclease audit fixture and developer type-generator script. Four tests failed
with FileNotFoundError. Copying the exact committed audit inputs fixed all four;
no wheel or production change was made. The complete wheel suite was restarted
with fresh results. Its final gate remains pending here.

## Wheel runner interruption

A later complete wheel attempt stopped after 1,757 reported passes, without an
assertion failure, final JUnit file or recoverable tool-session status. No process
remained; cgroup OOM counters were zero and disk space remained available. Cause
is undetermined. Both installed-wheel real transport-parity cases subsequently
passed in isolation (44.83 seconds), with unchanged production/wheel bytes. The
complete wheel suite is being repeated under a detached qualification supervisor
that records its exit status explicitly. No incomplete run is counted as a pass.
