#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 danus 的 P5/P6 两条禁令加进 gate。

来源：dsh-danus 0.1.0 的 contracts/verifier.md

    P5. Vague gestures at "well-known" results
        「由某个 well-known / classical / standard 论证」而不给具体引用
        → critical_error
    P6. Self-contained statement check
        「在标准假设下……」却不列出那些假设
        → gap（读者无法从这句话本身判断前提）

我们实测这两条目前都干净（P5 只 1 处正面用法、P6 零命中），
加进去是为了防退化 —— 以后改论文时新写的句子不会悄悄引入。
"""
import ast
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "gate.py")
s = open(P, encoding="utf-8").read()

FUNC = '''def chk_rigor(figdir: str) -> dict:
    """数学严谨性：模糊引用与不自足陈述（借自 dsh-danus 的 P5/P6）。

    软门：命中不一定错（「而不是取自教科书相关系数」就是正面用法），
    但每一条都值得人看一眼。
    """
    tex = os.path.join(figdir, "paper.tex")
    if not os.path.exists(tex):
        return _r("rigor", SOFT, "N/A", "没有 paper.tex")
    try:
        import re as _re
        x = open(tex, encoding="utf-8").read()
        body = _re.sub(r"\\\\[a-zA-Z]+\\*?(\\[[^\\]]*\\])?(\\{[^{}]*\\})?", " ", x)
        body = _re.sub(r"\\s+", " ", body)
        p5 = [r"\\bwell[- ]known\\b", r"\\bclassical\\b",
              r"\\bstandard\\s+(argument|result|theory|method)\\b",
              r"\\bobvious(ly)?\\b", r"\\bit is known\\b", r"\\btextbook\\b"]
        p6 = [r"[Uu]nder the (standard|usual|typical)",
              r"given the (usual|standard) (assumptions|hypotheses)"]
        h5 = sum(len(_re.findall(p, body, _re.I)) for p in p5)
        h6 = sum(len(_re.findall(p, body, _re.I)) for p in p6)
        if h5 + h6 == 0:
            return _r("rigor", SOFT, "PASS", "无模糊引用、无缺口陈述")
        # 「rather than taken from a textbook」这类是正面用法，不算问题
        if _re.search(r"rather than (taken from )?(a )?textbook", body, _re.I):
            h5 = max(0, h5 - 1)
        if h5 + h6 == 0:
            return _r("rigor", SOFT, "PASS", "只有正面用法")
        return _r("rigor", SOFT, "WARN",
                  f"P5 {h5} 处 / P6 {h6} 处，需人看")
    except Exception as e:                      # noqa: BLE001
        return _r("rigor", SOFT, "N/A", f"{type(e).__name__}: {e}")


'''

if "def chk_rigor(" not in s:
    k = s.find("def run_all(")
    s = s[:k] + FUNC + s[k:]
    s = s.replace("        chk_refs(figdir),",
                  "        chk_refs(figdir),\n        chk_rigor(figdir),", 1)
    ast.parse(s)
    compile(s, P, "exec")
    open(P, "w", encoding="utf-8", newline="\n").write(s)
    print("  gate 加了 rigor（P5/P6）")

import subprocess
import sys
r = subprocess.run([sys.executable, "gate.py", "out/fig"],
                   capture_output=True, text=True, encoding="utf-8",
                   errors="replace", cwd=HERE)
for ln in (r.stdout or "").splitlines():
    if "rigor" in ln or "质量门" in ln:
        print("  " + ln.strip())
