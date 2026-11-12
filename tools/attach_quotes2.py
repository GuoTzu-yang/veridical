"""给 redteam 的 finding 挂引文（第 119 轮，第二版）。

第一版拿中文 note 去英文正文里做词重合，得 0 条 —— 方法错了。
第二版：由人**指定一个关键词**（红队当时看到的那个数/那句话的关键词），
机器去论文里取包含它的那一句，并逐字校验。关键词必须能在正文里唯一定位，
否则报出来让人改——不静默塞一句无关的话。
"""
import io
import json
import os
import re

OUT = r"C:\Users\21246\Documents\deepseek-harness\default-workspace\model1-arch\out\final"
paper = io.open(os.path.join(OUT, "paper.tex"), encoding="utf-8").read()
flat = re.sub(r"\s+", " ", paper)


def sent_with(key: str):
    """取包含 key 的那一句（以句号/分号切）。"""
    i = flat.find(key)
    if i < 0:
        return None
    a = max(flat.rfind(". ", 0, i), flat.rfind("; ", 0, i)) + 1
    b = flat.find(". ", i)
    s = flat[a:b + 1 if b > 0 else i + 160].strip()
    return s if 30 <= len(s) <= 260 else flat[i - 60:i + 160].strip()


# 每条 finding 的关键词：红队当时看到的那处证据
KEYS = [
    ("analysis", "199"),
    ("analysis", "sum of the classes"),
    ("method_argument", "ledger"),
    ("validation", "window"),
    ("validation", "0.218"),
    ("validation", "ablation"),
    ("results", "traceab"),
    ("results", "94.1"),
    ("results", "never cited"),
    ("results", "23 problems"),
    ("self_correction", "N/A"),
    ("deployment", "editorial"),
    ("claims", "recall"),
]

rec = json.load(io.open(os.path.join(OUT, "redteam.json"), encoding="utf-8"))
rows = []
for rv in rec["reviews"]:
    for p in rv.get("probes", []):
        if p.get("verdict") != "finding":
            continue
        rows.append((rv.get("section", ""), p))

print("finding 共 %d 条，关键词 %d 个" % (len(rows), len(KEYS)))
missing = []
for (sec, p), (ks, key) in zip(rows, KEYS):
    s = sent_with(key)
    if not s:
        missing.append((sec, key))
        continue
    p["quote"] = s
    p["where"] = sec
    print("  [%s] %s ..." % (key, s[:70]))

if missing:
    print("\n关键词在正文里找不到：", missing)
json.dump(rec, io.open(os.path.join(OUT, "redteam.json"), "w", encoding="utf-8",
                       newline="\n"), ensure_ascii=False, indent=1)
print("\n已写入 %d 条引文" % (len(rows) - len(missing)))
