#!/bin/bash
set -euo pipefail
cd "${REMEDIATION_SUITE:-/workspace/crispresso-pe-pipeline-v1}"
export MPLCONFIGDIR=/tmp/v1-mpl XDG_CACHE_HOME=/tmp/v1-cache
export M11B_INTEGRATION=1 M3_CORE_EXECUTABLE=/workspace/m11c1-remediation/native-bin/CRISPResso
export M31_RUNTIME_IMAGE=pinellolab/crispresso2@sha256:b7e7971a87769aa584d31d21e199a9abca5f641c4f889c2e807cb6324fc8ce0c
export PATH=/workspace/m11c1-remediation/native-bin:/workspace/m11c1-remediation/native-env/bin:$PATH
unset PYTHONPATH
label=${1:-source}
python=${REMEDIATION_PYTHON:-/workspace/v1-desktop-qualification/source-env/bin/python}
"$python" -m pytest -q tests/test_desktop_library.py tests/test_desktop_remediation.py tests/test_desktop_reveal.py tests/test_desktop_summary.py tests/test_gui.py tests/test_gui_packaging.py tests/test_practical_version.py tests/test_m11b.py tests/test_m11c_recovery.py tests/test_m11c1_recovery.py tests/test_m11c2_integrity.py tests/test_m11c2_lifecycle.py --basetemp=/workspace/v1-final-remediation/$label-focused-final-tmp --junitxml=/workspace/v1-final-remediation/$label-focused.xml > /workspace/v1-final-remediation/$label-focused.log 2>&1
"$python" -m pytest -q tests/test_desktop_remediation_integration.py tests/test_practical_integration.py --basetemp=/workspace/v1-final-remediation/$label-integration-tmp --junitxml=/workspace/v1-final-remediation/$label-integration.xml > /workspace/v1-final-remediation/$label-integration.log 2>&1
