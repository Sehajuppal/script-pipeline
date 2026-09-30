"""The trend dataset on disk: a directory that is its own (private) git
repo, default branch `data` (the Hermes profile denies pushes to main).

    dataset_dir(path=None)     --dir > VSP_TRENDS_DIR > ~/viral-trends-db
    init(d) -> [created]       copy trends-db-template/ (never overwrites)
    is_initialized(d)

Layout (trends-db-template/README.md has the full description):
  observations/YYYY/MM/YYYY-MM-DD.jsonl  append-only snapshots: one line per
                                         post per day; readers merge a post's
                                         snapshots by (platform, post_id) =
                                         obs_id, keeping the latest metrics
  creators/creators.jsonl                latest snapshot per (platform, handle)
  signals/YYYY/MM/YYYY-MM-DD.jsonl       aggregate trend signals (TikTok
                                         Creative Center lists) — not posts
  usage/used.jsonl                       recipes used by pipeline runs
                                         (novelty memory; append-only)
  derived/                               regenerated, never hand-edited:
                                         outliers.jsonl, trends.json,
                                         recipes.jsonl, quota.json
  digests/YYYY-MM-DD.md

Every write is atomic (temp file + os.replace). JSONL lines are compact
(nulls dropped), key-sorted JSON, so re-running a command on the same
input produces byte-identical files.
"""
import json
import os
import re
import shutil
import tempfile

from vsp import config
from vsp.trends import schema as S

ENV_DIR = "VSP_TRENDS_DIR"
DEFAULT_DIR = "~/viral-trends-db"
TEMPLATE_NAME = "trends-db-template"
SIZE_WARN_BYTES = 900 * 1024        # GitHub's soft limit is ~1 MB per object
LAYOUT_DIRS = ("schema", "observations", "creators", "signals", "usage", "derived",
               "digests")
DERIVED = ("outliers.jsonl", "trends.json", "recipes.jsonl", "quota.json")


class NotInitialized(RuntimeError):
    """The dataset directory has no layout yet (run `init`)."""


# ------------------------------------------------------------------ paths
def dataset_dir(path=None):
    p = path or os.environ.get(ENV_DIR) or DEFAULT_DIR
    return os.path.abspath(os.path.expanduser(p))


def template_dir():
    return os.path.join(config.REPO, TEMPLATE_NAME)


def is_initialized(d):
    return os.path.isdir(os.path.join(d, "observations"))


def require(d):
    if not is_initialized(d):
        raise NotInitialized(
            f"trend dataset not initialised at {d} — run `python3 -m vsp.trends "
            f"--dir {d} init` (or set {ENV_DIR})")
    return d


def day_str(dt):
    return S.utc(dt).strftime("%Y-%m-%d")


def dated_path(d, sub, day, ext=".jsonl"):
    """<d>/<sub>/YYYY/MM/YYYY-MM-DD<ext>."""
    return os.path.join(d, sub, day[:4], day[5:7], day + ext)


def obs_path(d, day):
    return dated_path(d, "observations", day)


def signal_path(d, day):
    return dated_path(d, "signals", day)


def creators_path(d):
    return os.path.join(d, "creators", "creators.jsonl")


def usage_path(d):
    return os.path.join(d, "usage", "used.jsonl")


def derived_path(d, name):
    return os.path.join(d, "derived", name)


def digest_path(d, day):
    return os.path.join(d, "digests", day + ".md")


def _dated_files(d, sub):
    root = os.path.join(d, sub)
    out = []
    if not os.path.isdir(root):
        return out
    for dp, dns, fns in os.walk(root):
        dns.sort()
        for fn in sorted(fns):
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}\.jsonl", fn):
                out.append(os.path.join(dp, fn))
    return sorted(out, key=lambda p: os.path.basename(p))


def observation_files(d):
    return _dated_files(d, "observations")


def signal_files(d):
    return _dated_files(d, "signals")


