#!/usr/bin/env bash
set -euo pipefail
python_bin="$(realpath -s "$1")"
results_root="$(realpath -m "$2")"
if [[ -e "$results_root" ]]; then
  echo "Results directory must be new: $results_root" >&2
  exit 1
fi
mkdir -p "$results_root"
export M3_CORE_EXECUTABLE="${M3_CORE_EXECUTABLE:-$(command -v CRISPResso)}"
export M3_POOLED_EXECUTABLE="${M3_POOLED_EXECUTABLE:-$(command -v CRISPRessoPooled)}"
export M3_SAMTOOLS_EXECUTABLE="${M3_SAMTOOLS_EXECUTABLE:-$(command -v samtools)}"
export M3_CHILD_CORE_COMMAND="${M3_CHILD_CORE_COMMAND:-CRISPResso}"
export M31_RUNTIME_IMAGE=pinellolab/crispresso2@sha256:b7e7971a87769aa584d31d21e199a9abca5f641c4f889c2e807cb6324fc8ce0c
export M3_INTEGRATION=1 M31_INTEGRATION=1 M311_INTEGRATION=1 M312_INTEGRATION=1
export M4_INTEGRATION=1 M41_INTEGRATION=1 M42_INTEGRATION=1 M421_INTEGRATION=1 M422_INTEGRATION=1
export M3_RESULTS_DIR="$results_root/m3" M31_RESULTS_DIR="$results_root/m31"
export M311_RESULTS_DIR="$results_root/m311" M312_RESULTS_DIR="$results_root/m312"
export M4_RESULTS_DIR="$results_root/m4" M41_RESULTS_DIR="$results_root/m41"
export M42_RESULTS_DIR="$results_root/m42" M421_RESULTS_DIR="$results_root/m421" M422_RESULTS_DIR="$results_root/m422"
"$python_bin" -m pytest -q --basetemp="$results_root/pytest" --junitxml="$results_root/tests.xml" > "$results_root/tests.txt" 2>&1
