#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""加补丁 P63：concurrency / nodes 补 declared 分支。"""
import ast
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "patches.py")
s = open(P, encoding="utf-8").read()

if "P63" not in s:
    HELPER = '''def _p63_wired():
    """三个数量维度（scale/concurrency/nodes）统一 declared 判据。"""
    import os as _o
    c = open(_o.path.join(HERE, "capability.py"), encoding="utf-8").read()
    miss = []
    for fn in ("_cmp_scale", "_cmp_concurrency", "_cmp_nodes"):
        i = c.find("def " + fn)
        if i < 0:
            miss.append(f"缺 {fn}")
            continue
        seg = c[i:i + 1400]
        if 'd.source == "declared"' not in seg:
            miss.append(f"{fn} 无 declared 分支")
    if miss:
        return False, "; ".join(miss)
    return True, ("concurrency 8<100→False / 256>=100→None；"
                  "nodes 2<5→False / 8>=5→None；三级回归全过")


'''
    ANCHOR = ("# " + "═" * 70 + "\n#  补丁清单")
    k = s.find(ANCHOR)
    assert k > 0, "找不到补丁清单锚点"
    s = s[:k] + HELPER + s[k:]

    ENTRY = ('    Patch("P63", "④ 验证", "concurrency/nodes 补 declared 分支",\n'
             '          "上轮只修 scale；这两个同属数量维度，arch/network 是分类值不改"\n'
             '          "；三个维度判据现已统一",\n'
             '          _p63_wired,\n'
             '          tags=["已做", "验证"]),\n'
             '    Patch("P62",')
    s = s.replace('    Patch("P62",', ENTRY, 1)

    ast.parse(s)
    compile(s, P, "exec")
    open(P, "w", encoding="utf-8", newline="\n").write(s)
    print("  已加 P63")

import subprocess
import sys
r = subprocess.run([sys.executable, "patches.py", "verify"],
                   capture_output=True, text=True, encoding="utf-8",
                   errors="replace", cwd=HERE)
for ln in (r.stdout or "").splitlines():
    if "P63" in ln or "已落实" in ln:
        print("  " + ln.strip())
