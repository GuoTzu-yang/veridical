#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""e_verify.py —— E 的验收器：按交稿口径（单点严判）逐题核验。只读。

用法:
    python tools/e_verify.py                 # 5 道红题 + out/final
    python tools/e_verify.py --all           # runs.json 全部
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import freeze                    # noqa: E402
import untraced as U             # noqa: E402
import gate as G                 # noqa: E402

FIVE = ["age_struct", "nflis", "multiobjective", "icm2006c", "pop_panel"]


def check(d):
    """按该目录**自己的**口径核验：交稿才用单点严判 + 严来源。

    模板卷用 gate 的同一判据（single_point/strict_source 都关）——
    我第一版在这里硬写 True，于是 5 篇模板卷的 numbers 明明 100%
    可溯源，仍报 FAIL，原因只是冻结表没写 generated_from（A2 护栏，
    而 A2 本来就只对交稿生效）。判据跟着主张走。
    """
    tex = os.path.join(d, "paper.tex")
    fz = os.path.join(d, "冻结数字.json")
    if not (os.path.exists(tex) and os.path.exists(fz)):
        return None
    deliverable = G._is_deliverable(d)
    frozen = json.load(io.open(fz, encoding="utf-8"))
    dv = U.data_values_of(U.find_data_file(d))
    r = freeze.check_paper(io.open(tex, encoding="utf-8").read(), frozen,
                           single_point=deliverable,
                           data_values=dv, strict_source=deliverable)
    r["deliverable"] = deliverable
    r["has_generated_from"] = bool(str(frozen.get("generated_from") or "").strip())
    return r


def main(argv):
    cfg = json.load(io.open(os.path.join(HERE, "runs.json"), encoding="utf-8"))
    names = FIVE
    if "--all" in argv:
        names = list(cfg.keys())
    bad = 0
    print("%-16s %-11s %-8s %-7s %-10s %s"
          % ("题", "溯源", "判决", "整数未判", "是否交稿", "剩余未溯源"))
    print("-" * 92)
    for nm in names:
        d = os.path.join(HERE, cfg[nm]["out"])
        rd = check(d)
        if rd is None:
            print("%-16s 缺 paper.tex 或 冻结数字.json" % nm)
            continue
        flag = "OK" if rd["ok"] else "**FAIL**"
        if not rd["ok"]:
            bad += 1
        # 红队独立验收 §3-③：验收器必须和 gate 报同一条边界，
        # 否则拿验收器看会看不见「整数未纳入判定」这件事。
        print("%-16s %4d/%-4d  %-8s %-7d %-10s %s"
              % (nm, rd["n_traced"], rd["n_numbers"], flag,
                 int(rd.get("n_int_not_judged") or 0),
                 "交稿" if rd["deliverable"] else "模板卷",
                 rd["untraced"][:8]))
        if rd["high_precision_untraced"]:
            print("                 高精度未溯源（会判死交稿）：%s"
                  % rd["high_precision_untraced"])
        if rd.get("reasons"):
            print("                 判死理由：%s" % "；".join(rd["reasons"]))
    # 交付物
    d = os.path.join(HERE, "out", "final")
    if os.path.isdir(d):
        rd = check(d)
        if rd:
            print("-" * 88)
            print("%-16s %4d/%-4d  %-8s %-10s gen_from=%s"
                  % ("out/final", rd["n_traced"], rd["n_numbers"],
                     "OK" if rd["ok"] else "**FAIL**",
                     "交稿" if rd["deliverable"] else "模板卷",
                     rd["has_generated_from"]))
            if not rd["ok"]:
                bad += 1
    print("-" * 88)
    print("红题数：%d" % bad)
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
