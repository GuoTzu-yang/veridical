#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gate 新增 chk_claims：「声明-证据」节的诚实性检查。

判据
----
缺这一节                → FAIL   （没有诚实性声明）
有节但「无支撑」为 0 条  → WARN   （要么真的完整，要么没检查）
有节且有 >=1 条无支撑    → PASS

为什么「0 条无支撑」值得警告
---------------------------
一篇论文如果声称每条声明都有证据，比承认三处没有更可疑。
后者说明作者真的逐条查过；前者通常意味着没查。
这和 warn-before-trust 是同一个道理：**敢说不足，才可信**。
"""
import ast
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "gate.py")
s = open(P, encoding="utf-8").read()

FUNC = '''

def chk_claims(figdir: str) -> dict:
    """「声明-证据」节：声称全有证据，比承认几处没有更可疑。"""
    p = os.path.join(figdir, "paper.tex")
    if not os.path.exists(p):
        return _r("claims", SOFT, "N/A", "没有 paper.tex")
    t = open(p, encoding="utf-8").read()
    if "What each claim rests on" not in t:
        return _r("claims", SOFT, "FAIL",
                  "缺「声明-证据」节 —— 没有任何地方说明哪些结论证据不足")
    n_sup = t.count("Evidence:")
    n_uns = t.count("Not supported")
    if n_sup == 0:
        return _r("claims", SOFT, "FAIL", "该节里一条声明都没列")
    if n_uns == 0:
        return _r("claims", SOFT, "WARN",
                  f"{n_sup} 条全部声称有证据 —— 要么真的完整，要么没逐条查")
    return _r("claims", SOFT, "PASS",
              f"{n_sup} 条有证据 / {n_uns} 条明确无支撑")


'''

if "chk_claims" not in s:
    # 插在 run_all 之前
    k = s.find("def run_all(")
    assert k > 0, "找不到 run_all"
    s = s[:k] + FUNC + s[k:]

    # 加进 checks 列表
    ANCHOR = "        chk_falsify(figdir),"
    if ANCHOR not in s:
        ANCHOR = "        chk_aitaste(figdir),"
    assert ANCHOR in s, "找不到 checks 列表锚点"
    s = s.replace(ANCHOR, ANCHOR + "\n        chk_claims(figdir),", 1)

    # 归入衰减项
    WANCHOR = '    "falsify": "decay",'
    if WANCHOR in s:
        s = s.replace(WANCHOR, WANCHOR + '\n    "claims": "decay",', 1)
    else:
        WANCHOR2 = '    "aitaste": "decay",'
        assert WANCHOR2 in s, "找不到 GATE_WEIGHT 锚点"
        s = s.replace(WANCHOR2, WANCHOR2 + '\n    "claims": "decay",', 1)

    ast.parse(s)
    compile(s, P, "exec")
    open(P, "w", encoding="utf-8", newline="\n").write(s)
    print("  已加 chk_claims 并归入衰减项")

import subprocess
import sys
r = subprocess.run([sys.executable, "gate.py", "out/fig"],
                   capture_output=True, text=True, encoding="utf-8",
                   errors="replace", cwd=HERE)
for ln in (r.stdout or "").splitlines():
    if "claims" in ln or "质量门" in ln or "综合风险" in ln:
        print("  " + ln.strip())
