#!/usr/bin/env bash
# Install one operator-supplied candidate wheel into a NEW Python 3.12 venv.
set -euo pipefail
if [[ $# -lt 1 || $# -gt 2 ]]; then echo "Usage: $0 WHEEL [NEW_VENV]" >&2; exit 2; fi
[[ $(uname -s) == Linux && $(uname -m) == x86_64 ]] || { echo 'Use x86_64 Linux/WSL2, not native Windows.' >&2; exit 2; }
wheel=$1
venv=${2:-"$HOME/.venvs/peanalyzer"}
[[ -f "$wheel" && "$wheel" == *.whl ]] || { echo 'Supply the downloaded/built .whl file.' >&2; exit 2; }
[[ ! -e "$venv" && ! -L "$venv" ]] || { echo 'Venv already exists; choose a new path. Nothing removed.' >&2; exit 2; }
python3.12 -c 'import sys; assert sys.version_info[:2] == (3, 12)'
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
wheel=$(python3.12 -c 'import pathlib,sys; print(pathlib.Path(sys.argv[1]).resolve(strict=True))' "$wheel")
python3.12 -m venv "$venv"
"$venv/bin/python" -m pip install --upgrade pip
"$venv/bin/python" -m pip install --constraint "$script_dir/constraints.txt" "${wheel}[gui]"
"$venv/bin/python" -m pip check
"$venv/bin/python" -c 'import importlib.metadata as m,peanalyzer; assert m.version("crispresso-pe-pipeline")=="0.8.0"; print(m.version("crispresso-pe-pipeline")); print(peanalyzer.__file__)'
"$venv/bin/peanalyzer-viewer" --help
printf '\nInstalled. Activate in this terminal: source %q/bin/activate\n' "$venv"
