#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""e_probe.py —— E 任务的取证工具（第 122 轮）。

只做三件事，不改任何东西：
  1. 对指定的产物目录跑 verify.trace，列出**每一个**未溯源 token（不截断）
  2. 用 untraced.classify_token 给每个 token 归类
  3. 打印 token 所在行的原文，方便判断它是「模板编的」还是「溯源口径漏的」

用法:
    python tools/e_probe.py age_struct nflis multiobjective icm2006c pop_panel
    python tools/e_probe.py --all          # runs.json 全部
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import untraced as U          # noqa: E402
import verify as V            # noqa: E402


def probe(name, item):
    d = os.path.join(HERE, item["out"])
    tex = os.path.join(d, "paper.tex")
    if not os.path.exists(tex):
        return dict(name=name, error="no paper.tex")
    text = io.open(tex, encoding="utf-8").read()
    outs = V.load_outputs(d)
    r = V.trace(text, outs)
    dv = U.data_values_of(U.find_data_file(d))
    unt = r.get("untraced") or []
    rows = []
    for u in unt:
        tok = u["token"]
        k = U.classify_token(tok, dv)
        rows.append(dict(token=tok, cls=k, line=(u.get("line") or "")[:110]))
    return dict(name=name, dir=item["out"],
                n_numbers=r["n_numbers"], n_untraced=r["n_untraced"],
                ratio=round(100.0 * r["n_untraced"] / max(1, r["n_numbers"]), 1),
                has_data=bool(dv), rows=rows)


def main(argv):
    cfg = json.load(io.open(os.path.join(HERE, "runs.json"), encoding="utf-8"))
    names = argv[1:]
    if not names or names == ["--all"]:
        names = list(cfg.keys())
    agg = {}
    bad = 0
    for nm in names:
        if nm not in cfg:
            print("  未知题号:", nm)
            continue
        p = probe(nm, cfg[nm])
        if p.get("error"):
            print("%-16s %s" % (nm, p["error"]))
            continue
        if p["n_untraced"]:
            bad += 1
        print("=" * 78)
        print("%-16s %3d 个数字 / 未溯源 %3d (%.1f%%)  输入表=%s"
              % (nm, p["n_numbers"], p["n_untraced"], p["ratio"],
                 "有" if p["has_data"] else "无"))
        for row in p["rows"]:
            agg[row["cls"]] = agg.get(row["cls"], 0) + 1
            print("   [%-11s] %-14s | %s" % (row["cls"], row["token"], row["line"]))
    print("=" * 78)
    print("红题数:", bad, "/", len(names))
    print("分类合计:", json.dumps(agg, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
