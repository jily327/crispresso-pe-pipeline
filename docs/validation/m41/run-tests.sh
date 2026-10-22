#!/usr/bin/env bash
set -euo pipefail
python_bin="$1"
results_root="$2"
export M3_INTEGRATION=1 M31_INTEGRATION=1 M311_INTEGRATION=1 M312_INTEGRATION=1 M4_INTEGRATION=1 M41_INTEGRATION=1
export M3_CORE_EXECUTABLE=/workspace/m311-tools/CRISPResso
export M3_POOLED_EXECUTABLE=/workspace/m311-tools/CRISPRessoPooled
export M3_SAMTOOLS_EXECUTABLE=/workspace/m311-tools/samtools
export M3_CHILD_CORE_COMMAND=CRISPResso
export M31_RUNTIME_IMAGE=pinellolab/crispresso2@sha256:b7e7971a87769aa584d31d21e199a9abca5f641c4f889c2e807cb6324fc8ce0c
export M3_RESULTS_DIR="$results_root/m3"
export M31_RESULTS_DIR="$results_root/m31"
export M311_RESULTS_DIR="$results_root/m311"
export M312_RESULTS_DIR="$results_root/m312"
export M4_RESULTS_DIR="$results_root/m4"
export M41_RESULTS_DIR="$results_root/m41"
"$python_bin" -m pytest -q --junitxml="$results_root-tests.xml" > "$results_root-tests.txt" 2>&1
