#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""rt_twojudges.py —— 只读：同一份产物，用两套「书写精度」判据各判一次。

目的：把「修判据」与「修生成器」分开量化。

  判据 A（121 轮的 freeze._decimals）：小数位 = len(tok.split(".")[1])
        → "1.541e+04" 被当成 7 位小数，容差 5e-8
  判据 B（当前 freeze._decimals）：科学计数法按有效位数换算，容许负 dec

另外统计两个「分母漏洞」（与判据精度无关，是候选集口径）：
  · 不带小数点的 token 根本不进候选（同一张表里 9599 免检、1.541e+04 要检）
  · |v| >= 1e6 的 token 被丢弃（荒谬的大百分比因此完全不检查）

只读：不改产物，只打印。
"""
from __future__ import annotations

import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import verify as V      # noqa: E402
import freeze as F      # noqa: E402
import untraced as U    # noqa: E402

TASKS = ["age_struct", "nflis", "multiobjective", "icm2006c", "pop_panel"]


def dec_old(tok: str) -> int:
    """121 轮口径。"""
    return len(tok.split(".")[1]) if "." in tok else 0


def dec_new(tok: str) -> int:
    return F._decimals(tok)


def candidates(tex: str):
    """返回 (带小数候选, 整数 token, 被 1e6 过滤的 token)。"""
    t = re.sub(r"\\begin\{thebibliography\}.*?\\end\{thebibliography\}", " ", tex,
               flags=re.S)
    allt = V.extract_numbers(t, skip_meta=False)
    dots, ints, big = [], [], []
    seen = set()
    for tok, line in allt:
        if "." not in tok:
            ints.append(tok)
            continue
        try:
            v = float(tok)
        except ValueError:
            continue
        if v != v or v in (float("inf"), float("-inf")):
            continue          # 与生产判据一致：122 轮已去掉 1e6 上限
        dots.append((tok, v, line))
    # 去重：与 check_paper 同（按 值+书写精度），但精度取「当前判据」，两种判据
    # 只在比较时用各自的 dec，不影响去重集合（去重键用 token 的原始书写）
    out, seen2 = [], set()
    for tok, v, line in dots:
        key = (round(v, 6), tok)
        if key in seen2:
            continue
        seen2.add(key)
        out.append((tok, v, line))
    return out, ints, big


def judge(tex: str, frozen: dict, decfn, dv):
    cand, ints, big = candidates(tex)
    fv = [it["value"] for it in frozen.get("items", [])]
    un = []
    n_data = 0
    for tok, v, line in cand:
        dec = decfn(tok)
        if F._match_written(v, dec, fv):
            continue
        if dv and round(v, 6) in dv:
            n_data += 1
            continue
        un.append((tok, v, dec, line))
    return dict(n=len(cand), untraced=un, n_data=n_data,
                ratio=(len(un) / len(cand)) if cand else 0.0,
                n_int=len(ints), ints=ints, n_big=len(big), big=big)


def main(argv=None) -> int:
    names = argv[1:] or TASKS
    for name in names:
        d = os.path.join(ROOT, "out", "runs", name)
        tex = io.open(os.path.join(d, "paper.tex"), encoding="utf-8").read()
        frozen = json.load(io.open(os.path.join(d, "冻结数字.json"),
                                  encoding="utf-8"))
        df = U.find_data_file(d)
        dv = U.data_values_of(df) if df else set()
        A = judge(tex, frozen, dec_old, dv)
        B = judge(tex, frozen, dec_new, dv)
        print("=" * 78)
        print("%s   frozen_n=%d  candidates=%d   整数漏检=%d   |v|>=1e6 漏检=%d"
              % (name, len(frozen.get("items", [])), A["n"], A["n_int"],
                 A["n_big"]))
        print("  判据A(旧/小数位) : 未溯源 %2d  (%.1f%%)"
              % (len(A["untraced"]), 100 * A["ratio"]))
        print("  判据B(新/有效位) : 未溯源 %2d  (%.1f%%)"
              % (len(B["untraced"]), 100 * B["ratio"]))
        onlyA = [x for x in A["untraced"] if x[0] not in
                 {y[0] for y in B["untraced"]}]
        print("  仅判据A判红（即「值在表里、精度算错」）: %d 个" % len(onlyA))
        for tok, v, dec, line in onlyA[:40]:
            print("     %-14s dec_old=%-2d dec_new=%-3d" % (tok, dec, dec_new(tok)))
        both = [x for x in B["untraced"]]
        print("  两套判据都红（真·来源缺失）: %d 个" % len(both))
        for tok, v, dec, line in both:
            print("     %-14s dec_new=%-3d   %s" % (tok, dec, line.strip()[:90]))
        if A["big"]:
            print("  |v|>=1e6 被丢弃的例子: %s" % A["big"][:6])
        if A["ints"]:
            print("  整数 token 例子: %s" % A["ints"][:10])
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
