#!/usr/bin/env python3
"""Fast in-process eval: generate -> gate1 -> rubric (and optional gate2).

usage: python3 tools/fast_eval.py [--repo .] [--durations 30] [--seeds 1,2,3]
                       [--show D43,R08] [--n 5] [--gate2]
"""
import argparse, collections, json, os, re, sys, tempfile, traceback

ap = argparse.ArgumentParser()
ap.add_argument("--repo", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ap.add_argument("--durations", default="30")
ap.add_argument("--seeds", default="1,2,3")
ap.add_argument("--formats", default="demo,talking-head,pov-vlog,transformation,review")
ap.add_argument("--presenters", default="human,ai")
ap.add_argument("--show", default="")
ap.add_argument("--n", type=int, default=4)
ap.add_argument("--gate2", action="store_true")
ap.add_argument("--only", default="", help="prompt id filter (comma)")
ap.add_argument("--dump", default="", help="write all scripts to this jsonl")
a = ap.parse_args()

sys.path.insert(0, a.repo)
os.chdir(a.repo)
if a.gate2:
    from vsp.fixtures import build_fixture_db
    d = tempfile.mkdtemp()
    os.environ["VSP_VIRAL_DB"] = build_fixture_db(os.path.join(d, "viral.db"))
    os.environ["VSP_FIXTURE_OK"] = "1"
import viral_script_maker as vsm  # noqa
from vsp.gates import gate1, gate2  # noqa
from vsp import rubric as RUB  # noqa
if a.gate2:
    import make_shotlist

golden = [json.loads(l) for l in open(os.path.join(a.repo, "evals/golden.jsonl")) if l.strip()]
if a.only:
    keep = set(a.only.split(","))
    golden = [g for g in golden if g["id"] in keep]


def rid(msg):
    m = re.match(r"\s*(D\d+[a-z]?|B4a|R\d+)\b", msg)
    if m:
        return m.group(1)
    if "hashtag/niche mismatch" in msg:
        return "TAG-MISMATCH"
    return "OTHER:" + "-".join(msg.split()[:3])


rows = []
dump = open(a.dump, "w") if a.dump else None
for du in [int(x) for x in a.durations.split(",")]:
    for g in golden:
        for fmt in a.formats.split(","):
            for pr in a.presenters.split(","):
                for sd in [int(x) for x in a.seeds.split(",")]:
                    key = f"{g['id']}|{fmt}|{pr}|{sd}|{du}"
                    try:
                        s = vsm.generate(g["prompt"], presenter=pr, fmt=fmt,
                                         duration=du, seed=sd)
                        s = json.loads(json.dumps(s))
                    except Exception:
                        rows.append({"key": key, "crash": traceback.format_exc()[-600:]})
                        continue
                    g1 = gate1(s)
                    r = RUB.score(s)
                    row = {"key": key, "g1": g1, "rub": r, "s": s}
                    if a.gate2 and not g1:
                        try:
                            bt, _, _ = make_shotlist.build_bundle(s)
                            row["g2"] = gate2(bt, s)
                        except Exception:
                            row["g2"] = ["STAGE2 crash " + traceback.format_exc()[-300:]]
                    rows.append(row)
                    if dump:
                        dump.write(json.dumps({"key": key, "script": s}) + "\n")

n = len(rows)
crash = [r for r in rows if "crash" in r]
ok = [r for r in rows if "crash" not in r]
g1p = [r for r in ok if not r["g1"]]
print(f"runs {n} crash {len(crash)} gate1-pass {len(g1p)}/{n} = {100*len(g1p)/max(1,n):.1f}%")
if a.gate2:
    g2p = [r for r in g1p if not r.get("g2")]
    print(f"  e2e pass {len(g2p)}/{n} = {100*len(g2p)/max(1,n):.1f}%")
    c2 = collections.Counter()
    for r in g1p:
        for m in set(rid(x) for x in r.get("g2") or []):
            c2[m] += 1
    print("  gate2 fails:", dict(c2.most_common(12)))
cnt = collections.Counter()
ex = collections.defaultdict(list)
for r in ok:
    for m in r["g1"]:
        k = rid(m)
        cnt[k] += 1
        ex[k].append((r["key"], m))
print("gate1 fails (msgs):", dict(cnt.most_common(20)))
per_run = collections.Counter()
for r in ok:
    for k in set(rid(m) for m in r["g1"]):
        per_run[k] += 1
print("gate1 fails (runs):", dict(per_run.most_common(20)))
if ok:
    mean = sum(r["rub"]["score"] for r in ok) / len(ok)
    print(f"rubric mean {mean:.1f}")
    rc = collections.Counter()
    rex = collections.defaultdict(list)
    for r in ok:
        for c in r["rub"]["checks"]:
            if c["pass"] is False:
                rc[c["id"]] += 1
                rex[c["id"]].append((r["key"], c["detail"]))
        for p in r["rub"]["pitfalls"]:
            rc[p["id"]] += 1
            rex[p["id"]].append((r["key"], p["hit"]))
    print("rubric fails:", dict(sorted(rc.items())))
    comp = collections.Counter(f for r in ok for f in r["rub"]["compliance_flags"])
    print("compliance:", dict(comp))
    hooks = [RUB.hook_line(r["s"]) for r in ok]
    fb = sum(1 for h in hooks if RUB.FALLBACK_HOOK.match(h.strip()))
    print(f"fallback hooks {fb}/{len(hooks)} = {100*fb/len(hooks):.1f}%  distinct {len(set(hooks))}")
    src = collections.Counter(r["s"].get("hook_source") for r in ok)
    print("hook_source:", dict(src))
for k in [x for x in a.show.split(",") if x]:
    print(f"\n== {k} examples ==")
    src = ex.get(k) or rex.get(k) or []
    seen = set()
    for key, m in src:
        if m in seen:
            continue
        seen.add(m)
        print(" ", key, "::", str(m)[:300])
        if len(seen) >= a.n:
            break
if crash:
    print("\n== crashes ==")
    for r in crash[:3]:
        print(r["key"], r["crash"])
