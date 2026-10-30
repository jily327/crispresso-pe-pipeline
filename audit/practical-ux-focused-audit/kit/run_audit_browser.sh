#!/usr/bin/env bash
# usage: run_audit_browser.sh LABEL PY SERVER_CWD   (run under isolate.sh)
P=/tmp/claude-0/-home-user-crispresso-pe-pipeline/9767c72f-405b-5205-aa52-fc76302ea49c/scratchpad/pux; S=$(dirname $P)
label=$1; py=$2; cwd=$3; shift 3; R=$P/e2e-audit-$label; rm -rf $R; mkdir -p $R
export AUDIT_E2E_ROOT=$R/root AUDIT_E2E_PORT=8779
(cd $cwd && exec env -i HOME=/root PATH=/usr/bin:/bin MPLCONFIGDIR=$P/mpl PYTHONDONTWRITEBYTECODE=1 AUDIT_E2E_ROOT=$R/root AUDIT_E2E_PORT=8779 $py -I $P/kit/audit_server.py > $R/server.log 2>&1) & SP=$!
for i in $(seq 1 300); do grep -q "Uvicorn running on" $R/server.log && break; sleep 1; done
cd $P/fe/frontend && AUDIT_FIXTURES=$P/prep/audit/practical-ux/fixtures AUDIT_PY=$P/venv/bin/python AUDIT_BIG=$P/runs/stream2/small/R1.fastq.gz \
  AUDIT_PE_TEMPLATE=$S/m11c/prep/m11c-audit-prep/fixtures/pe/draft-template.json PLAYWRIGHT_CHROMIUM_EXECUTABLE=/opt/pw-browsers/chromium-1194/chrome-linux/chrome \
  timeout 3600 npx playwright test --config playwright.audit-pux.config.ts --output $R/test-results "$@" > $R/audit.txt 2>&1; echo "EXIT $?" >> $R/audit.txt
cp test-results/audit-pux.json $R/ 2>/dev/null
kill -TERM $SP; wait $SP
tail -40 $R/audit.txt
