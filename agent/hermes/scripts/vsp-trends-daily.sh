#!/usr/bin/env bash
# Daily trend intelligence, no agent: research-DB reels (official Graph API
# via vsp.ingest) -> YouTube Shorts per niche (official Data API, only when
# VSP_YT_API_KEY is set) -> score -> lifecycle -> synth -> digest, then a
# commit + push of the dataset repo on branch `data` (only when it is a git
# repo with changes; never force, never main). Silent on success.
# Exit 3 from vsp.trends = nothing to do / YouTube quota stop -> not an error.
set -u
cd "${VSP_REPO:?set VSP_REPO to the script-pipeline checkout}" || exit 1
dir="${VSP_TRENDS_DIR:-$HOME/viral-trends-db}"
log=""
run() {
  out=$(python3 -m vsp.trends --dir "$dir" "$@" 2>&1); rc=$?
  if [ $rc -ne 0 ] && [ $rc -ne 3 ]; then
    log="$log\nvsp.trends $* failed (exit $rc):\n$(echo "$out" | tail -15)"
  fi
}
[ -d "$dir/observations" ] || run init
db="${VSP_VIRAL_DB:-$HOME/workspace/viral-research/viral.db}"
[ -s "$db" ] && run import-ingest --db "$db"
if [ -n "${VSP_YT_API_KEY:-}" ] && [ -n "${VSP_TRENDS_NICHES:-}" ]; then
  IFS=',' read -r -a niches <<< "$VSP_TRENDS_NICHES"
  for n in "${niches[@]}"; do
    n="$(echo "$n" | tr -d '[:space:]')"
    [ -n "$n" ] && run youtube --query "$n shorts" --niche "$n"
  done
fi
run score
run lifecycle
run synth --invent 3
run digest
if git -C "$dir" rev-parse --is-inside-work-tree >/dev/null 2>&1 &&
   [ -n "$(git -C "$dir" status --porcelain)" ]; then
  branch="$(git -C "$dir" rev-parse --abbrev-ref HEAD)"
  if [ "$branch" != "data" ]; then
    log="$log\ndataset repo $dir is on branch '$branch', not 'data': not committing"
  else
    out=$(git -C "$dir" add -A 2>&1 &&
          git -C "$dir" commit -q -m "trends $(date -u +%F)" 2>&1); rc=$?
    [ $rc -ne 0 ] && log="$log\ngit commit in $dir failed (exit $rc):\n$(echo "$out" | tail -5)"
    if [ $rc -eq 0 ] && git -C "$dir" remote get-url origin >/dev/null 2>&1; then
      out=$(git -C "$dir" push -q origin data 2>&1); rc=$?
      [ $rc -ne 0 ] && log="$log\ngit push origin data failed (exit $rc):\n$(echo "$out" | tail -5)"
    fi
  fi
fi
[ -n "$log" ] && printf "%b\n" "$log"
exit 0
