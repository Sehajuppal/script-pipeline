#!/usr/bin/env bash
# Daily health check. Prints nothing when green (Hermes --no-agent delivers
# nothing), the failure tail otherwise.
set -u
cd "${VSP_REPO:?set VSP_REPO to the script-pipeline checkout}" || exit 1
out=$(python3 pipeline.py --self-test 2>&1)
rc=$?
if [ $rc -ne 0 ]; then
  echo "vsp self-test FAILED (exit $rc):"
  echo "$out" | tail -40
fi
exit 0
