#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""rt7_repro_twogate.py —— 两口径并列（只读）。

口径 A（gate.numbers）：freeze.check_paper，只判**带小数点**的 token，
        来源池 = 冻结数字.json。
口径 B（verify.py）：verify.trace，判**全部** token，
        来源池 = 目录下所有 .json/.csv。

同时打印 data.json 里登记的历史值，用来判断工件是否已 stale。
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import freeze                    # noqa: E402
import gate as G                 # noqa: E402
import untraced as U             # noqa: E402
import verify as V               # noqa: E402


def gates(d):
    tex = os.path.join(d, "paper.tex")
    fz = os.path.join(d, "冻结数字.json")
    if not (os.path.exists(tex) and os.path.exists(fz)):
        return None
    deliverable = G._is_deliverable(d)
    frozen = json.load(io.open(fz, encoding="utf-8"))
    txt = io.open(tex, encoding="utf-8").read()
    dv = U.data_values_of(U.find_data_file(d))
    a = freeze.check_paper(txt, frozen, single_point=deliverable,
                           data_values=dv, strict_source=deliverable)
    # 口径 B：verify 自己的池
    outs = V.load_outputs(d)
    b = V.trace(txt, outs)
    # 口径 B'：把冻结表从池里剔掉（看两个口径是否真的独立）
    outs_nofz = []
    for root, _dd, ff in os.walk(d):
        for f in ff:
            p = os.path.join(root, f)
            if f == "冻结数字.json" or f.startswith("."):
                continue
            if f.endswith(".json"):
                try:
                    outs_nofz.append(json.load(io.open(p, encoding="utf-8")))
                except (OSError, ValueError):
                    pass
            elif f.endswith(".csv"):
                try:
                    outs_nofz.append(io.open(p, encoding="utf-8",
                                             errors="replace").read())
                except OSError:
                    pass
    b2 = V.trace(txt, outs_nofz)
    n_cand = len(V.extract_numbers(txt))
    n_int = int(a.get("n_int_not_judged") or 0)
    return dict(
        deliv=deliverable,
        A_ok=a["ok"], A_tr=a["n_traced"], A_n=a["n_numbers"],
        A_hi=len(a["high_precision_untraced"]),
        n_int=n_int,
        B_ok=b["ok"], B_tr=b["n_numbers"] - b["n_untraced"], B_n=b["n_numbers"],
        B2_ok=b2["ok"], B2_tr=b2["n_numbers"] - b2["n_untraced"],
        B2_n=b2["n_numbers"],
        B_unt=[u["token"] for u in b["untraced"][:6]],
        B2_unt=[u["token"] for u in b2["untraced"]][:6],
        n_pool_items=len(outs),
    )


def main():
    cfg = json.load(io.open(os.path.join(HERE, "runs.json"), encoding="utf-8"))
    dj = {}
    dp = os.path.join(HERE, "out", "final", "data.json")
    if os.path.exists(dp):
        D = json.load(io.open(dp, encoding="utf-8"))
        for r in D["problems"]:
            nm = r.get("name")
            dj[nm] = r
    hdr = ("%-18s %-7s %-13s %-13s %-13s %s"
           % ("题", "交稿?", "A gate口径", "B verify全量", "B2 去冻结表",
              "data.json 登记(num/gate)"))
    print(hdr)
    print("-" * len(hdr))
    rows = []
    for nm in list(cfg.keys()) + ["__final__"]:
        if nm == "__final__":
            d = os.path.join(HERE, "out", "final")
            label = "out/final"
        else:
            d = os.path.join(HERE, cfg[nm]["out"])
            label = nm
        r = gates(d)
        if r is None:
            print("%-18s 缺文件" % label)
            continue
        ref = dj.get("out/final" if nm == "__final__" else nm) or {}
        hist = ""
        if ref:
            hist = "%s/%s ; %s/%s" % (ref.get("num_ok"), ref.get("num_total"),
                                      ref.get("gate_num_ok"),
                                      ref.get("gate_num_total"))
        print("%-18s %-7s %4d/%-4d %-5s %4d/%-4d %-5s %4d/%-4d %-5s %s"
              % (label,
                 "交稿" if r["deliv"] else "模板",
                 r["A_tr"], r["A_n"], "OK" if r["A_ok"] else "FAIL",
                 r["B_tr"], r["B_n"], "OK" if r["B_ok"] else "FAIL",
                 r["B2_tr"], r["B2_n"], "OK" if r["B2_ok"] else "FAIL",
                 hist))
        rows.append((label, r, ref))
    print()
    print("整数 token 未纳入 gate 判定（会被判死通道）：")
    for label, r, _ in rows:
        print("   %-18s %d" % (label, r["n_int"]))
    print()
    print("B 口径未溯源的 token（前 6 个）：")
    for label, r, _ in rows:
        if r["B_unt"]:
            print("   %-18s %s" % (label, r["B_unt"]))
    print()
    print("B2（把冻结表从池里剔掉）新增未溯源：")
    for label, r, _ in rows:
        if r["B2_tr"] != r["B_tr"]:
            print("   %-18s %d -> %d 个可溯源（差 %d）"
                  % (label, r["B_tr"], r["B2_tr"], r["B_tr"] - r["B2_tr"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
