#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""实测：换一道完全不同的题，这套东西输出什么。

造一个完全无关的数据集（工厂产量 vs 温度/压力/时间），
用同一套 mmkit run 跑一遍，看能不能出稿、出的是不是胡说。
"""
import os
import subprocess
import sys

import openpyxl

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 造数据：产量 = 温度 - 压力 + 噪声，完全不像热沉
XLSX = os.path.join(HERE, "out", "scope_test.xlsx")
wb = openpyxl.Workbook()
ws = wb.active
ws.append(["工厂编号", "反应温度", "操作压力", "停留时间",
           "产量", "能耗", "次品率"])
import random
random.seed(7)
for i in range(60):
    t = round(180 + random.uniform(0, 40), 1)       # 180-220
    p = round(1.0 + random.uniform(0, 0.8), 2)      # 1.0-1.8
    s = round(2 + random.uniform(0, 6), 1)          # 2-8
    y = round(120 + 0.35 * t - 18 * p + 0.5 * s + random.gauss(0, 1.2), 2)
    e = round(40 + 0.05 * t + 3.0 * p + random.gauss(0, 0.6), 2)
    d = round(max(0.1, 3.0 - 0.008 * t + 0.4 * p + random.gauss(0, 0.15)), 2)
    ws.append([f"F{i + 1:03d}", t, p, s, y, e, d])
wb.save(XLSX)
print(f"  造好 {XLSX}（60 行，化工场景）")

OUT = os.path.join(HERE, "out", "scope_test")
os.makedirs(OUT, exist_ok=True)
TEX = os.path.join(OUT, "paper.tex")

r = subprocess.run(
    [sys.executable, "mmkit.py", "run",
     "--data", XLSX, "--y", "产量", "--x", "反应温度,操作压力,停留时间",
     "--min", "产量,能耗,次品率",
     "--tex", TEX, "--team", "2612345", "--problem", "chemical reactor yield",
     "--no-gate"],
    capture_output=True, text=True, encoding="utf-8", errors="replace",
    cwd=HERE)
print(f"  退出码 {r.returncode}")
if "Traceback" in (r.stderr or ""):
    print("  崩溃：")
    for ln in (r.stderr or "").strip().splitlines()[-4:]:
        print("    " + ln[:100])
elif os.path.exists(TEX):
    t = open(TEX, encoding="utf-8").read()
    print(f"  出稿 {len(t)} 字符")
    print()
    print("  === 检查有没有把热沉的物理搬进化工场景 ===")
    for kw in ("thermal resistance", "pressure drop", "manifold",
               "pin-fin", "conservation of energy", "coolant",
               "heat sink", "导热", "散热"):
        n = t.lower().count(kw.lower())
        if n:
            print(f"    !! {kw:<24}{n} 次")
    print()
    print("  === 摘要开头 ===")
    import re
    m = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", t, re.S)
    b = m.group(1) if m else ""
    print("    " + b[:400].replace("\n", " "))
