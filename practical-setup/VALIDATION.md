# Independently observed setup validation

Study date: **2026-10-28** (America/New_York). Exact independently fetched
`feat/m11c-recovery` candidate: **232d380c73f456181bade0e5c11138c8c5ec6570**.
Package version **0.8.0**. This artifact branch starts directly from that SHA.

## What was actually tested

| Check | Observed result |
|---|---|
| Fresh wheel build from exact candidate export | PASS; separate build venv, no editable application install |
| Fresh host application venv | PASS: quoted absolute `wheel.whl[gui]` plus candidate constraints; `pip check`, site-packages import and official launcher help |
| Clean Ubuntu 24.04 nonroot install | PASS: Python 3.12.3, fresh venv, GUI extra and same wheel/constraints; no Node available |
| Native runtime provisioning | PASS: full pinned image extraction, native Core **2.3.4**, bundled fastp **1.3.3** |
| Read-only doctor | PASS; input/output/cache bytes and mtimes unchanged; missing input exits 2; occupied test port yields PASS_WITH_NOTES |
| Official view-only startup | PASS: only 127.0.0.1, printed URL has token fragment, bundled JS/CSS HTTP 200, Run disabled |
| Clean Ubuntu PE public-API workflow | COMPLETED; existing target precise-PE oracle **2/24**, final workflow verified, M10 open succeeds |
| Clean Ubuntu nuclease public-API workflow | COMPLETED; existing indel oracle **8/20**, final workflow verified, M10 open succeeds |
| Setup/Review writes | No scientific workspace before explicit Run for either mode |
| View-results wrapper | Both completed workspaces open via M10; workspace/input bytes and mtimes unchanged |
| Recovery wrapper | Both completed workspaces classify COMPLETED, non-executable; workspace/input bytes and mtimes unchanged |
| Linux browser end-to-end | Chromium **154.0.8037.57**; both modes pass real wizard → Review → Run → verified Open Results with expected counts |
| Actual Windows browser / WSL2 | **NOT TESTED**: unavailable on this execution host |
| `/mnt/c`, network FS, Docker Desktop setup | **NOT QUALIFIED** by this study |

Machine-readable summaries are in [evidence/ubuntu-smoke.json](evidence/ubuntu-smoke.json),
[evidence/browser-smoke.json](evidence/browser-smoke.json),
[evidence/doctor-final.json](evidence/doctor-final.json), and
[evidence/install-identity.json](evidence/install-identity.json).
The installed public dependency inventory is in
[evidence/ubuntu-packages.json](evidence/ubuntu-packages.json). Script syntax,
argument/overwrite refusals and Markdown links also passed
[package checks](evidence/package-checks.json).
They contain only synthetic fixture paths, public package/runtime identity and
setup results. No session token, recovery key or real experimental data is shipped.

## Exact tested installation structure

The Linux outer host was Debian 13 x86_64, kernel 6.18.55. A fresh build venv was
created with the available Python 3.12 interpreter. The candidate was exported
with `git archive 232d380c73f456181bade0e5c11138c8c5ec6570` to a separate directory.
Build commands used the new venv, not the development application environment:

```bash
python -m pip install -c /workspace/practical-gui-setup/practical-setup/constraints.txt build setuptools wheel
python -m build --wheel --no-isolation --outdir /workspace/validation/practical-setup/dist
```

Actual wheel: `crispresso_pe_pipeline-0.8.0-py3-none-any.whl`.
SHA-256: `2db7bdb62e883c85883e88a3e29294e13ba7a40d4c1b9987902a7f48cea19a9e`.
Wheel builds may have different ZIP timestamps; this identifies the tested bytes,
not a requirement that future rebuilds reproduce the same archive hash.

The actual installer was run as follows (new venv each time):

```bash
bash /workspace/practical-gui-setup/practical-setup/install-wsl.sh \
  /workspace/validation/practical-setup/dist/crispresso_pe_pipeline-0.8.0-py3-none-any.whl \
  /workspace/validation/practical-setup/host-app
```

