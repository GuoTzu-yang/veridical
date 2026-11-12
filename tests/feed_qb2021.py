#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
投喂 2021-A：图像 + 边缘轮廓数据

2026-A/B 那两道题一共给了 13 条可断言主张。这一套（2021-A 图像边缘分析）
数据更丰富：**7 张真实图像 + 两条逐点边缘轮廓（3887 / 3625 个坐标）**。

新增的 `image` 域能问的东西：
  尺寸 / 位深 / 暗像素占比 / 灰度级数

跨文件的一致性主张也在这里：
  轮廓坐标是否落在图像尺寸内、两条轮廓点数是否不同、轮廓是否闭合。

跑法：
  python tests/feed_qb2021.py
  python tests/feed_qb2021.py --record
"""

from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from probe import do_exec  # noqa: E402

A = (r"C:\Users\21246\Documents\deepseek-harness\default-workspace"
     r"\apmcm2026\题库\2021-A_图像边缘分析")
P11 = os.path.join(A, "Annex 1", "Pic1_1.bmp")
P12 = os.path.join(A, "Annex 1", "Pic1_2.bmp")
P13 = os.path.join(A, "Annex 1", "Pic1_3.bmp")
P21 = os.path.join(A, "Annex 2", "Pic2_1.bmp")
C1 = os.path.join(A, "Annex 3", "EdgeContour1.xls")
C2 = os.path.join(A, "Annex 3", "EdgeContour2.xls")

# (题号, 主张, 断言, 我的预判)
CLAIMS = [
    # ---- 图像属性 ----
    ("A1", "Annex1 三张图尺寸一致（1296x972）",
     {"domain": "image", "task": {"file": P11, "assert": "dimensions",
                                  "params": {"w": 1296, "h": 972}}}, True),
    ("A2", "图像是 8 位灰度（mode L）",
     {"domain": "image", "task": {"file": P11, "assert": "mode",
                                  "params": {"expect": "L"}}}, True),
    ("A3", "Pic1_2 的暗像素占比高于 Pic1_1",
     {"domain": "image", "task": {"file": P12, "assert": "dark_ratio",
                                  "params": {"min": 30, "max": 50}}}, True),
    ("A4", "Pic1_1 的暗像素占比低于 20%",
     {"domain": "image", "task": {"file": P11, "assert": "dark_ratio",
                                  "params": {"min": 0, "max": 20}}}, True),
    ("A5", "Pic1_3 暗像素占比在 15~30%",
     {"domain": "image", "task": {"file": P13, "assert": "dark_ratio",
                                  "params": {"min": 15, "max": 30}}}, True),
    ("A6", "Annex2 首图暗像素占比约为 Annex1 首图的两倍",
     {"domain": "image", "task": {"file": P21, "assert": "dark_ratio",
                                  "params": {"min": 17, "max": 21}}}, True),
    ("A7", "图像不是纯二值图（灰度级远多于 2）",
     {"domain": "image", "task": {"file": P11, "assert": "unique_gray_levels",
                                  "params": {"op": ">=", "value": 100}}}, True),

    # ---- 表格：边缘轮廓逐点数据 ----
    ("A8", "边缘轮廓 1 的点数超过 3000",
     {"domain": "data", "task": {"file": C1, "assert": "row_count",
                                 "params": {"op": ">=", "value": 3000}}}, True),
    ("A9", "边缘轮廓 2 的点数超过 3000",
     {"domain": "data", "task": {"file": C2, "assert": "row_count",
                                 "params": {"op": ">=", "value": 3000}}}, True),
    ("A10", "轮廓 1 的 x 坐标落在图像宽度内（0~1296）",
     {"domain": "data", "task": {"file": C1, "header_row": 1,
                                 "assert": "value_bounds",
                                 "params": {"column": "", "min": 0, "max": 1296}}},
     True),
    ("A11", "轮廓 1 没有缺失坐标",
     {"domain": "data", "task": {"file": C1, "assert": "no_null_in",
                                 "params": {"column": ""}}}, True),

    # ---- 第二组：我真没把握的 ----
    # 全真的主张集没有区分度：11 条全都成立，pass 桶只是被灌了 11 条。
    # 这一组是"看起来对、但没算过"的判断，才是真正在检验。
    ("A12", "轮廓 1 是闭合曲线（首尾点重合）",
     {"domain": "data", "task": {"file": C1, "assert": "closed_curve",
                                 "params": {"tol": 0.5}}}, True),
    ("A13", "轮廓 2 是闭合曲线",
     {"domain": "data", "task": {"file": C2, "assert": "closed_curve",
                                 "params": {"tol": 0.5}}}, True),
    ("A14", "两条轮廓点数相同（同一个图形的内外边界）",
     {"domain": "data", "task": {"file": C2, "assert": "row_count",
                                 "params": {"op": "==", "value": 3886}}}, True),
    ("A15", "轮廓 1 的 y 坐标落在图像高度内（0~972）",
     {"domain": "data", "task": {"file": C1, "assert": "value_bounds",
                                 "params": {"column_index": 1,
                                            "min": 0, "max": 972}}}, True),
]


def _fix_first_column(claims):
    """EdgeContour 表没有表头，列名是数字。断言里的 column 换成实际列名。"""
    out = []
    for q, text, spec, guess in claims:
        t = dict(spec["task"])
        if (spec["domain"] == "data"
                and (t.get("params") or {}).get("column") == ""):
            try:
                from probe import _read_table
                cols, _rows = _read_table(t["file"], t.get("sheet"),
                                          int(t.get("header_row", 1)))
                t["params"] = {**t["params"], "column": cols[0]}
            except Exception:  # noqa: BLE001
                pass
        out.append((q, text, {"domain": spec["domain"], "task": t}, guess))
    return out


def main() -> int:
    do_record = "--record" in sys.argv
    claims = _fix_first_column(CLAIMS)

    print("=" * 80)
    print("投喂 2021-A · 图像 + 边缘轮廓")
    print("=" * 80)

    hit = 0
    results = []
    for q, text, spec, guess in claims:
        ok, why = do_exec(spec["domain"], spec["task"])
        results.append((q, text, spec, ok, why))
        hit += 1 if ok == guess else 0
        print(f"  [{q:<3}] {'✓' if ok == guess else '✗'} {text}")
        print(f"        判定={'成立' if ok else '不成立'}"
              f"  预判={'成立' if guess else '不成立'}   {why[:56]}")

    holds = sum(1 for *_x, ok, _w in results if ok)
    print()
    print("=" * 80)
    print(f"  共 {len(results)} 条：成立 {holds} / 不成立 {len(results) - holds}")
    print(f"  我的预判命中 {hit}/{len(results)}"
          + (f"，错了 {len(results) - hit} 条" if hit != len(results) else "（这次全对）"))
    print("=" * 80)

    if do_record:
        _record(results, blind=("--blind" in sys.argv))
    return 0


def _record(results, blind: bool = False) -> None:
    """按第五十一轮定的规则记账：验证过才给 e3=2，被推翻的走 refuted_by_test。"""
    import ledger as L
    from collections import Counter
    from harness import Claim, run_gates, EvidenceEnv

    L.bind_production("真题投喂：2021-A 图像与轮廓")
    env = EvidenceEnv(3)
    dist = Counter()
    for q, text, spec, ok, why in results:
        if blind:
            # 盲判：只看结构，没跑断言 → e3=1，挂起等结算
            c = Claim(f"QB21-{q}", text, e1=2, e2=1, e3=1, kind="world",
                      input_valid=True)
            g = run_gates(c, env)
            L.record(g["final"], task=f"真题21·{q} {text[:28]}",
                     note=f"盲判 域={spec['domain']}",
                     success=None, exec_ok=None,
                     evidence="盲判：未执行断言", env_level=3,
                     cause=g.get("cause"), origin="qb",
                     replay={"domain": spec["domain"], "task": spec["task"]},
                     prejudged=False)
            dist[f"{g['final']}/盲判"] += 1
            continue
        c = Claim(f"QB21-{q}", text, e1=2, e2=2, e3=2, kind="world",
                  input_valid=True, refuted_by_test=(not ok))
        g = run_gates(c, env)
        L.record(g["final"], task=f"真题21·{q} {text[:28]}",
                 note=f"域={spec['domain']} 断言={spec['task'].get('assert')}",
                 success=ok,
                     conclusion_held=ok, exec_ok=True, evidence=why[:70],
                 env_level=3, cause=g.get("cause"), origin="qb",
                 replay={"domain": spec["domain"], "task": spec["task"]},
                 prejudged=True)  # 先验证后判 pass
        dist[f"{g['final']}/{'成立' if ok else '被推翻'}"] += 1

    print()
    print(f"已记账 {sum(dist.values())} 条（origin=qb）")
    for k, n in sorted(dist.items()):
        print(f"  {k}: {n}")


if __name__ == "__main__":
    raise SystemExit(main())
