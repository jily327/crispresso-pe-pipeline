#!/usr/bin/env bash
set -euo pipefail
[[ $# -ge 1 && $# -le 2 && -d "$1" ]] || { echo "Usage: $0 EXISTING_WORKFLOW_DIRECTORY [TRUSTED_CORE_PATH]" >&2; exit 2; }
core=${2:-"$HOME/peanalyzer/runtime/crispresso-2.3.4/bin/CRISPResso"}
[[ -x "$core" && "$core" = /* ]] || { echo 'Supply the absolute native Core path from install-runtime.sh.' >&2; exit 2; }
exec peanalyzer-viewer --recover-workspace "$1" --run-crispresso "$core"
