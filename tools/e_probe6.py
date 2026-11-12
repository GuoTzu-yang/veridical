#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""e_probe6.py —— 冻结表里到底冻了什么？只读。

对每道题：
  · 冻结表 items 的 path 前缀分布（eda.per_col / fit / diag ...）
  · eda 相关的项有几个，值是什么
  · 论文里那个 5.924e+04 能否在冻结表里找到 59240 附近的项
"""
import io
import json
import os
import re
import sys
from collections import Counter

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)


def main(argv):
    cfg = json.load(io.open(os.path.join(HERE, "runs.json"), encoding="utf-8"))
    names = argv[1:] or ["age_struct", "nflis", "multiobjective",
                         "icm2006c", "pop_panel"]
    for nm in names:
        fz = os.path.join(HERE, cfg[nm]["out"], "冻结数字.json")
        j = json.load(io.open(fz, encoding="utf-8"))
        items = j.get("items") or []
        pref = Counter()
        for it in items:
            p = it.get("path") or ""
            top = p.split(".")[0] if "." in p else "(top)"
            pref[top] += 1
        print("=" * 72)
        print("%-14s %d 项；顶层前缀：%s"
              % (nm, len(items), dict(pref)))
        eda = [it for it in items if it["path"].startswith("eda")]
        print("   eda 相关项 %d 个%s" % (len(eda),
              ("  样例: " + str([(e["path"], e["value"]) for e in eda[:3]]))
              if eda else ""))
        # 找 5.924e+04 → 59240 附近
        for target, label in ((59240.0, "5.924e+04"), (2519000.0, "2.519e+06")):
            near = [(it["path"], it["value"]) for it in items
                    if abs(it["value"] - target) <= 0.5 * 10]
            print("   %-10s (=%s) 冻结表内 ±5 的项: %s"
                  % (label, target, near[:3] if near else "无"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
