# -*- coding: utf-8 -*-
"""rt7_claim_loose.py —— 生产判据 vs「严格半格」判据，在**真实语料**上逐例比对（只读）。

动机：主张「判据没有被改松」如果只用 20000 个随机 (v,f) 对来支撑，那是抽样；
这里换成真实语料的全量 token × 冻结表，看生产判据是否比「严格半格」更宽。

严格判据（S）：
    S = (round(f, dec) == v)                      # 同量、同符号
     or (round(f*100, dec) == v)                  # 百分比写法
     or (round(f/100, dec) == v)                  # 小数写法
生产判据（P）= freeze._match_written(v, dec, fvals)，容差 tol = 0.5*10^-dec*(1+1e-9)
**注意**：生产判据把为 v 算的 tol 原样用到 f*100 / f/100 上，
于是百分比分支的实际容差是应有半格的 100 倍 —— 本脚本把这类「超宽接受」单独数出来。

输出：每个产物的 P真S假 / P假S真 个数，及超宽接受的例子（含超出倍数）。
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import freeze          # noqa: E402
import verify as V     # noqa: E402

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

FIVE = ["age_struct", "nflis", "multiobjective", "icm2006c", "pop_panel"]


def strict_ok(v, dec, f):
    for cand in (f, f * 100.0, f / 100.0):
        try:
            if round(cand, dec) == round(v, dec):
                return True
        except (ValueError, OverflowError):
            continue
    return False


def scan(d):
    tex = io.open(os.path.join(d, "paper.tex"), encoding="utf-8").read()
    frozen = json.load(io.open(os.path.join(d, "冻结数字.json"), encoding="utf-8"))
    fvals = [it["value"] for it in frozen.get("items", [])]
    paths = [it.get("path", "") for it in frozen.get("items", [])]

    seen, uniq = set(), []
    for tok, _l in V.extract_numbers(tex, skip_meta=False):
        if "." not in tok:
            continue
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

    res = dict(n=0, loose=0, strict_only=0, wide=[])
    for tok, v, dec in uniq:
        res["n"] += 1
        p = freeze._match_written(v, dec, fvals)
        s = any(strict_ok(v, dec, f) for f in fvals)
        if p and not s:
            res["loose"] += 1
            # 找出造成「P 真 S 假」的那一对，算它超出应有半格多少倍
            tol = 0.5 * (10.0 ** -dec) * (1.0 + 1e-9)
            best = None
            for f, pa in zip(fvals, paths):
                for scale, tag in ((1.0, "1"), (100.0, "×100"), (0.01, "÷100")):
                    dlt = abs(abs(v) - abs(f) * scale)
                    if dlt <= tol:
                        allowed = tol / scale if scale else tol
                        ratio = dlt / allowed if allowed else float("inf")
                        if best is None or ratio > best[2]:
                            best = (f, tag, ratio, pa)
            if best and best[2] > 2:
                res["wide"].append((tok, v, dec, best))
        elif s and not p:
            res["strict_only"] += 1
    return res


def main():
    cfg = json.load(io.open(os.path.join(HERE, "runs.json"), encoding="utf-8"))
    tot = dict(n=0, loose=0, strict_only=0)
    print("产物          带小数token  生产认/严格拒  严格认/生产拒")
    print("-" * 72)
    for nm in FIVE + ["out/final"]:
        d = os.path.join(HERE, "out", "final") if nm == "out/final" \
            else os.path.join(HERE, cfg[nm]["out"])
        if not os.path.exists(os.path.join(d, "paper.tex")):
            continue
        r = scan(d)
        for k in tot:
            tot[k] += r[k]
        print("%-12s %10d %13d %15d"
              % (nm, r["n"], r["loose"], r["strict_only"]))
        for tok, v, dec, (f, tag, ratio, pa) in r["wide"][:5]:
            print(f"      超宽接受 {tok!r:>12} dec={dec:>2}  ← f={f!r} scale={tag}"
                  f"  实际偏差/应有半格={ratio:.1f}×  path={pa}")
    print("-" * 72)
    print("合计：token %d ｜ 生产认而严格拒 %d (%.2f%%) ｜ 严格认而生产拒 %d"
          % (tot["n"], tot["loose"], 100.0 * tot["loose"] / max(1, tot["n"]),
             tot["strict_only"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