Inside clean Ubuntu, the setup package was mounted at `/setup`, the validation
directory at its same absolute path, and host CA trust was provided for the
managed network. No dev venv, node_modules, user package cache or application
checkout was mounted as the installed application. The native runtime was newly
extracted, not borrowed from the prior development environment.

Ubuntu image digest:
`ubuntu@sha256:24737cef17f4e22b1977df7d9a05e77c4e28b7da5b8911f8d8ccda136bf3573c`.
The test container is an isolated Ubuntu approximation, not an end-user deployment
recommendation. It shares the host Linux kernel, not a WSL kernel.

As container administrator, provisioned only:

```bash
apt-get update
apt-get install -y --no-install-recommends python3.12-venv ca-certificates libgomp1
```

As existing nonroot Ubuntu user (UID 1000):

```bash
bash /setup/install-wsl.sh \
  /workspace/validation/practical-setup/dist/crispresso_pe_pipeline-0.8.0-py3-none-any.whl \
  /home/ubuntu/.venvs/peanalyzer
source /home/ubuntu/.venvs/peanalyzer/bin/activate
python -m pip check
peanalyzer-viewer --help
python -B /setup/validation/smoke_api.py --package /setup \
  --root /workspace/validation/practical-setup/ubuntu-smoke \
  --core /workspace/validation/practical-setup/runtime/bin/CRISPResso
```

The actual user wrappers launch `peanalyzer-viewer`, not a monkeypatched test
server. `smoke_api.py` uses live HTTP with the printed random session token,
validates loopback through `/proc/net/tcp`, and does not print/store that token.
It calls `verify_workflow_output` from the installed package after completion.
Two biological-fixture workflows ran: one sample / one target / two PE copies,
and one sample / one target / one nuclease copy. No novel biological oracle was
introduced; fixture generator hashes are committed with the inputs.

The final doctor was independently rechecked after removing its timeout-kill
behavior: it performs no automatic signalling, even of its trusted version-probe
child. The required native `--version` command returns normally. Successful,
missing-input and occupied-port checks left recorded file bytes/mtimes unchanged.

## Browser driver

The fresh host-installed wheel was tested using a separate Playwright test driver
and system Chromium. Reproduce with an installed app venv active and a separate
test-only Playwright installation (not required for ordinary users):

```bash
node validation/browser_smoke.cjs "$PWD" /absolute/new/browser-smoke-root \
  "$HOME/peanalyzer/runtime/crispresso-2.3.4/bin/CRISPResso" /usr/bin/chromium
```

The observed driver used `NODE_PATH=/workspace/m11c-recovery/frontend/node_modules`
solely to find the existing Playwright test tool. It did not use development
application code: official launcher resolved from the fresh `host-app/bin`,
served the installed production bundle and executed the fresh native Core.
Both modes selected actual UI fields, reached Open Results, and matched 2/24
and 8/20. Test containers required Chromium `--no-sandbox`; that test-driver flag
is not an end-user browser deployment instruction.

## Integrity and scope

Only `practical-setup/` is added relative to the candidate. Application source,
scientific contracts and production branch refs remain unchanged. The exact
artifact SHA is the commit containing this package (also reported at publication);
it is intentionally not self-embedded to avoid recursive commit identity.
Use `git rev-parse HEAD` in the artifact checkout and `git rev-parse HEAD^` to
confirm the direct candidate base. [SHA256SUMS](SHA256SUMS) inventories every
published package file except itself; [FILE_LIST.txt](FILE_LIST.txt) lists the
exact package inventory including both integrity files.

The final independent candidate audit, full historical suites, interruption
recovery/cancellation qualification, actual WSL2 and private real datasets are
outside this setup study. Candidate advancement requires rechecking the guide
against the final merged SHA before real-data use.
