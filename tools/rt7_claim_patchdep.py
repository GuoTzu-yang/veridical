# -*- coding: utf-8 -*-
"""rt7_claim_patchdep.py —— 「100% 有多少是靠补丁撑起来的」（只读）。

做法：把冻结表里来自**补丁路径**的条目剔掉，重判每篇的 numbers，
看有多少 token 失去出处。补丁路径按记录原话取：
    rep["cond"] / rep["falsify"] / rep["q5_tradeoff"] / appl* / model_gap_pct

用法: python tools/rt7_claim_patchdep.py
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import freeze          # noqa: E402
import untraced as U   # noqa: E402
import verify as V     # noqa: E402

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

FIVE = ["age_struct", "nflis", "multiobjective", "icm2006c", "pop_panel"]
PATCH_PREFIX = ("cond", "falsify", "q5_tradeoff", "appl", "model_gap_pct")


def is_patch(path):
    p = str(path or "").strip()
    return any(p == x or p.startswith(x) for x in PATCH_PREFIX)


def run(d):
    tex = io.open(os.path.join(d, "paper.tex"), encoding="utf-8").read()
    frozen = json.load(io.open(os.path.join(d, "冻结数字.json"), encoding="utf-8"))
    items = frozen.get("items", [])
    keep = [it for it in items if not is_patch(it.get("path"))]
    trimmed = dict(frozen)
    trimmed["items"] = keep
    try:
        dv = U.data_values_of(U.find_data_file(d))
    except Exception:
        dv = None
    full = freeze.check_paper(tex, frozen, single_point=False,
                             data_values=dv, strict_source=False)
    cut = freeze.check_paper(tex, trimmed, single_point=False,
                            data_values=dv, strict_source=False)
    return (len(items), len(keep), full["n_traced"], full["n_numbers"],
            cut["n_traced"], cut["n_numbers"])


def main():
    cfg = json.load(io.open(os.path.join(HERE, "runs.json"), encoding="utf-8"))
    print("产物            冻结项  去掉补丁项  全表溯源   去补丁后溯源   失去支撑")
    print("-" * 88)
    tot_lost = 0
    for nm in FIVE + ["out/final"]:
        d = os.path.join(HERE, "out", "final") if nm == "out/final" \
            else os.path.join(HERE, cfg[nm]["out"])
        if not os.path.exists(os.path.join(d, "冻结数字.json")):
            continue
        n, nk, t1, n1, t2, n2 = run(d)
        lost = t2 - t1 if n2 == n1 else (t1 - t2)
        tot_lost += max(0, t1 - t2)
        print("%-14s %7d %11d %8d/%-4d %10d/%-4d %8d"
              % (nm, n, nk, t1, n1, t2, n2, max(0, t1 - t2)))
    print("-" * 88)
    print("合计：剔掉补丁路径后失去出处的 token = %d" % tot_lost)
    return 0


if __name__ == "__main__":
    sys.exit(main())
