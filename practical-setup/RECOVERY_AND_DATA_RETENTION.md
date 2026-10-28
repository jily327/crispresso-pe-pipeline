# Reopen, recover, and preserve your data

## Completed results

Activate the same application environment and use:

```bash
bash ./launch-view-results.sh "$HOME/peanalyzer/analyses/my-analysis"
```

This calls official `peanalyzer-viewer --view-only --workspace PATH`. Open the
printed localhost URL. The complete workflow is checked by the existing M10
verifier; a directory or `report.html` alone is not proof of completion. Viewing
does not require Core execution. Do not rewrite a rejected manifest to make it
open. Mutation after registration can evict the workspace from the viewer.

## Cancel an active job

Use **Cancel analysis** and confirm cancellation. Wait for the displayed terminal
state; CANCELLING is not yet finished. Repeated clicking is not a stronger kill.
If cancellation is incomplete, retain the workspace and diagnostic information;
do not delete locks or start another worker to bypass the containment check.
Browser reload can reconnect while the server remains alive. Server restart is
different: use registered workspace recovery rather than expecting live job
memory to survive. Sleep, shutdown or `wsl --shutdown` is not normal cancellation.

## Inspect an interrupted workspace

From the same Linux account and compatible installed environment:

```bash
bash ./launch-recovery.sh "$HOME/peanalyzer/analyses/my-analysis"
```

The wrapper uses official `--recover-workspace PATH --run-crispresso PATH`.
Choose **Recover Analysis**, inspect the classification and stage table. A failed
or cancelled job in the live server also offers **Inspect Recovery**.

| Classification | What to do |
|---|---|
| COMPLETED | Use **Open Results**; the GUI does not offer a completed-workspace recovery run |
| RESUMABLE | Review the current preview and confirm resume if execution is enabled |
| RESUMABLE_WITH_FORCE | Inspect required stage families, descendant stages and exact removal paths; generate a fresh preview and explicitly confirm only if understood |
| STALE_INPUT | Stop: original source identity changed; resolve with the maintainer, never silently substitute snapshots |
| SOFTWARE_CHANGED | Stop and check the approved environment; only a backend-approved explicit full rebuild can replace identities |
| TAMPERED / INVALID_WORKSPACE | Preserve evidence; do not edit hashes, graph, manifest or ownership records |
| ACTIVE | Another host/workspace job or lock remains; do not steal or delete it |
| UNSUPPORTED | Inspect the reason: unavailable runtime and lost/unanchored recovery ownership are different problems |

Classification alone does not authorize execution. The current preview must be
executable and confirmed. Force is **not a generic retry button**. It may delete
owned stages and their descendants. It cannot legalize changed inputs, unknown
foreign files, unsafe paths or corrupt unforced dependencies. Do not add notes or
extra files inside a scientific workspace; keep notes elsewhere. Unknown files
can prevent destructive recovery. Nonempty orphan output without provable
ownership may be refused even if you believe it belongs to a failed run.

## Critical: account-local recovery key

Recovery authentication currently depends on a private account-local key under
`/tmp/peanalyzer-UID-recovery/` (UID is the Linux numeric user ID). **If `/tmp` is
cleared or the key is lost, destructive recovery of an incomplete workspace may
be unavailable** (`UNANCHORED_RECOVERY_OWNERSHIP`). A reboot/shutdown or cleanup
policy may clear `/tmp`; do not assume it preserves recovery authorization.

Do not copy, publish, edit or manually back up this key. The product does not
provide a supported manual key-transfer/backup procedure. Do not manufacture a
replacement key or ownership record. Complete runs normally where possible.
Scientifically valid completed workspaces remain handled through the normal
verifier; loss of recovery ownership is not by itself evidence that completed
scientific results changed.

## Files that must remain

Preserve at their stable paths:

- Original raw FASTQs or the complete external M2 archive, plus registered
  metadata sources where applicable.
- The entire workflow directory, including workflow/stage manifests, provenance,
  analysis/routing/backend outputs, statistics and report.
- Hidden durable sibling directories named **`.NAME.gui-inputs-JOB_ID`** beside
  the workspace. They contain GUI execution inputs and are not temporary trash.

Use `ls -la` on the output parent to see hidden siblings. Do not move/rename an
active or completed workspace, its inputs, or these siblings. Relocation is
unsupported; original source paths and identities remain part of verification.
Copying only figures, metric JSON or the report is useful for sharing but is not
a verifiable/recoverable workflow. Ordinary data backups do not automatically
provide portable recovery; there is no supported key migration here.

This setup study tested completed-workspace view and recovery inspection without
scientific writes. It did not repeat the full interrupted/cancellation audit;
those behaviors remain subject to the final independent M11C.2 qualification.
