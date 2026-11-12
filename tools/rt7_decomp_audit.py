# -*- coding: utf-8 -*-
"""rt7_decomp_audit.py —— 七板红队·analysis/decomposition-auditor 的探针。

只读：不写任何 .py/.tex/.json，只 print。
覆盖四条探针：
  P1 互斥（顺序导致的抢占）
  P2 穷尽（token 会不会掉出五类 / '?' 统计了吗）
  P3 分类改变检查器能问什么（同一 token 换类的判决差）
  P4 分母是否完整（n_untraced 是否被截断）
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import untraced as U
import verify as V


def hr(t):
    print("\n" + "=" * 78)
    print(t)
    print("=" * 78)


# ─────────────────────────── P1 互斥 / 抢占 ───────────────────────────
def p1():
    hr("P1  互斥性：classify_token 的顺序导致谁抢谁")
    probes = ["28285", "422", "1000", "1001", "2000", "1998", "78.8", "98.3",
              "0.95", "0.05", "0.5", "0", "84", "-12", "3.3342e-12", "7"]
    print("%-12s %-12s %-12s" % ("token", "无数据表", "数据表含该值"))
    for t in probes:
        a = U.classify_token(t)
        b = U.classify_token(t, {28285.0, 422.0, 1000.0, 78.8, 98.3, 0.95,
                                 0.05, 0.5, 84.0, 2000.0})
        print("%-12s %-12s %-12s%s" % (t, a, b,
                                       "   <-- 数据表被抢占" if a != b else ""))
    print("\n结论判据：若某 token 在两张表下同类，说明它从未有机会成为 E_data。")

    # 顺序矩阵：每个类在哪些区间是「先手」
    print("\n-- 顺序先手表（判据从上到下命中即停）--")
    print("  1900<=v<=2100 且无小数点  -> C_year     （年份/期号，也可能是 n=2000）")
    print("  有小数点 且 v∈{0.05,0.01,0.95,0.90,0.5} -> B_config（也可能是算出来的 R²/准确率）")
    print("  无小数点 且 |v|<=1000      -> A_struct   （行号表号，也可能是真数据/真结果）")
    print("  v 六位小数命中输入表单元格 -> E_data")
    print("  其余                       -> D_computed")


# ─────────────────────────── 输入表规模 ───────────────────────────
def table_stats():
    hr("P1b 输入表里有多少值「永远当不成 E_data」")
    cfg = json.load(io.open(os.path.join(HERE, "runs.json"), encoding="utf-8"))
    print("%-16s %-34s %8s %8s %9s %9s" %
          ("题", "输入表", "数值格", "<=1000", "[1900,2100]", "无小数点"))
    for nm in ("age_struct", "nflis", "birth_rate", "pop_panel", "life_exp"):
        if nm not in cfg:
            continue
        d = os.path.join(HERE, cfg[nm]["out"])
        f = U.find_data_file(d)
        if not f:
            print("%-16s %-34s  找不到输入表" % (nm, "(find_data_file 返回空)"))
            continue
        try:
            import pandas as pd
        except Exception as e:                            # noqa: BLE001
            print("pandas 不可用:", e)
            return
        tot = le1000 = yearband = nodot = 0
        try:
            for sh in pd.ExcelFile(f).sheet_names:
                df = pd.read_excel(f, sheet_name=sh)
                for c in df.columns:
                    col = pd.to_numeric(df[c], errors="coerce").dropna()
                    for x in col.tolist():
                        x = float(x)
                        tot += 1
                        if abs(x) <= 1000:
                            le1000 += 1
                        if 1900 <= x <= 2100 and x == int(x):
                            yearband += 1
                        if x == int(x):
                            nodot += 1
        except Exception as e:                            # noqa: BLE001
            print("%-16s 读取失败: %s" % (nm, e))
            continue
        print("%-16s %-34s %8d %8d %9d %9d"
              % (nm, os.path.basename(f), tot, le1000, yearband, nodot))
        if tot:
            print("%-16s   -> 其中 %.1f%% 落在 |v|<=1000（A_struct 先手，永不做 E_data）"
                  % ("", 100.0 * le1000 / tot))
            print("%-16s   -> 其中 %.1f%% 落在 [1900,2100] 整数（C_year 先手）"
                  % ("", 100.0 * yearband / tot))


# ─────────────────────────── P2 穷尽 ───────────────────────────
def p2():
    hr("P2  穷尽性：token 会不会掉出五类；'?' 统计了吗")
    # 2a 分类函数本身是否覆盖全部 float
    import math
    bad = []
    tests = [0.0, -0.0, 1e308, -1e308, float("nan"), float("inf"), 1900.0,
             2100.0, 1000.5, 1e-12, -28285.0]
    for v in tests:
        k = U.classify_token(repr(v))
        if k not in U.CLASSES and k != "?":
            bad.append((v, k))
    print("2a 分类函数对极端 float 的返回：", {repr(v): U.classify_token(repr(v))
                                              for v in tests})
    print("   掉出五类且非'?'的：", bad if bad else "无（函数本身是全域的）")

    # 2b 上游：extract_numbers 会不会把 token 丢在分类之前
    print("\n2b 上游 extract_numbers 的静默丢弃（这发生在 classify 之前）")
    print("   verify.py:133  if skip_meta and v in PLAUSIBLE_META: continue")
    print("   PLAUSIBLE_META =", sorted(V.PLAUSIBLE_META))
    tex = "\\begin{document} 1 2 3 7 30 365 999 2000 28285 end{document}"
    withskip = V.extract_numbers(tex, skip_meta=True)
    noskip = V.extract_numbers(tex, skip_meta=False)
    print("   skip_meta=True  抽出 %d 个: %s" % (len(withskip), [t for t, _ in withskip]))
    print("   skip_meta=False 抽出 %d 个: %s" % (len(noskip), [t for t, _ in noskip]))
    print("   -> 被 skip_meta 静默丢掉 %d 个，它们连 n_numbers 分母都不进"
          % (len(noskip) - len(withskip)))

    # 2c 语料里 '?' 实际出现次数；corpus() 聚合是否包含 '?'
    print("\n2c 全语料 '?' 计数与 corpus 聚合口径")
    cfg = json.load(io.open(os.path.join(HERE, "runs.json"), encoding="utf-8"))
    q = 0
    tot_unt = 0
    for nm, it in cfg.items():
        d = os.path.join(HERE, it["out"])
        if not os.path.exists(os.path.join(d, "paper.tex")):
            continue
        a = U.analyse(d)
        if a.get("error"):
            continue
        q += a["counts"].get("?", 0)
        tot_unt += a["n_untraced"]
    print("   23 篇 '?' 合计 = %d ；未溯源合计 = %d" % (q, tot_unt))
    print("   untraced.corpus() 第150-153行 agg 只累加 CLASSES，'?' 不进 agg：")
    print("   分母用 unt（含 ?），分子只有五类 -> 若 ? > 0，各类百分比之和 < 100%")
    src = io.open(os.path.join(HERE, "untraced.py"), encoding="utf-8").read()
    print("   '?' in corpus 聚合代码：",
          "agg[k] += a[\"counts\"][k]" in src,
          "| agg 里有无 '?' 键：", "\"?\"" in src.split("def corpus")[1][:900])

    # 2d trace 的 token 是否一定可 float —— 决定 '?' 是否可达
    print("\n2d '?' 分支在一篇真实论文上是否可达")
    texp = os.path.join(HERE, cfg["nflis"]["out"], "paper.tex")
    cand = V.extract_numbers(io.open(texp, encoding="utf-8").read())
    nf = 0
    for t, _ in cand:
        try:
            float(t)
        except ValueError:
            nf += 1
    print("   nflis 候选 %d 个，其中 float() 失败的 %d 个 -> '?' 不可达" % (len(cand), nf))


# ─────────────────────────── P3 分类改变判决 ───────────────────────────
def p3():
    hr("P3  同一 token 换一个类，检查器能问什么就变了")
    cases = [
        ("28285", "nflis 州总报告数（真数据）", "D_computed" ),
        ("422",   "年龄表里的一个计数", "A_struct"),
        ("2000",  "样本量 n=2000", "C_year"),
        ("0.95",  "模型准确率 0.95", "B_config"),
        ("78.8",  "dwts2026c 的未溯源值", "D_computed"),
    ]
    print("%-8s %-26s %-12s %-34s %s" %
          ("token", "它实际是什么", "判成", "该类的举证门槛", "untraced.main 退出码"))
    gates = {"A_struct": "不要求任何出处（布局）",
             "B_config": "不要求任何出处（方法约定）",
             "C_year": "不要求任何出处（数据标签）",
             "E_data": "必须出现在输入表某个单元格",
             "D_computed": "必须追到插件计算产物（out/ 的 json/csv）"}
    for tok, what, want in cases:
        got = U.classify_token(tok)
        code = 0 if got != "D_computed" else 1
        print("%-8s %-26s %-12s %-34s %d" % (tok, what, got, gates[got], code))
    print("\n读法：classify_token 的返回值直接决定 untraced.main() 的退出码")
    print("      （untraced.py:232  return 0 if counts['D_computed']==0 else 1）")
    print("      同一个 422，若它其实是算出来的结果，判成 A_struct 就永远不算缺陷。")

    # 实证：把 nflis 的 C_year 类 token 列出来，看是否真的都是年份
    print("\n3b 实证：nflis 未溯源 token 逐类样本（上下文取自 verify.trace）")
    cfg = json.load(io.open(os.path.join(HERE, "runs.json"), encoding="utf-8"))
    d = os.path.join(HERE, cfg["nflis"]["out"])
    tex = io.open(os.path.join(d, "paper.tex"), encoding="utf-8").read()
    outs = V.load_outputs(d)
    r = V.trace(tex, outs)
    dv = U.data_values_of(U.find_data_file(d))
    print("   输入表可读: %s（dv 大小 %d）" % (bool(dv), len(dv)))
    from collections import Counter
    per = {}
    for u in r["untraced"]:
        k = U.classify_token(u["token"], dv)
        per.setdefault(k, []).append((u["token"], (u.get("line") or "")[:58]))
    for k in list(U.CLASSES) + ["?"]:
        rows = per.get(k, [])
        print("   %-11s %3d 个" % (k, len(rows)))
        for tok, ctx in rows[:6]:
            print("        %-10s | %s" % (tok, ctx))


# ─────────────────────────── P4 分母完整性 ───────────────────────────
def p4():
    hr("P4  分母是否完整：n_untraced 是全集还是前 N 条")
    print("4a verify.trace 是否截断 untraced？")
    vv = io.open(os.path.join(HERE, "verify.py"), encoding="utf-8").read()
    print("   verify.py:242-257  untraced.append(...) 无切片；返回 untraced=untraced 全长")
    print("   verify.py 里对 untraced 的切片：")
    for i, ln in enumerate(vv.splitlines(), 1):
        if "untraced" in ln and "[" in ln and ":" in ln:
            print("      %4d: %s" % (i, ln.strip()))
    print("   -> 只有 report() 打印时用 [:15]，数据本身不截断")

    print("\n4b freeze.check_paper 的 untraced 明细")
    ff = io.open(os.path.join(HERE, "freeze.py"), encoding="utf-8").read().splitlines()
    for i in (296, 297, 258, 295):
        if i - 1 < len(ff):
            print("      %4d: %s" % (i, ff[i - 1]))

    print("\n4c 实证：构造 30 个带小数的未溯源值，看 check_paper 返回几个")
    import tempfile
    import freeze
    td = tempfile.mkdtemp(prefix="rt7_p4_")
    toks = ["%.4f" % (1.1 + i) for i in range(30)]
    tex = "\\begin{document} " + " ".join(toks) + " end{document}"
    frozen = dict(items=[], generated_from="", source="")
    res = freeze.check_paper(tex, frozen, must=3, max_untraced=0.10,
                             single_point=False, strict_source=False)
    print("   n_numbers=%s  n_traced=%s  untraced_ratio=%s"
          % (res["n_numbers"], res["n_traced"], res["untraced_ratio"]))
    print("   len(res['untraced']) = %d  （真正的未溯源数应为 30）"
          % len(res["untraced"]))
    print("   -> 明细被 [:20] 截断；比例 untraced_ratio 用的是全量，两者口径不同")

    print("\n4d untraced.analyse 的 n_untraced 是哪来的")
    uu = io.open(os.path.join(HERE, "untraced.py"), encoding="utf-8").read().splitlines()
    for i in (103, 105, 116, 117):
        print("      %4d: %s" % (i, uu[i - 1]))

    print("\n4e e_verify 显示的是几层截断")
    ev = io.open(os.path.join(HERE, "tools", "e_verify.py"), encoding="utf-8").read()
    for i, ln in enumerate(ev.splitlines(), 1):
        if "untraced" in ln:
            print("      %4d: %s" % (i, ln.strip()))


def main():
    p1()
    table_stats()
    p2()
    p3()
    p4()
    return 0


if __name__ == "__main__":
    sys.exit(main())
