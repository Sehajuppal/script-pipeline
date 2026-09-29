---
name: vsp-feedback
description: Learn from posted reels' performance and update hook priors
version: 2.0.0
platforms: [linux, macos]
metadata:
  hermes:
    tags: [instagram, analytics, learning]
    category: content
    requires_toolsets: [terminal]
    related_skills: [vsp-produce, vsp-self-improve]
---
# Learn from posted reels

## When to Use
Hourly for pulling metrics, daily for learning, and whenever the user asks
"what's working?".

## Procedure
1. Register the account's new reels: `python3 -m vsp.ingest own`.
2. Link reels to the runs that made them: `python3 -m vsp.feedback link --auto`
   (matches the `#vsp-<sha8>` caption tag). Manual:
   `python3 -m vsp.feedback link --media-id <ID> --manifest outputs/<slug>/manifest.json [--trial]`.
3. Pull insights at ~24h/48h/7d/28d: `python3 -m vsp.feedback pull`.
4. Learn: `python3 -m vsp.feedback learn` → writes `learned/priors.json`
   (Beta posteriors per niche × hook family from skip rate, watch ratio,
   share and save rates).
5. Report: `python3 -m vsp.feedback report` → `learned/PERFORMANCE.md`.
   Summarise it for the user in plain language.

## Pitfalls
- Insights lag up to 48 h; early numbers are noisy. Priors only influence
  generation once a family has ≥3 labelled posts, and only as a tie-break
  among equally good hooks — quality always wins.
- `learned/priors.json` changes what the maker generates: commit it on a
  branch like code.

## Verification
`python3 -m vsp.feedback status` shows linked posts with snapshots, and
`learned/PERFORMANCE.md` has an updated date.
