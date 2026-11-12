#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""rt7_stat_01_baseline.py —— 只读：复现「5 篇模板卷 100%」与「D_computed=28」两个主张的原始口径。

三个口径并列打印，互不混用：
  V 口径  verify.trace()        —— 全量 token（含整数），逐 token 判有无出处
  G 口径  freeze.check_paper()  —— 只判「带小数」的 token，另报 n_int_not_judged
  U 口径  untraced.classify_token() —— 把 V 口径的未溯源集合按五类归档

输出：每个 run 一行；末行合计。不改任何文件，不写产物（只 print）。
用法：python tools/rt7_stat_01_baseline.py
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
os.chdir(HERE)

import verify as V          # noqa: E402
import freeze as FZ         # noqa: E402
import untraced as U        # noqa: E402

CFG = json.load(io.open(os.path.join(HERE, "runs.json"), encoding="utf-8"))


def one(name: str, out: str) -> dict:
    d = os.path.join(HERE, out)
    tex = os.path.join(d, "paper.tex")
    if not os.path.exists(tex):
        return dict(name=name, error="no tex")
    text = io.open(tex, encoding="utf-8").read()
    outs = V.load_outputs(d)
    # ── V 口径 ──
    rv = V.trace(text, outs)
    dv = U.data_values_of(U.find_data_file(d))
    cnt = dict((k, 0) for k in U.CLASSES)
    cnt["?"] = 0
    for u in (rv.get("untraced") or []):
        k = U.classify_token(u["token"], dv)
        cnt[k] = cnt.get(k, 0) + 1
    # ── G 口径 ──
    fzp = os.path.join(d, "冻结数字.json")
    rg = None
    if os.path.exists(fzp):
        frozen = json.load(io.open(fzp, encoding="utf-8"))
        rg = FZ.check_paper(text, frozen, single_point=False,
                            data_values=dv, strict_source=False)
    return dict(name=name, out=out,
                n_tok=rv["n_numbers"], n_unt=rv["n_untraced"],
                traced_pct=round(100.0 * rv["traced_ratio"], 1),
                A=cnt["A_struct"], B=cnt["B_config"], C=cnt["C_year"],
                E=cnt["E_data"], D=cnt["D_computed"],
                g_n=(rg or {}).get("n_numbers"),
                g_tr=(rg or {}).get("n_traced"),
                g_pct=round(100.0 * (rg or {}).get("untraced_ratio", 0.0), 1),
                g_int=(rg or {}).get("n_int_not_judged"))


rows = [one(k, v["out"]) for k, v in CFG.items()]
hdr = ("%-16s %5s %5s %6s | %3s %3s %3s %3s %3s | %5s %5s %5s %5s"
       % ("run", "n_tok", "n_unt", "V%tr", "A", "B", "C", "E", "D",
          "g_n", "g_tr", "g_%un", "g_int"))
print(hdr)
print("-" * len(hdr))
for r in rows:
    if r.get("error"):
        print("%-16s  %s" % (r["name"], r["error"]))
        continue
    print("%-16s %5d %5d %6.1f | %3d %3d %3d %3d %3d | %5s %5s %5s %5s"
          % (r["name"], r["n_tok"], r["n_unt"], r["traced_pct"],
             r["A"], r["B"], r["C"], r["E"], r["D"],
             r["g_n"], r["g_tr"], r["g_pct"], r["g_int"]))

ok = [r for r in rows if not r.get("error")]
print()
print("合计 runs=%d" % len(ok))
print("  V 口径 token  %d" % sum(r["n_tok"] for r in ok))
print("  V 口径 未溯源 %d" % sum(r["n_unt"] for r in ok))
for k, key in (("A_struct", "A"), ("B_config", "B"), ("C_year", "C"),
               ("E_data", "E"), ("D_computed", "D")):
    print("    %-11s %5d" % (k, sum(r[key] for r in ok)))
print("  G 口径 判定 token（带小数） %d" % sum((r["g_n"] or 0) for r in ok))
print("  G 口径 未纳入判定的整数 token %d" % sum((r["g_int"] or 0) for r in ok))

print()
print("=== 百分比行为 100.0 的 run（主张②：模板卷全部 100%）===")
print("  V 口径 100.0%%：", [r["name"] for r in ok if r["traced_pct"] == 100.0])
print("  G 口径 无出处 0.0%%：", [r["name"] for r in ok if r["g_pct"] == 0.0])
print("  V 口径 <100%%：",
      [(r["name"], r["traced_pct"]) for r in ok if r["traced_pct"] < 100.0])
