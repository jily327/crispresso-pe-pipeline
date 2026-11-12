#!/usr/bin/env bash
# Install only into a new release. Never overwrite an existing backend wrapper.
set -euo pipefail
if [[ "$#" != 1 ]]; then
  echo 'Usage: bash desktop/install-runtime.sh /absolute/path/to/new-release' >&2
  exit 2
fi
release_dir=$(cd -- "$1" && pwd -P)
python_bin="$release_dir/venv/bin/python"
entry="$release_dir/venv/bin/peanalyzer-crispresso"
if [[ ! -x "$python_bin" || ! -x "$entry" ]]; then
  echo 'Install this release wheel (including GUI dependencies) into NEW-RELEASE/venv first.' >&2
  exit 1
fi
# Actual pinned-image probe: missing Docker/image/shared lease fails clearly.
"$entry" --version
"$python_bin" - "$release_dir" <<'PY'
from pathlib import Path
import os,sys
release=Path(sys.argv[1]);directory=release/'bin'
if directory.is_symlink():raise SystemExit('Refusing a symlinked bin directory')
directory.mkdir(exist_ok=True)
destination=directory/'CRISPResso'
if destination.exists() or destination.is_symlink():
    raise SystemExit('CRISPResso already exists; nothing was replaced. Use a new release directory.')
os.symlink('../venv/bin/peanalyzer-crispresso',destination)
print('Guarded wrapper installed. Keep peanalyzer-current unchanged until the synthetic smoke tests pass.')
PY
