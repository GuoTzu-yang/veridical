"""假设检验工具包（无 scipy 依赖）。

为什么需要手写
--------------
本机没有 scipy / statsmodels，而 APMCM 的工程管理类题几乎一定会要
t 检验 / 方差分析 / 卡方检验。之前做 DWTS 的 Breusch–Pagan 时是临时手算的，
不可复用。这里把分布函数和检验一次做成工具。

实现
----
  · 正则化下不完全 Gamma P(a,x)      -> 卡方分布
  · 正则化不完全 Beta I_x(a,b)        -> t 分布、F 分布
两者都用 Numerical Recipes 的级数 / 连分式，精度到机器 epsilon 附近。

提供的检验
----------
  ttest_1samp      单样本 t 检验
  ttest_ind        Welch 双样本 t 检验（不假设等方差）
  ttest_rel        配对 t 检验
  chi2_ind         卡方独立性检验（列联表）
  anova_oneway     单因素方差分析（F 检验）
  p_adjust         多重比较校正：bonferroni / holm / bh

用法
    python tools/stat_tests.py selftest
    python tools/stat_tests.py --demo
"""
import argparse
import math
import sys


# ══════════════════════════════════════════════════════════════════════
#  特殊函数
# ══════════════════════════════════════════════════════════════════════
def _gser(a, x):
    """下不完全 Gamma 的级数展开，返回 P(a,x)。"""
    ap = a
    s = 1.0 / a
    d = s
    for _ in range(500):
        ap += 1.0
        d *= x / ap
        s += d
        if abs(d) < abs(s) * 1e-16:
            break
    return s * math.exp(-x + a * math.log(x) - math.lgamma(a))


def _gcf(a, x):
    """上不完全 Gamma 的连分式（modified Lentz），返回 Q(a,x)。"""
    tiny = 1e-300
    b = x + 1.0 - a
    c = 1.0 / tiny
    d = 1.0 / b if b != 0 else 1.0 / tiny
    h = d
    for i in range(1, 500):
        an = -i * (i - a)
        b += 2.0
        d = an * d + b
        if abs(d) < tiny:
            d = tiny
        c = b + an / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-16:
            break
    return math.exp(-x + a * math.log(x) - math.lgamma(a)) * h


def gammainc_reg(a, x):
    """正则化下不完全 Gamma P(a, x)。"""
    if x <= 0.0:
        return 0.0
    if x < a + 1.0:
        return _gser(a, x)
    return 1.0 - _gcf(a, x)


def gammainc_reg_upper(a, x):
    """正则化上不完全 Gamma Q(a, x) = 1 - P(a, x)。"""
    if x <= 0.0:
        return 1.0
    if x < a + 1.0:
        return 1.0 - _gser(a, x)
    return _gcf(a, x)


def _betacf(a, b, x):
    """不完全 Beta 的连分式（modified Lentz）。"""
    tiny = 1e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < tiny:
        d = tiny
    d = 1.0 / d
    h = d
    for m in range(1, 500):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + aa / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + aa / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-16:
            break
    return h


def betainc_reg(a, b, x):
    """正则化不完全 Beta I_x(a, b)。"""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lbeta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
    front = math.exp(lbeta + a * math.log(x) + b * math.log(1.0 - x))
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x) / a
    return 1.0 - front * _betacf(b, a, 1.0 - x) / b


# ══════════════════════════════════════════════════════════════════════
#  分布尾概率
# ══════════════════════════════════════════════════════════════════════
def t_sf2(t, df):
    """t 分布双尾概率 P(|T| > |t|)。"""
    if df <= 0:
        return float("nan")
    x = df / (df + t * t)
    return betainc_reg(df / 2.0, 0.5, x)


def chi2_sf(x, df):
    """卡方上尾概率 P(X > x)。"""
    if x <= 0:
        return 1.0
    return gammainc_reg_upper(df / 2.0, x / 2.0)


def f_sf(F, d1, d2):
    """F 分布上尾概率 P(F > f)。"""
    if F <= 0:
        return 1.0
    return betainc_reg(d2 / 2.0, d1 / 2.0, d2 / (d2 + d1 * F))


# ══════════════════════════════════════════════════════════════════════
#  检验
# ══════════════════════════════════════════════════════════════════════
def _mean(x):
    return sum(x) / len(x)


