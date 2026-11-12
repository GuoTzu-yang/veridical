#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""e_probe3.py —— 三个假设的直证。

H1  论文的数据表用 %.3e 打印，四舍五入后不再等于输入表原值，
    而 E_data 判据是 round(v,6) in data_values（精确成员，无容差）。
H2  -021 / -035 这类是题号 2020-021 被分词器切成两个 token。
H3  paper.py 里存在硬编码常数（1.96 / 1000 等）直接写进正文。
"""
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)


def h1():
    print("### H1 科学计数法 vs 输入表原值")
    import pandas as pd
    p = os.path.join(HERE, "out", "data", "pop_panel.xlsx")
    xl = pd.ExcelFile(p)
    print("  sheets:", xl.sheet_names)
    df = pd.read_excel(p, sheet_name=xl.sheet_names[0])
    print("  cols:", list(df.columns)[:12], "... 共", len(df.columns))
    # 论文写 1950 & 5.924e+04 & 2.51e+05 & 0.13 & 2.519e+06
    for col in df.columns:
        s = pd.to_numeric(df[col], errors="coerce").dropna()
        if not len(s):
            continue
        near = s[(s > 5.9e4) & (s < 5.95e4)]
        if len(near):
            print("  列 %r 里 5.9e4 附近的值: %s" % (col, near.head(5).tolist()))
    # 直接看第一行
    print("  第一行前 8 列:", df.iloc[0, :8].tolist())
    return p


def h2():
    print("\n### H2 题号被切碎")
    d = os.path.join(HERE, "out", "runs", "multiobjective", "paper.tex")
    text = io.open(d, encoding="utf-8").read()
    for line in text.splitlines():
        if "-021" in line or "-043" in line:
            print("  原文:", line.strip()[:300])
            break
    import verify as V
    toks = [t for t, _ in V.extract_numbers(text)]
    print("  含 '-' 且形如 -0xx 的 token:",
          sorted({t for t in toks if re.fullmatch(r"-\d{3}", t)})[:10])


def h3():
    print("\n### H3 paper.py 里的硬编码常数")
    src = io.open(os.path.join(HERE, "paper.py"), encoding="utf-8").read()
    for pat, label in ((r"1\.96", "1.96 正态临界值"),
                       (r"\b1000\b", "1000"),
                       (r"0\.05", "0.05"),
                       (r"2\.58", "2.58")):
        for m in re.finditer(pat, src):
            ln = src[:m.start()].count("\n") + 1
            row = src.splitlines()[ln - 1].strip()
            print("  %-14s L%-5d %s" % (label, ln, row[:120]))


if __name__ == "__main__":
    h1()
    h2()
    h3()
