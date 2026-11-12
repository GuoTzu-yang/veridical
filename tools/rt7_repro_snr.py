#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""rt7_repro_snr.py —— 冻结表信噪比：冻结项到底被论文印出来了吗（只读）。

两个判据并列：
  loose  = freeze._found_in_paper（项目自己的判据；**子串匹配**，小整数会
           撞上任何一处出现的同数字串，因此偏高）
  strict = 论文里存在一个 token，它至少写了 2 位小数，且
           round(冻结值, 该 token 的小数位) == token
           （即「这个值真的被当作一个测量值印出来了」，而不是被 "21"
             这种 1~2 位整数顺手命中）

抽样用固定种子 random.Random(7)，可复现。
"""
import io
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import freeze                                                    # noqa: E402
import verify as V                                               # noqa: E402


def strict_hit(value, toks):
    """toks: [(float, decimals), ...]，只保留 dec>=2 的。"""
    for v, dec in toks:
        if dec < 2:
            continue
        try:
            if abs(round(value, dec) - v) <= 1e-12:
                return True
        except (ValueError, OverflowError):
            pass
    return False


def token_index(tex):
    out = []
    for tok, _line in V.extract_numbers(tex, skip_meta=False):
        try:
            v = float(tok)
        except ValueError:
            continue
        out.append((v, V._written_decimals(tok)))
    return out


def snr(dirpath, label, n_sample=20, seed=7):
    fz = json.load(io.open(os.path.join(dirpath, "冻结数字.json"),
                           encoding="utf-8"))
    tex = io.open(os.path.join(dirpath, "paper.tex"), encoding="utf-8").read()
    items = fz["items"]
    toks = token_index(tex)
    n_loose = sum(1 for it in items
                  if freeze._found_in_paper(it["value"], tex))
    n_strict = sum(1 for it in items if strict_hit(it["value"], toks))
    print("=== %-18s items=%-5d loose=%-5d(%5.1f%%)  strict=%-5d(%5.1f%%)"
          % (label, len(items), n_loose, 100.0 * n_loose / len(items),
             n_strict, 100.0 * n_strict / len(items)))
    rr = random.Random(seed)
    idx = rr.sample(range(len(items)), min(n_sample, len(items)))
    idx.sort()
    print("    抽样 %d 条（seed=%d）：" % (len(idx), seed))
    kl = ks = 0
    for i in idx:
        it = items[i]
        lo = freeze._found_in_paper(it["value"], tex)
        st = strict_hit(it["value"], toks)
        kl += 1 if lo else 0
        ks += 1 if st else 0
        print("      [%3d] %-4s %-5s %-42s = %-22.10g"
              % (i, "L" if lo else "-", "S" if st else "-",
                 it["path"], it["value"]))
    print("    抽样：loose %d/%d，strict %d/%d"
          % (kl, len(idx), ks, len(idx)))
    print()
    return dict(label=label, n=len(items), loose=n_loose, strict=n_strict,
                sl=len(idx), kl=kl, ks=ks)


def main():
    rows = []
    for nm in ("age_struct", "nflis", "multiobjective", "icm2006c",
               "pop_panel"):
        rows.append(snr(os.path.join(HERE, "out", "runs", nm), nm))
    rows.append(snr(os.path.join(HERE, "out", "final"), "out/final"))
    print("── 汇总 ──")
    print("%-16s %8s %10s %10s %8s %8s"
          % ("题", "items", "loose", "strict", "抽L", "抽S"))
    for r in rows:
        print("%-16s %8d %9.1f%% %9.1f%% %8s %8s"
              % (r["label"], r["n"],
                 100.0 * r["loose"] / r["n"], 100.0 * r["strict"] / r["n"],
                 "%d/%d" % (r["kl"], r["sl"]), "%d/%d" % (r["ks"], r["sl"])))
    print()
    print("── nflis 冻结表构成（说明 loose 为什么偏高）──")
    fz = json.load(io.open(os.path.join(HERE, "out", "runs", "nflis",
                                        "冻结数字.json"), encoding="utf-8"))
    import collections
    c = collections.Counter(it["path"].split(".")[0].split("[")[0]
                            for it in fz["items"])
    for k, v in c.most_common(8):
        print("   %-20s %6d  (%.1f%%)" % (k, v, 100.0 * v / len(fz["items"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