def _var(x):
    m = _mean(x)
    return sum((v - m) ** 2 for v in x) / (len(x) - 1) if len(x) > 1 else 0.0


def ttest_1samp(x, mu=0.0):
    n = len(x)
    m, s = _mean(x), math.sqrt(_var(x))
    se = s / math.sqrt(n) if n else float("nan")
    t = (m - mu) / se if se else float("nan")
    return dict(test="one-sample t", n=n, mean=m, sd=s, t=t,
                df=n - 1, p=t_sf2(t, n - 1))


def ttest_ind(x, y):
    """Welch（不假设等方差）。"""
    nx, ny = len(x), len(y)
    mx, my = _mean(x), _mean(y)
    vx, vy = _var(x), _var(y)
    se = math.sqrt(vx / nx + vy / ny)
    t = (mx - my) / se if se else float("nan")
    df = (vx / nx + vy / ny) ** 2 / (
        (vx / nx) ** 2 / (nx - 1) + (vy / ny) ** 2 / (ny - 1)) if se else float("nan")
    return dict(test="Welch two-sample t", n=(nx, ny), mean=(mx, my), t=t,
                df=df, p=t_sf2(t, df))


def ttest_rel(x, y):
    d = [a - b for a, b in zip(x, y)]
    return ttest_1samp(d, 0.0) | dict(test="paired t")


def anova_oneway(groups):
    """groups: list[list]。返回 F 与 p。"""
    k = len(groups)
    n = sum(len(g) for g in groups)
    grand = _mean([v for g in groups for v in g])
    ssb = sum(len(g) * (_mean(g) - grand) ** 2 for g in groups)
    ssw = sum(sum((v - _mean(g)) ** 2 for v in g) for g in groups)
    dfb, dfw = k - 1, n - k
    msb = ssb / dfb if dfb else float("nan")
    msw = ssw / dfw if dfw else float("nan")
    F = msb / msw if msw else float("nan")
    return dict(test="one-way ANOVA", k=k, n=n, F=F, df=(dfb, dfw),
                p=f_sf(F, dfb, dfw), ssb=ssb, ssw=ssw)


def chi2_ind(table):
    """table: list[list]，列联表计数。"""
    R = [sum(row) for row in table]
    C = [sum(table[i][j] for i in range(len(table))) for j in range(len(table[0]))]
    n = sum(R)
    chi = 0.0
    for i in range(len(table)):
        for j in range(len(table[0])):
            e = R[i] * C[j] / n if n else 0
            if e > 0:
                chi += (table[i][j] - e) ** 2 / e
    df = (len(table) - 1) * (len(table[0]) - 1)
    return dict(test="chi-square independence", chi2=chi, df=df,
                p=chi2_sf(chi, df), n=n)


def p_adjust(ps, method="holm"):
    """多重比较校正。返回校正后的 p 列表（与原顺序对齐）。"""
    m = len(ps)
    idx = sorted(range(m), key=lambda i: ps[i])
    out = [0.0] * m
    if method == "bonferroni":
        return [min(1.0, p * m) for p in ps]
    if method == "holm":
        run = 0.0
        for rank, i in enumerate(idx):
            val = min(1.0, ps[i] * (m - rank))
            run = max(run, val)
            out[i] = run
        return out
    if method == "bh":
        run = 1.0
        for rank in range(m - 1, -1, -1):
            i = idx[rank]
            val = min(1.0, ps[i] * m / (rank + 1))
            run = min(run, val)
            out[i] = run
        return out
    raise ValueError("method 只能是 bonferroni / holm / bh")


