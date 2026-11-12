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
print("  === 各题「假设」节的内容（是否因题而变）===")
for n, p in PAPERS.items():
    t = open(os.path.join(HERE, p), encoding="utf-8").read()
    i = t.find(r"\section{Assumptions and Notations}")
    j = t.find(r"\section{", i + 10)
    seg = t[i:j]
    items = re.findall(r"\\item\s+([^\\\\]{0,110})", seg)
    print("  %-12s (%d 条假设)" % (n, len(items)))
    for x in items[:3]:
        print("      - %s" % " ".join(x.split())[:82])
print()
print("  === 各题的「机理基础」节 ===")
for n, p in PAPERS.items():
    t = open(os.path.join(HERE, p), encoding="utf-8").read()
    i = t.find(r"\section{Mechanistic basis}")
    if i < 0:
        i = t.find(r"\section{机理基础}")
    j = t.find(r"\section{", i + 10)
    seg = t[i:j]
    items = re.findall(r"\\item\s+([^\\\\]{0,110})", seg)
    print("  %-12s (%d 条机理)" % (n, len(items)))
    for x in items[:2]:
        print("      - %s" % " ".join(x.split())[:82])