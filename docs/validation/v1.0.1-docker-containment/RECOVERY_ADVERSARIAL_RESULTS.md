# Recovery and containment boundaries

Legacy model independently reproduced: killing the local Docker exec client after genuine nonempty output left Core alive. The replacement never relies on the local client exit code alone.

The genuine suite exercises the shipped wrapper with SIGTERM, SIGKILL, killed Docker CLI, and killed supervisor while the wrapper survives. The container guard sees loss of its kernel ownership lease and stops its owned backend. Independent daemon queries must report absent, or Running=false/Pid=0; the tests check this before test cleanup. Successful daemon auto-removal of that exact invocation is sufficient because its PID namespace has ended. No arbitrary container is removed by production code.

The GUI sequence is backend nonzero exit after partial writes, resume, cancel, resume, cancel, resume and verified completion. Each interruption has a real nonempty Core running log. Each terminal GUI state must already satisfy the independent daemon check. No final metrics directory or workflow completion manifest is accepted from partial output. All three planted foreign files in retained attempt directories survive. Successful recovery yields Exact PE 2/400 and a verified completed workspace.

The completion-race case signals the wrapper after the guard records successful backend completion. A wrapper exit race is allowed; an uncontrolled backend is not. Normal successful PE and nuclease workflows run while a test legacy persistent container stays stopped and a separate unrelated idle container stays unchanged.

Unit tests cover missing daemon/image, foreign container identity, observation failure, absent owner, stopped backend escalation, protected mount paths, installer refusal to overwrite, and launcher failures. They are supplemental to genuine Docker tests.

Safety constraints retained: session records authorize observation only; there is no name-based kill, sweep, recursive removal of host outputs or bypass of HMAC ownership. Missing/unreachable daemon evidence leaves GUI containment unconfirmed and retains the analysis lease. Historical unauthenticated partial stage output remains unsupported and must be preserved. Deliberate daemon/root compromise is outside the local account trust boundary; a suspended VM/kernel can delay termination and is not reported as confirmed.
