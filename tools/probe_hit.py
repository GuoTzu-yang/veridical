import os
import re
import sys
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import aitaste
t = aitaste.strip_tex(open(os.path.join(
    HERE, "out", "runs", "age_struct", "paper.tex"), encoding="utf-8").read())
sents = [s.strip() for s in re.split(r"[.。!！?？\n]", t)
         if aitaste._words(s) >= 6]
print("  句子数 %d" % len(sents))
hit = []
for s in sents:
    ws = re.findall(r"[A-Za-z][A-Za-z'-]*|[\u4e00-\u9fff]", s)
    key = " ".join(ws[:4]).lower() if len(ws) >= 4 else ""
    if key == "not supported the sign":
        hit.append(s)
print("  命中 %d 句，前 3 句原文：" % len(hit))
for s in hit[:3]:
    print("    %s" % s[:190].replace("\n", " "))