#!/usr/bin/env bash
set -euo pipefail
export M7_INTEGRATION=1
export M7_RESULTS_DIR="$(realpath -m "$2")/m7"
bash docs/validation/m422/run-tests.sh "$1" "$2"
