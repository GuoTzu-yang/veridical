#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""rt_corpus_cmp.py —— 只读：122 轮前后的 untraced 语料对比 + 当前 D_computed 明细。"""
from __future__ import annotations

import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import verify as V      # noqa: E402
import untraced as U    # noqa: E402

BASE = os.path.join(ROOT, "out", "_backup_r122",
                    "untraced_corpus_before_r122.json")
NOW = os.path.join(ROOT, "out", "untraced_corpus.json")
CLASSES = U.CLASSES


def load(p):
    return {r["name"]: r for r in json.load(io.open(p, encoding="utf-8"))}


def main():
    b = load(BASE)
    n = load(NOW)
    print("题目                      tokens(b→a)   未溯源(b→a)   D_computed(b→a)")
    print("-" * 78)
    S = dict(tok_b=0, tok_a=0, un_b=0, un_a=0, d_b=0, d_a=0)
    for nm in sorted(set(b) | set(n)):
        rb, ra = b.get(nm), n.get(nm)
        if not rb or not ra:
            print("%-22s %s" % (nm, "缺一侧"))
            continue
        print("%-22s %4d→%4d   %4d→%4d    %4d→%4d" % (
            nm, rb["n_tokens"], ra["n_tokens"],
            rb["n_untraced"], ra["n_untraced"],
            rb["D_computed"], ra["D_computed"]))
        for k, key in (("tok_b", "n_tokens"), ("tok_a", "n_tokens")):
            pass
        S["tok_b"] += rb["n_tokens"]; S["tok_a"] += ra["n_tokens"]
        S["un_b"] += rb["n_untraced"]; S["un_a"] += ra["n_untraced"]
        S["d_b"] += rb["D_computed"]; S["d_a"] += ra["D_computed"]
    print("-" * 78)
    print("合计  tokens %d→%d   未溯源 %d→%d   D_computed %d→%d"
          % (S["tok_b"], S["tok_a"], S["un_b"], S["un_a"], S["d_b"], S["d_a"]))
    print()
    print("=== 当前 D_computed 明细（这一类才必须追到计算产物）===")
    cfg = json.load(io.open(os.path.join(ROOT, "runs.json"), encoding="utf-8"))
    tot = 0
    for nm, it in cfg.items():
        d = os.path.join(ROOT, it["out"])
        if not os.path.exists(os.path.join(d, "paper.tex")):
            continue
        text = io.open(os.path.join(d, "paper.tex"), encoding="utf-8").read()
        outs = V.load_outputs(d)
        r = V.trace(text, outs)
        dv = U.data_values_of(U.find_data_file(d))
        hits = [u for u in (r.get("untraced") or [])
                if U.classify_token(u["token"], dv) == "D_computed"]
        if hits:
            print("  %-18s %d 个" % (nm, len(hits)))
            for u in hits:
                print("      %-14s  ← %s" % (u["token"], u["line"][:80]))
            tot += len(hits)
    print("  当前 D_computed 总计 = %d" % tot)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
