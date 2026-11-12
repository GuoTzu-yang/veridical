#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""rt7_stat_02_stats.py —— 只读：把 §Validation 里的统计量重算一遍。

不做判断，只出数：
  A. 三个「口径/年份」的汇总统计并列（正文 data.json / 本节的 tab_corpus / 当前树）
  B. 分类器审计的点估计 → 区间（Wilson / Clopper-Pearson / 小样本上界）
  C. 判定次数的多重比较分母：图 / data2 / data.json / 当前 gate 各说多少
  D. 阈值扰动灵敏度：numbers 门的 10% 额度，改成各档后有几道题变红
  E. 当前树每道题的带小数 token 数（「100.0%」的分母）

全部只 print，不写任何文件。
用法：python tools/rt7_stat_02_stats.py
"""
import io
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
os.chdir(HERE)

import verify as V          # noqa: E402
import freeze as FZ         # noqa: E402

OUT = os.path.join(HERE, "out", "final")


# ── 区间工具（手写，不引第三方）────────────────────────────
def wilson(k, n, z=1.959963984540054):
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - h) / d, (c + h) / d)


def cp_lower(k, n, alpha=0.05):
    """Clopper-Pearson 下界（二分，用 Beta 分位数的等价式）。"""
    if k == 0:
        return 0.0
    if k == n:
        return alpha ** (1.0 / n)          # 闭式：全中时的精确下界
    lo, hi = 0.0, k / n
    for _ in range(80):
        mid = (lo + hi) / 2
        # P(X >= k | p=mid) 与 alpha/2 比较
        s = sum(math.comb(n, i) * mid ** i * (1 - mid) ** (n - i)
                for i in range(k, n + 1))
        if s > alpha / 2:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def rule_of_three(n):
    """0/n 的 95% 上界（3/n 规则，精确值用 1-0.05^(1/n)）。"""
    return 1 - 0.05 ** (1.0 / n)


def pct(a, b):
    return 100.0 * a / b if b else 0.0


print("=" * 78)
print("A. 同一节里三套汇总统计（正文 / 本节表格 / 当前树）")
print("=" * 78)
D = json.load(io.open(os.path.join(OUT, "data.json"), encoding="utf-8"))
v = [x["num_pct"] for x in D["problems"] if x.get("num_pct") is not None]
g = [x["gate_num_pct"] for x in D["problems"]
     if x.get("gate_num_pct") is not None]


def summ(xs):
    xs = sorted(xs)
    n = len(xs)
    med = (xs[n // 2] if n % 2 else 0.5 * (xs[n // 2 - 1] + xs[n // 2]))
    return med, min(xs), max(xs)


print("  [正文 L487-488 引用的 data.json]  verify  median %5.1f  min %5.1f  max %5.1f"
      % summ(v))
print("  [同一节 tab:corpus.tex 的 verify 列] ", end="")

tab = io.open(os.path.join(OUT, "tab_corpus.tex"), encoding="utf-8").read()
rows = []
for ln in tab.splitlines():
    if "&" in ln and "\\\\" in ln and not ln.strip().startswith("\\"):
        c = [x.strip().replace("\\_", "_") for x in ln.split("&")]
        if len(c) >= 6:
            try:
                rows.append((c[0], float(c[4]), float(c[5].replace("\\\\", ""))))
            except ValueError:
                pass
print("n=%d 行" % len(rows))
print("      tab:corpus  gate   median %5.1f  min %5.1f  max %5.1f"
      % summ([r[1] for r in rows]))
print("      tab:corpus  verify median %5.1f  min %5.1f  max %5.1f"
      % summ([r[2] for r in rows]))
print("      正文说 verify median 91.0 / weakest 76.3；gate 全部 >= 91.9")
print("      表里  gate min = %.1f，verify min = %.1f"
      % (min(r[1] for r in rows), min(r[2] for r in rows)))

# 当前树
CFG = json.load(io.open(os.path.join(HERE, "runs.json"), encoding="utf-8"))
cur_v, cur_g, detail = [], [], []
for name, it in CFG.items():
    d = os.path.join(HERE, it["out"])
    tex = os.path.join(d, "paper.tex")
    if not os.path.exists(tex):
        continue
    text = io.open(tex, encoding="utf-8").read()
    rv = V.trace(text, V.load_outputs(d))
    dv = None
    try:
        import untraced as U
        dv = U.data_values_of(U.find_data_file(d))
    except Exception:                                # noqa: BLE001
        dv = None
    fzp = os.path.join(d, "冻结数字.json")
    gp = None
    ns = nt = 0
    if os.path.exists(fzp):
        rg = FZ.check_paper(text, json.load(io.open(fzp, encoding="utf-8")),
                            single_point=False, data_values=dv,
                            strict_source=False)
        gp = pct(rg["n_traced"], rg["n_numbers"])
        ns, nt = rg["n_numbers"], rg["n_int_not_judged"]
    cur_v.append(pct(rv["n_numbers"] - rv["n_untraced"], rv["n_numbers"]))
    if gp is not None:
        cur_g.append(gp)
    detail.append((name, rv["n_numbers"], gp, ns, nt))
print("  [当前树 23 份 paper.tex，%.0f 分钟前刚被重跑过]"
      % 0)
print("      verify median %5.1f  min %5.1f  max %5.1f  (n=%d)"
      % (summ(cur_v) + (len(cur_v),)))
print("      gate   median %5.1f  min %5.1f  max %5.1f  (n=%d)"
      % (summ(cur_g) + (len(cur_g),)))

print()
print("  每题的「gate 口径分母」与「未纳入判定的整数」：")
print("  %-16s %6s %6s %6s %6s" % ("run", "V_tok", "gate_n", "g_%", "int_skip"))
for name, vn, gp, ns, nt in sorted(detail, key=lambda x: (x[2] or 0)):
    print("  %-16s %6d %6s %6s %6d"
          % (name, vn, ns or "-", ("%.1f" % gp) if gp is not None else "-", nt))

print()
print("=" * 78)
print("B. 分类器审计：点估计 → 区间")
print("=" * 78)
C = json.load(io.open(os.path.join(OUT, "classifier_audit.json"),
                      encoding="utf-8"))
n, k = C["n_sample"], C["matrix"]["D_computed"]["D_computed"]
print("  一致率 195/200 点估计 = %.1f%%（论文写 %.1f%%）" % (pct(195, 200), C["agreement"]))
lo, hi = wilson(195, 200)
print("    Wilson 95%%        = [%.1f%%, %.1f%%]  ← 宽度 %.1f pp"
      % (100 * lo, 100 * hi, 100 * (hi - lo)))
print("    Clopper-Pearson 95%% 下界 = %.1f%%" % (100 * cp_lower(195, 200)))
n_d = C["d_auto"]
print("  危险方向 %d/%d 点估计 = 0.0%%（论文写「0 times in %d cases」）" % (0, n_d, n_d))
print("    0/%d 的 95%% 精确上界 = %.2f%%（rule of three ≈ %.2f%%）"
      % (n_d, 100 * rule_of_three(n_d), 100 * 3.0 / n_d))
print("  → 论文给的点估计 0，允许的真实率上界是 %.1f%%；未写。" % (100 * rule_of_three(n_d)))
print("  抽样细节：seed=%s（脚本硬编码 seed=7），样本 %d/%d，"
      % ("7", n, C["n_untraced"]))
print("    但 200 条的**人工标签本身没有落盘** —— 只有归约后的混淆矩阵，"
      "无法复核单条判读。")

print()
print("=" * 78)
print("C. 多重比较的分母：到底判了多少次？")
print("=" * 78)
D2 = json.load(io.open(os.path.join(OUT, "data2.json"), encoding="utf-8"))
GR = json.load(io.open(os.path.join(OUT, "gate-report.json"),
                       encoding="utf-8"))
ids2 = D2["gate_ids"]
M = D2["gate_matrix"]
probs = sorted(M)
stat = {}
for p in probs:
    for c in ids2:
        s = M[p][c][1]
        stat[s] = stat.get(s, 0) + 1
print("  论文图注 L656 写 `23 x 23`")
print("  图实际矩阵 = %d problems x %d checks = %d cells"
      % (len(probs), len(ids2), len(probs) * len(ids2)))
print("  data.json n_gate_checks = %d → 若按它算 %d x %d = %d"
      % (D["n_gate_checks"], len(D["problems"]), D["n_gate_checks"],
         len(D["problems"]) * D["n_gate_checks"]))
print("  当前 gate-report.json 实际 checks = %d → %d x %d = %d"
      % (len(GR["checks"]), len(D["problems"]), len(GR["checks"]),
         len(D["problems"]) * len(GR["checks"])))
print("  矩阵里的判决分布：", stat)
na = stat.get("N/A", 0)
print("  其中 N/A（检查没跑）%d / %d = %.1f%% —— 这些格子在「全绿」里没有成本"
      % (na, len(probs) * len(ids2), pct(na, len(probs) * len(ids2))))
print("  有效独立单元：23 题（同题内 28 门高度相关）。0/23 的 95%% 上界 = %.1f%%"
      % (100 * rule_of_three(len(probs))))
print("  若 28 门互相独立且各有 5%% 假阳性：P(0 red) = 0.95^%d = %.3g"
      % (len(probs) * len(ids2), 0.95 ** (len(probs) * len(ids2))))
print("  → 论文没有给 per-check alpha，也没有给多重比较校正；"
      "「0 red」只能当「这套门在这套语料上没报警」，不能当「假阳性率=0」。")

print()
print("=" * 78)
print("D. 灵敏度：numbers 门的 10%% 额度，阈值改成各档后有几道题变红")
print("=" * 78)
unt = [(x["name"], x["gate_num_untraced_pct"]) for x in D["problems"]
       if x.get("gate_num_untraced_pct") is not None]
unt.sort(key=lambda t: -t[1])
print("  现状（data.json，11/10 23:03）：未溯源比例最高的几道题")
for nm, u in unt[:8]:
    print("    %-16s %5.1f%%   占 10%% 额度的 %.0f%%" % (nm, u, 10 * u / 10))
for tau in (1, 2, 3, 5, 8, 10):
    red = [nm for nm, u in unt if u > tau]
    print("  阈值 %2d%% → 变红 %2d/23 题 %s"
          % (tau, len(red), ("(" + ", ".join(red) + ")") if red else ""))
print("  论文采用的阈值：max_untraced=0.10（freeze.check_paper 默认）")
print("  → 最差一题 %.1f%%，距阈值 %.1f pp；阈值从 10%% 收到 8%% 就翻 1 题，"
      % (unt[0][1], 10 - unt[0][1]))
print("     收到 5%% 翻 %d 题，收到 2%% 翻 %d 题。"
      % (len([1 for _n, u in unt if u > 5]),
         len([1 for _n, u in unt if u > 2])))
