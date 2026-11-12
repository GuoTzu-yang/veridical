#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一次补齐剩余四个缺口（先写完+检查，最后才编译）。

缺口（对照表与题目要求）：
  A 优点只有 2 条，要求 >=3
  B 参数来源没有标注（题目/数据/文献）
  C 引言没有文献综述，且 \cite 只出现在正文别处
  D 没有「影响规律」小结 —— 问题 1 明确要求分析三因子对三指标的影响规律

LaTeX 片段放在独立的 .txt 里读入，避免在多层字符串里数反斜杠。
"""
import ast
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T = os.path.join(HERE, "tools")
P = os.path.join(HERE, "paper.py")
s = open(P, encoding="utf-8").read()


def frag(name):
    return open(os.path.join(T, name), encoding="utf-8").read().strip()


def as_para(text, indent):
    """把一个多行片段变成论文里的一行 _para(...) 调用。"""
    pad = " " * indent
    lines = [x.strip() for x in text.splitlines() if x.strip()]
    out = []
    for i, ln in enumerate(lines):
        pre = "        " if i == 0 else "        "
        tail = "" if i < len(lines) - 1 else ""
        out.append(f'{pre}f"{ln} "')
    body = "\n".join(out)
    return f"{pad}_para(\n{body})"


n = 0

# ══ A 优点补第 3 条 ══
A = ('        L.append(\n'
     '            r"  \\item Each indicator is modelled separately rather than "\n'
     '            r"forced into one specification, so the functional form was "\n'
     '            r"decided by cross-validated error instead of convenience, and "\n'
     '            r"a design that cannot be predicted precisely is reported as "\n'
     '            r"such rather than given a number it does not support.")\n')
if "Each indicator is modelled separately" not in s:
    # 插到 Strengths 小节结束前
    m = None
    for key in ('L += [r"\\subsection{Limitations}"',
                'L.append(r"\\subsection{Limitations}"'):
        if key in s:
            m = key
            break
    if m:
        i = s.find(m)
        s = s[:i] + A + s[i:]
        n += 1
        print("A 优点第 3 条已加")

# ══ B 参数来源标注 ══
if "Where the numbers come from" not in s:
    fragB = as_para(frag("frag_sources.txt"), 4)
    B = (fragB.replace("    _para(\n", "    L.append(r\"\\subsection{Where the "
                        "numbers come from}\")\n    _para(\n", 1) + "\n")
    anchor = '    L += [r"\\subsection{Notation}"'
    if anchor in s:
        s = s.replace(anchor, B + anchor, 1)
        n += 1
        print("B 参数来源标注已加")

# ══ C 引言文献综述 ══
if "Previous work on this class of problem" not in s:
    fragC = as_para(frag("frag_survey.txt"), 4)
    # 插在 Introduction 节内的第一段之后
    anchor = '    L.append(r"\\section{Introduction}"'
    if anchor in s:
        i = s.find(anchor)
        # 找到该 section 之后第一个 L.append("") 之前
        j = s.find("\n    L.append", i + len(anchor))
        if j > 0:
            s = s[:j] + "\n" + fragC + s[j:]
            n += 1
            print("C 引言文献综述已加")

# ══ D 影响规律小结 ══
if "The ordering of the factors" not in s:
    fragD = as_para(frag("frag_influence.txt"), 4)
    D = (fragD.replace("    _para(\n", "    L.append(r\"\\subsection{The ordering "
                        "of the factors}\")\n    _para(\n", 1) + "\n")
    anchor = ('    L += [r"\\section{Problem 2: Design selection under '
              'constraints}", ""]')
    if anchor in s:
        s = s.replace(anchor, D + anchor, 1)
        n += 1
        print("D 影响规律小结已加")

ast.parse(s)
compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print(f"  改了 {n} 处，已写入 paper.py（{len(s.splitlines())} 行）")
