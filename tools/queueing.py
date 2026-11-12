"""排队论解析解（M/M/1、M/M/c、有限容量），含成本最优服务台数。

为什么需要
----------
`runs.json` 里就有排队题（"simulation of queueing waiting time vs staffing cost"），
而插件只有蒙特卡洛仿真，没有解析公式。排队题的答案通常是「配几个人最优」，
那需要 Lq/Wq 的闭式表达再对成本求最小 —— 仿真给不了这个。

公式（标准结果）
----------------
M/M/1：ρ=λ/μ, P0=1-ρ, L=ρ/(1-ρ), Lq=ρ²/(1-ρ), W=1/(μ-λ), Wq=ρ/(μ-λ)
M/M/c：ρ=λ/(cμ)，Erlang-C 得 P(wait)，Lq=P(wait)·ρ/(1-ρ)，Wq=Lq/λ
M/M/1/K：ρ=λ/μ，P0=(1-ρ)/(1-ρ^(K+1))，P_K 为损失率，有效到达率 λ(1-P_K)

成本模型（排队题的标准做法）
--------------------------
    TC(c) = c·Cs + λ_eff·Wq(c)·Cw
Cs = 每个服务台单位时间成本，Cw = 每个顾客单位等待时间成本。
对 c 从 1 枚举到 max_c，取 TC 最小 —— 因为 c 是整数且范围小，枚举即全局最优。

用法
    python tools/queueing.py selftest
    python tools/queueing.py --lam 4 --mu 1.2            # 单服务台单值
    python tools/queueing.py --lam 4 --mu 1.2 --cs 10 --cw 25 --max-c 8
"""
import argparse
import math
import sys


# ── M/M/1 ──────────────────────────────────────────────────────────────
def mm1(lam, mu):
    if lam >= mu:
        return dict(model="M/M/1", stable=False, rho=lam / mu,
                    note="λ≥μ，队列不稳定（Lq 发散）")
    rho = lam / mu
    L = rho / (1 - rho)
    Lq = rho * rho / (1 - rho)
    W = 1.0 / (mu - lam)
    Wq = rho / (mu - lam)
    return dict(model="M/M/1", stable=True, rho=rho, P0=1 - rho,
                L=L, Lq=Lq, W=W, Wq=Wq,
                Pn=lambda n: (1 - rho) * rho ** n)


# ── M/M/c ──────────────────────────────────────────────────────────────
def _erlang_c(lam, mu, c):
    """Erlang-C：到达后需等待的概率。"""
    a = lam / mu                       # offered load
    rho = a / c
    if rho >= 1:
        return None
    # 用递推算 Σ a^n/n!，避免阶乘溢出
    s = 0.0
    term = 1.0
    for n in range(c):
        if n > 0:
            term *= a / n
        s += term
    term_c = term * (a / c) / (1 - rho) if c > 0 else 0.0
    return term_c / (s + term_c)


def mmc(lam, mu, c):
    a = lam / mu
    rho = a / c
    if rho >= 1:
        return dict(model="M/M/c", c=c, stable=False, rho=rho,
                    note="ρ≥1，队列不稳定")
    pw = _erlang_c(lam, mu, c)
    Lq = pw * rho / (1 - rho)
    Wq = Lq / lam
    W = Wq + 1.0 / mu
    L = lam * W
    P0 = 1.0 / (sum(a ** n / math.factorial(n) for n in range(c))
                + a ** c / math.factorial(c) / (1 - rho))
    return dict(model="M/M/c", c=c, stable=True, rho=rho, P_wait=pw,
                P0=P0, Lq=Lq, Wq=Wq, W=W, L=L)


# ── M/M/1/K（有限容量） ────────────────────────────────────────────────
def mm1k(lam, mu, K):
    rho = lam / mu
    if abs(rho - 1.0) < 1e-12:
        P0 = 1.0 / (K + 1)
        Pn = [P0] * (K + 1)
    else:
        P0 = (1 - rho) / (1 - rho ** (K + 1))
        Pn = [P0 * rho ** n for n in range(K + 1)]
    Ploss = Pn[K]
    lam_eff = lam * (1 - Ploss)
    L = sum(n * Pn[n] for n in range(K + 1))
    Lq = L - (1 - Ploss)
    W = L / lam_eff if lam_eff > 0 else float("inf")
    Wq = Lq / lam_eff if lam_eff > 0 else float("inf")
    return dict(model="M/M/1/K", K=K, rho=rho, P_loss=Ploss, lam_eff=lam_eff,
                L=L, Lq=Lq, W=W, Wq=Wq)


