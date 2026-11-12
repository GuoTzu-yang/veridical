#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
投喂第二批真题：2021-B 折射率库 / 2023 五岳杯 / 2024-A 空模板

第一批（feed_qb.py 覆盖 2026-A_B_C，feed_qb2021.py 覆盖 2021-A）拿到的样本
集中在「中文赛题 + 传感器时序 + 图像」。这一批换赛道，专门找**英文题 + 物理
常数库 + 离散优化小表**，看断言层在完全不同的数据形态上还能不能判定。

三套题的实测地位（[实] = 本轮脚本扫目录得出的，不是印象）：
  [实] 2021-B  26 个折射率 CSV（n/k 光学常数），能量化的量很多
  [实] 2023-五岳杯  4 个 CSV（需求分布网格 + 候选设施），表很小但结构干净
  [空] 2024-A  只有一个 Answer.xls，两个 sheet **只有表头没有数据行**
  [空] 2021-C / 2023-A / 2023-B / 2023-C / 2024-B / 2024-C / 2024-D
        逐目录扫过，零个 xls/xlsx/csv/bmp/png；2024-D 的 5 个 Attachment 全是 PDF

本批最值钱的一条「看表头会看错」：
  10 个介质文件（Al2O3/AlN/MgF2/MgO/Si3N4/SiC/SiO2/Y2O3/ZnO/ZnS）表头写三列
  `Wavelength, µm / n / k`，**数据行只有两个数**——k 列根本没数据。
  于是 `column_exists` 判「表头有 k」成立，`value_bounds` 判「k 有数值」
  直接列表越界算不出来。同一个文件上，两条断言给出互相矛盾的样子。

免责：本脚本**不记账**（不碰 ledger.record / resolve），只打印实测结果。

主张里 unsure=True 的是我**真没算过**的，共 8 条：
  Ag/Au 的 n~k 相关方向、Ag/TiO2/Ge 的波长单调性、Cr 的 n~波长方向、
  Al 的 n~波长方向、五岳杯 X/Y 与需求量的相关方向。
这批才是检验；其余是陪跑。

跑法：
  python tests/feed_qb_more.py
