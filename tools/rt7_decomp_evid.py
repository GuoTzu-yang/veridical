# -*- coding: utf-8 -*-
"""rt7_decomp_evid.py —— 用 gate/redteam.check 的同一种读法，验我准备写进
redteam json 的 where+evidence 是否逐字成立。只读。
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

CASES = [
    ("untraced.py", "not has_dot and abs(v) <= 1000"),
    ("out/final/tab_anatomy.tex", "Tabulated data"),
    ("freeze.py", 'if "." in t'),
    ("out/final/tab_anatomy.tex", "1054"),
    ("out/final/paper.tex", "into four kinds"),
    ("out/final/paper.tex", "1{,}482"),
    ("out/final/paper.tex", "the sample size come from"),
]

bad = 0
for w, ev in CASES:
    fp = os.path.join(HERE, w)
    if not os.path.exists(fp):
        print("  [MISS] 文件不存在 %s" % w)
        bad += 1
        continue
    body = io.open(fp, encoding="utf-8", errors="replace").read()
    ok = ev in body
    print("  [%s] %-30s <- %r" % ("OK " if ok else "MISS", w, ev))
    if not ok:
        bad += 1
        # 给出行号辅助
        for i, ln in enumerate(body.splitlines(), 1):
            if ev[:12] in ln:
                print("        近似命中 L%d: %s" % (i, ln.strip()[:100]))

# 顺带确认 redteam.py 的 SPEC 顺序与我 json 的探针顺序一致
import redteam
print("\n  SPEC['analysis'] 探针顺序：")
for i, p in enumerate(redteam.SPEC["analysis"]["probes"], 1):
    print("    %d. %s" % (i, p))
print("  role =", redteam.SPEC["analysis"]["role"])
print("\n%s" % ("全部逐字成立" if bad == 0 else "有 %d 条不成立" % bad))
sys.exit(0 if bad == 0 else 1)
