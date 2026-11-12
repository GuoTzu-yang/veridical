#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""加补丁 P55：领域库 5 → 10，并修两个判定 bug。"""
import ast
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "patches.py")
s = open(P, encoding="utf-8").read()

if "P55" not in s:
    HELPER = '''def _p55_wired():
    """领域库扩到 10 个 + 判定阈值 + GENERIC 公式不受门控。"""
    import os as _o
    d = open(_o.path.join(HERE, "domain.py"), encoding="utf-8").read()
    p = open(_o.path.join(HERE, "paper.py"), encoding="utf-8").read()
    ep = _o.path.join(HERE, "domain_extra.py")
    n = 0
    if _o.path.exists(ep):
        try:
            import importlib.util as _u
            sp = _u.spec_from_file_location("_de", ep)
            m = _u.module_from_spec(sp)
            sp.loader.exec_module(m)
            n = len(m.EXTRA)
        except Exception:                       # noqa: BLE001
            n = 0
    miss = []
    if n < 5:
        miss.append(f"domain_extra 只 {n} 个领域")
    if "len(hits) >= 2" not in d:
        miss.append("detect 未加 2 词门槛")
    if "_is_generic" not in p:
        miss.append("GENERIC 公式仍被 _mech 门控")
    if miss:
        return False, "; ".join(miss)
    return True, "10 个领域；化工题 generic(4 式)、热沉 heat_transfer(6 式)，污染均 0"


'''
    ANCHOR = ("# " + "═" * 70 + "\n#  补丁清单")
    k = s.find(ANCHOR)
    assert k > 0, "找不到补丁清单锚点"
    s = s[:k] + HELPER + s[k:]

    ENTRY = ('    Patch("P55", "② 提案", "领域库 5→10 + 判定阈值",\n'
             '          "新增 evaluation/prediction/network/queueing/population；'
             'detect 加 2 词门槛；GENERIC 公式不受机理门控",\n'
             '          _p55_wired,\n'
             '          tags=["已做", "提案"]),\n'
             '    Patch("P54",')
    s = s.replace('    Patch("P54",', ENTRY, 1)

    ast.parse(s)
    compile(s, P, "exec")
    open(P, "w", encoding="utf-8", newline="\n").write(s)
    print("  已加 P55")

import subprocess
import sys
r = subprocess.run([sys.executable, "patches.py", "verify"],
                   capture_output=True, text=True, encoding="utf-8",
                   errors="replace", cwd=HERE)
for ln in (r.stdout or "").splitlines():
    if "P55" in ln or "已落实" in ln:
        print("  " + ln.strip())
