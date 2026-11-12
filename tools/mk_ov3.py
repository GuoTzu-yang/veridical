import json, os, re
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
t = open(os.path.join(HERE, "out", "t2", "paper.tex"), encoding="utf-8").read()
paras = [p.strip() for p in t.split("\n\n")
         if p.strip() and not p.strip().startswith(("\\", "%"))
         and "\\begin{" not in p and "\\end{" not in p and len(p.strip()) > 120]
# 挑「Problem 3」那段当靶子（稳定性检验，本来就该重写）
tgt = [p for p in paras if p.startswith("Problem 3 asks")][:1]
print("  靶子段落: %r" % (tgt[0][:70] if tgt else "未找到"))
key = " ".join(tgt[0].split())[:40] if tgt else ""
ov = {key: ("The stability check is built around the question this problem "
            "actually asks: does the ranking survive a change of scale? "
            "Three scale choices were compared, and a conclusion is only "
            "reported when all three agree.")}
p = os.path.join(HERE, "out", "ov2.json")
json.dump(ov, open(p, "w", encoding="utf-8", newline="\n"),
          ensure_ascii=False, indent=1)
print("  key = %r" % key)