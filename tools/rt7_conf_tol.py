#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""红队七板 · 第 5 板（self_correction / confession-auditor）· 只读探针 A。

审的对象：第 122 轮那次「去掉 1e-12 地板 → 引入假阳性 → 改成相对余量」的自我纠错。

本探针**不改任何源码**，只 import 生产函数并调用；不写盘。
六段实验与报告 §2 的探针 4 一一对应：

  T1 复现 lead 记录里的三个浮点数（可核）
  T2 复现 out/_rt_E2_tolfix.txt 的 A/B 表，并检验「A 组 4/4 全 Y、B 组 4/4 全 n」
  T3 列出两个公式的关系：rel_tol ? floor_tol，按 dec 扫
  T4 构造 (v, dec, f)：相对余量判错、绝对地板判对（用 Decimal 精确判真值）
  T5 反向搜：相对余量把「合法舍入」判红的用例（说明它自己也不是精确解）
  T6 verify._near 里的 +1e-12 是否还在（同一概念的另一个实现）

跑法：
  $env:PYTHONIOENCODING="utf-8"; $env:PYTHONUTF8="1"
  & $py tools\\rt7_conf_tol.py
"""
from __future__ import annotations

import os
import sys
from decimal import Decimal, getcontext

getcontext().prec = 60

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import freeze      # noqa: E402
import verify      # noqa: E402


def hr(t):
    print("\n" + "=" * 78)
    print(t)
    print("=" * 78)


# ---------------------------------------------------------------- 两个判据
def tol_rel(dec: int) -> float:
    """生产判据（freeze._match_written，第 122 轮最终版）。"""
    return 0.5 * (10.0 ** -dec) * (1.0 + 1e-9)


def tol_floor(dec: int) -> float:
    """第 122 轮第一版（错的）：绝对地板 +1e-12。"""
    return 0.5 * (10.0 ** -dec) + 1e-12


def judge_rel(v: float, dec: int, f: float) -> bool:
    """照 freeze._match_written 的循环抄一遍（三个方向 + abs）。"""
    t = tol_rel(dec)
    for cv, cf in ((abs(v), abs(f)), (abs(v), abs(f) * 100.0), (abs(v), abs(f) / 100.0)):
        if abs(cv - cf) <= t:
            return True
    return False


def judge_floor(v: float, dec: int, f: float) -> bool:
    t = tol_floor(dec)
    for cv, cf in ((abs(v), abs(f)), (abs(v), abs(f) * 100.0), (abs(v), abs(f) / 100.0)):
        if abs(cv - cf) <= t:
            return True
    return False


def judge_naked(v: float, dec: int, f: float) -> bool:
    """第 122 轮第一版（删掉地板、没有余量）= _rt_E2_tolfix.txt 里的 T1。"""
    t = 0.5 * (10.0 ** -dec)
    for cv, cf in ((abs(v), abs(f)), (abs(v), abs(f) * 100.0), (abs(v), abs(f) / 100.0)):
        if abs(cv - cf) <= t:
            return True
    return False


def judge_naked2(v: float, dec: int, f: float) -> bool:
    """同 judge_naked，但**只有 direct + ×100 两个方向**（= 证据文件里的 T1 形状）。"""
    t = 0.5 * (10.0 ** -dec)
    for cv, cf in ((abs(v), abs(f)), (abs(v), abs(f) * 100.0)):
        if abs(cv - cf) <= t:
            return True
    return False


def truth_exact(vstr: str, dec: int, fval: float) -> bool:
    """真值：|v - f| <= 0.5*10^-dec，用 Decimal 精确算（把 float 噪声排除在真值外）。

    v 用论文里那个 token 的字符串，f 用它 float 的精确十进制展开。
    """
    half = Decimal(5) * (Decimal(10) ** (-dec - 1))
    v = Decimal(vstr)
    f = Decimal(fval)          # Decimal(float) 给的是精确二进制值
    for cf in (abs(f), abs(f) * 100, abs(f) / 100):
        if abs(abs(v) - abs(cf)) <= half:
            return True
    return False


# ---------------------------------------------------------------- T1
hr("T1  复现 lead 记录里的浮点数（OPTIMIZATION 第 122 轮 §七）")
pairs = [
    ("0.78751", 5, 0.787505, 5.0000000000287557e-06),
    ("32.95", 2, 32.945, None),
    ("2.0839e-13", 17, 0.0, None),
]
print("%-12s %4s %-24s %-24s %-3s" % ("token", "dec", "float diff", "记录里的值", "一致"))
for tok, dec, f, claimed in pairs:
    d = abs(float(tok) - f)
    ok = "-" if claimed is None else ("是" if repr(d) == repr(claimed) else "否")
    print("%-12s %4d %-24r %-24r %-3s" % (tok, dec, d, claimed, ok))
print("\n半格：dec=5 → 5e-06 %r ; dec=2 → 5e-03 %r ; dec=17 → 5e-18 %r"
      % (0.5 * 10 ** -5, 0.5 * 10 ** -2, 0.5 * 10 ** -17))
print("0.78751 的差比半格大多少：%r" % (abs(0.78751 - 0.787505) - 0.5 * 10 ** -5))

# ---------------------------------------------------------------- T2
hr("T2  复现 out/_rt_E2_tolfix.txt，并检验「A 4/4、B 4/4」")
rows = [
    ("A 合法舍入", "0.78751", 5, 0.787505),
    ("A 合法舍入", "0.73916", 5, 0.739155),
    ("A 合法舍入", "32.95", 2, 32.945),
    ("A 合法舍入", "0.78751", 5, 0.7875050000000001),
    ("B 地板", "2.0839e-13", 17, 0.0),
    ("B 地板", "1.4792e-13", 17, -2.4671622769447922e-17),
    ("B 地板", "5.481e-13", 16, -2.4671622769447922e-17),
    ("B 地板", "6.7973e-14", 18, -2.4671622769447922e-17),
    ("B 控制?", "0.0", -3, -942.6619609415065),
]
print("%-12s %-12s %4s %-24s %-22s %-22s" %
      ("组", "token", "dec", "f", "floor(T0)", "rel(T1/生产)"))
nfail = {"A": 0, "B": 0}
for grp, tok, dec, f in rows:
    r0 = judge_floor(float(tok), dec, f)
    r1 = judge_rel(float(tok), dec, f)
    prod = freeze._match_written(float(tok), dec, [f])   # 真实生产函数
    print("%-12s %-12s %4d %-24r %-22s %-22s  prod=%s" %
          (grp, tok, dec, f, "Y" if r0 else "n", "Y" if r1 else "n", "Y" if prod else "n"))
    if grp == "A" and not r1:
        nfail["A"] += 1
    if grp == "B" and r1:
        nfail["B"] += 1
print("\nA 组：共 %d 行，rel 判 n 的有 %d 行 → 「A 组 4/4 通过」%s"
      % (sum(1 for r in rows if r[0] == "A"), nfail["A"],
         "复现" if nfail["A"] == 0 else "不复现"))
nb = sum(1 for r in rows if r[0] == "B")
nbn = sum(1 for r in rows if r[0] == "B" and not judge_rel(float(r[1]), r[2], r[3]))
print("B 组：共 %d 行（含 1 行 floor 也判 n 的对照），rel 判 n 的有 %d 行" % (nb, nbn))

# ---------------------------------------------------------------- T3
hr("T3  rel_tol 与 floor_tol 的关系（按 dec 扫）")
print("%4s %-26s %-26s %-24s" % ("dec", "rel=0.5*10^-dec*(1+1e-9)", "floor=0.5*10^-dec+1e-12", "谁更松"))
band = []
for dec in range(-6, 19):
    r, f = tol_rel(dec), tol_floor(dec)
    who = "rel" if r > f else ("floor" if f > r else "相等")
    if r > f:
        band.append(dec)
    if dec in (-6, -3, -2, -1, 0, 1, 2, 3, 5, 12, 17):
        print("%4d %-26.6e %-26.6e %-24s" % (dec, r, f, who))
print("\nrel 比 floor 松的 dec 段：%s" % (band if band else "无"))
print("临界：0.5*10^-dec*1e-9 > 1e-12  ⇔  dec < log10(500) = %.4f" % __import__("math").log10(500))

# ---------------------------------------------------------------- T4
hr("T4  构造：相对余量判错、绝对地板判对")
print("思路：dec<=2 时 rel 的余量 > floor 的余量（见 T3），")
print("      因此存在 d 落在 (floor_tol, rel_tol] 内 —— 地板判「不是同一个数」，相对余量判「是」。")
print("      用 Decimal 算真值（半格 = 0.5*10^-dec），看谁错。\n")
witness = []
for dec in (2, 1, 0, -1, -2, -3):
    half = Decimal(5) * (Decimal(10) ** (-dec - 1))
    r_extra = Decimal(tol_rel(dec)) - Decimal(tol_floor(dec))    # rel 比 floor 多出来的量
    if r_extra <= 0:
        continue
    d = Decimal(tol_floor(dec)) + r_extra / 2                     # 落在地板之外、余量之内
    base = Decimal(251) if dec == 2 else Decimal(1234)
    v_dec = (base.scaleb(-dec)).quantize(Decimal(1).scaleb(-dec))  # 写成 dec 位
    f_dec = v_dec - d
    vstr = format(v_dec, "f")
    f_f = float(f_dec)
    v_f = float(vstr)
    # 用真实生产函数与地板实现各判一次
    j_rel = freeze._match_written(v_f, dec, [f_f])
    j_flr = judge_floor(v_f, dec, f_f)
    j_tru = truth_exact(vstr, dec, f_f)
    d_real = Decimal(abs(v_f - f_f))
    witness.append((dec, vstr, repr(f_f), d, j_rel, j_flr, j_tru, d_real > half))
    print("dec=%-3d v=%-14s f=%-24s  d=%-24s" % (dec, vstr, repr(f_f), format(d, "f")))
    print("       真值(Decimal): |v-f|=%-24s 半格=%-10s → 合法? %s"
          % (format(d_real, "f"), format(half, "f"), "是" if j_tru else "否"))
    print("       相对余量(生产 freeze._match_written) → %-3s   绝对地板 → %-3s"
          % ("Y" if j_rel else "n", "Y" if j_flr else "n"))
    verdict = []
    if j_rel and not j_tru:
        verdict.append("相对余量错")
    if (not j_flr) and (not j_tru):
        verdict.append("地板对")
    print("       判决：%s\n" % ("；".join(verdict) if verdict else "未构成反例"))
print("能同时满足「相对余量判错 + 地板判对」的 dec 段：%s"
      % [w[0] for w in witness if w[4] and not w[6] and not w[5]])

# ---------------------------------------------------------------- T5
hr("T5  反向：相对余量把「合法舍入」判红的用例（它自己也不是精确解）")
print("思路：合法舍入的浮点差 = 半格 ± ulp/2。相对余量只留 1e-9 相对余量，")
print("      即 半格*1e-9；当 ulp(f)/2 > 半格*1e-9 时，合法舍入会被判红。")
print("      条件约：|f| * 1.1e-16 > 0.5*10^-dec * 1e-9  ⇔  |f| > 4.5e6 * 10^-dec\n")
found = []
import math
for dec in (1, 2, 3):
    for mag in (1e5, 1e6, 1e7, 1e8, 1e9, 1e10, 1e11, 1e12):
        # 造一个「恰好半格」的真值：f = k + 0.5*10^-dec 的附近，遍历几个 k
        for k in (1, 3, 7, 9):
            f = mag + k + 0.5 * 10 ** -dec
            vstr = format(f, ".%df" % dec)
            v = float(vstr)
            if float(vstr) != v:
                continue
            # 合法：v 就是 f 按 dec 位的打印结果，这才叫合法舍入
            if format(f, ".%df" % dec) != vstr:
                continue
            j = freeze._match_written(v, dec, [f])
            if not j:
                found.append((dec, mag, vstr, repr(f), repr(abs(v - f)), repr(tol_rel(dec))))
                if len(found) <= 6:
                    print("dec=%d |f|=%.0e v=%-18s f=%-24r |v-f|=%-12r tol=%-12r → 判红"
                          % (dec, mag, vstr, f, abs(v - f), tol_rel(dec)))
print("\n命中数 = %d（判红的是**合法舍入**，即假阳性）" % len(found))
if found:
    print("最小命中：%s" % (found[0],))

# ---------------------------------------------------------------- T6
hr("T6  同一概念的其他实现：+1e-12 绝对地板还在不在")
print("ARCH §4 自己数过：「论文数 vs 账本数」匹配有 4 处实现。")
print("本轮改的是 freeze._match_written 一处。逐个看：\n")
cases = [("2.0839e-13", 17, 0.0), ("1.4792e-13", 17, -2.4671622769447922e-17)]
for tok, dec, f in cases:
    a, b = float(tok), f
    print("token=%s dec=%d  f=%r" % (tok, dec, f))
    print("   freeze._match_written(生产)            → %s"
          % ("Y" if freeze._match_written(a, dec, [b]) else "n"))
    print("   verify._near(a, b, decimals=%d)         → %s   ← 带 +1e-12 的那处"
          % (dec, "Y" if verify._near(a, b, dec) else "n"))
    print("   verify._near(a, b, decimals=None)       → %s"
          % ("Y" if verify._near(a, b) else "n"))
print("\nverify._near 源码里的地板：")
src = open(os.path.join(HERE, "verify.py"), encoding="utf-8").read().splitlines()
for i, ln in enumerate(src, 1):
    if "1e-12" in ln:
        print("  verify.py:%d  %s" % (i, ln.strip()))
print("\nfreeze.py 里还有没有 1e-12：")
for i, ln in enumerate(open(os.path.join(HERE, "freeze.py"), encoding="utf-8").read().splitlines(), 1):
    if "1e-12" in ln:
        print("  freeze.py:%d  %s" % (i, ln.strip()))

hr("完")