# ----------------------------------------------------------------- writes
def write_atomic(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".tmp-", dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def dumps_line(rec):
    return json.dumps(S.compact(_public(rec)), sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"))


def write_jsonl(path, records):
    write_atomic(path, "".join(dumps_line(r) + "\n" for r in records))


def write_json(path, obj):
    write_atomic(path, json.dumps(obj, indent=1, sort_keys=True, ensure_ascii=False) + "\n")


def read_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def read_jsonl(path):
    """-> [(line_no, obj | None, error | None)] (blank lines skipped)."""
    out = []
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.read().splitlines()
    except OSError as e:
        return [(0, None, f"unreadable: {e}")]
    for i, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except ValueError as e:
            out.append((i, None, f"invalid JSON: {e}"))
            continue
        if not isinstance(obj, dict):
            out.append((i, None, "line is not a JSON object"))
            continue
        out.append((i, obj, None))
    return out


def _public(rec):
    """Drop in-memory bookkeeping keys (leading underscore)."""
    if isinstance(rec, dict):
        return {k: v for k, v in rec.items() if not str(k).startswith("_")}
    return rec


# ------------------------------------------------------------------- init
def _template_files():
    """{relative path: text} of the dataset layout (from the repo template,
    or generated when the template folder is not next to the package)."""
    t = template_dir()
    files = {}
    if os.path.isdir(t):
        for dp, dns, fns in os.walk(t):
            dns.sort()
            for fn in sorted(fns):
                p = os.path.join(dp, fn)
                with open(p, encoding="utf-8") as f:
                    files[os.path.relpath(p, t)] = f.read()
        return files
    for name in S.SPECS:
        files[os.path.join("schema", f"{name}.v{S.SCHEMA_VERSION}.json")] = \
            schema_file_text(name)
    for sub in LAYOUT_DIRS[1:]:
        files[os.path.join(sub, ".gitkeep")] = ""
    files["README.md"] = ("# viral-trends-db\n\nTrend dataset for the script "
                          "pipeline (vsp.trends). See the pipeline repo's "
                          "trends-db-template/README.md.\n")
    return files


def schema_file_text(name):
    """The exact text of trends-db-template/schema/<name>.v1.json."""
    return json.dumps(S.json_schema(name), indent=1, ensure_ascii=False) + "\n"


def write_template_schemas(t=None):
    """(Re)generate <template>/schema/*.v1.json from vsp.trends.schema."""
    t = t or template_dir()
    out = []
    for name in S.SPECS:
        p = os.path.join(t, "schema", f"{name}.v{S.SCHEMA_VERSION}.json")
        write_atomic(p, schema_file_text(name))
        out.append(p)
    return out


def init(d):
    """Create the layout from the template; never overwrites. -> [created]."""
    created = []
    os.makedirs(d, exist_ok=True)
    for rel, text in sorted(_template_files().items()):
        p = os.path.join(d, rel)
        if os.path.exists(p):
            continue
        write_atomic(p, text)
        created.append(rel)
    for sub in LAYOUT_DIRS:
        os.makedirs(os.path.join(d, sub), exist_ok=True)
    return created


def git_init_data_branch(d):
    """`git init` with HEAD on branch `data` (idempotent). -> message."""
    import subprocess
    if os.path.isdir(os.path.join(d, ".git")):
        return "already a git repository"
    try:
        subprocess.run(["git", "init", "-q", d], check=True, capture_output=True)
        subprocess.run(["git", "-C", d, "symbolic-ref", "HEAD", "refs/heads/data"],
                       check=True, capture_output=True)
    except (OSError, subprocess.CalledProcessError) as e:
        return f"git init failed: {e}"
    return "initialised git repository on branch data (add a private remote: " \
           "git -C DIR remote add origin <url>)"


# ------------------------------------------------------------ observations
def load_snapshots(d):
    """Every observation line -> [(order, path, line_no, record)], records
    expanded to the full form. Unparseable lines are skipped (validate
    reports them)."""
    out = []
    order = 0
    for p in observation_files(d):
        for ln, obj, err in read_jsonl(p):
            if obj is None:
                continue
            out.append((order, p, ln, S.expand(obj)))
            order += 1
    return out


def _overlay(base, new):
    """Non-null leaves of `new` over `base` (nested objects per field)."""
    for k, v in new.items():
        if str(k).startswith("_"):
            continue
        if isinstance(v, dict):
            cur = base.get(k) if isinstance(base.get(k), dict) else {}
            base[k] = _overlay(dict(cur), v)
        elif isinstance(v, list):
            if k == "trend_keys":
                base[k] = sorted(set(base.get(k) or []) | set(v))
            elif v:
                base[k] = list(v)
            else:
                base.setdefault(k, [])
        elif v is not None:
            base[k] = v
    return base


def merge_snapshots(snaps):
    """[(order, path, line, rec)] -> {obs_id: merged record}. Snapshots are
    applied oldest first (observed_at, then file order), so metrics and
    every other field hold the latest non-null value and trend_keys the
    union. `_sources` lists every source, `_snapshots` the count."""
    groups = {}
    for order, _p, _ln, rec in snaps:
        oid = rec.get("obs_id")
        if oid:
            groups.setdefault(oid, []).append((rec.get("observed_at") or "", order, rec))
    out = {}
    for oid in sorted(groups):
        items = sorted(groups[oid], key=lambda t: (t[0], t[1]))
        merged = S.expand({})
        for _, _, rec in items:
            merged = _overlay(merged, rec)
        latest = items[-1][2]
        merged["source"] = latest.get("source")
        merged["retention"] = dict(latest.get("retention") or {"purge_after": None})
        merged["_sources"] = sorted({r.get("source") for _, _, r in items if r.get("source")})
        merged["_snapshots"] = len(items)
        fol = (merged.get("creator") or {}).get("followers")
        merged["creator"]["tier"] = S.tier_for(fol) if isinstance(fol, int) else \
            merged["creator"].get("tier")
        out[oid] = merged
    return out


def load_observations(d):
    """Merged (deduplicated) observations sorted by obs_id."""
    merged = merge_snapshots(load_snapshots(d))
    return [merged[k] for k in sorted(merged)]


def _content_key(rec):
    body = S.compact(_public(rec))
    for k in ("observed_at", "retention", "analyst"):
        body.pop(k, None)
    return json.dumps(body, sort_keys=True)


def _purge_after(rec):
    return ((rec or {}).get("retention") or {}).get("purge_after") or ""


def add_observations(d, records, now):
    """Append validated records to today's file, one line per (post, source)
    per day: a second record for the same post and source today is merged
    into that line. A record that adds nothing to the post's merged state is
    skipped (unchanged) unless it extends the retention date (an API
    refresh of identical stats still counts as a refresh).
    -> {"new", "updated", "refreshed", "unchanged", "file"}."""
    require(d)
    day = day_str(now)
    path = obs_path(d, day)
    merged = merge_snapshots(load_snapshots(d))
    existing = [obj for _, obj, _ in read_jsonl(path) if obj] if os.path.isfile(path) else []
    index = {(r.get("obs_id"), r.get("source")): i for i, r in enumerate(existing)}
    rep = {"new": 0, "updated": 0, "refreshed": 0, "unchanged": 0,
           "file": os.path.relpath(path, d)}
    for rec in records:
        oid = rec["obs_id"]
        prev = merged.get(oid)
        kind = "new" if prev is None else "updated"
        if prev is not None and _content_key(_overlay(S.expand(prev), rec)) == \
                _content_key(prev):
            if _purge_after(rec) and _purge_after(rec) > _purge_after(prev):
                kind = "refreshed"
            else:
                rep["unchanged"] += 1
                continue
        key = (oid, rec.get("source"))
        if key in index:
            old = existing[index[key]]
            if (old.get("observed_at") or "") <= (rec.get("observed_at") or ""):
                existing[index[key]] = S.compact(_overlay(S.expand(old), _public(rec)))
            else:
                existing[index[key]] = S.compact(_overlay(S.expand(_public(rec)), old))
        else:
            index[key] = len(existing)
            existing.append(S.compact(_public(rec)))
        rep[kind] += 1
        merged[oid] = _overlay(S.expand(prev) if prev else S.expand({}), rec)
        merged[oid]["retention"] = dict(rec.get("retention") or {})
    if rep["new"] or rep["updated"] or rep["refreshed"]:
        write_jsonl(path, existing)
    return rep


# ---------------------------------------------------------------- creators
def _creator_key(rec):
    return (rec.get("platform") or "", rec.get("handle") or "")


def load_creators(d):
    """{(platform, handle): snapshot} — the latest per key."""
    out = {}
    p = creators_path(d)
    if not os.path.isfile(p):
        return out
    for _, obj, _ in read_jsonl(p):
        if not obj:
            continue
        rec = S.expand(obj, S.CREATOR)
        key = _creator_key(rec)
        if key not in out or (out[key].get("snapshot_at") or "") <= \
                (rec.get("snapshot_at") or ""):
            out[key] = rec
    return out


def upsert_creators(d, snapshots):
    """Keep one line per (platform, handle): the newest snapshot (a re-fetch
    with identical numbers still moves snapshot_at / purge_after forward:
    that is the refresh the retention policy asks for). -> counts."""
    cur = load_creators(d)
    rep = {"new": 0, "updated": 0, "refreshed": 0, "unchanged": 0}
    for rec in snapshots:
        key = _creator_key(rec)
        old = cur.get(key)
        if old is not None and (old.get("snapshot_at") or "") >= (rec.get("snapshot_at") or ""):
            rep["unchanged"] += 1
            continue
        if old is not None:
            a, b = dict(S.compact(old)), dict(S.compact(rec))
            for k in ("snapshot_at", "retention"):
                a.pop(k, None)
                b.pop(k, None)
            rep["refreshed" if a == b else "updated"] += 1
        else:
            rep["new"] += 1
        cur[key] = rec
    if rep["new"] or rep["updated"] or rep["refreshed"] or \
            not os.path.isfile(creators_path(d)):
        write_jsonl(creators_path(d), [cur[k] for k in sorted(cur)])
    return rep


# ----------------------------------------------------------------- signals
def load_signals(d):
    """Aggregate signals deduplicated by signal_id (latest observed_at)."""
    out = {}
    for p in signal_files(d):
        for _, obj, _ in read_jsonl(p):
            if not obj:
                continue
            rec = S.expand(obj, S.SIGNAL)
            sid = rec.get("signal_id")
            if sid and (sid not in out or (out[sid].get("observed_at") or "") <=
                        (rec.get("observed_at") or "")):
                out[sid] = rec
    return [out[k] for k in sorted(out)]


def add_signals(d, records, now):
    """Signals go to the file of their list date; one line per signal_id."""
    require(d)
    have = {r["signal_id"]: r for r in load_signals(d)}
    by_day = {}
    rep = {"new": 0, "updated": 0, "unchanged": 0, "files": []}
    for rec in records:
        old = have.get(rec["signal_id"])
        if old is not None:
            a, b = dict(S.compact(old)), dict(S.compact(rec))
            a.pop("observed_at", None)
            b.pop("observed_at", None)
            if a == b:
                rep["unchanged"] += 1
                continue
        by_day.setdefault(rec["date"], []).append(rec)
        rep["updated" if old is not None else "new"] += 1
        have[rec["signal_id"]] = rec
    for day in sorted(by_day):
        path = signal_path(d, day)
        lines = [obj for _, obj, _ in read_jsonl(path) if obj] if os.path.isfile(path) else []
        idx = {o.get("signal_id"): i for i, o in enumerate(lines)}
        for rec in by_day[day]:
            line = S.compact(rec)
            if rec["signal_id"] in idx:
                lines[idx[rec["signal_id"]]] = line
            else:
                idx[rec["signal_id"]] = len(lines)
                lines.append(line)
        write_jsonl(path, lines)
        rep["files"].append(os.path.relpath(path, d))
    return rep


# ------------------------------------------------------------------- usage
def load_usage(d):
    p = usage_path(d)
    if not os.path.isfile(p):
        return []
    return [obj for _, obj, _ in read_jsonl(p) if obj]


def append_usage(d, entry):
    p = usage_path(d)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(entry, sort_keys=True, ensure_ascii=False,
                           separators=(",", ":")) + "\n")


# ----------------------------------------------------------------- recipes
def expand_top(obj, spec):
    """Top-level fields present (None / []), nested objects left as stored
    (an absent optional object stays None)."""
    out = dict(obj)
    for k, s in spec.items():
        if k not in out:
            out[k] = [] if s["type"] == "list" else None
    return out


def load_recipes(d):
    p = derived_path(d, "recipes.jsonl")
    if not os.path.isfile(p):
        return []
    return [expand_top(obj, S.RECIPE) for _, obj, _ in read_jsonl(p) if obj]


def save_recipes(d, recipes):
    write_jsonl(derived_path(d, "recipes.jsonl"),
                sorted(recipes, key=lambda r: r.get("recipe_id") or ""))


# ------------------------------------------------------------------- quota
def load_quota(d):
    return read_json(derived_path(d, "quota.json"), {}) or {}


def save_quota(d, q):
    write_json(derived_path(d, "quota.json"), q)


# ------------------------------------------------------------------ helpers
def file_sizes(d):
    """[(relative path, bytes)] of every file over SIZE_WARN_BYTES."""
    out = []
    for dp, dns, fns in os.walk(d):
        dns[:] = sorted(x for x in dns if x != ".git")
        for fn in sorted(fns):
            p = os.path.join(dp, fn)
            try:
                n = os.path.getsize(p)
            except OSError:
                continue
            if n > SIZE_WARN_BYTES:
                out.append((os.path.relpath(p, d), n))
    return out


def rmtree_quiet(p):
    shutil.rmtree(p, ignore_errors=True)
