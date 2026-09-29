#!/usr/bin/env bash
# Hourly: register our new reels, link them to their runs, pull insights.
set -u
cd "${VSP_REPO:?set VSP_REPO to the script-pipeline checkout}" || exit 1
log=""
for cmd in "vsp.ingest own" "vsp.feedback link --auto" "vsp.feedback pull"; do
  out=$(python3 -m $cmd 2>&1); rc=$?
  if [ $rc -ne 0 ] && [ $rc -ne 3 ]; then
    log="$log\n$cmd failed (exit $rc):\n$(echo "$out" | tail -15)"
  fi
done
[ -n "$log" ] && printf "%b\n" "$log"
exit 0
