# -*- coding: utf-8 -*-
"""Read-only probe 2: do the entities each case's Change/How-found claim actually
exist in the workspace?

Searches only the plugin root (top-level *.py) and out/final/*.json|*.tex|*.txt,
skipping external/, node_modules and the 红队七板 directory. Prints file:line hits.
Writes nothing.
"""
import os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MARKERS = {
    "case1_tokenizer": ["3.3342", "51,737", "1970-1975", "10231", "1482", "1053", "14.5"],
    "case2_cite": ["17 references", "all balanced", "bib_exempt", "uncited", "cite"],
    "case3_na": ["NA_ABSENT", "not applicable", "did not run", "na_kind", "strict"],
    "case4_stamp": ["--stamp", "stamp", "sha256"],
    "case5_abstract": ["128", "29 rounds", "recorded rounds", "rounds of repair"],
    "case6_time_axis": ["time_axis", "is_time", "temporal", "TIME"],
    "case7_figures": ["figure environ", "22--24", "0--4", "figcount"],
}

def candidates():
    out = []
    for name in sorted(os.listdir(ROOT)):
        p = os.path.join(ROOT, name)
        if os.path.isfile(p) and name.endswith((".py", ".json", ".md", ".txt")):
            out.append(p)
    fin = os.path.join(ROOT, "out", "final")
    if os.path.isdir(fin):
        for name in sorted(os.listdir(fin)):
            p = os.path.join(fin, name)
            if os.path.isfile(p) and name.endswith((".json", ".tex", ".txt", ".md")):
                out.append(p)
    return out

files = candidates()
print("files scanned:", len(files))
print("excluded: external/, out/ except out/final/, 红队七板/")
print()

texts = {}
for p in files:
    try:
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            texts[p] = f.read()
    except Exception as e:
        print("SKIP", p, e)

for case, marks in MARKERS.items():
    print("=" * 78)
    print("##", case)
    for m in marks:
        hits = []
        for p, t in texts.items():
            for i, ln in enumerate(t.split("\n"), 1):
                if m in ln:
                    hits.append((os.path.relpath(p, ROOT), i, ln.strip()[:160]))
        print("  [%s]  %d hit(s)" % (m, len(hits)))
        for h in hits[:8]:
            print("      %s:%d  %s" % h)
        if len(hits) > 8:
            print("      ... (%d more)" % (len(hits) - 8))
