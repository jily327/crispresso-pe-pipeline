#!/usr/bin/env bash
# Science parity batch: candidate 1.0.1 wheel + shipped guarded Docker runtime + pinned image.
# Usage: run_science_batch.sh SCRATCH V101_ROOT
set -u
S=$1; V=$2; DIG=pinellolab/crispresso2@sha256:b7e7971a87769aa584d31d21e199a9abca5f641c4f889c2e807cb6324fc8ce0c
export HOME=$V/home; cd $V/home
docker events --format '{{json .}}' > $V/logs/docker_events_science.jsonl 2>/dev/null &
EV=$!
for job in "pe pe_in contrasts" "nucW2 nuc_in2 -" "nucW4 nuc_in4 -" "mc_routable mc_in_routable -" "mc_blocked mc_in_blocked -"; do
  set -- $job; name=$1; in=$S/work/$2; extra=""; [ "$3" = contrasts ] && extra="--contrasts $in/contrasts.yaml"
  start=$(date +%s)
  $V/release/venv/bin/peanalyzer run --r1 $in/pool_R1.fastq.gz --r2 $in/pool_R2.fastq.gz --samples $in/samples.csv --targets $in/targets.csv --config $in/config.yaml \
    --output $V/work/sci_$name --crispresso $V/release/bin/CRISPResso --runtime-digest $DIG $extra > $V/logs/sci_$name.log 2>&1
  echo "$name exit=$? seconds=$(( $(date +%s) - start ))"
done
kill $EV
