import os
import re
from collections import Counter

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAPERS = ["out/fig/paper.tex",
          "out/domains/evaluation/paper.tex",
          "out/domains/prediction/paper.tex",
          "out/domains/network/paper.tex",
          "out/real/paper.tex"]

def section_sentences(path):
    t = open(os.path.join(HERE, path), encoding="utf-8").read()
    # 按 \section 切
    parts = re.split(r"(\\section\*?\{[^}]*\})", t)
    out = {}
    cur = "(preamble)"
    for p in parts:
        m = re.match(r"\\section\*?\{([^}]*)\}", p)
        if m:
            cur = m.group(1)
            continue
        body = re.sub(r"\\begin\{(table|tabular|figure|verbatim|itemize)\}.*?"
                      r"\\end\{\1\}", " ", p, flags=re.S)
        body = re.sub(r"\\[a-zA-Z]+(\[[^\]]*\])?(\{[^}]*\})?", " ", body)
        body = re.sub(r"[{}$\\]", " ", body)
        for s in re.split(r"(?<=[.!?])\s+", body):
            s = " ".join(s.split())
            if len(s.split()) >= 6:
                out.setdefault(cur, []).append(s)
    return out

alls = [section_sentences(p) for p in PAPERS]
secs = []
for a in alls:
    for k in a:
        if k not in secs:
            secs.append(k)

print("  章节                                     题数  总句  全题都有的句")
print("  " + "-" * 66)
rows = []
for k in secs:
    sets = []
    for a in alls:
        sets.append(set(a.get(k, [])))
    common = set.intersection(*sets) if len(sets) > 1 else set()
    tot = sum(len(a.get(k, [])) for a in alls)
    n_with = sum(1 for a in alls if a.get(k))
    rows.append((len(common), n_with, tot, k, common))
rows.sort(reverse=True)
for nc, nw, tot, k, common in rows:
    if nc == 0:
        continue
    pct = nc / max(1, tot / max(1, nw)) * 100
    print("  %-40s %2d  %4d  %3d (%.0f%%)" % (k[:40], nw, tot, nc, pct))
    ex = sorted(common)[0]
    print("        例: %s" % ex[:88])