# -*- coding: utf-8 -*-
"""Probe 3 (evaluation board): are the two "immediate" extensions executable?

Claim under test (paper.tex L1144-1147):
  "Two extensions are immediate: applying the gate to retrieval-augmented
   pipelines, where the ``number'' is a quoted passage rather than a digit; and
   replacing the single-corpus calibration with a rolling audit, where each new
   report is checked against the previous verdicts."

An extension is executable here if a reader could act on it: either a script, a
design artifact, a defined criterion, or an input contract. We check the repo,
not the prose.

Read-only. Prints only.
"""
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAPER = os.path.join(ROOT, "out", "final", "paper.tex")

SKIP_DIRS = {"external", "__pycache__", "kb", "ledger-history", ".git"}


def iter_project_files():
    """Every project file, external corpora excluded (they are third-party data)."""
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            yield os.path.join(dirpath, fn)


def main():
    print("=" * 78)
    print("PROBE 3  executability of the two 'immediate' extensions")
    print("=" * 78)

    terms = {
        "retrieval-augmented": re.compile(r"retrieval[\s\-]?augmented", re.I),
        "RAG": re.compile(r"\bRAG\b"),
        "rolling audit": re.compile(r"rolling[\s\-]?audit", re.I),
        "quoted passage": re.compile(r"quoted passage", re.I),
        "previous verdicts": re.compile(r"previous verdicts", re.I),
    }

    hits = {k: [] for k in terms}
    scanned = 0
    for path in iter_project_files():
        if os.path.getsize(path) > 4_000_000:
            continue
        try:
            txt = open(path, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        scanned += 1
        rel = os.path.relpath(path, ROOT)
        for name, rx in terms.items():
            n = len(rx.findall(txt))
            if n:
                hits[name].append((rel, n))

    print("Files scanned (external/ excluded): %d\n" % scanned)
    for name in terms:
        rows = hits[name]
        print("%-22s total %d occurrence(s) in %d file(s)" % (name, sum(n for _, n in rows), len(rows)))
        for rel, n in rows[:12]:
            print("      %-58s x%d" % (rel, n))
        if not rows:
            print("      (none)")
        print()

    paper_only = all(rel.endswith("paper.tex") for rel, _ in
                     hits["rolling audit"] + hits["quoted passage"])
    print("Are 'rolling audit' / 'quoted passage' confined to paper.tex? %s" % paper_only)

    print()
    print("=" * 78)
    print("What a reader would need in order to act on each extension")
    print("=" * 78)
    need = [
        ("E1 retrieval-augmented gate",
         ["a passage resolver (what replaces the frozen token table?)",
          "a definition of 'traced' for a quoted passage",
          "a failing example the gate should catch",
          "an input contract for a document with quotes"]),
        ("E2 rolling audit",
         ["where previous verdicts are stored and in what format",
          "the drift criterion: what counts as disagreement with history",
          "what happens when the new report legitimately changes a number",
          "a threshold or alerting rule"]),
    ]
    for name, items in need:
        print(" %s" % name)
        for it in items:
            print("   - %s" % it)
        print("   repo artifacts addressing these: searching ...")
        key = ("retrieval" if "retrieval" in name else "rolling")
        found = [rel for rel, _ in hits.get("retrieval-augmented" if key == "retrieval" else "rolling audit", [])]
        print("   -> %s" % (found if found else "NONE beyond paper.tex"))
        print()

    print("=" * 78)
    print("Is there a scratch/design note for either extension?")
    print("=" * 78)
    pat = re.compile(r"extension|extend", re.I)
    notes = []
    for path in iter_project_files():
        rel = os.path.relpath(path, ROOT)
        if not rel.endswith((".md", ".txt")):
            continue
        try:
            txt = open(path, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        if re.search(r"retrieval[\s\-]?augmented|rolling[\s\-]?audit", txt, re.I):
            notes.append(rel)
    print("design notes mentioning either extension: %s" % (notes or "NONE"))

    print()
    print("VERDICT INPUT:")
    print("  'rolling audit' appears in project files: %d (paper.tex only: %s)"
          % (len(hits['rolling audit']), paper_only))
    print("  any script/contract/criterion for either extension: none found")
    print("  the word carrying the feasibility claim is 'immediate' (L1144).")


if __name__ == "__main__":
    main()
