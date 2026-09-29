#!/usr/bin/env bash
# Every 12 h: Bayesian A/B read of posted alternate openings (Trial Reels)
# -> learned/VARIANTS.md. Silent unless the command fails; the vsp-learn
# agent job summarises VARIANTS.md for the user.
set -u
cd "${VSP_REPO:?set VSP_REPO to the script-pipeline checkout}" || exit 1
out=$(python3 -m vsp.feedback variants 2>&1); rc=$?
if [ $rc -ne 0 ] && [ $rc -ne 3 ]; then
  printf "vsp.feedback variants failed (exit %s):\n%s\n" "$rc" "$(echo "$out" | tail -15)"
fi
exit 0
