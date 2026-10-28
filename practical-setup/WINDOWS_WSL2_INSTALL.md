# One-time Windows / WSL2 installation

This is a candidate-specific preparation guide. Practice with synthetic inputs
now; wait for independent audit/merge approval before real-data use.

## 1. Install Ubuntu under WSL2

On an updated x64 Windows 10/11 PC, open **PowerShell as Administrator** for this
Windows setup step only:

```powershell
wsl --install -d Ubuntu-24.04
```

Restart Windows if requested. Open **Ubuntu 24.04** from Start and create your
Linux username/password. If the distribution is not listed, use `wsl --update`
and `wsl --list --online`; consult Microsoft's WSL installation instructions:
https://learn.microsoft.com/windows/wsl/install

In PowerShell, confirm:

```powershell
wsl --list --verbose
```

Ubuntu must show **VERSION 2**. If necessary:

```powershell
wsl --set-version Ubuntu-24.04 2
```

All commands below run in **Ubuntu**, as your normal Linux user, not PowerShell
and not a root shell. Native Windows scientific execution is unsupported.

## 2. Check Linux and prepare folders

```bash
uname -srm
cat /etc/os-release
sudo apt-get update
sudo apt-get install -y python3.12-venv ca-certificates libgomp1 git
python3.12 --version
mkdir -p ~/peanalyzer/{inputs,analyses,runtime,wheels}
```

Use **Ubuntu 24.04 LTS, x86_64, Python 3.12**. Repository metadata allows >=3.11,
but the tested dependency pins require 3.12. ARM64 and other Python versions are
not qualified by this package. Do not resolve a different dependency set just to
make another Python version install.

Keep active inputs and analyses under the Linux home directory. `/mnt/c`, network
shares, OneDrive folders and Windows filesystem semantics have **not** been
qualified for this workflow's inode, lock and containment checks. Copy FASTQs
from Windows into `~/peanalyzer/inputs/` before registration; do not modify those
copies afterward. Quoted paths may contain spaces. Confirm a copy if needed:

```bash
sha256sum '/mnt/c/Users/YOUR_WINDOWS_USER/Downloads/pool_R1.fastq.gz' \
  "$HOME/peanalyzer/inputs/pool_R1.fastq.gz"
```

The two hashes should match. Repeat for R2. Windows Explorer can browse Linux
files through `\\wsl.localhost\Ubuntu-24.04\home\YOUR_LINUX_USER\peanalyzer`.
Do not move/rename completed workflow directories to organize them later: choose
stable descriptive names when starting. There is no separate movable `completed`
folder in this recommendation.

## 3. Get this setup package

An easy terminal download of the reference material is:

```bash
git clone --depth 1 --branch artifacts/practical-gui-setup \
  https://github.com/jily327/crispresso-pe-pipeline.git ~/peanalyzer/setup-reference
cd ~/peanalyzer/setup-reference/practical-setup
```

Alternatively download the artifact branch ZIP in GitHub's web UI and extract it
into the Linux filesystem. Run scripts with `bash`; do not edit their line endings
in a Windows editor. **Do not install the application from this artifact branch.**
It carries reference documents, not a development or release base.

Check the downloaded package before using its scripts:

```bash
sha256sum -c SHA256SUMS
```

Every listed file should say `OK`. If not, obtain a fresh unmodified copy.

## 4. Temporary pre-release wheel build

Until an approved release wheel exists, build from the exact candidate in a
separate checkout. The SHA below is the studied candidate, not proof of audit
approval. After merge, confirm the approved immutable SHA with the maintainer.

```bash
SETUP_DIR="$PWD"
git clone https://github.com/jily327/crispresso-pe-pipeline.git ~/peanalyzer/candidate-source
cd ~/peanalyzer/candidate-source
git checkout --detach 232d380c73f456181bade0e5c11138c8c5ec6570
git rev-parse HEAD
python3.12 -m venv ~/peanalyzer/build-env
~/peanalyzer/build-env/bin/python -m pip install \
  -c "$SETUP_DIR/constraints.txt" build setuptools wheel
~/peanalyzer/build-env/bin/python -m build --wheel --no-isolation \
  --outdir "$HOME/peanalyzer/wheels"
cd "$SETUP_DIR"
```

No Node/npm command is needed. The build validates the committed production GUI
bundle. If it reports `VIEWER_ASSET_IDENTITY_MISMATCH`, stop and obtain a correct
approved source/wheel; do not regenerate a different interface to bypass it.

## 5. Install the wheel into a new application environment

```bash
bash ./install-wsl.sh \
  "$HOME/peanalyzer/wheels/crispresso_pe_pipeline-0.8.0-py3-none-any.whl"
source ~/.venvs/peanalyzer/bin/activate
python -m pip check
peanalyzer-viewer --help
```

The transparent installer runs `python3.12 -m venv`, upgrades pip, then uses the
**tested syntax** `python -m pip install --constraint constraints.txt
'/absolute/path/crispresso_pe_pipeline-0.8.0-py3-none-any.whl[gui]'`.
The quoted wheel path includes `[gui]`. Constraints are copied from the candidate's
two lock files; unused development pins do not install development tools.
This is an installed-wheel environment, not `pip install -e`.

The installer refuses an existing venv rather than overwriting it. For a separate
installation, pass a new venv path as its second argument and activate that one.
For a future approved release, use its supplied wheel and matching constraints;
cloning/building the application will no longer be necessary.

## 6. Install Core, then open the GUI

Follow [CRISPRESSO_RUNTIME.md](CRISPRESSO_RUNTIME.md), run `doctor.sh`, then use
[README.md](README.md). Keep the WSL terminal open. The printed token-bearing URL
normally opens from Windows via WSL2 localhost forwarding. Use it exactly, with
`127.0.0.1`, the printed port, and the fragment. No LAN binding or firewall port
exposure is needed.

This study tested Linux loopback and clean Ubuntu, **not an actual Windows browser
or WSL kernel**. On the target PC, confirm the page opens from Windows. If it does
not, see the [localhost troubleshooting entry](TROUBLESHOOTING.md); do not expose
the GUI on `0.0.0.0` as a workaround.
