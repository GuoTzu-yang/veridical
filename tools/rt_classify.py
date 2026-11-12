#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""rt_classify.py —— 只读：把 121 轮快照的未溯源 token 归类。

输入：out/_rt_E_numbers.txt（旧判据 + 旧产物，由 tools/rt_numbers.py 在
      2026-11-11 03:33 生成；该文本里每个 token 带原始行号与原文行）。

分类规则**按 token 出现行的语义文本**判定，优先序固定（先特例后一般）：

  K_formula   行含 "asymptotic critical"        → 方法/公式常数
  F_falsify   行含 "clearest violation"          → falsify 滑窗区间与局部相关
  C_cond      行含 "condition number"            → 标准化条件数
  T_tradeoff  行含 "remedy has a price"          → q5 取舍（from/to/shift）
  W_front     行含 "Worked example"              → 前沿示例差值
  G_gap       行含 "percent worse"               → 曲率对比的比值
  X_cross     行含 "reaches zero"                → 直线过零点
  S_table     行含 "&"                           → 表格里的统计量/坐标（.4g/.5g）

用法：python tools/rt_classify.py [txt]
"""
from __future__ import annotations

import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

RULES = [
    ("K_formula", "asymptotic critical"),
    ("F_falsify", "clearest violation"),
    ("C_cond", "condition number"),
    ("T_tradeoff", "remedy has a price"),
    ("W_front", "Worked example"),
    ("G_gap", "generalises best"),
    ("X_cross", "reaches zero"),
    ("S_table", "&"),
]


def parse(path):
    """→ [{task, token, dec, lines:[(n, text)]}]"""
    rows = []
    task = None
    cur = None
    for raw in io.open(path, encoding="utf-8").read().splitlines():
        m = re.match(r"^(\w+)\s+deliverable=", raw)
        if m:
            task = m.group(1)
            continue
        m = re.match(r"^\s{3}(\S+)\s+dec=(-?\d+)$", raw)
        if m:
            cur = dict(task=task, token=m.group(1), dec=int(m.group(2)), lines=[])
            rows.append(cur)
            continue
        m = re.match(r"^\s{8}L(\d+)\s+(.*)$", raw)
        if m and cur is not None:
            cur["lines"].append((int(m.group(1)), m.group(2)))
    return rows


def classify(row):
    texts = [t for _n, t in row["lines"]]
    for label, needle in RULES:
        if any(needle in t for t in texts):
            return label
    return "U_unknown"


def main(argv=None) -> int:
    path = argv[1] if len(argv) > 1 else os.path.join(
        ROOT, "out", "_rt_E_numbers.txt")
    rows = parse(path)
    print("解析 %s" % path)
    print("token 总数 = %d" % len(rows))
    by = {}
    for r in rows:
        r["cls"] = classify(r)
        by.setdefault(r["cls"], []).append(r)
    print("\n按类计数：")
    for k, v in sorted(by.items(), key=lambda kv: -len(kv[1])):
        print("  %-11s %3d" % (k, len(v)))
    print("\n按题 × 类：")
    tasks = []
    for r in rows:
        if r["task"] not in tasks:
            tasks.append(r["task"])
    for t in tasks:
        cnt = {}
        for r in rows:
            if r["task"] == t:
                cnt[r["cls"]] = cnt.get(r["cls"], 0) + 1
        print("  %-16s %s" % (t, ", ".join("%s=%d" % (k, cnt[k])
                                           for k in sorted(cnt))))
    print("\n全表（题 / token / 类 / 首个出现行）：")
    for r in rows:
        ln = r["lines"][0][0] if r["lines"] else 0
        print("  %-16s %-14s %-11s L%d" % (r["task"], r["token"], r["cls"], ln))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
