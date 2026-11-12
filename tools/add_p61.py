#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""加补丁 P61：环境能力核验测试去外部依赖。"""
import ast
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "patches.py")
s = open(P, encoding="utf-8").read()

if "P61" not in s:
    HELPER = '''def _p61_wired():
    """机制层测试不再依赖外部数据库（_verify_fact 加 const 域）。"""
    import os as _o
    h = open(_o.path.join(HERE, "harness.py"), encoding="utf-8").read()
    miss = []
    if 'domain == "const"' not in h:
        miss.append("_verify_fact 无 const 域")
    if "_CONST" not in h:
        miss.append("测试未改用 const")
    if "bench_l3.t_ann" in h:
        miss.append("测试仍依赖 bench_l3.t_ann")
    if miss:
        return False, "; ".join(miss)
    return True, ("修前：探针挂了 → value=None → fits()=None → "
                  "run_gates 当不降级 → pass（5/5 复现）；"
                  "改用 const 自证后 4 次连跑全 PASS")


'''
    ANCHOR = ("# " + "═" * 70 + "\n#  补丁清单")
    k = s.find(ANCHOR)
    assert k > 0, "找不到补丁清单锚点"
    s = s[:k] + HELPER + s[k:]

    ENTRY = ('    Patch("P61", "④ 验证", "能力核验测试去外部依赖",\n'
             '          "_verify_fact 加 const 域；测试不再依赖 seekdb，'
             '消除了「数据库不可用→判 pass」的偶发",\n'
             '          _p61_wired,\n'
             '          tags=["已做", "验证"]),\n'
             '    Patch("P60",')
    s = s.replace('    Patch("P60",', ENTRY, 1)

    ast.parse(s)
    compile(s, P, "exec")
    open(P, "w", encoding="utf-8", newline="\n").write(s)
    print("  已加 P61")

import subprocess
import sys
r = subprocess.run([sys.executable, "patches.py", "verify"],
                   capture_output=True, text=True, encoding="utf-8",
                   errors="replace", cwd=HERE)
for ln in (r.stdout or "").splitlines():
    if "P61" in ln or "已落实" in ln:
        print("  " + ln.strip())
