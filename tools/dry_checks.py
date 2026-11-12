#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""6 个未验证题型的 dry-run：只看 _methods_missing 报什么，不编译。

为什么需要
----------
第 38 轮发现 ward/dual 两个假阳性，但只验证了热沉题
（mechanism + regression + optimization）。另外 6 个题型的检查项
从未被触发过 —— 它们可能有同类假阳性，也可能 probe 写得太宽/太窄。

成本很低：不需要编译、不需要出 PDF，直接拿已有 tex 喂进匹配函数。
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import paper  # noqa: E402

# 5 个领域的 tex（test_domains.py 跑出来的）
SRC = [
    ("evaluation", "out/domains/evaluation/paper.tex"),
    ("prediction", "out/domains/prediction/paper.tex"),
    ("network", "out/domains/network/paper.tex"),
    ("queueing", "out/domains/queueing/paper.tex"),
    ("population", "out/domains/population/paper.tex"),
]

CHECKS = json.load(open(os.path.join(HERE, "kb", "methods", "checks.json"),
                        encoding="utf-8"))["kinds"]


def probe_hits(tex, probes):
    return [p for p in probes if paper._probe_hit(str(p).lower(), tex)]


def main():
    print(f"  {'题':<12}{'判定题型':<16}{'命中':<6}{'未命中'}")
    print("  " + "-" * 68)
    total_miss = 0
    for name, rel in SRC:
        p = os.path.join(HERE, rel)
        if not os.path.exists(p):
            print(f"  {name:<12}(缺 tex，先跑 tools/test_domains.py)")
            continue
        tex = open(p, encoding="utf-8").read().lower()
        # 用 domain 的 key 粗判题型（真实判定走 kind.detect，这里够用）
        kind = {"evaluation": "evaluation", "prediction": "prediction",
                "network": "network", "queueing": "simulation",
                "population": "prediction"}.get(name, "?")
        items = CHECKS.get(kind) or []
        hit, miss = [], []
        for it in items:
            prs = it.get("probes") or []
            h = probe_hits(tex, prs)
            (hit if h else miss).append((it["name"], h[0] if h else ""))
        total_miss += len(miss)
        print(f"  {name:<12}{kind:<16}{len(hit)}/{len(items):<4}")
        for nm, why in miss:
            print(f"      缺: {nm}")
        for nm, why in hit:
            print(f"      有: {nm}  ({why})")
    print()
    print(f"  合计未命中 {total_miss} 项 —— 每项都要人工判断"
          f"「真的没做」还是「probe 写窄了」")


if __name__ == "__main__":
    main()