#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一次补齐剩余四个缺口（先写完+检查，最后才编译）。

缺口：
  A 优点只有 2 条，要求 >=3
  B 参数来源没有标注
  C 引言没有文献综述（引言里 \cite 出现 0 次）
  D 没有「影响规律」小结

锚点（实测写法）：
  Strengths 末尾 → '    L.append(r"\\subsection{Limitations}")'
  Notation 前  → '    L.append(r"\\subsection{Notation}")'
  Introduction→ '    L += [r"\\section{Introduction}", ""]'
"""
import ast
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T = os.path.join(HERE, "tools")
P = os.path.join(HERE, "paper.py")
s = open(P, encoding="utf-8").read()
BS = chr(92)


def frag(name):
    return open(os.path.join(T, name), encoding="utf-8").read().strip()


def as_para(text, indent):
    """多行片段 → 一行 _para(...) 调用。行尾留空格，段落不断开。"""
    pad = " " * indent
    # 片段里的 \subsection{...} 由 head 单独提供，不能再当正文包成
    # f-string —— 否则 {Where the numbers...} 会被当成插值而语法错。
    lines = [x.strip() for x in text.splitlines()
             if x.strip() and not x.strip().startswith(chr(92) + "subsection")]
    out = []
    for ln in lines:
        out.append(f'{pad}    f"{ln} "')
    return f"{pad}_para(\n" + "\n".join(out) + ")"


n = 0

# ══ A 优点补第 3 条 ══
if "Each indicator is modelled separately" not in s:
    A = ('        L.append(\n'
         '            r"  \\item Each indicator is modelled separately rather than "\n'
         '            r"forced into one specification, so the functional form was "\n'
         '            r"decided by cross-validated error instead of convenience, and "\n'
         '            r"a design that cannot be predicted precisely is reported as "\n'
         '            r"such rather than given a number it does not support.")\n')
    anchor = '    L.append(r"' + BS + 'subsection{Limitations}")'
    if anchor in s:
        i = s.find(anchor)
        s = s[:i] + A + s[i:]
        n += 1
        print("A 优点第 3 条已加")

# ══ B 参数来源标注 ══
if "Where the numbers come from" not in s:
    head = ('    L.append(r"' + BS + "subsection{Where the numbers come "
            'from}")\n')
    body = as_para(frag("frag_sources.txt"), 4) + "\n"
    anchor = '    L.append(r"' + BS + 'subsection{Notation}")'
    if anchor in s:
        i = s.find(anchor)
        s = s[:i] + head + body + s[i:]
        n += 1
        print("B 参数来源标注已加")

# ══ C 引言文献综述 ══
if "Previous work on this class of problem" not in s:
    body = as_para(frag("frag_survey.txt"), 4) + "\n"
    anchor = '    L += [r"' + BS + 'section{Introduction}", ""]'
    if anchor in s:
        i = s.find(anchor)
        # 插在该 section 之后第一段之前
        j = s.find("\n    L.append", i + len(anchor))
        if j > 0:
            s = s[:j] + "\n" + body + s[j:]
            n += 1
            print("C 引言文献综述已加")

# ══ D 影响规律小结 ══
if "The ordering of the factors" not in s:
    head = ('    L.append(r"' + BS + "subsection{The ordering of the "
            'factors}")\n')
    body = as_para(frag("frag_influence.txt"), 4) + "\n"
    anchor = ('    L += [r"' + BS + 'section{Problem 2: Design selection '
              'under constraints}", ""]')
    if anchor in s:
        s = s.replace(anchor, body + anchor, 1)
        n += 1
        print("D 影响规律小结已加")

ast.parse(s)
compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print(f"  改了 {n} 处，已写入 paper.py（{len(s.splitlines())} 行）")
