#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""批量生成论文需要的 12 张图（scienceplots 主题）。

mmkit run 只写 tex，不画图；图要单独用 mmkit plot 出。
之前误删了 out/fig 下的图，这里一次补齐并逐张报告成败。
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "out", "fig")

JOBS = [
    ("flow", ["--y", "热阻"]),
    ("box", ["--y", "热阻,压降,温度"]),
    ("hist", ["--y", "热阻"]),
    ("corr", ["--y", "热阻,压降,温度"]),
    ("pred", ["--y", "热阻", "--x", "宽度,深高,排数"]),
    ("resid", ["--y", "热阻", "--x", "宽度,深高,排数"]),
    ("qq", ["--y", "热阻"]),
    ("pareto", ["--min", "热阻,压降,温度"]),
    ("surfaces", ["--y", "热阻,压降,温度", "--x", "宽度,深高,排数"]),
    ("tornado", ["--y", "热阻", "--x", "宽度,深高,排数"]),
    ("sens", ["--y", "热阻", "--x", "宽度,深高,排数"]),
    ("cand", ["--y", "热阻", "--x", "宽度,深高,排数"]),
]

ok, fail = [], []
for kind, args in JOBS:
    png = os.path.join(OUT, kind + ".png")
    r = subprocess.run(
        [sys.executable, "mmkit.py", "plot", "--kind", kind]
        + args + ["--out-png", png],
        capture_output=True, text=True, encoding="utf-8",
        errors="replace", cwd=HERE)
    o = (r.stdout or "") + (r.stderr or "")
    if os.path.exists(png) and os.path.getsize(png) > 3000:
        ok.append(kind)
        print(f"  OK   {kind:<10}{os.path.getsize(png):>8} 字节")
    else:
        fail.append((kind, o.strip().splitlines()[-1][:90] if o.strip() else "?"))
        print(f"  FAIL {kind:<10}{o.strip().splitlines()[-1][:70] if o.strip() else ''}")

print()
print(f"  成功 {len(ok)}/{len(JOBS)}")
if fail:
    print("  失败：")
    for k, why in fail:
        print(f"    {k}: {why}")
