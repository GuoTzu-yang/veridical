#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""补齐 gate._REQ_EVIDENCE 缺的 2 项。

28 个 required 文本里，映射表覆盖 26 项，缺：
    写明目标向量而非加权和
    解析解特例或数值稳定性验证

缺映射的后果不是报错，是**静默跳过** —— chick_required 里
`clues = _REQ_EVIDENCE.get(item); if clues is None: continue`，
于是这两项永远不会被检查，题型必做项形同虚设。
"""
import ast
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "gate.py")
s = open(P, encoding="utf-8").read()

ADD = '''    "写明目标向量而非加权和": ["mathbf{f}(x)", "objective vector", "min_{"],
    "解析解特例或数值稳定性验证": ["closed-form", "stability",
                                  "numerical stability", "verified"],
'''

if '"写明目标向量而非加权和"' not in s:
    ANCHOR = '    "Pareto 前沿与非支配说明": ["Pareto", "front"],'
    assert ANCHOR in s, "找不到 Pareto 锚点"
    s = s.replace(ANCHOR, ANCHOR + "\n" + ADD.rstrip("\n"), 1)
    ast.parse(s)
    compile(s, P, "exec")
    open(P, "w", encoding="utf-8", newline="\n").write(s)
    print("  已补 2 项映射")

import json
import subprocess
import sys
sys.path.insert(0, HERE)
import gate  # noqa: E402

d = json.load(open(os.path.join(HERE, "kb", "methods", "index.json"),
                   encoding="utf-8"))
allreq = []
for v in d["kinds"].values():
    for r in (v.get("required") or []):
        if r not in allreq:
            allreq.append(r)
miss = [r for r in allreq if r not in gate._REQ_EVIDENCE]
print(f"  required {len(allreq)} 项 / 映射 {len(gate._REQ_EVIDENCE)} 项 "
      f"/ 仍缺 {len(miss)} 项")
if miss:
    for r in miss:
        print("    " + r)

r = subprocess.run([sys.executable, "gate.py", "out/fig"],
                   capture_output=True, text=True, encoding="utf-8",
                   errors="replace", cwd=HERE)
for ln in (r.stdout or "").splitlines():
    if "required" in ln or "质量门" in ln:
        print("  " + ln.strip())
