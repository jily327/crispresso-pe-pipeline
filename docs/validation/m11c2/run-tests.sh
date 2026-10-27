#!/usr/bin/env bash
set -euo pipefail
label="$1"
python_bin="$2"
results_root="/workspace/validation/m11c2-checkpoint/${label}-tests"
mkdir "$results_root"
export PATH=/workspace/validation/m11c/bin:$PATH
export MPLCONFIGDIR=/tmp/m11b-mpl XDG_CACHE_HOME=/tmp/m11b-cache
export M3_CORE_EXECUTABLE=/workspace/validation/m11c/bin/CRISPResso
export M3_POOLED_EXECUTABLE=/workspace/validation/m11c/bin/CRISPRessoPooled
export M3_SAMTOOLS_EXECUTABLE=/workspace/validation/m11c/bin/samtools
export M3_CHILD_CORE_COMMAND=/workspace/validation/m11c/bin/CRISPResso
export M31_RUNTIME_IMAGE=pinellolab/crispresso2@sha256:b7e7971a87769aa584d31d21e199a9abca5f641c4f889c2e807cb6324fc8ce0c
export M10_INTEGRATION=1 M10_RESULTS_DIR="$results_root/m10"
export M8_INTEGRATION=1 M11A1_INTEGRATION=1 M11B_INTEGRATION=1 M11C_INTEGRATION=1
export M11C_RESULTS_DIR="$results_root/m11c"
export M11B_RESULTS_DIR="$results_root/m11b"
export M11A1_RESULTS_DIR="$results_root/m11a1"
export M8_RESULTS_DIR="$results_root/m8" M81_RESULTS_DIR="$results_root/m81"
export M3_INTEGRATION=1 M31_INTEGRATION=1 M311_INTEGRATION=1 M312_INTEGRATION=1
export M4_INTEGRATION=1 M41_INTEGRATION=1 M42_INTEGRATION=1 M421_INTEGRATION=1 M422_INTEGRATION=1 M7_INTEGRATION=1
export M3_RESULTS_DIR="$results_root/m3" M31_RESULTS_DIR="$results_root/m31"
export M311_RESULTS_DIR="$results_root/m311" M312_RESULTS_DIR="$results_root/m312"
export M4_RESULTS_DIR="$results_root/m4" M41_RESULTS_DIR="$results_root/m41"
export M42_RESULTS_DIR="$results_root/m42" M421_RESULTS_DIR="$results_root/m421"
export M422_RESULTS_DIR="$results_root/m422" M7_RESULTS_DIR="$results_root/m7"
"$python_bin" -m pytest -q --basetemp="$results_root/pytest" --junitxml="$results_root/tests.xml" > "$results_root/tests.txt" 2>&1
