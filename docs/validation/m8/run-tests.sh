#!/usr/bin/env bash
set -euo pipefail
export M8_INTEGRATION=1
export M8_RESULTS_DIR="$(realpath -m "$2")/m8"
bash docs/validation/m7/run-tests.sh "$1" "$2"
