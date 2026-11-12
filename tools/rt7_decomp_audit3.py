# -*- coding: utf-8 -*-
"""rt7_decomp_audit3.py —— 审 §Analysis 这一节自己的分母。

对照三处：
  paper.tex L188-190 caption        "10{,}231 tokens, 1{,}482 untraced"
  out/final/tab_anatomy.tex 表体     139/0/207/83/1054 = 1483
  untraced.py --corpus 实跑          5822 tokens / 263 untraced，28 D_computed
判据：同一句话的分子分母是不是同一个测量。只读。
"""
import io
import json
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import untraced as U
import verify as V


def hr(t):
    print("\n" + "=" * 78)
    print(t)
    print("=" * 78)


def papers():
    cfg = json.load(io.open(os.path.join(HERE, "runs.json"), encoding="utf-8"))
    out = []
    for nm, it in cfg.items():
        d = os.path.join(HERE, it["out"])
        if os.path.exists(os.path.join(d, "paper.tex")):
            out.append((nm, d))
    return out


def main():
    hr("1  同一份语料，两种 skip_meta 口径下的 token 总数 / 未溯源总数")
    c = defaultdict(int)
    for nm, d in papers():
        tex = io.open(os.path.join(d, "paper.tex"), encoding="utf-8").read()
        outs = V.load_outputs(d)
        for sm in (True, False):
            cand = V.extract_numbers(tex, skip_meta=sm)
            pool = V.collect_output_numbers(outs)
            unt = []
            for tok, line in cand:
                try:
                    v = float(tok)
                except ValueError:
                    continue
                dec = V._written_decimals(tok)
                if not any(V._near(v, p, dec) for p in pool):
                    unt.append(tok)
            c["tok_%s" % sm] += len(cand)
            c["unt_%s" % sm] += len(unt)
    print("  skip_meta=True  : %5d tokens, %5d untraced" %
          (c["tok_True"], c["unt_True"]))
    print("  skip_meta=False : %5d tokens, %5d untraced" %
          (c["tok_False"], c["unt_False"]))
    print("\n  论文 caption 写的是 10,231 tokens / 1,482 untraced")
    print("  untraced.py --corpus 实跑 5,822 tokens / 263 untraced")

    hr("2  skip_meta=False 口径下的五类分布（看能否复现表里的 139/0/207/83/1054）")
    agg = defaultdict(int)
    for nm, d in papers():
        tex = io.open(os.path.join(d, "paper.tex"), encoding="utf-8").read()
        outs = V.load_outputs(d)
        pool = V.collect_output_numbers(outs)
        cand = V.extract_numbers(tex, skip_meta=False)
        dv = U.data_values_of(U.find_data_file(d))
        for tok, _l in cand:
            try:
                v = float(tok)
            except ValueError:
                continue
            dec = V._written_decimals(tok)
            if not any(V._near(v, p, dec) for p in pool):
                agg[U.classify_token(tok, dv)] += 1
    for k in list(U.CLASSES) + ["?"]:
        print("    %-11s %5d" % (k, agg[k]))
    print("    合计        %5d" % sum(agg.values()))

    hr("3  论文表体 vs 今天实跑（同一套 untraced.py --corpus 口径）")
    tab = dict(A_struct=139, B_config=0, C_year=207, E_data=83, D_computed=1054)
    now = dict(A_struct=70, B_config=0, C_year=165, E_data=0, D_computed=28)
    print("  %-11s %8s %8s %8s" % ("类", "表里写的", "今天跑的", "差"))
    for k in U.CLASSES:
        print("  %-11s %8d %8d %+8d" % (k, tab[k], now[k], now[k] - tab[k]))
    print("  %-11s %8d %8d %+8d" % ("合计", sum(tab.values()), sum(now.values()),
                                    sum(now.values()) - sum(tab.values())))
    print("\n  表体自己写的 total 行 = 1483；caption 写 1,482 —— 同一表内差 1")
    print("  表体 D_computed = 1054；今天 untraced.py --corpus = 28")

    hr("4  谁生成这两个数？搜 10231 / 1482 / 1483 / 1054")
    import re
    hits = []
    for root, dirs, files in os.walk(HERE):
        dirs[:] = [x for x in dirs if x not in
                   ("__pycache__", "_removed_20261108", "external", "kb")]
        for f in files:
            if not f.endswith((".py", ".tex", ".json", ".md")):
                continue
            p = os.path.join(root, f)
            try:
                s = io.open(p, encoding="utf-8", errors="ignore").read()
            except Exception:                              # noqa: BLE001
                continue
            for pat in ("10231", "10{,}231", "1482", "1{,}482",
                        "1483", "1{,}483", "1054"):
                if pat in s:
                    for ln in s.splitlines():
                        if pat in ln:
                            hits.append((os.path.relpath(p, HERE), pat,
                                         ln.strip()[:110]))
    seen = set()
    for p, pat, ln in hits:
        k = (p, ln)
        if k in seen:
            continue
        seen.add(k)
        print("    %-46s [%s] %s" % (p[:46], pat, ln))
    return 0


if __name__ == "__main__":
    sys.exit(main())
