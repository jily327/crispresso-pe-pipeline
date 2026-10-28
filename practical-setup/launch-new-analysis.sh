#!/usr/bin/env bash
set -euo pipefail
[[ $# -ge 3 && $# -le 4 ]] || { echo "Usage: $0 POOL_R1.fastq.gz POOL_R2.fastq.gz OUTPUT_PARENT [TRUSTED_CORE_PATH]" >&2; exit 2; }
[[ -f "$1" && -f "$2" && -d "$3" ]] || { echo 'Both inputs and the output parent must already exist.' >&2; exit 2; }
core=${4:-"$HOME/peanalyzer/runtime/crispresso-2.3.4/bin/CRISPResso"}
[[ -x "$core" && "$core" = /* ]] || { echo 'Supply the absolute native Core path from install-runtime.sh.' >&2; exit 2; }
exec peanalyzer-viewer --setup-fastq "$1" --setup-fastq "$2" --setup-output-root "$3" --run-crispresso "$core"
