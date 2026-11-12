# -*- coding: utf-8 -*-
"""rt7_decomp_audit2.py —— 探针第二轮：把「类里装了什么」和「分母装了什么」摊开。

只读：不写任何 .py/.tex/.json，只 print。
"""
import io
import json
import os
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import untraced as U
import verify as V
import freeze


def hr(t):
    print("\n" + "=" * 78)
    print(t)
    print("=" * 78)


def load_cfg():
    return json.load(io.open(os.path.join(HERE, "runs.json"), encoding="utf-8"))


def all_papers():
    cfg = load_cfg()
    out = []
    for nm, it in cfg.items():
        d = os.path.join(HERE, it["out"])
        if os.path.exists(os.path.join(d, "paper.tex")):
            out.append((nm, d))
    return out


# ── A. D_computed 全集（28 个），这一类才是判决依据 ──
def a_dcomputed():
    hr("A  全语料 D_computed 全集：到底 28 个是什么")
    tot = 0
    per = defaultdict(list)
    for nm, d in all_papers():
        tex = io.open(os.path.join(d, "paper.tex"), encoding="utf-8").read()
        r = V.trace(tex, V.load_outputs(d))
        dv = U.data_values_of(U.find_data_file(d))
        for u in r["untraced"]:
            k = U.classify_token(u["token"], dv)
            if k == "D_computed":
                per[nm].append((u["token"], (u.get("line") or "")[:62]))
                tot += 1
    for nm in sorted(per):
        print("\n  [%s]  %d 个" % (nm, len(per[nm])))
        for tok, ctx in per[nm]:
            print("      %-12s | %s" % (tok, ctx))
    print("\n  D_computed 合计 = %d" % tot)
    return tot


# ── B. C_year 全集（165 个）：是不是真年份 ──
def b_cyear():
    hr("B  全语料 C_year 全集：165 个 token 是年份，还是别的什么")
    per = defaultdict(list)
    for nm, d in all_papers():
        tex = io.open(os.path.join(d, "paper.tex"), encoding="utf-8").read()
        r = V.trace(tex, V.load_outputs(d))
        dv = U.data_values_of(U.find_data_file(d))
        for u in r["untraced"]:
            if U.classify_token(u["token"], dv) == "C_year":
                per[nm].append((u["token"], (u.get("line") or "")[:62]))
    tot = sum(len(v) for v in per.values())
    c = Counter(tok for v in per.values() for tok, _ in v)
    print("  C_year 合计 = %d ；distinct = %d" % (tot, len(c)))
    print("\n  出现次数最多的 25 个值：")
    for tok, n in c.most_common(25):
        print("      %-8s x %d" % (tok, n))
    print("\n  ---- 全文样本（每篇前 4 条，带上下文）----")
    for nm in sorted(per):
        print("\n  [%s]  %d 个" % (nm, len(per[nm])))
        for tok, ctx in per[nm][:4]:
            print("      %-8s | %s" % (tok, ctx))
    return tot


# ── C. A_struct 全集（70 个）：布局号，还是被切碎的真数 ──
def c_astruct():
    hr("C  全语料 A_struct 全集：70 个 token 里有没有真数据/真结果")
    per = defaultdict(list)
    for nm, d in all_papers():
        tex = io.open(os.path.join(d, "paper.tex"), encoding="utf-8").read()
        r = V.trace(tex, V.load_outputs(d))
        dv = U.data_values_of(U.find_data_file(d))
        for u in r["untraced"]:
            if U.classify_token(u["token"], dv) == "A_struct":
                per[nm].append((u["token"], (u.get("line") or "")[:62]))
    tot = sum(len(v) for v in per.values())
    print("  A_struct 合计 = %d" % tot)
    for nm in sorted(per):
        print("\n  [%s]  %d 个" % (nm, len(per[nm])))
        for tok, ctx in per[nm]:
            print("      %-10s | %s" % (tok, ctx))
    return tot


# ── D. E_data 类是否可运行（has_data） ──
def d_edata():
    hr("D  E_data 类是否在跑：每篇的输入表能不能找到")
    print("%-16s %-8s %-34s %s" % ("题", "has_data", "find_data_file", "dv 大小"))
    n_yes = 0
    n = 0
    for nm, d in all_papers():
        n += 1
        f = U.find_data_file(d)
        dv = U.data_values_of(f) if f else set()
        if dv:
            n_yes += 1
        print("%-16s %-8s %-34s %d" % (nm, bool(dv),
                                       (os.path.basename(f) if f else "(空)"),
                                       len(dv)))
    print("\n  %d/%d 篇找得到输入表 —— 其余篇 E_data 永远为 0，"
          "那类的候选全部落进 D_computed" % (n_yes, n))
    return n_yes, n


# ── E. 判决分母：小数 vs 整数 ──
def e_denominator():
    hr("E  判决分母：check_paper 只判带小数点的 token")
    print("%-16s %8s %8s %10s %10s" %
          ("题", "小数候选", "整数跳过", "整数/全部", "判据里的 '100%'"))
    for nm, d in all_papers():
        tex = io.open(os.path.join(d, "paper.tex"), encoding="utf-8").read()
        _all = V.extract_numbers(tex, skip_meta=False)
        dec = [t for t, _ in _all if "." in t]
        itg = [t for t, _ in _all if "." not in t]
        tot = len(dec) + len(itg)
        fz = json.load(io.open(os.path.join(d, "冻结数字.json"),
                               encoding="utf-8"))
        dv = U.data_values_of(U.find_data_file(d))
        r = freeze.check_paper(tex, fz, single_point=False,
                               data_values=dv, strict_source=False)
        print("%-16s %8d %8d %9.1f%% %10s" %
              (nm, len(dec), len(itg),
               100.0 * len(itg) / max(1, tot),
               "%d/%d" % (r["n_traced"], r["n_numbers"])))
    print("\n  读法：'100%' 的分母是小数候选；整数候选整列不进判据。")
    print("  freeze.py:209  toks = [t for t, _line in _all if \".\" in t]")
    print("  freeze.py:217  n_int_skipped = sum(1 for t,_l in _all if \".\" not in t)")


# ── F. -035 / -058 从哪来 ──
def f_fragments():
    hr("F  被切成 -035 / -058 的原文是什么")
    cfg = load_cfg()
    d = os.path.join(HERE, cfg["nflis"]["out"])
    tex = io.open(os.path.join(d, "paper.tex"), encoding="utf-8").read()
    for pat in ("-035", "-058"):
        print("\n  ---- 原 tex 里含 %s 的行 ----" % pat)
        for i, ln in enumerate(tex.splitlines(), 1):
            if pat in ln:
                print("      %4d: %s" % (i, ln.strip()[:150]))
        print("      extract_numbers 抽到：",
              [(t, l[:60]) for t, l in V.extract_numbers(tex) if t == pat])


def main():
    a_dcomputed()
    b_cyear()
    c_astruct()
    d_edata()
    e_denominator()
    f_fragments()
    return 0


if __name__ == "__main__":
    sys.exit(main())
