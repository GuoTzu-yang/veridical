# -*- coding: utf-8 -*-
"""rt7_claim_judge.py —— 同一批 token，两门各自的判决逐例比对（只读）。

门 A = freeze.check_paper 的判据：_match_written（abs 比较，符号丢失）
门 B = verify.trace 的判据：_near（带符号 round 比较）

对每个**带小数**的 token（与 gate 同口径：去重 (值,精度)），分别问两门，
统计「只有 A 认」「只有 B 认」「都不认」的个数，并挑出符号相反的例子。

用法: python tools/rt7_claim_judge.py
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


def verdicts(d):
    tex_p = os.path.join(d, "paper.tex")
    fz_p = os.path.join(d, "冻结数字.json")
    if not (os.path.exists(tex_p) and os.path.exists(fz_p)):
        return None
    tex = io.open(tex_p, encoding="utf-8").read()
    frozen = json.load(io.open(fz_p, encoding="utf-8"))
    fvals = [it["value"] for it in frozen.get("items", [])]
    try:
        dv = U.data_values_of(U.find_data_file(d))
    except Exception:
        dv = None
    pool = V.collect_output_numbers(V.load_outputs(d))

    all_toks = V.extract_numbers(tex, skip_meta=False)
    toks = [t for t, _ in all_toks if "." in t]
    seen, uniq = set(), []
    for tok in toks:
        try:
            v = float(tok)
        except ValueError:
            continue
        dec = V._written_decimals(tok)
        key = (round(v, 6), dec)
        if key in seen:
            continue
        seen.add(key)
        uniq.append((tok, v, dec))

    rows = []
    for tok, v, dec in uniq:
        a = freeze._match_written(v, dec, fvals)
        a_data = False
        if not a and dv and round(v, 6) in dv:
            a, a_data = True, True
        b = any(V._near(v, p, dec) for p in pool)
        # 反号解释：A 认、B 不认时，看是不是靠 abs 才认的
        sign_only = False
        if a and not b:
            sign_only = freeze._match_written(-v, dec, fvals) and not any(
                V._near(-v, p, dec) for p in pool)
        rows.append(dict(tok=tok, v=v, dec=dec, A=a, A_data=a_data, B=b,
                         sign_only=sign_only))
    return rows


def main():
    cfg = json.load(io.open(os.path.join(HERE, "runs.json"), encoding="utf-8"))
    targets = [(nm, os.path.join(HERE, cfg[nm]["out"])) for nm in FIVE]
    targets.append(("out/final", os.path.join(HERE, "out", "final")))

    tot_a_only = tot_b_only = tot_both_no = 0
    print("题           带小数token  A认B不认  B认A不认  都不认   其中「靠abs才认」")
    print("-" * 92)
    for nm, d in targets:
        rows = verdicts(d)
        if rows is None:
            print(f"{nm:<12} 缺 paper.tex 或 冻结数字.json")
            continue
        a_only = [r for r in rows if r["A"] and not r["B"]]
        b_only = [r for r in rows if r["B"] and not r["A"]]
        none_ = [r for r in rows if not r["A"] and not r["B"]]
        signs = [r for r in a_only if r["sign_only"]]
        tot_a_only += len(a_only)
        tot_b_only += len(b_only)
        tot_both_no += len(none_)
        print("%-12s %8d %10d %9d %7d %12d"
              % (nm, len(rows), len(a_only), len(b_only), len(none_), len(signs)))
        for r in a_only[:6]:
            print("      A-only: %-12s v=%r dec=%d%s"
                  % (r["tok"], r["v"], r["dec"],
                     "  ← 只有 abs 能解释（反号）" if r["sign_only"] else ""))
        for r in b_only[:4]:
            print("      B-only: %-12s v=%r dec=%d" % (r["tok"], r["v"], r["dec"]))
    print("-" * 92)
    print("合计：A认B不认 %d ｜ B认A不认 %d ｜ 都不认 %d"
          % (tot_a_only, tot_b_only, tot_both_no))
    return 0


if __name__ == "__main__":
    sys.exit(main())
