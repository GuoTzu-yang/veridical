#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""exp_E_criteria.py —— 在内存里模拟「把判据补完整」，量化影响。只读。

红队独立诊断指出三条判据完整性漏洞（我都复核过，成立）：
  (a) 整数 token 完全不进候选（`if "." in t`）—— 把 :.4g 改成 :.0f 就能免检
  (b) `abs(v) < 1e6` 直接丢弃 —— 最可疑的大数（+24969352.7%）免检
  (c) verify 与 gate 的精度口径不一致（verify 遇 e 返回 None）

本工具在内存里跑 3 个变体，对 runs.json 全部 23 题 + out/final 各判一次：
  V0 = 现状（基准）
  V1 = 整数进候选，但按 untraced 的 A/B/C 分类算「可解释」，D_computed 才要求溯源
  V2 = V1 + 取消 1e6 上限
不改源码，只报「谁会从绿变红 / 从红变绿」。
"""
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import freeze                    # noqa: E402
import untraced as U             # noqa: E402
import verify as V               # noqa: E402
import gate as G                 # noqa: E402


def _cands(text, variant):
    """按变体抽候选 (tok, value, dec)。"""
    t = re.sub(r"\\begin\{thebibliography\}.*?\\end\{thebibliography\}",
               " ", text, flags=re.S)
    allt = V.extract_numbers(t, skip_meta=False)
    out, seen = [], set()
    for tk, _l in allt:
        # V0/W1：整数不进候选（现状）
        # W2：整数进候选，但 A/B/C 类算可解释
        if variant in ("V0", "W1") and "." not in tk:
            continue
        try:
            v = float(tk)
        except ValueError:
            continue
        # 1e6 上限：V0/V1/W2 保留（现状），V2/W1 去掉
        if variant in ("V0", "V1", "W2") and abs(v) >= 1e6:
            continue
        dec = freeze._decimals(tk)
        key = (round(v, 6), dec)
        if key in seen:
            continue
        seen.add(key)
        out.append((tk, v, dec))
    return out


def judge(d, variant, deliverable):
    tex_p = os.path.join(d, "paper.tex")
    fz_p = os.path.join(d, "冻结数字.json")
    if not (os.path.exists(tex_p) and os.path.exists(fz_p)):
        return None
    frozen = json.load(io.open(fz_p, encoding="utf-8"))
    fvals = [it["value"] for it in frozen.get("items", [])]
    dv = U.data_values_of(U.find_data_file(d))
    text = io.open(tex_p, encoding="utf-8").read()
    cands = _cands(text, variant)
    traced, unt = 0, []
    for tk, v, dec in cands:
        if freeze._match_written(v, dec, fvals):
            traced += 1
        elif dv and round(v, 6) in dv:
            traced += 1
        else:
            # V1/V2：整数按既有五类分类，A/B/C 算「可解释」，只有
            # D_computed（真计算量）才要求溯源。这样整数不制造假红，
            # 但也不能靠「少写一位小数」绕过检查。
            cls = U.classify_token(tk, dv if dv else None)
            if variant in ("V1", "V2") and "." not in tk \
                    and cls in ("A_struct", "B_config", "C_year"):
                traced += 1
            else:
                unt.append((tk, dec))
    n = len(cands)
    ratio = len(unt) / n if n else 0.0
    hp = [t for t, d2 in unt if d2 >= 3]
    ok = n >= 3 and ratio <= 0.10 and not (deliverable and hp)
    return dict(n=n, traced=traced, n_unt=len(unt), ratio=ratio,
                unt=unt, ok=ok, hp=hp)


def main():
    cfg = json.load(io.open(os.path.join(HERE, "runs.json"), encoding="utf-8"))
    targets = [(nm, os.path.join(HERE, it["out"])) for nm, it in cfg.items()]
    targets.append(("out/final", os.path.join(HERE, "out", "final")))
    print("%-16s %-6s %-6s %-6s   %s"
          % ("题", "V0", "V1", "V2", "变红/变绿"))
    print("-" * 78)
    tot = {"V0": 0, "V1": 0, "V2": 0}
    changes = []
    for nm, d in targets:
        deliv = G._is_deliverable(d)
        rs = {v: judge(d, v, deliv) for v in ("V0", "V1", "V2")}
        if rs["V0"] is None:
            continue
        line = []
        for v in ("V0", "V1", "V2"):
            r = rs[v]
            if not r["ok"]:
                tot[v] += 1
            line.append("红" if not r["ok"] else "绿")
        chg = ""
        if rs["V0"]["ok"] and not rs["V2"]["ok"]:
            chg = "**V2 变红** 未溯源 %d→%d（%s）" % (
                rs["V0"]["n_unt"], rs["V2"]["n_unt"],
                " ".join(t for t, _ in rs["V2"]["unt"][:4]))
            changes.append((nm, chg))
        print("%-16s %-6s %-6s %-6s   %s"
              % (nm, line[0], line[1], line[2], chg))
    print("-" * 78)
    print("红题数：V0=%d  V1=%d  V2=%d" % (tot["V0"], tot["V1"], tot["V2"]))
    if changes:
        print()
        print("### V2 会让这些题从绿变红（必须逐条确认是真缺陷还是假阳性）")
        for nm, c in changes:
            print("  %-16s %s" % (nm, c))
    return 0


if __name__ == "__main__":
    sys.exit(main())
