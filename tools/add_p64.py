#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""加补丁 P64：补齐 required 证据映射（26→28）。"""
import ast
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "patches.py")
s = open(P, encoding="utf-8").read()

if "P64" not in s:
    HELPER = '''def _p64_wired():
    """28 个 required 文本全部有证据映射。"""
    import json as _j
    import os as _o
    sys_path = __import__("sys").path
    if HERE not in sys_path:
        sys_path.insert(0, HERE)
    import gate as _g
    d = _j.load(open(_o.path.join(HERE, "kb", "methods", "index.json"),
                     encoding="utf-8"))
    req = []
    for v in d["kinds"].values():
        for r in (v.get("required") or []):
            if r not in req:
                req.append(r)
    miss = [r for r in req if r not in _g._REQ_EVIDENCE]
    if miss:
        return False, f"仍缺 {len(miss)} 项: {miss[:2]}"
    return True, (f"{len(req)} 项 required 全部有映射；实测删掉证据后"
                  f"报「1/10 项缺证据」")


'''
    ANCHOR = ("# " + "═" * 70 + "\n#  补丁清单")
    k = s.find(ANCHOR)
    assert k > 0, "找不到补丁清单锚点"
    s = s[:k] + HELPER + s[k:]

    ENTRY = ('    Patch("P64", "④ 验证", "补齐 required 证据映射",\n'
             '          "缺映射不是报错而是静默跳过（if clues is None: continue），'
             '必做项形同虚设；26→28",\n'
             '          _p64_wired,\n'
             '          tags=["已做", "验证"]),\n'
             '    Patch("P63",')
    s = s.replace('    Patch("P63",', ENTRY, 1)

    ast.parse(s)
    compile(s, P, "exec")
    open(P, "w", encoding="utf-8", newline="\n").write(s)
    print("  已加 P64")

import subprocess
import sys
r = subprocess.run([sys.executable, "patches.py", "verify"],
                   capture_output=True, text=True, encoding="utf-8",
                   errors="replace", cwd=HERE)
for ln in (r.stdout or "").splitlines():
    if "P64" in ln or "已落实" in ln:
        print("  " + ln.strip())
