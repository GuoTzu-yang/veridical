#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bootstrap_ci.py —— 给「23 题上的统计量」配上区间（第 123 轮）。

为什么必须补（NeurIPS Paper Checklist 第 7 项，Experiment Statistical
Significance）：论文写「median 96.9%、weakest 88.2%」—— 这是 **23 个点上的
统计量**，不是 23 个点本身的性质。中位数在另一个 23 题样本里会变多少？
不给区间，读者只能把它当精确值。

做法：对 23 个溯源率做 bootstrap 重采样（Efron 1979；Efron & Tibshirani 1993），
报中位数的 95% 百分位区间。**种子固定**，结果可复跑。

注意两条边界，写进论文时必须说：
  · 23 个点来自**同一个语料、同一个作者**，bootstrap 只刻画「换一批同类题目」的
    抽样波动，**不刻画换一个语料**的波动。后者大得多，bootstrap 给不出来。
  · 极值（weakest 88.2%）的区间没有意义：极值的抽样分布退化，报它等于假装
    它稳定。所以只报中位数与均值。

用法：
    python tools/bootstrap_ci.py
    python tools/bootstrap_ci.py --json
"""
import io
import json
import os
import random
import statistics
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "out", "final")
SEED = 20261112          # 固定种子：结果可复跑
N_BOOT = 10000


def pct(xs, q):
    """百分位（线性插值）。xs 已排序。"""
    if not xs:
        return None
    if len(xs) == 1:
        return xs[0]
    pos = (len(xs) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def boot(vals, stat, n=N_BOOT, seed=SEED):
    rnd = random.Random(seed)
    k = len(vals)
    out = []
    for _ in range(n):
        s = [vals[rnd.randrange(k)] for _ in range(k)]
        out.append(stat(s))
    out.sort()
    return pct(out, 0.025), pct(out, 0.975)


def main(argv):
    d = json.load(io.open(os.path.join(OUT, "data.json"), encoding="utf-8"))
    strict, loose = [], []
    for p in d["problems"]:
        ok, tot = p.get("num_ok"), p.get("num_total")
        if ok is not None and tot:
            strict.append(100.0 * ok / tot)
        g = p.get("gate_num_pct")
        if g is not None:
            loose.append(float(g))
    res = {}
    for name, vals in (("strict", strict), ("gate_scope", loose)):
        if not vals:
            continue
        med = statistics.median(vals)
        lo, hi = boot(vals, statistics.median)
        res[name] = dict(n=len(vals), median=med, ci_lo=lo, ci_hi=hi,
                         min=min(vals), max=max(vals))
    payload = dict(seed=SEED, n_boot=N_BOOT, stats=res,
                   note="bootstrap 只刻画「换一批同类题」的抽样波动，"
                        "不刻画「换一个语料」的波动；极值不报区间")
    io.open(os.path.join(OUT, "bootstrap_ci.json"), "w", encoding="utf-8",
            newline="\n").write(json.dumps(payload, ensure_ascii=False, indent=1))

    if "--json" in argv:
        print(json.dumps(payload, ensure_ascii=False, indent=1))
        return 0
    print("bootstrap：%d 次重采样，种子 %d" % (N_BOOT, SEED))
    for name, r in res.items():
        print("  %-10s n=%-3d  median=%6.2f%%  95%% CI [%6.2f%%, %6.2f%%]"
              "  范围 %6.2f--%6.2f" % (name, r["n"], r["median"], r["ci_lo"],
                                       r["ci_hi"], r["min"], r["max"]))
    print()
    print("已写 out/final/bootstrap_ci.json")
    print("写进论文时必须同时说明：这只覆盖抽样波动，不覆盖语料更换；")
    print("极值（weakest）不报区间 —— 极值的抽样分布退化，报它等于假装它稳定。")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
