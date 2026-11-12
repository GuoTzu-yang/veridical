"""论文全部实验：一次跑完，产出所有 CSV + JSON。

论文里每一个数都由本脚本生成，命令见 README：
    python tools/arch_experiment.py
产出（out/arch/）：
    abilities.csv        表 1：能力成本（10 次自检实测）
    greedy_vs_opt.csv    图 2 数据：贪婪 vs 最优（8 个预算）
    rate_width.csv       图 3 数据：Wilson 半宽随 n 变化
    layers.csv           表 4：分层耗时分解
    topsis.csv           表 5：TOPSIS 贴近度与排序
    experiment.json      汇总（供正文数字核对）
"""
import csv
import json
import math
import os
import statistics
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import numpy as np                                       # noqa: E402
from tools.mip import mip                                   # noqa: E402
from tools.topsis import topsis, entropy_weights            # noqa: E402

OUT = os.path.join(HERE, "out", "arch")
PY = r"C:\Users\21246\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"

TOOLS = [("topsis", 5), ("stat_tests", 13), ("queueing", 16), ("net_metrics", 14),
         ("fit_params", 5), ("mip", 13), ("dp", 27)]
# 30 次而不是 10 次：实测发现单次启动的抖动（0.112 vs 0.114 s）足以改变
# 贪心与整数最优在某些预算下是否并列，进而改变论文的主张。测量必须比被测
# 的效应更稳。
N_RUNS = 30


def measure_tools():
    """读已冻结的测量结果；没有才测。

    冻结是必须的：实测抖��（0.112 vs 0.114 s）足以改变贪心与整数最优是否
    并列，进而改变论文的主张。若每次重跑都重新测量，论文里的数就不可复现。
    首次运行会写出 abilities.csv，之后所有下游计算都用它。
    """
    p = os.path.join(OUT, "abilities.csv")
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        for r in rows:
            for k in ("checks", "pass_rate"):
                r[k] = int(r[k])
            for k in ("cost_s", "sd_s", "eta", "cv"):
                r[k] = float(r[k])
        print("   （使用冻结的 abilities.csv）")
        return rows
    rows = []
    for name, nchk in TOOLS:
        ts, ok = [], 0
        for _ in range(N_RUNS):
            t0 = time.perf_counter()
            r = subprocess.run([PY, os.path.join("tools", name + ".py"), "selftest"],
                               capture_output=True, text=True, encoding="utf-8",
                               cwd=HERE)
            ts.append(time.perf_counter() - t0)
            if "ALL PASS" in (r.stdout or ""):
                ok += 1
        m = statistics.mean(ts)
        sd = statistics.stdev(ts)
        rows.append(dict(tool=name, checks=nchk, cost_s=round(m, 3),
                         sd_s=round(sd, 3), eta=round(nchk / m, 1),
                         cv=round(sd / m, 4), pass_rate=ok))
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print("   写出并冻结 abilities.csv")
    return rows


def coverage_opt(cost, checks):
    """P1a：覆盖四小问需求 + 自检 >= 70，最小化总耗时。"""
    names = [t[0] for t in TOOLS]
    n = len(names)
    idx = {nm: i for i, nm in enumerate(names)}
    A = [[-c for c in checks]]
    b = [-70]
    for nm in ("stat_tests", "fit_params"):
        r = [0.0] * n
        r[idx[nm]] = -1.0
        A.append(r)
        b.append(-1)
    r = [0.0] * n
    for nm in ("topsis", "mip", "dp"):
        r[idx[nm]] = -1.0
    A.append(r)
    b.append(-1)
    for i in range(n):
        rr = [0.0] * n
        rr[i] = 1.0
        A.append(rr)
        b.append(50)
    res = mip(cost, A, b, ["int"] * n, maximize=False)
    x = [int(round(v)) for v in res["x"]]
    return dict(
        cost_s=round(sum(x[i] * cost[i] for i in range(n)), 3),
        checks=sum(x[i] * checks[i] for i in range(n)),
        mix="; ".join("%s x%d" % (names[i], x[i]) for i in range(n) if x[i] > 0),
        x=x)


def wilson(k, n, z=1.96):
    if n == 0:
        return 0.0, 0.0
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - h, c + h


def rate_curve():
    """半宽 <= 0.05 需要多少样本（p 取 8/22）。"""
    p = 8 / 22
    rows, need = [], None
    for n in range(10, 401, 5):
        lo, hi = wilson(int(round(n * p)), n)
        rows.append(dict(n=n, lo=round(lo, 4), hi=round(hi, 4),
                         width=round(hi - lo, 4)))
        if need is None and (hi - lo) / 2 <= 0.05:
            need = n
    return rows, need


