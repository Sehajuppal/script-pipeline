#!/usr/bin/env bash
# Daily research refresh via the official Instagram Graph API.
# Exit 3 from vsp.ingest = budget / rate limit reached -> resume next tick.
set -u
cd "${VSP_REPO:?set VSP_REPO to the script-pipeline checkout}" || exit 1
log=""
for step in "hashtags" "watchlist" "refresh-pack"; do
  out=$(python3 -m vsp.ingest $step 2>&1); rc=$?
  if [ $rc -ne 0 ] && [ $rc -ne 3 ]; then
    log="$log\nvsp.ingest $step failed (exit $rc):\n$(echo "$out" | tail -15)"
  fi
done
[ -n "$log" ] && printf "%b\n" "$log"
exit 0
