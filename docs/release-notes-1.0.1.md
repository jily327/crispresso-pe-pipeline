# PEAnalyzer 1.0.1 maintenance release

This release addresses the Fable final audit without changing scientific definitions, classifiers, alignments, barcode matching, reconstruction, biological statistics or CRISPResso2 2.3.4 integration.

Workflow metrics now publish atomically after validation. Interrupted/failed attempts are retained as private diagnostic directories beside the workspace, and ordinary resume can rerun the missing stage. A rare interruption after publication but before stage completion needs explicit metrics force, using authenticated publication ownership. Force never authorizes deletion of foreign files. Legacy v1.0.0 nonempty interrupted outputs remain unsupported: keep them and start a new workspace. Do not delete unknown content to make recovery proceed.

Recovery keys now persist under `~/.local/share/peanalyzer/recovery/key` (0700 directory, 0600 file). The original `/tmp/peanalyzer-<uid>-recovery/key` is reused when available; neither existing key is overwritten or rotated. Keep the original account and a secure key backup. Missing credentials and authentication mismatch are reported without claiming malicious tampering. WSL shutdown should preserve the Linux home filesystem, but actual WSL/reboot testing remains a manual release gate.

Zero-read samples are identified before metrics execution, with every offending barcode. Correct inputs/orientation or explicitly remove failed wells in Setup/Review and run into a new workspace. Samples are never silently dropped, and unavailable results never become 0%. Nonempty unusable samples still fail the plate contract; partial plate completion is deferred because it would change the workflow's reportability and replicate inventory.

The qualified runtime digest is a **declaration**, not image attestation. The observed CRISPResso version and executable SHA-256 do not prove which image executed (the executable can be a wrapper). Existing `runtime_digest` / `runtime_identity.image_digest` JSON fields retain that declared meaning. Results, Review, reports and Excel explain this limitation. No historical reportability or completed-workspace migration is introduced. The release's local Docker image qualification evidence does not turn arbitrary production wrapper calls into attested executions.

Whitespace-padded barcode IDs follow the existing Sample normalization consistently through Setup, accepted execution and export. Case and barcode sequences are unchanged. Export failure remains a warning independent of verified science.

Use `any_modification_fraction` alongside nuclease `indel_fraction`: CRISPResso may classify compact equal-length deletion/insertion events as substitutions. This upstream contract is unchanged.

The initial qualification showed that local descendant termination alone cannot establish Docker containment: signal-only wrappers can leave Core alive. The shipped `peanalyzer-crispresso` runtime now adds container-side owner-death guards and independent daemon observation before GUI containment confirmation. The supported desktop launcher requires it. Arbitrary external laboratory wrappers remain unqualified; replacing the user's old wrapper requires the installation and actual-PC tests below.

For desktop upgrades install into a new version directory and update `~/peanalyzer-current`; retain the permanent BAT, library root and old analysis directories. The launcher cleans its private URL log on exit. Linux launcher tests and user-reported Windows success are distinct from testing the final launcher on Windows. Follow [the manual checklist](validation/v1.0.1-audit-remediation/WINDOWS_SMOKE_TEST.md).

See [qualification evidence](validation/v1.0.1-audit-remediation/README.md) for actual results and remaining release gates.

Authorized legacy resume also persists its authenticated credential. If a different primary key already exists, it is preserved unchanged and the original credential is saved as `legacy-<nonsecret SHA-256 key ID>` in the same private recovery directory. Read-only inspection never creates or migrates keys. Receipts signed before migration remain recoverable through the archived original key after `/tmp` cleanup. Already-lost original credentials cannot be reconstructed.


## Docker containment deployment follow-up

The maintenance candidate now ships `peanalyzer-crispresso`, a pinned-image, per-invocation Docker runtime with container-side owner-death guards and independent daemon confirmation in GUI supervision. It replaces the unsafe persistent-container `docker exec` wrapper for the supported desktop launcher. No scientific calculation or recovery deletion authorization changed. Install beside the old release and qualify before switching `peanalyzer-current`; the old wrapper is not overwritten. See [installation, exact WSL tests and rollback](docker-runtime-1.0.1.md) and [follow-up qualification](validation/v1.0.1-docker-containment/README.md). Final Windows/WSL/Docker Desktop/Excel testing remains a manual deployment gate.
