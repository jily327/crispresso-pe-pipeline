# Findings disposition

| Finding | Disposition |
|---|---|
| V-01 | Corrected by canonicalizing only the configured executable alias before the existing no-symlink target check. Integrated installed-wheel regression and stale-alias checks passed; see test matrix. |
| V-02 | Exact `--version` uses the private invocation control directory; caller cwd and configured analysis roots are not mounted. Scientific mounts unchanged. Daemon-observed tests cover home, a Linux path with spaces/comma, and a Linux stand-in for Windows input storage. The stand-in is not `/mnt/c` qualification. |
| V-03 | Deferred CLI abrupt-caller-death enhancement. Wrapper TERM/KILL is contained; generic parent TERM/KILL alone does not release the wrapper's lease. Actual CLI SIGTERM unwinds its subprocess; SIGKILL cannot. GUI supervision adds a separate lease and process-tree containment. No claim of standalone upstream-parent death containment. |
| V-04 | Accepted retained private diagnostics, session directories and failed attempts. No automatic recursive cleanup added. |
| V-05 | Accepted unbounded fail-closed wait when independent containment cannot be established; do not release the host lease or advertise safe recovery. |
| V-06 | Accepted stale invocation lock after hard kill; never steal/remove automatically. Manual ownership review remains necessary. |
| V-07 | Corrected documentation: archive SHA identifies a build; controlled repeat equality is not arbitrary-checkout reproducibility. Member hashes establish application payload equality. |
| V-08 | Accepted upstream Core restriction on spaces/quotes/semicolons in scientific cwd. Private probe cwd avoids that concern for version probes only. |
| V-09 | Accepted whole-plate failure on empty/unusable sample. Earlier sample-specific diagnostic retained; no silent omission or zero measurement. |
| V-10 | Accepted conservative scientific provenance wording. Local daemon observation remains in runtime diagnostics; no retroactive image attestation claim. |
| V-11 | Version-neutral incompatible-viewer labels in discovery and failed Open. Compatibility rules and historical provenance unchanged. |
| Windows | OPEN deployment gate. Native Linux tests cannot establish Docker Desktop lock-release propagation, BAT/Explorer/Excel or real `/mnt/c` behavior. |

## Why executable resolution, not another wrapper

New workflow planning already resolves the alias, probes the resolved executable, and stores its canonical path and SHA-256. Recovery was applying a different path rule to the same configured command. A second regular wrapper would introduce another executable identity and deployment behavior without fixing that inconsistency for existing installations. Recovery now matches planning while remaining read-only: it hashes the resolved file but never invokes a probe during Inspect.

The accepted recovery digest binds the canonical backend identity, software identity and workspace preflight. Submission re-inspects, the worker re-inspects, and workflow execution rebuilds/probes and compares the accepted plan before invalidation. Each metrics stage checks the executable hash. Retargeting an alias after preview cannot authorize a changed plan through stale consent. Existing completed-metrics provenance rejects a different canonical backend even when its bytes are copied unchanged. Workspace, output, receipt and invocation-lock paths still use the original no-symlink checks. Same-account executable replacement is not a new adversarial security boundary; this patch does not promise cryptographic trust against the account that can rewrite executable code or signing keys.

Historical completed results are not rewritten. Historical incomplete runs retain software-identity checks and explicit force requirements; unauthenticated v1.0.0 nonempty partial output remains fail-closed. The permanent `peanalyzer-current` symlink and launcher target equality check remain unchanged.

## V-03 decision

A wrapper's immediate parent can be a shell, an executing shell, a workflow subprocess, or a detached launcher. Blind `PR_SET_PDEATHSIG` would change valid standalone/detached lifetimes and requires a parent-identity race protocol. Adding a workflow ownership lease spans CLI exception handling and backend launch contracts. That is outside this alias/probe maintenance correction. The narrower documented contract is retained and independently tested, without weakening GUI containment or calling a living backend stopped.

V-07 was independently exercised again: the candidate wheel built under the original conditions had SHA-256 `eec784af76f9649f7ca054d9320efeddf3da10c880af1bbfb32f7c1a227d0775`; a clean copied tree built with umask `0002` produced `8a6efc0eeb9735e0714b38b2d9c1c7488f0e71dd6526b9d0a41000b014aa39e3`. Every archive member's content hash was identical, while ZIP mode attributes differed. Merely changing one source file's group-write bit under the original umask had not changed the wheel, so that first experimental assumption was rejected. See `evidence/mode-build.json`.
