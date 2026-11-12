#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""领域公式编译回归：只编译公式片段，不跑整条流水线。

为什么单独做
------------
完整跑 5 次 `mmkit run --compile` 每次几十秒，放进 run_all 会让回归
从几秒变成几分钟。但公式本身能不能渲染是**独立的、更根本的问题** ——
`\\bigl\\| r_i - r^\\pm \\bigr\\|_2`、`\\begin{cases}`、`\\mathcal{R}_0`、
`\\tfrac{1}{N}` 这些构造出错时，整条流水线都要重跑才发现。

所以这里只做一件事：把每个领域的 equation + extra_eq 包进最小
document，pdflatex 编一次。快（每个 1-2 秒），且直接指向出错的那条公式。
"""
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import domain  # noqa: E402

TEMPLATE = r"""\documentclass[11pt]{article}
\usepackage{amsmath,amssymb}
\usepackage[T1]{fontenc}
\pagestyle{empty}
\begin{document}
%s
\end{document}
"""


def _find_pdflatex():
    for c in ("pdflatex", "pdflatex.exe"):
        p = shutil.which(c)
        if p:
            return p
    # 本机 MiKTeX 装在 %LOCALAPPDATA%\Programs\MiKTeX —— 不在 PATH 里。
    # 只查 C:\Program Files 会漏（实测漏了，测试变 SKIP 而假通过）。
    local = os.environ.get("LOCALAPPDATA", "")
    cands = [
        os.path.join(local, "Programs", "MiKTeX", "miktex", "bin", "x64",
                     "pdflatex.exe"),
        os.path.join(os.environ.get("APPDATA", ""), "MiKTeX", "miktex",
                     "bin", "x64", "pdflatex.exe"),
        r"C:\Program Files\MiKTeX\miktex\bin\x64\pdflatex.exe",
        r"C:\texlive\2024\bin\windows\pdflatex.exe",
        r"C:\texlive\2023\bin\windows\pdflatex.exe",
    ]
    for c in cands:
        if c and os.path.exists(c):
            return c
    return None


def check(dom_key, pdftex):
    d = domain.DOMAINS[dom_key]
    eq = d.get("equation") or ""
    eq2 = d.get("extra_eq") or ""
    if not eq:
        return False, "没有 equation 字段"
    body = eq + "\n" + eq2
    with tempfile.TemporaryDirectory() as td:
        tex = os.path.join(td, "t.tex")
        open(tex, "w", encoding="utf-8").write(TEMPLATE % body)
        r = subprocess.run(
            [pdftex, "-interaction=nonstopmode", "-halt-on-error",
             "t.tex"],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", cwd=td, timeout=90)
        if r.returncode == 0 and os.path.exists(
                os.path.join(td, "t.pdf")):
            return True, f"{len(body)} 字符"
        log = os.path.join(td, "t.log")
        first = ""
        if os.path.exists(log):
            txt = open(log, encoding="utf-8", errors="replace").read()
            for ln in txt.splitlines():
                if ln.startswith("!"):
                    first = ln[:80]
                    break
        return False, first or (r.stdout or "")[-120:]


def main():
    pdftex = _find_pdflatex()
    if not pdftex:
        # 退出码 0 会让 run_all 显示 OK —— 那是假通过。找不到编译器
        # 时这条测试**什么都没测**，必须显式说出来，退出码用 2。
        print("  [SKIP] 找不到 pdflatex —— 这条测试没有执行任何检查")
        print("         （不是通过：领域公式的渲染未被验证）")
        return 2
    bad = n = 0
    for k in sorted(domain.DOMAINS):
        n += 1
        ok, detail = check(k, pdftex)
        print(f"  [{'PASS' if ok else 'FAIL'}] {k:<16}{detail}")
        if not ok:
            bad += 1
    print()
    print(f"{'ALL PASS' if bad == 0 else 'FAILED'}  {n - bad}/{n}")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
