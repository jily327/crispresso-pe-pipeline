# Practical problems and safe next actions

Use the actual visible error code and stage. The doctor is read-only prerequisite
inspection, not a scientific qualification or a guarantee that a destination
will stay writable. It runs `--version` only on the explicitly trusted Core path.

| Symptom/code | Meaning and safest action | Do not do this |
|---|---|---|
| `peanalyzer-viewer: command not found` | Activate `~/.venvs/peanalyzer`; check `python -m pip show crispresso-pe-pipeline` and `command -v peanalyzer-viewer` | Do not install random global packages or run as root |
| GUI import missing | Install the approved wheel with `[gui]` and matching constraints into the intended new venv | Do not use editable development installs as a shortcut |
| CRISPResso not found | Check the absolute `runtime/crispresso-2.3.4/bin/CRISPResso` wrapper path and complete extraction | Do not point at an unrelated executable |
| Wrong Core version / runtime unqualified | Re-provision the pinned runtime into a fresh destination; verify 2.3.4 | Do not edit reported version/digest or loosen qualification |
| Docker unavailable during provisioning | Start the approved local daemon/Desktop WSL integration; check `docker info` | Do not replace native GUI jobs with a `docker run` wrapper |
| No space during runtime install | Free safe unrelated storage or expand WSL disk, then provision into a new destination | Do not delete scientific provenance to make room; partial install is not qualified |
| Port 8765 occupied | Identify your own existing GUI terminal. Reuse it or stop it normally when no job is active; official launcher also accepts `--port 8766` | Do not kill arbitrary processes |
| Windows browser cannot open URL | Keep Ubuntu server alive; use the exact printed `127.0.0.1` URL with token/port; check WSL2 and Microsoft's localhost/network guidance | Do not bind to `0.0.0.0`, expose a LAN port or disable security checks |
| Unauthorized after manual URL entry | Reopen the complete printed token-bearing URL from the current server | Do not publish the token or reuse an old server's token |
| Input path not registered | Stop safely and relaunch with each intended `--setup-fastq` or verified `--setup-demux` registration | Do not inject paths into browser requests or rename files behind a Review |
| Stale Review / `DRAFT_INPUT_CHANGED` | Check intended source bytes and metadata, revalidate the current draft and inspect a fresh Review | Do not submit an old scientific identity |
| Output already exists | Choose a new child workspace; inspect an existing incomplete workspace through Recovery | Do not delete/overwrite a workspace to satisfy a fresh Run |
| `WORKER_BUSY` / ACTIVE | Wait for the active scientific job or containment cleanup to finish, then retry | Do not remove the host lease or workspace lock |
| `STALE_INPUT` | Recorded original source changed/missing; preserve evidence and consult maintainer | Do not edit source hashes or silently replace with a snapshot |
| `SOFTWARE_CHANGED` | Environment differs from recorded provenance; inspect the approved environment and backend-approved recovery options | Do not edit recorded package/backend identity |
| `TAMPERED` / `FOREIGN_CONTENT_PRESENT` | Artifact/ownership/path inconsistency or unknown content blocks safe reuse/deletion | Do not delete unexplained files or patch manifests to make recovery pass |
| `UNANCHORED_RECOVERY_OWNERSHIP` / UNSUPPORTED | Private account-local recovery key/history may be unavailable, or runtime is unsupported; read exact reason | Do not create/copy a key or bypass ownership authentication |
| `CANCELLATION_INCOMPLETE` | Descendant cleanup is not confirmed; preserve job details and seek maintainer help | Do not treat it as cancelled/completed, delete locks or launch a competing job |
| Workspace moved | Stored paths/identities no longer match; relocation is unsupported | Do not rewrite absolute paths inside manifests |
| Original inputs missing | Verifier still needs original sources/GUI durable siblings; locate the untouched originals | Do not treat report-only copies as full workspaces |
| Backend stage fails | Open technical details, record exact stage/code, inspect disk and qualified runtime | Do not convert missing results to zero or change scientific settings to force success |
| Metric BLOCKED/NOT_ASSESSABLE | Existing scientific gate lacks valid evidence for that metric; read its reason | Do not interpret as zero editing or a request to weaken routing |

If you need support, retain the full workspace locally. Share only the minimum
sanitized error details and version information, never recovery keys/session
tokens/private experimental files. The [findings record](SETUP_FINDINGS.md)
separates tested Linux behavior from untested Windows/WSL installation steps.
