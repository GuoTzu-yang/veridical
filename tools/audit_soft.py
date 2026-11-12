import difflib
import os
import re

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAPERS = {
    "heat sink": "out/fig/paper.tex",
    "evaluation": "out/domains/evaluation/paper.tex",
    "prediction": "out/domains/prediction/paper.tex",
    "network": "out/domains/network/paper.tex",
    "real C2023": "out/real/paper.tex",
}

def sentences(path):
    t = open(os.path.join(HERE, path), encoding="utf-8").read()
    t = re.sub(r"\\begin\{(table|tabular|figure|verbatim|itemize)\}.*?"
               r"\\end\{\1\}", " ", t, flags=re.S)
    t = re.sub(r"\\[a-zA-Z]+(\[[^\]]*\])?(\{[^}]*\})?", " ", t)
    t = re.sub(r"[{}$\\]", " ", t)
    out = []
    for s in re.split(r"(?<=[.!?])\s+", t):
        s = " ".join(s.split())
        if len(s.split()) >= 6:
            out.append(s)
    return out

names = list(PAPERS)
print("  === 不同题目的论文句子重合率（模板味）===")
for i in range(len(names)):
    for j in range(i + 1, len(names)):
        a = sentences(PAPERS[names[i]])
        b = sentences(PAPERS[names[j]])
        sm = difflib.SequenceMatcher(None, a, b)
        same = sum(bl.size for bl in sm.get_matching_blocks())
        r = same / max(1, len(a))
        if r > 0.5:
            print("    %-12s vs %-12s 重合 %.0f%% (%d/%d 句完全相同)"
                  % (names[i], names[j], r * 100, same, len(a)))

print()
print("  === 跨题残留：热沉专有词是否漏到别的题 ===")
HEATSINK = ["针肋", "pin fin", "manifold", "channel", "heat sink",
            "thermal resistance", "pressure drop", "非均匀性"]
for n, p in PAPERS.items():
    t = open(os.path.join(HERE, p), encoding="utf-8").read().lower()
    hits = [w for w in HEATSINK if w.lower() in t]
    if n != "heat sink" and hits:
        print("    %-12s 命中: %s" % (n, hits))