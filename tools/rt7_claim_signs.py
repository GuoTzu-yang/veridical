# -*- coding: utf-8 -*-
"""rt7_claim_signs.py —— 只看「A 认 B 不认」的那几个 token 是怎么被认下来的（只读）。

对每个这样的 token：
  · 列出冻结表中落在 gate 容差内的值，标出符号是否与 token 相反；
  · 列出 verify 池里最接近的值；
据此判断分叉是「abs 丢符号」还是「两门查的不是同一本账」。
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


def analyse(d):
    tex = io.open(os.path.join(d, "paper.tex"), encoding="utf-8").read()
    frozen = json.load(io.open(os.path.join(d, "冻结数字.json"), encoding="utf-8"))
    items = frozen.get("items", [])
    fvals = [it["value"] for it in items]
    pool = V.collect_output_numbers(V.load_outputs(d))
    out = []
    for tok, _line in V.extract_numbers(tex, skip_meta=False):
        if "." not in tok:
            continue
        try:
            v = float(tok)
        except ValueError:
            continue
        dec = V._written_decimals(tok)
        a = freeze._match_written(v, dec, fvals)
        b = any(V._near(v, p, dec) for p in pool)
        if not (a and not b):
            continue
        tol = 0.5 * (10.0 ** -dec) * (1.0 + 1e-9)
        hits = []
        for it in items:
            f = it["value"]
            for scale, sn in ((1.0, ""), (100.0, "×100"), (0.01, "÷100")):
                if abs(abs(v) - abs(f) * scale) <= tol:
                    hits.append((f, scale, sn, it.get("path", "")))
        nearest = min(pool, key=lambda p: abs(abs(p) - abs(v))) if pool else None
        out.append(dict(tok=tok, v=v, dec=dec, hits=hits, nearest=nearest))
    return out


def main():
    cfg = json.load(io.open(os.path.join(HERE, "runs.json"), encoding="utf-8"))
    seen_tok = set()
    for nm in FIVE + ["out/final"]:
        d = os.path.join(HERE, "out", "final") if nm == "out/final" \
            else os.path.join(HERE, cfg[nm]["out"])
        if not os.path.exists(os.path.join(d, "paper.tex")):
            continue
        print(f"\n##### {nm}")
        for r in analyse(d):
            key = (nm, r["tok"], round(r["v"], 6))
            if key in seen_tok:
                continue
            seen_tok.add(key)
            flip = [h for h in r["hits"] if h[0] * r["v"] < 0]
            print(f"  token {r['tok']!r:>12}  v={r['v']!r}  dec={r['dec']}")
            for f, scale, sn, path in r["hits"][:4]:
                mark = "  ← 反号" if (f * r["v"] < 0) else ""
                print(f"      冻结表命中 {f!r:>22} scale={sn or '1'}  path={path}{mark}")
            if not r["hits"]:
                print("      冻结表内无命中（异常）")
            if r["nearest"] is not None:
                print(f"      verify 池最近值 {r['nearest']!r}  "
                      f"差={abs(abs(r['nearest']) - abs(r['v'])):.3g}")
            print(f"      判定：gate=认（{'、'.join(sorted({('反号' if (h[0]*r['v']<0) else '同号') for h in r['hits']})) or '?'}）"
                  f"  verify=不认")
    return 0


if __name__ == "__main__":
    sys.exit(main())
