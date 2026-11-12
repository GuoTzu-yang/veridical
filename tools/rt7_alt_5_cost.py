# -*- coding: utf-8 -*-
"""红队第二板探针 5：「0.12 s per report」在什么口径下成立（或都不成立）。

只读，只打印。对 23 篇各测四种口径，报中位/均值/区间。
  ① trace 单篇（verify.trace）
  ② check_paper 单篇（freeze.check_paper，gate 实际走的那条）
  ③ 读产物 + trace
  ④ 读产物 + check_paper
另外把 L376「The frozen table has 713 entries」与 out/final/冻结数字.json 对账。

用法
    python tools/rt7_alt_5_cost.py
"""
import io
import json
import os
import statistics as st
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import freeze as F          # noqa: E402
import untraced as U        # noqa: E402
import verify as V          # noqa: E402

RUNS = json.load(io.open(os.path.join(HERE, "runs.json"), encoding="utf-8"))


def main():
    rows = []
    for name, it in RUNS.items():
        d = os.path.join(HERE, it["out"])
        tp = os.path.join(d, "paper.tex")
        fp = os.path.join(d, "冻结数字.json")
        if not (os.path.exists(tp) and os.path.exists(fp)):
            continue
        tex = io.open(tp, encoding="utf-8").read()
        frozen = json.load(io.open(fp, encoding="utf-8"))
        dv = U.data_values_of(U.find_data_file(d))

        t = time.perf_counter(); V.trace(tex, V.load_outputs(d)); a = time.perf_counter() - t
        t = time.perf_counter()
        F.check_paper(tex, frozen, single_point=False, data_values=dv,
                      strict_source=False)
        b = time.perf_counter() - t
        t = time.perf_counter()
        outs = V.load_outputs(d); V.trace(tex, outs)
        c = time.perf_counter() - t
        t = time.perf_counter()
        outs = V.load_outputs(d)
        F.check_paper(tex, frozen, single_point=False, data_values=dv,
                      strict_source=False)
        e = time.perf_counter() - t
        rows.append((name, a, b, c, e))

    print("== [1] 四种口径的单篇耗时（秒），23 题 ==")
    hdr = ("题", "①trace", "②check_paper", "③读产物+trace", "④读产物+check")
    print("  %-16s %10s %14s %16s %16s" % hdr)
    for r in sorted(rows, key=lambda x: x[1]):
        print("  %-16s %10.4f %14.4f %16.4f %16.4f" % r)
    print()
    print("  %-16s %10s %14s %16s %16s" % ("中位", "", "", "", ""))
    for k, lab in ((1, "①trace"), (2, "②check_paper"), (3, "③读+trace"),
                   (4, "④读+check")):
        vals = [r[k] for r in rows]
        print("  %-14s 中位 %.4fs  均值 %.4fs  最小 %.4fs  最大 %.4fs"
              % (lab, st.median(vals), sum(vals) / len(vals),
                 min(vals), max(vals)))
    print()
    print("  论文 L341 写：measured at 0.12 s per report")
    for k, lab in ((1, "①"), (2, "②"), (3, "③"), (4, "④")):
        vals = [r[k] for r in rows]
        n_ge = sum(1 for v in vals if v >= 0.12)
        print("   口径%s：中位 %s 0.12（中位/0.12 = %.2f）；>=0.12s 的题 %d/%d"
              % (lab, ">=" if st.median(vals) >= 0.12 else "<",
                 st.median(vals) / 0.12, n_ge, len(vals)))
    print()

    print("== [2] L376「The frozen table has 713 entries」与 out/final 对账 ==")
    fzp = os.path.join(HERE, "out", "final", "冻结数字.json")
    fz = json.load(io.open(fzp, encoding="utf-8"))
    n_field = fz.get("n")
    n_items = len(fz.get("items") or [])
    vals = [it.get("value") for it in (fz.get("items") or [])]
    print("   文件：out/final/冻结数字.json")
    print("   字段 n = %s；len(items) = %d；distinct(value) = %d"
          % (n_field, n_items, len(set(vals))))
    print("   论文写 713；三者差值：n→%+d, items→%+d, distinct→%+d"
          % ((n_field or 0) - 713, n_items - 713, len(set(vals)) - 713))
    print("   注：本节作者可能用了别的口径（去重/只算 items），本函数未判定哪一种；"
          "只报「按文件里的 n 读不是 713」。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
