# -*- coding: utf-8 -*-
"""Probe 1 (evaluation board): is every self-assessment criterion in
\section{Evaluation and extension} (paper.tex L1119-1148) re-checkable by a
command that actually exists in this repo?

Read-only. Prints findings only. Never writes.

For each claim made in that section we look for (a) the claim text, (b) the
artifact that would let a reader re-run it, (c) whether the artifact exists.
"""
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAPER = os.path.join(ROOT, "out", "final", "paper.tex")
TIMING = os.path.join(ROOT, "out", "final", "tab_timing.tex")
ABL = os.path.join(ROOT, "out", "final", "ablation.json")


def readlines(path):
    with open(path, encoding="utf-8", errors="replace") as fh:
        return fh.read().splitlines()


def main():
    lines = readlines(PAPER)
    # The board under audit.
    sec = lines[1118:1148]
    print("=" * 78)
    print("SECTION UNDER AUDIT  paper.tex L1119-1148  (%d lines)" % len(sec))
    print("=" * 78)
    for i, ln in enumerate(sec, start=1119):
        print("%4d| %s" % (i, ln))

    print()
    print("=" * 78)
    print("C1.  'under five seconds for the full chain on one problem'")
    print("=" * 78)
    tim = readlines(TIMING)
    rows = []
    for ln in tim:
        m = re.match(r"^\s*(\d+)\s*&\s*(.+?)\s*&\s*([0-9.]+)\s*&\s*(\d+)\s*\\\\", ln)
        if m:
            rows.append((int(m.group(1)), m.group(2), float(m.group(3)), int(m.group(4))))
    total = 0.0
    for n, cmd, sec_s, ex in rows:
        total += sec_s
        print("  step %-2d %-32s %5.2fs  exit=%d" % (n, cmd, sec_s, ex))
    print("  sum of the %d listed steps      = %.2fs" % (len(rows), total))
    print("  sum without the gate (steps 1-8) = %.2fs"
          % sum(s for n, _, s, _ in rows if n != 9))
    print("  gate alone                       = %.2fs"
          % sum(s for n, _, s, _ in rows if n == 9))
    print("  ---> 'under five seconds' holds only for the 8 non-gate steps.")
    print("  ---> The paper's own total row in tab_timing.tex says 6.68s.")
    m = [ln for ln in tim if "total" in ln]
    print("  tab_timing.tex total row: %r" % (m[0].strip() if m else None))

    # Is the "full chain" defined anywhere with a runnable command?
    body = "\n".join(lines)
    print()
    print("  defining 'full chain' inside the evaluation section:",
          "full chain" in "\n".join(sec))
    print("  does the evaluation section name any command to run? ->",
          bool(re.search(r"\bpython\b|\btools/|gate\.py", "\n".join(sec))))

    print()
    print("=" * 78)
    print("C2.  'deterministic'  -- is there a command that could show this?")
    print("=" * 78)
    tools = sorted(os.listdir(os.path.join(ROOT, "tools")))
    det = [t for t in tools if re.search(r"determin|nondeterm|repeat|twice|stable", t, re.I)]
    print("  tool files matching determin*/repeat*/stable*: %d %s" % (len(det), det[:10]))
    # does any script hash a report twice?
    hits = []
    for name in tools:
        if not name.endswith(".py"):
            continue
        p = os.path.join(ROOT, "tools", name)
        try:
            txt = open(p, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        if re.search(r"determinis", txt, re.I):
            hits.append(name)
    print("  scripts whose source mentions 'determinis*': %d %s" % (len(hits), hits[:12]))

    print()
    print("=" * 78)
    print("C3.  'The provenance mechanism survives an ablation that removes it'")
    print("=" * 78)
    abl = json.load(open(ABL, encoding="utf-8"))
    print("  ablation.json problems: %d" % len(abl))
    for a in abl:
        print("    %-12s with=%.1f%% without=%.1f%% n_total=%d"
              % (a["name"], a["with_table"], a["without_table"], a["n_total"]))
    # subtle: n_with / n_without denominators
    print("  NOTE n_with is the numerator (traced), not a sample size:")
    for a in abl:
        print("    %-12s n_with=%d n_total=%d -> %.1f%%  | without n_without=%d -> %.1f%%"
              % (a["name"], a["n_with"], a["n_total"],
                 100.0 * a["n_with"] / a["n_total"],
                 a["n_without"], 100.0 * a["n_without"] / a["n_total_without"]))
    # which tool regenerates ablation.json?
    gen = []
    for name in tools:
        if not name.endswith(".py"):
            continue
        try:
            txt = open(os.path.join(ROOT, "tools", name), encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        if "ablation.json" in txt:
            gen.append(name)
    print("  scripts that write/read ablation.json: %s" % (gen or "NONE"))

    print()
    print("=" * 78)
    print("C4.  'defect taxonomy ... each instance tied to a round and a code change'")
    print("=" * 78)
    # the table lists representative instances as prose; look for round ids / patch ids
    t = body
    print("  evaluation section mentions 'round':", "round" in "\n".join(sec))
    print("  evaluation section mentions 'code change':", "code change" in "\n".join(sec))
    tax = re.search(r"\\label\{tab:taxonomy\}", t)
    print("  tab:taxonomy label present:", bool(tax))
    # does any machine-readable per-instance record (round id + patch id) exist?
    cand = [f for f in os.listdir(os.path.join(ROOT, "out", "final"))
            if f.endswith(".json") and re.search(r"taxo|defect|round|seeded", f, re.I)]
    print("  out/final json candidates: %s" % cand)
    for f in cand:
        p = os.path.join(ROOT, "out", "final", f)
        try:
            d = json.load(open(p, encoding="utf-8"))
        except Exception as exc:
            print("    %-24s unreadable: %s" % (f, exc))
            continue
        keys = list(d)[:8] if isinstance(d, dict) else ("list len %d" % len(d))
        print("    %-24s top-level: %s" % (f, keys))
        blob = json.dumps(d, ensure_ascii=False)
        for marker in ("round", "patch", "class"):
            print("        contains %-6r: %s" % (marker, marker in blob.lower()))

    print()
    print("=" * 78)
    print("VERDICT INPUT: claims whose re-run command exists")
    print("=" * 78)
    print("  C1 under-five-seconds : command absent; own table contradicts (6.68s)")
    print("  C2 deterministic      : no runnable determinism check found in tools/")
    print("  C3 ablation           : ablation.json exists (data present)")
    print("  C4 taxonomy rounds    : %s machine-readable per-instance round+patch record"
          % ("NO" if not cand else "see above"))


if __name__ == "__main__":
    main()
