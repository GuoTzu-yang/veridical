# -*- coding: utf-8 -*-
"""scope-auditor / probe 1: does the restatement cover every question of the brief?

Read-only. Prints:
  A. every \section / \subsection in out/final/paper.tex with line numbers
  B. the restatement block L75-L170 verbatim with line numbers
  C. evidence search for an EXTERNAL brief: files whose name or content looks
     like a problem statement, with the full exclusion rule and encoding used
  D. runs.json brief table (title + first 80 chars) to see whether any entry
     could be the brief behind out/final
No file is written, nothing is modified.
"""
import io
import json
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAPER = os.path.join(ROOT, "out", "final", "paper.tex")

EXCLUDE_DIRS = {
    "out", "out_runs", "out\\runs", "runs", "runs_backup",
    "node_modules", "__pycache__", "external", ".git", "fig", "dist", "build",
}


def read_lines(path):
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read().splitlines()


def rel(p):
    return os.path.relpath(p, ROOT).replace("\\", "/")


lines = read_lines(PAPER)
print("== A. section skeleton of %s (%d lines) ==" % (rel(PAPER), len(lines)))
for i, ln in enumerate(lines, 1):
    if re.match(r"\\(section|subsection)\{", ln):
        print("  L%-5d %s" % (i, ln.strip()[:110]))

print()
print("== B. restatement block L75-L170 verbatim ==")
for i in range(74, min(170, len(lines))):
    print("L%-4d| %s" % (i + 1, lines[i]))

print()
print("== C. external brief search ==")
print("exclusion rule: walk %s, skip any path whose parts intersect %s,"
      % (rel(ROOT), sorted(EXCLUDE_DIRS)))
print("                extensions .md/.txt/.tex/.json; decode utf-8 errors=replace")
print("                also skip everything under out/ (papers are products, not briefs)")

NAME_HINT = re.compile(r"(题面|题目|problem|brief|requirement|要求|任务|statement)", re.I)
BODY_HINT = re.compile(
    r"(Problem Statement|问题重述|题目要求|Your task|You are asked|"
    r"背景与要求|赛题|MCM/ICM|Contest Problem)", re.I)

name_hits = []
body_hits = []
scanned = 0
for dirpath, dirnames, filenames in os.walk(ROOT):
    parts = set(os.path.normpath(dirpath).split(os.sep))
    if parts & EXCLUDE_DIRS or "out" in os.path.relpath(dirpath, ROOT).split(os.sep)[:1]:
        dirnames[:] = []
        continue
    for fn in filenames:
        if not fn.lower().endswith((".md", ".txt", ".tex", ".json")):
            continue
        p = os.path.join(dirpath, fn)
        scanned += 1
        if NAME_HINT.search(fn):
            name_hits.append(rel(p))
        try:
            with open(p, "r", encoding="utf-8", errors="replace") as fh:
                body = fh.read()
        except OSError:
            continue
        m = BODY_HINT.search(body)
        if m:
            body_hits.append((rel(p), m.group(0)))

print("scanned %d files outside out/ (excluding %s)" % (scanned, sorted(EXCLUDE_DIRS)))
print("name-hint hits (%d): %s" % (len(name_hits), name_hits))
print("body-hint hits (%d):" % len(body_hits))
for p, g in body_hits:
    print("   %-60s marker=%r" % (p, g))

print()
print("== C2. does any file in the repo contain the paper's own team id? ==")
tid = "2612345"
tid_hits = []
for dirpath, dirnames, filenames in os.walk(ROOT):
    base = os.path.relpath(dirpath, ROOT).split(os.sep)[0]
    if base in EXCLUDE_DIRS or base.startswith("out"):
        dirnames[:] = []
        continue
    for fn in filenames:
        if not fn.lower().endswith((".md", ".txt", ".tex", ".json", ".py")):
            continue
        p = os.path.join(dirpath, fn)
        try:
            with open(p, "r", encoding="utf-8", errors="replace") as fh:
                if tid in fh.read():
                    tid_hits.append(rel(p))
        except OSError:
            pass
print("team-id hits outside out/: %d %s" % (len(tid_hits), tid_hits[:12]))

print()
print("== D. runs.json brief table ==")
rj = os.path.join(ROOT, "runs.json")
try:
    data = json.loads(open(rj, "r", encoding="utf-8").read())
except Exception as exc:  # noqa: BLE001
    print("runs.json unreadable: %r" % (exc,))
    data = None
if isinstance(data, dict):
    probs = data.get("problems") or data.get("runs") or []
else:
    probs = data or []
print("problems: %d" % len(probs))
for p in probs[:40]:
    if not isinstance(p, dict):
        continue
    brief = (p.get("题面") or p.get("problem") or p.get("brief") or "")
    print("  %-16s 题面[%d]=%r" % (p.get("name", "?"), len(str(brief)), str(brief)[:80]))
