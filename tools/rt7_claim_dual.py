# -*- coding: utf-8 -*-
"""rt7_claim_dual.py —— 同一份产物，两种口径各报一遍（只读）。

口径 A = gate.chk_numbers → freeze.check_paper（只取带小数的 token，按 (值,精度) 去重）
口径 B = verify.trace（全部 token，含整数，skip_meta=True，不去重）

输出：每条论文 A 与 B 的数字，方便看「100%」是在哪个口径下成立的。
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


def measure_both(d):
    tex_p = os.path.join(d, "paper.tex")
    fz_p = os.path.join(d, "冻结数字.json")
    row = {"dir": d}
    if not os.path.exists(tex_p):
        row["error"] = "no paper.tex"
        return row
    tex = io.open(tex_p, encoding="utf-8").read()

    # ---- 口径 A：gate / freeze ----
    if os.path.exists(fz_p):
        frozen = json.load(io.open(fz_p, encoding="utf-8"))
        try:
            dv = U.data_values_of(U.find_data_file(d))
        except Exception:
            dv = None
        ra = freeze.check_paper(tex, frozen, single_point=False,
                                data_values=dv, strict_source=False)
        row["A_traced"] = ra["n_traced"]
        row["A_numbers"] = ra["n_numbers"]
        row["A_int_not_judged"] = ra["n_int_not_judged"]
        row["A_ok"] = ra["ok"]
        row["A_from_data"] = ra.get("n_from_data")
    else:
        row["A_traced"] = None

    # ---- 口径 B：verify.trace ----
    try:
        outputs = V.load_outputs(d)
        rb = V.trace(tex, outputs)
        row["B_numbers"] = rb["n_numbers"]
        row["B_untraced"] = rb["n_untraced"]
        row["B_ratio"] = round(100.0 * rb["traced_ratio"], 1)
        row["B_first_untraced"] = [x["token"] for x in rb["untraced"][:12]]
    except Exception as e:
        row["B_error"] = repr(e)

    # ---- 原始 token 计数（不分口径）----
    all_toks = V.extract_numbers(tex, skip_meta=False)
    meta_toks = V.extract_numbers(tex, skip_meta=True)
    row["tok_all"] = len(all_toks)
    row["tok_after_meta_filter"] = len(meta_toks)
    row["tok_with_dot"] = sum(1 for t, _ in all_toks if "." in t)
    row["tok_int"] = sum(1 for t, _ in all_toks if "." not in t)
    return row


def main():
    cfg = json.load(io.open(os.path.join(HERE, "runs.json"), encoding="utf-8"))
    targets = [(nm, os.path.join(HERE, cfg[nm]["out"])) for nm in FIVE]
    targets.append(("out/final", os.path.join(HERE, "out", "final")))

    print("题/目录           A(gate口径)  A_整数未判   B(verify口径)   B=未溯源   tok全/带点/整数")
    print("-" * 108)
    rows = []
    for nm, d in targets:
        r = measure_both(d)
        rows.append((nm, r))
        if r.get("error"):
            print(f"{nm:<16} {r['error']}")
            continue
        print("%-16s %4s/%-5s %-11s %4s/%-5s %-9s %s/%s/%s"
              % (nm, r["A_traced"], r["A_numbers"], r["A_int_not_judged"],
                 r.get("B_numbers", 0) - r.get("B_untraced", 0), r.get("B_numbers"),
                 f"{r.get('B_ratio')}%",
                 r["tok_all"], r["tok_with_dot"], r["tok_int"]))
        if r.get("B_untraced"):
            print("                  B 口径下未溯源样例：%s" % r["B_first_untraced"])
    print("-" * 108)
    return rows


if __name__ == "__main__":
    main()
