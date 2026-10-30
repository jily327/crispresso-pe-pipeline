#!/usr/bin/env bash
# usage: run_adapter.sh OUTDIR PY [pytest -k expr...]
P=/tmp/claude-0/-home-user-crispresso-pe-pipeline/9767c72f-405b-5205-aa52-fc76302ea49c/scratchpad/pux
out=$1; py=$2; shift 2
mkdir -p $out; cd $P/prep/audit/practical-ux
AUDIT_LOG_DIR=$out PYTHONPATH=$P/kit MPLCONFIGDIR=$P/mpl PYTHONDONTWRITEBYTECODE=1 $py -m pytest -q -p no:cacheprovider --rootdir $P/prep/audit/practical-ux -c /dev/null -p auditor_candidate_binding \
  --basetemp=$out/tmp --junitxml=$out/junit.xml -rA "$@" audit_candidate.py > $out/pytest.txt 2>&1
echo "EXIT $?" >> $out/pytest.txt
