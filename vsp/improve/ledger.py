"""learned/LEDGER.md — append-only record of every accepted / rejected
change, with its evidence. Written by verify, promote and cycle."""
import os

from vsp.improve import common as C

HEADER = """# LEDGER — the self-improvement loop's decisions

Append-only (newest last). Written by `python3 -m vsp.improve` — `verify`,
`promote` and `cycle`. Every entry names its verdict, the ACCEPT rules it was
judged by, and where the evidence lives. Automation never edits gate or rule
code to pass, never pushes to main and never merges its own PRs.
"""


def path():
    return C.learned("LEDGER.md")


def append(kind, subject, verdict, lines=(), evidence=None, when=None):
    """Append one entry. -> the ledger path."""
    p = path()
    when = when or C.now_utc()
    head = f"## {when.strftime('%Y-%m-%d %H:%M:%SZ')} · {kind} · {subject} · {verdict}"
    body = [head, ""]
    for ln in lines:
        ln = str(ln).rstrip()
        if ln:
            body.append(ln if ln.startswith(("-", "|", "  ")) else f"- {ln}")
    if evidence:
        ev = evidence if isinstance(evidence, (list, tuple)) else [evidence]
        body.append("- evidence: " + ", ".join(f"`{C.rel(e)}`" for e in ev if e))
    text = "\n".join(body) + "\n\n"
    os.makedirs(os.path.dirname(p), exist_ok=True)
    if not os.path.exists(p):
        with open(p, "w", encoding="utf-8") as f:
            f.write(HEADER + "\n")
    with open(p, "a", encoding="utf-8") as f:
        f.write(text)
    return p


def entries(p=None):
    """Parsed entry headers: [{when, kind, subject, verdict}] (oldest first)."""
    out = []
    try:
        with open(p or path(), encoding="utf-8") as f:
            for line in f:
                if line.startswith("## ") and " · " in line:
                    parts = [x.strip() for x in line[3:].split(" · ")]
                    if len(parts) >= 4:
                        out.append({"when": parts[0], "kind": parts[1],
                                    "subject": " · ".join(parts[2:-1]),
                                    "verdict": parts[-1]})
    except OSError:
        pass
    return out