def greedy_vs_opt(cost, checks):
    n = len(cost)

    def greedy(price):
        order = sorted(range(n), key=lambda i: -checks[i] / cost[i])
        rem, x = price, [0] * n
        for i in order:
            k = int(rem // cost[i] + 1e-12)
            x[i] = k
            rem -= k * cost[i]
        return x

    def opt(price):
        A, b = [list(cost)], [price]
        for i in range(n):
            r = [0.0] * n
            r[i] = 1.0
            A.append(r)
            b.append(100)
        r = mip(checks, A, b, ["int"] * n)
        return [int(round(v)) for v in r["x"]]

    rows = []
    for price in (0.50, 0.585, 0.60, 0.70, 0.75, 0.80, 1.00, 1.20):
        gx, ox = greedy(price), opt(price)
        rows.append(dict(
            budget=price,
            greedy_checks=sum(gx[i] * checks[i] for i in range(n)),
            greedy_cost=round(sum(gx[i] * cost[i] for i in range(n)), 3),
            opt_checks=sum(ox[i] * checks[i] for i in range(n)),
            opt_cost=round(sum(ox[i] * cost[i] for i in range(n)), 3),
            opt_mix="; ".join("%s x%d" % (TOOLS[i][0], ox[i])
                              for i in range(n) if ox[i] > 0)))
    return rows


def main():
    os.makedirs(OUT, exist_ok=True)

    print("== 1/5 实测能力成本（%d 次/工具）==" % N_RUNS)
    ab = measure_tools()
    cost = [r["cost_s"] for r in ab]
    checks = [r["checks"] for r in ab]
    for r in ab:
        print("   %-12s %2d 项  %.3f s  η=%.1f  cv=%.4f  %d/%d"
              % (r["tool"], r["checks"], r["cost_s"], r["eta"], r["cv"],
                 r["pass_rate"], N_RUNS))

    print("== 2/5 覆盖约束下的最优路由（P1a）==")
    cov = coverage_opt(cost, checks)
    print("   最小耗时 %.3f s，自检 %d 项：%s"
          % (cov["cost_s"], cov["checks"], cov["mix"]))

    print("== 3/5 预算约束下的最大检查数（P1b）与贪心对比 ==")
    gv = greedy_vs_opt(cost, checks)
    for r in gv:
        print("   预算 %.3f  贪婪 %3d  最优 %3d  差 %d"
              % (r["budget"], r["greedy_checks"], r["opt_checks"],
                 r["greedy_checks"] - r["opt_checks"]))
    best_budget = max(gv, key=lambda r: r["opt_checks"] / r["budget"])
    print("   0.60 s 预算：最优 %d 项（%s）"
          % (next(r["opt_checks"] for r in gv if abs(r["budget"] - 0.6) < 1e-9),
             next(r["opt_mix"] for r in gv if abs(r["budget"] - 0.6) < 1e-9)))

    print("== 4/5 失败率区间与所需样本 ==")
    rc, need = rate_curve()
    lo, hi = wilson(8, 22)
    print("   Wilson 8/22 = [%.4f, %.4f]  半宽 %.4f" % (lo, hi, (hi - lo) / 2))
    print("   半宽 <= 0.05 需要 n >= %d" % need)

    print("== 4/5 TOPSIS 排名 ==")
    X = np.array([[r["checks"], r["cost_s"], r["cv"]] for r in ab], dtype=float)
    dirs = ["benefit", "cost", "cost"]
    w = entropy_weights(X)
    tr = topsis(X, w, dirs)
    order = sorted(range(len(ab)), key=lambda i: -tr["closeness"][i])
    tp = []
    for rank, i in enumerate(order, 1):
        tp.append(dict(tool=ab[i]["tool"], closeness=round(float(tr["closeness"][i]), 3),
                       rank=rank))
        print("   %d. %-12s C=%.3f" % (rank, ab[i]["tool"], tr["closeness"][i]))
    print("   熵权 %s" % [round(float(x), 3) for x in w])

    print("== 5/5 分层耗时（本轮实测，不使用手写估计值）==")
    # 早期版本把 4.6 s / 3-20 s / 25.1 s 直接写进 print 语句，是估计值不是仪表
    # 读数，评审一眼看出加不起来。现在整层耗时全部在本脚本内现场测量：可重跑，
    # 也就可被核对。
    import shutil
    ver = []
    for rd in ("age_struct", "birth_rate", "chemical"):
        dd = os.path.join(HERE, "out", "runs", rd)
        if not os.path.isdir(dd):
            continue
        t0 = time.perf_counter()
        for script in ("gate.py", "verify.py", "falsify.py", "lanes.py"):
            sp = os.path.join(HERE, script)
            if os.path.exists(sp):
                subprocess.run([PY, sp, dd], capture_output=True)
        ver.append(time.perf_counter() - t0)
    ver_s = statistics.median(ver) if ver else float("nan")

    tex = os.path.join(OUT, "paper.tex")
    pdf = shutil.which("pdflatex") or r"C:\Users\21246\AppData\Local\Programs\MiKTeX\miktex\bin\x64\pdflatex.exe"
    cmp_s = float("nan")
    if os.path.exists(tex) and os.path.exists(pdf):
        t0 = time.perf_counter()
        for _ in range(2):
            subprocess.run([pdf, "-interaction=nonstopmode", "-halt-on-error",
                            "paper.tex"], cwd=OUT, capture_output=True)
        cmp_s = time.perf_counter() - t0

    # 端到端：一次真实出稿的墙钟，来自 out/arch/时间与质量.md（04:19:00 -> 04:37:44）
    E2E_S = 1124.0
    plug_s = sum(cost)
    mach_s = plug_s + ver_s + cmp_s
    agent_s = E2E_S - mach_s
    print("   能力层 %.3f s | 验证层 %.2f s | 编译 %.2f s | 机器小计 %.2f s"
          % (plug_s, ver_s, cmp_s, mach_s))
    print("   端到端 %.0f s -> agent 层 %.0f s（占 %.1f%%）"
          % (E2E_S, agent_s, 100 * agent_s / E2E_S))

    def pct(v):
        return round(100 * v / E2E_S, 1)

    layers = [
        dict(layer="Plugin layer (7 capabilities, 93 checks)",
             cost_s=round(plug_s, 3), share_pct=pct(plug_s)),
        dict(layer="Verification (gate, provenance, falsify, lanes)",
             cost_s=round(ver_s, 2), share_pct=pct(ver_s)),
        dict(layer="Compilation (two pdflatex passes)",
             cost_s=round(cmp_s, 2), share_pct=pct(cmp_s)),
        dict(layer="Machine subtotal, measured",
             cost_s=round(mach_s, 2), share_pct=pct(mach_s)),
        dict(layer="Agent layer (LLM), residual",
             cost_s=round(agent_s, 0), share_pct=pct(agent_s)),
        dict(layer="End-to-end, one paper",
             cost_s=E2E_S, share_pct=100.0),
    ]

    def dump(name, rows):
        p = os.path.join(OUT, name)
        with open(p, "w", newline="", encoding="utf-8") as f:
            wcsv = csv.DictWriter(f, fieldnames=list(rows[0]))
            wcsv.writeheader()
            wcsv.writerows(rows)
        print("   写出 %s" % name)

    dump("abilities.csv", ab)
    dump("greedy_vs_opt.csv", gv)
    dump("rate_width.csv", rc)
    dump("topsis.csv", tp)
    dump("layers.csv", layers)

    summary = dict(
        abilities=ab,
        coverage=cov,
        greedy_vs_opt=gv,
        rate=dict(point=8 / 22, wilson=[round(lo, 4), round(hi, 4)],
                  half_width=round((hi - lo) / 2, 4), n_needed=need),
        topsis=dict(weights=[round(float(x), 3) for x in w], ranking=tp),
        layers=layers,
        layers_meta=dict(e2e_s=E2E_S, machine_s=round(mach_s, 2),
                         agent_s=round(agent_s, 0),
                         agent_share_pct=pct(agent_s),
                         machine_share_pct=pct(mach_s),
                         verification_runs=len(ver)),
        total_capability_s=round(sum(cost), 3),
        total_checks=sum(checks),
        efficiency_ratio=round(max(checks[i] / cost[i] for i in range(len(cost))) /
                               min(checks[i] / cost[i] for i in range(len(cost))), 1),
    )
    with open(os.path.join(OUT, "experiment.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print("   写出 experiment.json")
    print("\n全部完成。摘要数字：")
    print("   能力层合计 %.3f s，自检 %d 项，效率差 %.1f 倍"
          % (summary["total_capability_s"], summary["total_checks"],
             summary["efficiency_ratio"]))
    print("   失败率 Wilson %s，n>=%d" % (summary["rate"]["wilson"], need))


if __name__ == "__main__":
    main()
