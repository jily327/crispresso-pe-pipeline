#!/usr/bin/env bash
# M11C browser qualification: $1 label  $2 python  $3 tests dir  $4 server cwd  $5 M10 fixture root
# Run the whole script under isolate.sh (private /tmp => private host lease scope).
set -uo pipefail
label=$1; py=$2; tests=$3; cwd=$4; M10ROOT=$5
M=/tmp/claude-0/-home-user-crispresso-pe-pipeline/9767c72f-405b-5205-aa52-fc76302ea49c/scratchpad/pux
R=$M/e2e-$label; rm -rf "${R:?}"; mkdir -p "$R"
CHROME=/opt/pw-browsers/chromium-1194/chrome-linux/chrome
NODEFREE=/usr/bin:/bin
FE=$M/fe/frontend
free() { ! curl -s -o /dev/null -m 2 "http://127.0.0.1:$1/"; }
stop() { local p=$1; kill -TERM "$p" 2>/dev/null; for i in $(seq 1 40); do kill -0 "$p" 2>/dev/null || return 0; sleep 1; done; echo "SIGKILL $p" >> "$R/runner.log"; kill -KILL "$p"; }
bound() { for i in $(seq 1 600); do grep -q "Uvicorn running on" "$1" && return 0; grep -q "address already in use" "$1" && return 1; sleep 1; done; return 1; }
free 8792 && free 8766 && free 8767 || { echo "PORT BUSY - abort" | tee -a "$R/runner.log"; exit 3; }
SENV="HOME=/root PATH=$NODEFREE MPLCONFIGDIR=$M/mpl PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=$tests M3_CORE_EXECUTABLE=$M/native-bin/CRISPResso"
(cd "$cwd" && exec env -i $SENV M10_E2E_ROOT=$M10ROOT M11_SETUP_ROOT=$R/setup M10_E2E_PORT=8792 M10_E2E_EVIDENCE=$R/existing-immutability.json "$py" "$tests/gui_e2e_server.py" > "$R/existing-server.log" 2>&1) & SP=$!
bound "$R/existing-server.log" || { echo "existing server did not bind" | tee -a "$R/runner.log"; stop $SP; exit 4; }
(cd $FE && M11_SETUP_ROOT=$R/setup M10_E2E_ROOT=$M10ROOT PLAYWRIGHT_CHROMIUM_EXECUTABLE=$CHROME M10_E2E_URL=http://127.0.0.1:8792 timeout 2400 npx playwright test --config playwright.config.ts > "$R/existing.txt" 2>&1; echo "EXIT $?" >> "$R/existing.txt")
stop $SP; free 8792 || echo "8792 still busy" >> "$R/runner.log"
(cd "$cwd" && exec env -i $SENV M11B_E2E_ROOT=$R/run M11B_E2E_PORT=8766 "$py" "$tests/m11b_e2e_server.py" > "$R/run-server.log" 2>&1) & RP=$!
bound "$R/run-server.log" || { echo "run server did not bind" | tee -a "$R/runner.log"; stop $RP; exit 5; }
(cd $FE && M11B_E2E_ROOT=$R/run PLAYWRIGHT_CHROMIUM_EXECUTABLE=$CHROME M11B_E2E_URL=http://127.0.0.1:8766 timeout 3600 npx playwright test --config playwright.run.config.ts > "$R/run.txt" 2>&1; echo "EXIT $?" >> "$R/run.txt")
stop $RP; free 8766 || echo "8766 still busy" >> "$R/runner.log"
(cd "$cwd" && exec env -i $SENV M11C_E2E_ROOT=$R/recovery M11C_E2E_PORT=8767 "$py" "$tests/m11c_e2e_server.py" > "$R/recovery-server.log" 2>&1) & CP=$!
bound "$R/recovery-server.log" || { echo "recovery server did not bind" | tee -a "$R/runner.log"; stop $CP; exit 6; }
(cd $FE && env M11C_E2E_ROOT=$R/recovery M11C_E2E_PYTHON=$py M11C_E2E_SERVER=$tests/m11c_e2e_server.py PYTHONPATH=$tests M3_CORE_EXECUTABLE=$M/native-bin/CRISPResso MPLCONFIGDIR=$M/mpl M11C_E2E_PORT=8767 \
   PLAYWRIGHT_CHROMIUM_EXECUTABLE=$CHROME M11C_E2E_URL=http://127.0.0.1:8767 timeout 3600 npx playwright test --config playwright.recovery.config.ts > "$R/recovery.txt" 2>&1; echo "EXIT $?" >> "$R/recovery.txt")
kill -0 $CP 2>/dev/null && stop $CP
[ -f "$R/recovery/server-pid" ] && { p=$(cat "$R/recovery/server-pid"); kill -0 "$p" 2>/dev/null && { echo "restarted server $p still up; stopping" >> "$R/runner.log"; stop "$p"; }; }
(cd "$cwd" && exec env -i $SENV PRACTICAL_E2E_ROOT=$R/practical "$py" "$tests/practical_e2e_server.py" > "$R/practical-server.log" 2>&1) & PP=$!
bound "$R/practical-server.log" || { echo "practical server did not bind" | tee -a "$R/runner.log"; stop $PP; exit 7; }
(cd $FE && PRACTICAL_E2E_ROOT=$R/practical PLAYWRIGHT_CHROMIUM_EXECUTABLE=$CHROME timeout 3600 npx playwright test --config playwright.practical.config.ts > "$R/practical.txt" 2>&1; echo "EXIT $?" >> "$R/practical.txt")
stop $PP
grep -E "^\s+[0-9]+ (passed|failed|flaky|skipped)|EXIT" "$R/existing.txt" "$R/run.txt" "$R/recovery.txt" "$R/practical.txt"
