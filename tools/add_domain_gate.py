#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""给 gate 加「领域污染」检查。

思路：从论文自己的 Problem 1 标题里读出响应变量名，再看正文有没有
不属于该领域的术语。

    Problem 1: How the geometry governs **output**   ← 响应是 output
    但正文出现 R_{th} / Nu = C / thermal resistance  → 污染

这一条是「任意题直通」的守门员：换一道题后如果机理层没被正确
门控，它会立刻报出来，而不是等评委发现。
"""
import ast
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "gate.py")
s = open(P, encoding="utf-8").read()

FUNC = '''def chk_domain(figdir: str) -> dict:
    """领域污染：正文出现与响应变量不匹配的领域术语。"""
    tex = os.path.join(figdir, "paper.tex")
    if not os.path.exists(tex):
        return _r("domain", HARD, "N/A", "没有 paper.tex")
    try:
        import re as _re
        x = open(tex, encoding="utf-8").read()
        m = _re.search(r"Problem 1: How the geometry governs ([^}]+)", x)
        resp = (m.group(1) if m else "").strip().lower()
        if not resp:
            return _r("domain", HARD, "N/A", "读不到 Problem 1 的响应名")
        # 响应名不是热学类，却出现热沉术语 → 污染
        thermal_resp = any(k in resp for k in
                           ("thermal", "resistance", "heat", "temperature"))
        if thermal_resp:
            return _r("domain", HARD, "PASS",
                      f"响应「{resp[:24]}」与领域一致")
        bad = [w for w in ("R_{th}", "Nu = C", "subsection{Thermal resistance}",
                           "thermal resistance", "pressure drop",
                           "manifold", "pin-fin")
               if w in x]
        if bad:
            return _r("domain", HARD, "FAIL",
                      f"响应「{resp[:20]}」但出现 {len(bad)} 类热沉术语: "
                      f"{bad[:3]}")
        return _r("domain", HARD, "PASS",
                  f"响应「{resp[:24]}」无跨领域术语")
    except Exception as e:                      # noqa: BLE001
        return _r("domain", HARD, "N/A", f"{type(e).__name__}: {e}")


'''

if "def chk_domain(" not in s:
    k = s.find("def run_all(")
    s = s[:k] + FUNC + s[k:]
    s = s.replace("        chk_rigor(figdir),",
                  "        chk_rigor(figdir),\n        chk_domain(figdir),", 1)
    ast.parse(s)
    compile(s, P, "exec")
    open(P, "w", encoding="utf-8", newline="\n").write(s)
    print("  gate 加了 domain（领域污染）")

import subprocess
import sys
r = subprocess.run([sys.executable, "gate.py", "out/fig"],
                   capture_output=True, text=True, encoding="utf-8",
                   errors="replace", cwd=HERE)
for ln in (r.stdout or "").splitlines():
    if "domain" in ln or "质量门" in ln:
        print("  " + ln.strip())
