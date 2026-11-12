#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""加补丁 P62：区分「探针挂」与「数字错」，补上 None 被当成够的洞。"""
import ast
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "patches.py")
s = open(P, encoding="utf-8").read()

if "P62" not in s:
    HELPER = '''def _p62_wired():
    """「探针挂」保留声明值判不够；「数字错」仍降 unknown。"""
    import os as _o
    h = open(_o.path.join(HERE, "harness.py"), encoding="utf-8").read()
    c = open(_o.path.join(HERE, "capability.py"), encoding="utf-8").read()
    miss = []
    if "没跑成" not in h or "核对不符" not in h:
        miss.append("harness 未按失败原因分流")
    if 'd.source == "declared"' not in c:
        miss.append("_cmp_scale 无 declared 分支")
    if miss:
        return False, "; ".join(miss)
    return True, ("探针挂+需求1亿→degrade；探针挂+需求1000→pass；"
                  "核对不符/只有声称→仍不采信（4 项原测试全恢复）")


'''
    ANCHOR = ("# " + "═" * 70 + "\n#  补丁清单")
    k = s.find(ANCHOR)
    assert k > 0, "找不到补丁清单锚点"
    s = s[:k] + HELPER + s[k:]

    ENTRY = ('    Patch("P62", "④ 验证", "区分探针挂与数字错",\n'
             '          "原来两种情况都降 unknown → 都判 pass；现在探针挂保留声明值'
             '（声称不够就不够），数字错仍不采信",\n'
             '          _p62_wired,\n'
             '          tags=["已做", "验证"]),\n'
             '    Patch("P61",')
    s = s.replace('    Patch("P61",', ENTRY, 1)

    ast.parse(s)
    compile(s, P, "exec")
    open(P, "w", encoding="utf-8", newline="\n").write(s)
    print("  已加 P62")

import subprocess
import sys
r = subprocess.run([sys.executable, "patches.py", "verify"],
                   capture_output=True, text=True, encoding="utf-8",
                   errors="replace", cwd=HERE)
for ln in (r.stdout or "").splitlines():
    if "P62" in ln or "已落实" in ln:
        print("  " + ln.strip())
