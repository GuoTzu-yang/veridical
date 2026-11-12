#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""给 gate 加「裸 % 扫描」与「引用配对」两条硬门。

为什么要加
----------
① 裸 %
   `%` 在 LaTeX 里是注释符。Python 的 `:.1%` 格式符会输出裸 %，
   于是「a shift of -1.7%, costs what the tolerance table does not
   show: ...」整段被吞，PDF 里断在 "-1.7" 就没了（实测第 19 页）。
   13 项 gate 里原来没有一项能发现这种「半句话消失」。

② \ref / \label 配对
   AI 声明里 \ref{sec:selection} 指向不存在的 label，编译成
   "Section??was"（实测第 25 页）。评委看到 ?? 会直接判定
   「连编译检查都没做」。

两条都是正则一行能查的，之前一直没查。
"""
import ast
import os
import re

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "gate.py")
s = open(P, encoding="utf-8").read()

FUNC = '''def chk_bare_pct(figdir: str) -> dict:
    """扫裸 %：它会把同一行后面的内容变成注释。

    排除 \\% 与 \\\\%（正确写法），以及整行注释。
    """
    tex = os.path.join(figdir, "paper.tex")
    if not os.path.exists(tex):
        return _r("bare_pct", HARD, "N/A", "没有 paper.tex")
    try:
        bad = []
        for i, ln in enumerate(open(tex, encoding="utf-8"), 1):
            body = ln.rstrip("\\n")
            if body.lstrip().startswith("%"):
                continue                        # 整行注释，正常
            for m in re.finditer(r"%", body):
                j = m.start()
                # 往前数反斜杠：奇数个说明已转义
                k = j - 1
                nb = 0
                while k >= 0 and body[k] == "\\\\":
                    nb += 1
                    k -= 1
                if nb % 2 == 0:
                    bad.append((i, body[max(0, j - 40):j + 30]))
        if bad:
            i, seg = bad[0]
            return _r("bare_pct", HARD, "FAIL",
                      f"{len(bad)} 处裸 %（首处 L{i}: ...{seg}...）")
        return _r("bare_pct", HARD, "PASS", "没有裸 %")
    except Exception as e:                      # noqa: BLE001
        return _r("bare_pct", HARD, "N/A", f"{type(e).__name__}: {e}")


def chk_refs(figdir: str) -> dict:
    """\\ref 指向的 label 是否都存在。不存在会编译成 ??。"""
    tex = os.path.join(figdir, "paper.tex")
    if not os.path.exists(tex):
        return _r("refs", HARD, "N/A", "没有 paper.tex")
    try:
        x = open(tex, encoding="utf-8").read()
        refs = set(re.findall(r"\\\\ref\\{([^}]+)\\}", x))
        labs = set(re.findall(r"\\\\label\\{([^}]+)\\}", x))
        miss = sorted(refs - labs)
        if miss:
            return _r("refs", HARD, "FAIL",
                      f"{len(miss)} 个 \\\\ref 无对应 \\\\label: {miss[:3]}")
        return _r("refs", HARD, "PASS",
                  f"{len(refs)} 个引用全部配平")
    except Exception as e:                      # noqa: BLE001
        return _r("refs", HARD, "N/A", f"{type(e).__name__}: {e}")


'''

if "def chk_bare_pct(" not in s:
    k = s.find("def run_all(")
    s = s[:k] + FUNC + s[k:]
    s = s.replace("        chk_abs_page(figdir),",
                  "        chk_abs_page(figdir),\n"
                  "        chk_bare_pct(figdir),\n"
                  "        chk_refs(figdir),", 1)
    ast.parse(s)
    compile(s, P, "exec")
    open(P, "w", encoding="utf-8", newline="\n").write(s)
    print("  ① gate 加了 bare_pct / refs 两条硬门")
else:
    print("  已有")

import subprocess
import sys
r = subprocess.run([sys.executable, "gate.py", "out/fig"],
                   capture_output=True, text=True, encoding="utf-8",
                   errors="replace", cwd=HERE)
for ln in (r.stdout or "").splitlines():
    if "bare_pct" in ln or "refs" in ln or "质量门" in ln:
        print("  " + ln.strip())
