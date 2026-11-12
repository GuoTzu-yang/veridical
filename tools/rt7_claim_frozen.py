# -*- coding: utf-8 -*-
"""rt7_claim_frozen.py —— 「冻结表有多少项没人引用」在**全部 23 题**上重算（只读）。

复刻 tools/arch_audit_E.py 的 E 段判据（同一公式，逐字照抄），
但把样本从硬编码的 5 题扩到 runs.json 的全部题：
    hit  ⟺ ∃ token 值 c, |abs(v) - abs(c)| <= 0.5 * 10^-max(0, len(str(v).split('.')[-1]))

同时给出「76%」的几种算法候选，便于核对报告里的 76% 是哪一个。
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import verify as V   # noqa: E402

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def measure(nm, outdir):
    fz = os.path.join(HERE, outdir, "冻结数字.json")
    tex_p = os.path.join(HERE, outdir, "paper.tex")
    if not (os.path.exists(fz) and os.path.exists(tex_p)):
        return None
    items = json.load(io.open(fz, encoding="utf-8")).get("items") or []
    tex = io.open(tex_p, encoding="utf-8").read()
    toks = {tk for tk, _l in V.extract_numbers(tex, skip_meta=False)}
    vals = set()
    for tk in toks:
        try:
            vals.add(abs(float(tk)))
        except ValueError:
            pass
    hit = 0
    for it in items:
        v = abs(it["value"])
        tol = 0.5 * 10 ** -max(0, len(str(v).split(".")[-1]))
        if any(abs(v - c) <= tol for c in vals):
            hit += 1
    return dict(n=len(items), hit=hit, toks=len(toks))


def main():
    cfg = json.load(io.open(os.path.join(HERE, "runs.json"), encoding="utf-8"))
    rows = []
    print("题                  冻结项  论文token  被用到   用到率")
    print("-" * 62)
    for nm, c in cfg.items():
        r = measure(nm, c["out"])
        if r is None:
            print("%-18s 缺 paper.tex 或 冻结数字.json" % nm)
            continue
        rows.append((nm, r))
        print("%-18s %6d %9d %8d %7.1f%%"
              % (nm, r["n"], r["toks"], r["hit"],
                 100.0 * r["hit"] / max(1, r["n"])))
    print("-" * 62)
    tn = sum(r["n"] for _nm, r in rows)
    th = sum(r["hit"] for _nm, r in rows)
    print("全部 %d 题：冻结 %d 项，被用到 %d（%.1f%%）→ 没人引用 %.1f%%"
          % (len(rows), tn, th, 100.0 * th / tn, 100.0 * (tn - th) / tn))

    five = ["age_struct", "nflis", "pop_panel", "icm2006c", "multiobjective"]
    sub = [(nm, r) for nm, r in rows if nm in five]
    sn = sum(r["n"] for _n, r in sub)
    sh = sum(r["hit"] for _n, r in sub)
    print("报告取的那 5 题：冻结 %d 项，被用到 %d（%.1f%%）→ 没人引用 %.1f%%"
          % (sn, sh, 100.0 * sh / sn, 100.0 * (sn - sh) / sn))

    four = [(nm, r) for nm, r in sub if nm != "nflis"]
    fn = sum(r["n"] for _n, r in four)
    fh = sum(r["hit"] for _n, r in four)
    print("去掉 nflis 的 4 题：冻结 %d 项，被用到 %d（%.1f%%）→ 没人引用 %.1f%%"
          % (fn, fh, 100.0 * fh / fn, 100.0 * (fn - fh) / fn))
    un = sum(100.0 * (r["n"] - r["hit"]) / max(1, r["n"]) for _n, r in four) / len(four)
    print("去掉 nflis 的 4 题「各题没引用率」算术平均：%.1f%%" % un)
    return 0


if __name__ == "__main__":
    sys.exit(main())
