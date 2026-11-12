#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""example_audit.py —— 论文里用 \code{} 举的例子，是真数还是编的？

为什么需要它（第 123 轮，用户原话：「正确性和质量是底层的规矩！不可侵犯」）：

`numbers` 门只判**带小数的 token**，而且 tokenizer 会 blank 掉 `\code{...}`
的参数。两件事叠加出一个盲区：**写进 \code{} 的整数例子，既不被 numbers 判，
也查不到**。

实测事故：本轮我写「heat-sink 报告印一个编号 \code{12} 的表行、一个 \code{2019}
年的年份、一个 \code{0.05} 的显著性水平」—— heat_sink 报告里**根本没有年份列**，
`12` 是设计编号不是行号。**三个例子两个是编的**，而 gate 全绿。

本工具把盲区照亮：抽出所有 \code{...}，逐字到真实工件里搜。
它**不是门**（举例本来就可以是假想的），它是**提示器**：
  · 「在工件里找到」→ 说明这个例子有据
  · 「找不到」→ 要么是真·假想例子（那就该写明白），要么是编的（那就该改）

**它不判断「是不是正文声称的那一篇」**：同一个 `12` 可能在很多报告里都有。
找到 ≠ 对。若正文写「take one page of the heat-sink report」，你要自己确认
命中列表里有 heat_sink。本工具会把**全部**命中文件列出来，供你核。

用法：
    python tools/example_audit.py
    python tools/example_audit.py --json
"""
import glob
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "out", "final")


def codes(tex):
    r"""抽出 \code{...} / \texttt{...} / \verb|...| 里的字面量，带行号。"""
    out = []
    for i, ln in enumerate(tex.splitlines(), 1):
        for m in re.finditer(r"\\(?:code|texttt)\{([^{}]*)\}", ln):
            out.append((i, m.group(1).strip()))
        for m in re.finditer(r"\\verb\|([^|]*)\|", ln):
            out.append((i, m.group(1).strip()))
    return out


def corpus():
    """所有真实的报告与被冻结的工件，拼成一个大字符串。"""
    blobs = []
    # 23 篇模板卷 + 竞赛稿 + 本论文
    for pat in ("out/runs/*/paper.tex", "out/d2026c/paper.tex",
                "out/final/*.tex", "out/final/*.json"):
        for p in glob.glob(os.path.join(HERE, pat)):
            try:
                blobs.append((p, io.open(p, encoding="utf-8",
                                         errors="replace").read()))
            except Exception:                       # noqa: BLE001
                pass
    return blobs


def main(argv):
    tex = io.open(os.path.join(OUT, "paper.tex"), encoding="utf-8",
                  errors="replace").read()
    items = codes(tex)
    blobs = corpus()

    rows = []
    for line, lit in items:
        if not lit:
            continue
        has_digit = bool(re.search(r"\d", lit))
        where = [os.path.relpath(p, HERE) for p, s in blobs
                 if lit in s and not p.endswith("out/final/paper.tex")]
        rows.append(dict(line=line, literal=lit, has_digit=has_digit,
                         found_in=where[:3], n_found=len(where)))

    missing = [r for r in rows if r["has_digit"] and r["n_found"] == 0]

    if "--json" in argv:
        print(json.dumps(dict(rows=rows, missing=missing),
                         ensure_ascii=False, indent=1))
        return 0

    print("\\code{} 例子审计：%d 处（含数字的 %d 处）"
          % (len(rows), sum(1 for r in rows if r["has_digit"])))
    print()
    found = [r for r in rows if r["has_digit"] and r["n_found"] > 0]
    print("有据的（在**某个**工件里逐字找到）：%d" % len(found))
    print("  （找到 ≠ 对：正文若写「take one page of X」，请确认 X 在命中列表里）")
    for r in found[:14]:
        print("  L%-5d %-22s ← %d 个文件：%s"
              % (r["line"], r["literal"][:22], r["n_found"],
                 ", ".join(x.split(os.sep)[-2] if os.sep in x else x
                           for x in r["found_in"])))
    print()
    print("**查不到出处的（含数字）**：%d" % len(missing))
    for r in missing:
        print("  L%-5d %-22s  ← 工件里找不到；若是假想例子，请在正文写明"
              % (r["line"], r["literal"][:22]))
    if missing:
        print()
        print("提醒：`numbers` 门**不会**判这些 —— tokenizer 会 blank 掉")
        print("      \\code{} 的参数。本轮实测：我写了 `\\code{2019}` 当「年份」，")
        print("      而 heat_sink 报告根本没有年份列，gate 全绿。")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