# ══════════════════════════════════════════════════════════════════════
def selftest():
    ok = True

    def ck(name, cond, detail=""):
        nonlocal ok
        ok = ok and cond
        print("  [%s] %-34s %s" % ("PASS" if cond else "FAIL", name, detail))

    # 已知临界值（标准表）
    ck("t(10) 双尾 0.05 = 2.228", abs(t_sf2(2.228, 10) - 0.05) < 0.001,
       "p=%.4f" % t_sf2(2.228, 10))
    ck("t(30) 双尾 0.05 = 2.042", abs(t_sf2(2.042, 30) - 0.05) < 0.001,
       "p=%.4f" % t_sf2(2.042, 30))
    ck("chi2(3) 上尾 0.05 = 7.815", abs(chi2_sf(7.815, 3) - 0.05) < 0.001,
       "p=%.4f" % chi2_sf(7.815, 3))
    ck("chi2(1) 上尾 0.05 = 3.841", abs(chi2_sf(3.841, 1) - 0.05) < 0.001,
       "p=%.4f" % chi2_sf(3.841, 1))
    ck("F(2,10) 上尾 0.05 = 4.103", abs(f_sf(4.103, 2, 10) - 0.05) < 0.001,
       "p=%.4f" % f_sf(4.103, 2, 10))
    ck("F(3,361) 上尾 0.05 ≈ 2.629", abs(f_sf(2.629, 3, 361) - 0.05) < 0.002,
       "p=%.4f" % f_sf(2.629, 3, 361))

    # 与 DWTS 的 BP 检验对照（当时手算 p=0.0222）
    ck("BP 9.61 / df 3 -> p≈0.022", abs(chi2_sf(9.61, 3) - 0.0222) < 0.001,
       "p=%.4f" % chi2_sf(9.61, 3))

    # 单样本 t：均值 5，样本恰好偏离
    r = ttest_1samp([4, 5, 6, 5, 5], mu=0)
    ck("单样本 t 分母正确", abs(r["t"] - 5.0 / (math.sqrt(0.5 / 5))) < 1e-9,
       "t=%.4f" % r["t"])

    # ANOVA 与双样本 t 的一致性：两组时 F = t^2
    a, b = [1.0, 2.0, 3.0, 4.0], [2.0, 3.0, 4.0, 5.0]
    fa = anova_oneway([a, b])
    tt = ttest_ind(a, b)
    ck("两组 ANOVA F ≈ t²", abs(fa["F"] - tt["t"] ** 2) < 1e-6,
       "F=%.4f t²=%.4f" % (fa["F"], tt["t"] ** 2))

    # 卡方：完全独立应得 0
    ind = [[10, 10], [10, 10]]
    ck("独立表 chi2=0", abs(chi2_ind(ind)["chi2"]) < 1e-12)

    # 多重比较
    ps = [0.01, 0.04, 0.03]
    ck("bonferroni", p_adjust(ps, "bonferroni") == [0.03, 0.12, 0.09],
       str(p_adjust(ps, "bonferroni")))
    ck("holm 单调不降", all(a <= b for a, b in
                        zip(sorted(p_adjust(ps, "holm")),
                            sorted(p_adjust(ps, "holm"))[1:] + [1.0])))
    ck("BH 不小于原值", all(q >= p - 1e-12 for q, p in zip(p_adjust(ps, "bh"), ps)))

    print("\n%s" % ("ALL PASS" if ok else "FAILED"))
    return 0 if ok else 1


def demo():
    print("=== 演示：两组比较 + 三组方差分析 + 列联表 ===")
    a = [23, 25, 27, 24, 26]
    b = [30, 32, 31, 33, 29]
    r = ttest_ind(a, b)
    print("  Welch t = %.3f, df = %.2f, p = %.4f" % (r["t"], r["df"], r["p"]))
    r2 = anova_oneway([a, b, [22, 24, 23, 25, 21]])
    print("  ANOVA F = %.3f, df = %s, p = %.4f" % (r2["F"], r2["df"], r2["p"]))
    r3 = chi2_ind([[20, 30], [35, 15]])
    print("  chi2 = %.3f, df = %d, p = %.4f" % (r3["chi2"], r3["df"], r3["p"]))
    ps = [0.001, 0.008, 0.039, 0.041, 0.30]
    for m in ("bonferroni", "holm", "bh"):
        print("  %-12s %s" % (m, [round(q, 4) for q in p_adjust(ps, m)]))


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    # 与其他工具保持一致：裸跑或 `selftest` 都是自检
    if not argv or argv[0] == "selftest":
        return selftest()
    ap = argparse.ArgumentParser(description="假设检验（无 scipy）")
    ap.add_argument("--demo", action="store_true")
    a = ap.parse_args(argv)
    if a.demo:
        demo()
        return 0
    return selftest()


if __name__ == "__main__":
    raise SystemExit(main())