"""

from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from probe import do_exec, _read_table  # noqa: E402

# 控制台是 GBK 时中文会直接抛 UnicodeEncodeError（第一批脚本踩过）。
# 这里自己兜住，让用户在任意代码页下都能看到完整输出。
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

QB = (r"C:\Users\21246\Documents\deepseek-harness\default-workspace"
      r"\apmcm2026\题库")

B21_DIR = os.path.join(QB, "2021-B_热辐射器设计", "References",
                       "[5]Refractive index database (part data)")
WU_DIR = os.path.join(QB, "2023-五岳杯_量子计算分赛道",
                      "2023 APMCM  Wuyue Cup Problems", "Attachment")
A24_XLS = os.path.join(QB, "2024-A_水下图像增强", "Answer.xls")

# 本次要检验的 10 套题（2021-A 与 2026 三题已由前两个脚本覆盖，跳过）
SUITES = [
    ("2021-B 热辐射器", os.path.join(QB, "2021-B_热辐射器设计")),
    ("2021-C 生态保护", os.path.join(QB, "2021-C_生态保护评价")),
    ("2023-A 采摘机器人", os.path.join(QB, "2023-A_采摘机器人识别")),
    ("2023-B 温室微气候", os.path.join(QB, "2023-B_温室微气候")),
    ("2023-C 新能源汽车", os.path.join(QB, "2023-C_新能源汽车")),
    ("2023-五岳杯", os.path.join(QB, "2023-五岳杯_量子计算分赛道")),
    ("2024-A 水下图像", os.path.join(QB, "2024-A_水下图像增强")),
    ("2024-B 空调形状", os.path.join(QB, "2024-B_空调形状优化")),
    ("2024-C 宠物产业", os.path.join(QB, "2024-C_宠物产业分析")),
    ("2024-D 量子加速AI", os.path.join(QB, "2024-D_量子加速AI")),
]

DATA_EXT = (".xls", ".xlsx", ".csv", ".bmp", ".png", ".jpg", ".jpeg", ".tif")


def scan_suites() -> None:
    """逐个套题目录数数据文件，先把「谁真的有数据」钉死。

    这一步是本地目录遍历，不是断言——目的是给 [实]/[空] 标记留证据，
    而不是凭印象说某题「应该有数据」。
    """
    print("=" * 88)
    print("第一步：谁真的带数据文件（递归扫 xls/xlsx/csv/bmp/png）")
    print("=" * 88)
    for name, path in SUITES:
        if not os.path.isdir(path):
            print(f"  [空] {name:<16} 目录不存在：{path}")
            continue
        hits = []
        for dp, _dn, fns in os.walk(path):
            for fn in fns:
                if fn.lower().endswith(DATA_EXT):
                    rel = os.path.relpath(os.path.join(dp, fn), path)
                    hits.append(rel)
        # 有后缀 ≠ 有数据：2024-A 的 Answer.xls 是空白答卷模板，得单独说明
        note = ""
        if name.startswith("2024-A"):
            note = "  ← 仅 Answer.xls，两个 sheet 只有表头（下面 A1/A2 实测）"
        mark = "[实]" if hits else "[空]"
        print(f"  {mark} {name:<16} 数据文件 {len(hits):>2} 个{note}")
        for h in hits[:4]:
            print(f"         · {h}")
        if len(hits) > 4:
            print(f"         · …… 另 {len(hits) - 4} 个")
    print()


def real_columns() -> dict:
    """读出文件里**真实**的列名，断言里直接引用，不手写。

    理由：2021-B 的首列名是 `Wavelength, µm`——中间有逗号、空格、微符号。
    手写这个字符串时 µ 用 U+00B5 还是 U+03BC 全靠运气；从文件读出来最稳。
    """
    ag = os.path.join(B21_DIR, "Ag-Refractive Index.csv")
    a1 = os.path.join(WU_DIR, "Problem 1",
                      "Attachment 1_Computational Demand Distribution Data.csv")
    a3 = os.path.join(WU_DIR, "Problem 2",
                      "Attachment 3_Candidate Edge Facilities Data.csv")
    return {
        "b": _read_table(ag, None, 1)[0],
        "w1": _read_table(a1, None, 1)[0],
        "w3": _read_table(a3, None, 1)[0],
    }


def build_claims() -> list[tuple]:
    """构建主张表：(题号, 主张, 断言规格, 我的预判, 是否真的没把握)。

    预判**故意留着**：跑完才知道直觉准不准。
    unsure=True 的 8 条是我没算过、只凭物理/经验猜的——
    全挑成立的主张等于没测，必须留几条踩空的可能。
    """
    C = real_columns()
    WAV, N, K = C["b"][0], C["b"][1], C["b"][2]          # 'Wavelength, µm' / 'n' / 'k'
    WX, WY, WA = C["w1"][0], C["w1"][1], C["w1"][2]      # 'X-axis' / 'Y-axis' / 'Amount...'
    WF = C["w3"][3]                                       # 'Fixed Cost'

    def f(name: str) -> str:
        return os.path.join(B21_DIR, name)

    def w(*parts: str) -> str:
        return os.path.join(WU_DIR, *parts)

    A1 = w("Problem 1", "Attachment 1_Computational Demand Distribution Data.csv")
    A2 = w("Problem 2", "Attachment 2_Computational Demand Distribution Data.csv")
    A3 = w("Problem 2", "Attachment 3_Candidate Edge Facilities Data.csv")

    def data_d(file: str, assert_: str, params: dict, header_row: int = 1,
               sheet=None) -> dict:
        """组一条 data 域规格；header_row 显式写，别依赖默认值。"""
        t = {"file": file, "header_row": header_row,
             "assert": assert_, "params": params}
        if sheet is not None:
            t["sheet"] = sheet
        return {"domain": "data", "task": t}

    return [
        # ═════ 2021-B 折射率库：16 条 ═════
        # 口径：每行一个波长，n 是实部折射率，k 是消光系数
        ("B1", f"Al2O3 表头声明了 {K} 列（介质也有消光系数）",
         data_d(f("Al2O3-Refractive Index.csv"), "column_exists",
                {"column": K}), True, False),

        # 本批最要紧的一条：表头有 k，数据行只有两列。
        # value_bounds 会直接列表越界——断言跑不完，主张就没有依据。
        ("B2", f"Al2O3 表里 {K} 列真的有数值（不只是表头声明）",
         data_d(f("Al2O3-Refractive Index.csv"), "value_bounds",
                {"column": K, "min": -1, "max": 1e9}), False, False),

        ("B3", f"Al2O3 的波长从 0.1 µm 以上开始",
         data_d(f("Al2O3-Refractive Index.csv"), "value_bounds",
                {"column": WAV, "min": 0.1, "max": 10}), True, False),

        ("B4", f"Ag 的 {K} 全部落在 0~100",
         data_d(f("Ag-Refractive Index.csv"), "value_bounds",
                {"column": K, "min": 0, "max": 100}), True, False),

        ("B5", f"Ag 的波长最小值不低于 0.25 µm",
         data_d(f("Ag-Refractive Index.csv"), "value_bounds",
                {"column": WAV, "min": 0.25, "max": 20}), False, False),

        ("B6", f"Ag 的 {N} 与 {K} 同向变化（正相关）",
         data_d(f("Ag-Refractive Index.csv"), "corr_sign",
                {"x": N, "y": K, "expect": "positive"}), True, True),

        ("B7", "Ag 的波长按四段均值递增（表是按波长升序排的）",
         data_d(f("Ag-Refractive Index.csv"), "monotone_quarters",
                {"column": WAV, "expect": "increasing"}), True, True),

        ("B8", "Al 表的行数超过 500",
         data_d(f("Al-Refractive Index.csv"), "row_count",
                {"op": ">=", "value": 500}), False, False),

        ("B9", "Ge 表的行数超过 600（红外材料采样更密）",
         data_d(f("Ge-Refractive Index.csv"), "row_count",
                {"op": ">=", "value": 600}), True, False),

        ("B10", f"Ge 的 {N} 都不低于 2.9（Ge 是常用红外材料里折射率最高的）",
         data_d(f("Ge-Refractive Index.csv"), "value_bounds",
                {"column": N, "min": 2.9, "max": 10}), True, False),

        ("B11", "TiO2 表的行数超过 1400",
         data_d(f("TiO2-Refractive Index.csv"), "row_count",
                {"op": ">=", "value": 1400}), True, False),

        ("B12", f"TiO2 的 {N} 都不超过 2.5",
         data_d(f("TiO2-Refractive Index.csv"), "value_bounds",
                {"column": N, "min": 0, "max": 2.5}), True, False),

        ("B13", "TiO2 的波长按四段均值递增（1451 行，可能按波数排列）",
         data_d(f("TiO2-Refractive Index.csv"), "monotone_quarters",
                {"column": WAV, "expect": "increasing"}), True, True),

        ("B14", "Ge 表的波长按四段均值递增",
         data_d(f("Ge-Refractive Index.csv"), "monotone_quarters",
                {"column": WAV, "expect": "increasing"}), True, True),

        ("B15", f"Cr 的 {N} 随波长变长而下降（负相关）",
         data_d(f("Cr-Refractive Index.csv"), "corr_sign",
                {"x": WAV, "y": N, "expect": "negative"}), True, True),

        ("B16", f"Au 的 {N} 与 {K} 同向变化（正相关）",
         data_d(f("Au-Refractive Index.csv"), "corr_sign",
                {"x": N, "y": K, "expect": "positive"}), True, True),

        # ═════ 2023 五岳杯：7 条 ═════
        ("W1", "Attachment 1 有 16 行需求记录",
         data_d(A1, "row_count", {"op": "==", "value": 16}), True, False),

        ("W2", f"Attachment 1 的 {WX} 都落在 1~6",
         data_d(A1, "value_bounds",
                {"column": WX, "min": 1, "max": 6}), True, False),

        ("W3", f"Attachment 1 的 {WA} 非负",
         data_d(A1, "value_bounds",
                {"column": WA, "min": 0, "max": 1000}), True, False),

        ("W4", "Attachment 2 是满网格，共 36 行（6×6）",
         data_d(A2, "row_count", {"op": "==", "value": 36}), True, False),

        ("W5", f"Attachment 2 的 {WX} 与 {WA} 负相关（靠边的格子需求更少）",
         data_d(A2, "corr_sign",
                {"x": WX, "y": WA, "expect": "negative"}), False, True),

        ("W6", f"Attachment 2 的 {WY} 与 {WA} 负相关",
         data_d(A2, "corr_sign",
                {"x": WY, "y": WA, "expect": "negative"}), False, True),

        ("W7", f"Attachment 3 的 {WF} 都落在 40~80",
         data_d(A3, "value_bounds",
                {"column": WF, "min": 40, "max": 80}), True, False),

        # ═════ 2024-A 空模板：2 条 ═════
        # 「标记 [空]」这件事本身也被测一次，不然它只是一句印象。
        ("A1", "Answer.xls 第一张 sheet 没有有效答题数据（≤1 行）",
         data_d(A24_XLS, "row_count", {"op": "<=", "value": 1},
                sheet="attachment1 results"), True, False),

        ("A2", "Answer.xls 第二张 sheet 一行数据都没有",
         data_d(A24_XLS, "row_count", {"op": "==", "value": 0},
                sheet="attachment 2 results"), True, False),
    ]


def run_one(spec: dict) -> tuple[bool, str]:
    """跑一条断言。断言自己抛异常时按「不成立」记，并把现场写进依据。

    为什么不能让它崩：`value_bounds` 取的是 `r[idx]`，当表头有这一列、
    但数据行没有时（Al2O3 的 k）会 IndexError。断言跑不完 ≠ 主张成立，
    也更不该让整份报告挂在一个越界异常上。
    所以异常时额外读一次表，把行宽分布附上——看的人才知道是「缺列」，
    而不是脚本坏了。
    """
    try:
        return do_exec(spec["domain"], spec["task"])
    except Exception as e:  # noqa: BLE001
        extra = ""
        try:
            t = spec["task"]
            cols, rws = _read_table(t["file"], t.get("sheet"),
                                    int(t.get("header_row", 1)))
            widths: dict[int, int] = {}
            for r in rws:
                widths[len(r)] = widths.get(len(r), 0) + 1
            extra = (f"；表头 {len(cols)} 列，数据行宽分布 {widths}"
                     f"，列名 {cols}")
        except Exception:  # noqa: BLE001
            pass
        return False, f"断言执行抛异常 {type(e).__name__}: {str(e)[:36]}{extra}"


def main() -> int:
    scan_suites()
    claims = build_claims()

    print("=" * 88)
    print("第二步：主张 × 确定性断言（逐条真跑，全部为 [实]）")
    print("  行首「命中 / 错判」= 判定与我的预判是否一致；与主张成立与否无关。")
    print("=" * 88)

    rows = []
    for q, text, spec, guess, unsure in claims:
        ok, why = run_one(spec)
        hit = (ok == guess)
        rows.append((q, text, spec, guess, unsure, ok, why, hit))
        star = " ※没把握" if unsure else ""
        print(f"  [{q:<3}] {'命中' if hit else '错判'}  {text}{star}")
        print(f"        判定={'成立' if ok else '不成立'}"
              f"   预判={'成立' if guess else '不成立'}"
              f"   {'一致' if hit else '**预判错**'}")
        print(f"        依据：{why}")

    total = len(rows)
    holds = sum(1 for r in rows if r[5])
    hit_n = sum(1 for r in rows if r[7])
    wrong = total - hit_n
    unsure_rows = [r for r in rows if r[4]]
    unsure_hit = sum(1 for r in unsure_rows if r[7])

    print()
    print("=" * 88)
    print(f"  共 {total} 条主张：成立 {holds} / 不成立 {total - holds}")
    print(f"  我的预判命中 {hit_n}/{total}，错了 {wrong} 条")
    print(f"  其中标注「没把握」的 {len(unsure_rows)} 条："
          f"预判对 {unsure_hit}/{len(unsure_rows)}"
          f"，错 {len(unsure_rows) - unsure_hit} 条")
    if wrong:
        print("  预判错的条目：")
        for r in rows:
            if not r[7]:
                print(f"    · [{r[0]}] {r[1]}")
                print(f"        我猜{'成立' if r[3] else '不成立'}，实际"
                      f"{'成立' if r[5] else '不成立'} —— {r[6][:64]}")
    print("=" * 88)

    per = {}
    for r in rows:
        key = {"B": "2021-B", "W": "五岳杯", "A": "2024-A"}[r[0][0]]
        a = per.setdefault(key, [0, 0])
        a[0] += 1 if r[5] else 0
        a[1] += 1
    print("  分套题：")
    for k, (a, b) in per.items():
        print(f"    {k:<8} 成立 {a}/{b}")
    print("=" * 88)
    print()
    print("怎么读：")
    print("  「不成立」不是脚本出错，是数据本身给了否定答案——")
    print("  每一条都带上真实依据（范围/相关系数/行数），可复核。")
    print("  「预判错」才是这轮的产出：说明我的直觉在哪些地方不如算一遍。")
    print("=" * 88)
    # ---- 落账（第六十二轮加）----
    # 这批主张之前只打印、不入账，等于白测。加进来是为了让它们变成
    # **真检验样本**：盲判时 success=None，隔一轮用 resolve-blind 结算。
    if "--record" in sys.argv:
        import ledger as _L
        from harness import Claim as _C, run_gates as _rg, EvidenceEnv as _EE

        blind = "--blind" in sys.argv
        _L.bind_production("真题投喂：2021-B / 五岳杯 / 2024-A")
        _env = _EE(3)
        n_rec = 0
        for q, text, spec, _guess, _unsure, _ok, _why, _hit in rows:
            if blind:
                # 盲判：只看题目与数据结构，不跑断言。
                # 没跑就不该给 e3=2，所以 e3=1 → 落在 degrade，等验证来升或否。
                c = _C(q, text, e1=2, e2=1, e3=1, kind="world")
                g = _rg(c, _env)
                _L.record(g["final"], task="真题M·" + q + " " + text[:26],
                          note="盲判 域=" + spec["domain"],
                          success=None, exec_ok=None,
                          evidence="盲判：只看题目与数据结构，未执行断言",
                          env_level=3, cause=g.get("cause"), origin="qb",
                          replay=spec, prejudged=False)
            else:
                ok, why = run_one(spec)
                c = _C(q, text, e1=2, e2=2, e3=2, kind="world",
                       refuted_by_test=(not ok))
                g = _rg(c, _env)
                _L.record(g["final"], task="真题M·" + q + " " + text[:26],
                          note="域=" + spec["domain"],
                          success=ok,
                     conclusion_held=ok, exec_ok=True, evidence=why[:70],
                          env_level=3, cause=g.get("cause"), origin="qb",
                          replay=spec, prejudged=True)
            n_rec += 1
        print()
        print("已记账 " + str(n_rec) + " 条（"
              + ("盲判，等 resolve-blind" if blind else "先验证后判") + "）")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