# ── 成本最优 ────────────────────────────────────────────────────────────
def optimal_servers(lam, mu, cs=1.0, cw=1.0, max_c=20):
    """枚举 c，最小化 TC = c·Cs + λ·Wq(c)·Cw。返回 (最优 c, 表)。"""
    rows = []
    best = None
    for c in range(1, max_c + 1):
        r = mmc(lam, mu, c)
        if not r.get("stable"):
            rows.append(dict(c=c, stable=False, total=None))
            continue
        wait_cost = lam * r["Wq"] * cw
        serve_cost = c * cs
        tc = serve_cost + wait_cost
        rows.append(dict(c=c, rho=r["rho"], Wq=r["Wq"], Lq=r["Lq"],
                         serve_cost=serve_cost, wait_cost=wait_cost,
                         total=tc, stable=True))
        if best is None or tc < best[1]:
            best = (c, tc)
    return best, rows


def selftest():
    ok = True

    def ck(name, cond, detail=""):
        nonlocal ok
        ok = ok and cond
        print("  [%s] %-32s %s" % ("PASS" if cond else "FAIL", name, detail))

    # M/M/1：λ=2, μ=3 → ρ=2/3, L=2, Lq=4/3, W=1, Wq=2/3
    r = mm1(2.0, 3.0)
    ck("M/M/1 ρ=2/3", abs(r["rho"] - 2 / 3) < 1e-12)
    ck("M/M/1 L=2", abs(r["L"] - 2.0) < 1e-12, "%.6f" % r["L"])
    ck("M/M/1 Lq=4/3", abs(r["Lq"] - 4 / 3) < 1e-12, "%.6f" % r["Lq"])
    ck("M/M/1 W=1", abs(r["W"] - 1.0) < 1e-12, "%.6f" % r["W"])
    ck("M/M/1 Wq=2/3", abs(r["Wq"] - 2 / 3) < 1e-12, "%.6f" % r["Wq"])
    # Little 定律 L = λW
    ck("Little 定律 L=λW", abs(r["L"] - 2.0 * r["W"]) < 1e-12)

    # M/M/c：c=1 应退化为 M/M/1
    r1 = mmc(2.0, 3.0, 1)
    ck("M/M/c 在 c=1 退化为 M/M/1",
       abs(r1["Lq"] - r["Lq"]) < 1e-9 and abs(r1["Wq"] - r["Wq"]) < 1e-9,
       "Lq=%.6f vs %.6f" % (r1["Lq"], r["Lq"]))

    # M/M/c 加服务台应降低等待
    r2 = mmc(4.0, 1.2, 4)
    r3 = mmc(4.0, 1.2, 5)
    ck("加服务台降低 Wq", r3["Wq"] < r2["Wq"],
       "%.4f -> %.4f" % (r2["Wq"], r3["Wq"]))

    # 不稳定判定
    ck("λ≥μ 判不稳定", not mm1(3.0, 3.0)["stable"])
    ck("ρ≥1 的 M/M/c 判不稳定", not mmc(6.0, 1.0, 5)["stable"])

    # M/M/1/K：K=1 时退化为损失制（M/M/1/1），P_loss = ρ/(1+ρ)
    k1 = mm1k(2.0, 3.0, 1)
    ck("M/M/1/1 损失率 = ρ/(1+ρ)",
       abs(k1["P_loss"] - (2 / 3) / (1 + 2 / 3)) < 1e-9,
       "%.6f" % k1["P_loss"])
    # K 增大应趋近无容量限制的 L
    k_big = mm1k(2.0, 3.0, 200)
    ck("K 很大时 L 趋近 M/M/1", abs(k_big["L"] - r["L"]) < 0.01,
       "%.4f vs %.4f" % (k_big["L"], r["L"]))

    # 成本最优：Cs 远大于 Cw 时只要最小可行台数
    # 注意 λ 必须 < μ，否则最小可行 c = ceil(λ/μ) 不是 1
    b1, _ = optimal_servers(0.8, 1.2, cs=1000.0, cw=1.0, max_c=8)
    ck("服务台极贵 -> 最少台 c=1", b1[0] == 1, "c=%d" % b1[0])
    # 也验证：最小可行 c 会自动跳过不稳定的配置
    b3, rows3 = optimal_servers(4.0, 1.2, cs=1000.0, cw=1.0, max_c=8)
    ck("不稳定配置被跳过（λ/μ=3.33 -> c≥4）", b3[0] == 4, "c=%d" % b3[0])
    ck("c<4 的行标记为不稳定",
       all(not r.get("stable") for r in rows3 if r["c"] < 4))
    # Cw 远大于 Cs 时应多开
    b2, _ = optimal_servers(4.0, 1.2, cs=1.0, cw=1000.0, max_c=8)
    ck("等待极贵 -> c 更多", b2[0] > 3, "c=%d" % b2[0])

    print("\n%s" % ("ALL PASS" if ok else "FAILED"))
    return 0 if ok else 1


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    if not argv or argv[0] == "selftest":
        return selftest()
    ap = argparse.ArgumentParser(description="排队论解析解")
    ap.add_argument("--lam", type=float, required=True)
    ap.add_argument("--mu", type=float, required=True)
    ap.add_argument("--c", type=int, default=1)
    ap.add_argument("--K", type=int, default=0)
    ap.add_argument("--cs", type=float, default=0.0)
    ap.add_argument("--cw", type=float, default=0.0)
    ap.add_argument("--max-c", type=int, default=10)
    a = ap.parse_args(argv)

    if a.K:
        r = mm1k(a.lam, a.mu, a.K)
        print("M/M/1/K  λ=%.3f μ=%.3f K=%d" % (a.lam, a.mu, a.K))
        for k in ("rho", "P_loss", "lam_eff", "L", "Lq", "W", "Wq"):
            print("  %-8s %.6f" % (k, r[k]))
        return 0
    if a.c > 1:
        r = mmc(a.lam, a.mu, a.c)
        print("M/M/c  λ=%.3f μ=%.3f c=%d" % (a.lam, a.mu, a.c))
        if not r.get("stable"):
            print("  ρ=%.3f ≥1，队列不稳定" % r["rho"])
            return 1
        for k in ("rho", "P_wait", "P0", "Lq", "Wq", "W", "L"):
            print("  %-8s %.6f" % (k, r[k]))
    else:
        r = mm1(a.lam, a.mu)
        print("M/M/1  λ=%.3f μ=%.3f" % (a.lam, a.mu))
        if not r.get("stable"):
            # 不提前 return：单台不稳定恰恰是「该加服务台」的信号，
            # 下面的成本优化会给出最优 c。早期版本在这里 return 1，
            # 等于在最需要它的场景下关掉了它。
            print("  ρ=%.3f ≥1，单台不稳定（需要更多服务台）" % r["rho"])
        else:
            for k in ("rho", "P0", "L", "Lq", "W", "Wq"):
                print("  %-8s %.6f" % (k, r[k]))

    if a.cs > 0 and a.cw > 0:
        best, rows = optimal_servers(a.lam, a.mu, a.cs, a.cw, a.max_c)
        print("\n成本最优（Cs=%.3f, Cw=%.3f）" % (a.cs, a.cw))
        print("  %-4s %-8s %-10s %-12s %-12s %-10s"
              % ("c", "rho", "Wq", "serve_cost", "wait_cost", "total"))
        for row in rows:
            if not row.get("stable"):
                print("  %-4d 不稳定" % row["c"])
                continue
            mark = "  <== 最优" if best and row["c"] == best[0] else ""
            print("  %-4d %-8.4f %-10.4f %-12.3f %-12.3f %-10.3f%s"
                  % (row["c"], row["rho"], row["Wq"], row["serve_cost"],
                     row["wait_cost"], row["total"], mark))
        print("  最优服务台数 c* = %d，总成本 %.3f" % best)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
