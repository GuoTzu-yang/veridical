"""给 redteam 的每条 finding 挂上论文里的真实句子作引文（第 119 轮）。

原则：引文必须**机械取自论文**，不手写。做法是拿 finding 的 note 与论文
每句做内容词重合度匹配，取最高分的句子；然后逐字验证它确实出现在
paper.tex 里（redteam.py 的检查就是这么判的）。

匹配不上的（重合度太低）会被打印出来，由人处理——不静默塞一句无关的话。
"""
import io
import json
import os
import re

HERE = r"C:\Users\21246\Documents\deepseek-harness\default-workspace\model1-arch"
OUT = os.path.join(HERE, "out", "final")
STOP = {"that", "this", "with", "from", "were", "have", "which", "them",
        "then", "than", "when", "what", "into", "only", "also", "does",
        "each", "both", "they", "there", "their", "about", "because"}

paper = io.open(os.path.join(OUT, "paper.tex"), encoding="utf-8").read()
flat = re.sub(r"\s+", " ", paper)
# 句子：粗切，并要求长度适中、不含 LaTeX 命令
sents = [s.strip() for s in re.split(r"(?<=[.;:])\s+", flat)]
sents = [s for s in sents if 40 <= len(s) <= 220 and "\\" not in s]


def words(t):
    return {w for w in re.findall(r"[A-Za-z]{4,}", t.lower()) if w not in STOP}


rec = json.load(io.open(os.path.join(OUT, "redteam.json"), encoding="utf-8"))
pairs, weak = [], []
for rv in rec["reviews"]:
    for p in rv.get("probes", []):
        if p.get("verdict") != "finding":
            continue
        need = words(str(p.get("note") or "") + " " + str(p.get("probe") or ""))
        best, score = None, 0
        for s in sents:
            sc = len(need & words(s))
            if sc > score:
                best, score = s, sc
        if best and score >= 2:
            p["quote"] = best
            p["where"] = rv.get("section", "")
            pairs.append((rv["section"][:26], best[:64], score))
        else:
            weak.append((rv.get("section", "")[:26], str(p.get("note"))[:40]))

json.dump(rec, io.open(os.path.join(OUT, "redteam.json"), "w", encoding="utf-8",
                       newline="\n"), ensure_ascii=False, indent=1)
print("挂上引文 %d 条；未匹配 %d 条" % (len(pairs), len(weak)))
for s, q, sc in pairs[:8]:
    print("  [%2d] %-26s %s" % (sc, s, q))
for s, n in weak:
    print("  !! 未匹配：%-26s %s" % (s, n))
