# The qualified native CRISPResso runtime

Both PE and nuclease GUI execution require **CRISPResso 2.3.4**. Viewing and
Setup/Review can run without Core by using `peanalyzer-viewer --view-only`.
A version string alone is not proof of runtime qualification.

The existing M11C qualification extracted the complete `/CRISPResso2` tree,
including its pinned Pixi Python/environment, from:

```text
pinellolab/crispresso2@sha256:b7e7971a87769aa584d31d21e199a9abca5f641c4f889c2e807cb6324fc8ce0c
```

The corresponding inspected image ID is:
`sha256:518eb6dd6672f4edee8ec464b75d7555cf04ca185ce1ca676d7b930bde24655d`.
This runbook independently reproduced that extraction and native execution.
Do not replace it with `latest`, an arbitrary Conda environment, or a different
binary that happens to print 2.3.4.

## Provision once under Ubuntu/WSL

You need a working Docker client/daemon **only for provisioning the pinned files**.
A practical Windows route is Docker Desktop with the WSL2 backend and integration
enabled for Ubuntu 24.04. Follow https://docs.docker.com/desktop/setup/install/windows-install/
and https://docs.docker.com/desktop/features/wsl/ . Start Docker Desktop, then
check `docker info` in Ubuntu. Alternatively an administrator may provision a
local Docker Engine. This study's Linux daemon was already available; the Docker
Desktop installation and WSL integration need confirmation on your PC.

Allow several GB of free disk for image layers, a stopped extraction container,
the native copy and Python environments; **10 GB of free setup space** is a
practical allowance, additional to all sequencing data and outputs.

From this setup directory:

```bash
bash ./install-runtime.sh
"$HOME/peanalyzer/runtime/crispresso-2.3.4/bin/CRISPResso" --version
```

Expected stdout: `CRISPResso 2.3.4`. The script also checks bundled `fastp`
(observed **1.3.3**). It refuses an existing destination. A partial failed
installation is not a qualified runtime: inspect the error and use a fresh
runtime destination, never point Run at a partial directory.

The readable script performs:

1. Pull the exact `linux/amd64` digest.
2. Create a stopped container, copy `/CRISPResso2`, then remove only that container.
3. Keep the complete native environment and record image identity.
4. Create `bin/CRISPResso`, a small wrapper using that environment's Python,
   libraries, module path and executable PATH; initialize the normal plot cache.
5. Run `--version` without a scientific input.

The wrapper ends in **`exec` of native Python/Core**, not `docker run`, SSH, a
remote command, or a detached daemon. GUI jobs and child processes remain local
POSIX processes under the existing supervisor. After provisioning, Docker is not
needed to execute an analysis. Do not install the GUI into the Core Pixi environment.

If a different installation directory is needed, pass a new absolute path to
`install-runtime.sh`, then pass its `bin/CRISPResso` explicitly to doctor and the
launch wrappers. Keep that path stable. The default launch path is:

```bash
--run-crispresso "$HOME/peanalyzer/runtime/crispresso-2.3.4/bin/CRISPResso"
```

Use `$(command -v CRISPResso)` only if you deliberately added **this** wrapper's
`bin` directory to PATH and confirmed the resolved path. Do not select an unrelated
system installation. The GUI's qualified runtime digest is server-owned; it is
not a switch that can make an arbitrary executable qualified.

## Dependencies and actual scientific paths

| Component | Current GUI PE / nuclease FASTQ paths |
|---|---|
| Native Core 2.3.4 + bundled Python libraries | Required; retain the whole pinned tree |
| `fastp` | Required for Core's paired-read processing; wrapper puts bundled binary on PATH |
| Bowtie2 / CRISPRessoPooled | Not used as production copy routing; internal qualified routing precedes Core |
| `samtools` | Not a separate requirement for these FASTQ/suppressed-BAM GUI paths; used by historical BAM/Pooled diagnostics |
| Standard Linux shell/coreutils, gzip, awk | Supplied by Ubuntu; used by the backend |
| Node/npm | Not an application or Core runtime dependency |

Retain all bundled tools instead of deleting apparently unused parts. PE uses the
existing target/comparator and confident-copy Core paths. Nuclease uses its
separate single-copy qualified contract, including all 58 required settings.
Those settings are not user overrides; full qualification occurs during Run.
The clean Ubuntu smoke tests use both modes and the existing scientific oracles.

Native Windows and a GUI backend wrapper around `docker run` are unsupported.
The clean Ubuntu container used for setup testing was an isolated test OS; it was
not a recommendation to deploy the end-user GUI as a container service.
