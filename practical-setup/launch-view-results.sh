#!/usr/bin/env bash
set -euo pipefail
[[ $# -eq 1 && -d "$1" ]] || { echo "Usage: $0 COMPLETED_WORKFLOW_DIRECTORY" >&2; exit 2; }
exec peanalyzer-viewer --view-only --workspace "$1"
