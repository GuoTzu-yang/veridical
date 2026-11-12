#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""rt_near.py —— 红队只读复现（E 项，第二探针）：给每个未溯源 token 找"最近的疑似的源"。

只读。输出：
  · 冻结表里 |f-v| 相对误差最小的 3 条（path / value / relerr）
  · 输入表 data_values 里是否有舍入相等的值
  · 若把 dec 按"有效数字"重算（科学计数法按尾数量级），_match_written 是否通过
"""
from __future__ import annotations

import io
import json
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import verify as V      # noqa: E402
import freeze as F      # noqa: E402
import untraced as U    # noqa: E402

TASKS = ["age_struct", "nflis", "multiobjective", "icm2006c", "pop_panel"]


def eff_decimals(tok: str):
    """按书写形态返回 (小数位, 十进制容差)。

    科学计数法：a.bcdE+xx → 尾数有 k 位小数、指数 e → 容差 = 0.5*10^(e-k)。
    普通写法：容差 = 0.5*10^-k。
    """
    t = tok.strip()
    m = re.fullmatch(r"-?(\d+)(?:\.(\d+))?(?:[eE]([+-]?\d+))?", t)
    if not m:
        return None, None
    frac = m.group(2) or ""
    exp = int(m.group(3) or 0)
    k = len(frac)
    tol = 0.5 * (10.0 ** (exp - k))
    return k, tol


def near_frozen(v: float, items, k=3):
    cand = []
    for it in items:
        f = it["value"]
        d = abs(f - v)
        rel = d / max(abs(v), 1e-12)
        cand.append((rel, d, it["path"], f))
    cand.sort(key=lambda x: (x[0], x[1]))
    return cand[:k]


def main(argv=None) -> int:
    names = argv[1:] or TASKS
    data = json.load(io.open(os.path.join(ROOT, "out", "_rt_E_numbers.json"),
                            encoding="utf-8"))
    for name in names:
        res = data[name]
        d = res["dir"]
        frozen = json.load(io.open(os.path.join(d, "冻结数字.json"),
                                  encoding="utf-8"))
        items = frozen.get("items", [])
        df = U.find_data_file(d)
        dv = U.data_values_of(df) if df else set()
        print("=" * 78)
        print("%s  未溯源 %d 个" % (name, len(res["untraced"])))
        for x in res["untraced"]:
            tok, v = x["token"], x["value"]
            k, tol = eff_decimals(tok)
            print("\n  token=%-13s v=%-14.6g 书写小数位=%s 有效容差=%.3g"
                  % (tok, v, k, tol if tol else float("nan")))
            # ① 冻结表最近邻
            for rel, dd, path, f in near_frozen(v, items):
                ok_now = F._match_written(v, F._decimals(tok), [f])
                ok_eff = abs(v - f) <= tol if tol else False
                print("     frozen   %-46s f=%-16.8g rel=%.2e | "
                      "当前判据=%s 有效容差判=%s"
                      % (path, f, rel, ok_now, ok_eff))
            # ② 输入表
            hit = None
            for scale in (1.0, 100.0, 0.01):
                key = round(v * scale, 6)
                if key in dv:
                    hit = (scale, key)
                    break
            print("     in_data  %s" % (("scale=%s key=%s" % hit) if hit
                                        else "否（%d 个输入表值中无匹配）" % len(dv)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
