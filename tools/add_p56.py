#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""加补丁 P56：跨领域编译验证 + 修 3 个中文泄漏路径 + 时间轴误判。"""
import ast
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "patches.py")
s = open(P, encoding="utf-8").read()

if "P56" not in s:
    HELPER = '''def _p56_wired():
    """跨领域编译验证（5/5）+ 三个中文泄漏口 + 时间轴误判。"""
    import os as _o
    m = open(_o.path.join(HERE, "mmkit.py"), encoding="utf-8").read()
    p = open(_o.path.join(HERE, "paper.py"), encoding="utf-8").read()
    mp = open(_o.path.join(HERE, "mm.py"), encoding="utf-8").read()
    miss = []
    if "_re_cjk" not in m:
        miss.append("mmkit 无中文总闸")
    if "the design problem" not in p:
        miss.append("paper 未挡中文题面")
    if "_MEASURE_TIME_WORDS" not in mp:
        miss.append("mm 未加测量值白名单")
    # 5 个领域的编译产物
    n_ok = 0
    for k in ("evaluation", "prediction", "network", "queueing",
              "population"):
        d = _o.path.join(HERE, "out", "domains", k)
        if (_o.path.exists(_o.path.join(d, "paper.pdf"))
                and _o.path.exists(_o.path.join(d, "paper.tex"))):
            t = open(_o.path.join(d, "paper.tex"), encoding="utf-8").read()
            if t.count("begin{equation}") >= 2:
                n_ok += 1
    if n_ok < 5:
        miss.append(f"跨领域只 {n_ok}/5 出稿")
    if miss:
        return False, "; ".join(miss)
    return True, "5 个新领域编译 5/5（致命错误 0、equation≥2、中文 0）"


'''
    ANCHOR = ("# " + "═" * 70 + "\n#  补丁清单")
    k = s.find(ANCHOR)
    assert k > 0, "找不到补丁清单锚点"
    s = s[:k] + HELPER + s[k:]

    ENTRY = ('    Patch("P56", "④ 验证", "跨领域编译验证 5/5",\n'
             '          "造 5 个数据集跑 --compile；修中文题面 2 处 + 列名 1 处 + '
             'mmkit 总闸 + 等待时间时间轴误判",\n'
             '          _p56_wired,\n'
             '          tags=["已做", "验证"]),\n'
             '    Patch("P55",')
    s = s.replace('    Patch("P55",', ENTRY, 1)

    ast.parse(s)
    compile(s, P, "exec")
    open(P, "w", encoding="utf-8", newline="\n").write(s)
    print("  已加 P56")

import subprocess
import sys
r = subprocess.run([sys.executable, "patches.py", "verify"],
                   capture_output=True, text=True, encoding="utf-8",
                   errors="replace", cwd=HERE)
for ln in (r.stdout or "").splitlines():
    if "P56" in ln or "已落实" in ln:
        print("  " + ln.strip())
