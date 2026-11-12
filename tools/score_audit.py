#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""框架评分用的客观指标（不评估质量，只数事实）。"""
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MODS = ["mmkit", "paper", "mm", "q4", "q5", "multimodel", "cards",
        "innovation", "abstract", "gate", "plot_mpl", "cite", "schema",
        "freeze", "rules", "verify", "verify_math", "falsify", "lanes",
        "contract", "orchestrate", "distill", "papercheck", "dataprof"]

print("  === 规模 ===")
tot = 0
n_ok = 0
for m in MODS:
    p = os.path.join(HERE, m + ".py")
    if not os.path.exists(p):
        print(f"    {m:<16} 缺")
        continue
    lines = len(open(p, encoding="utf-8").read().splitlines())
    tot += lines
    n_ok += 1
print(f"    模块 {n_ok}/{len(MODS)} 存在，共 {tot} 行")

print()
print("  === 自测 ===")
r = subprocess.run([sys.executable, "tests/run_all.py"],
                   capture_output=True, text=True, encoding="utf-8",
                   errors="replace", cwd=HERE)
o = (r.stdout or "")
print(f"    退出码 {r.returncode}")
m = re.search(r"(\d+)\s*/\s*(\d+)", o)
lines_ok = len(re.findall(r"ALL PASS", o))
print(f"    ALL PASS 出现 {lines_ok} 次")

print()
print("  === gate ===")
r = subprocess.run([sys.executable, "gate.py", "out/fig"],
                   capture_output=True, text=True, encoding="utf-8",
                   errors="replace", cwd=HERE)
o = (r.stdout or "")
ok = len(re.findall(r"\[OK", o))
bad = len(re.findall(r"\[FAIL", o))
print(f"    OK {ok} 项 / FAIL {bad} 项")
for ln in o.splitlines():
    if "质量门" in ln:
        print("    " + ln.strip())

print()
print("  === 论文数字 ===")
sys.path.insert(0, HERE)
import freeze
d = json.load(open(os.path.join(HERE, "out", "fig", "冻结数字.json"),
                   encoding="utf-8"))
t = open(os.path.join(HERE, "out", "fig", "paper.tex"),
         encoding="utf-8").read()
r2 = freeze.check_paper(t, d)
print(f"    冻结 {d['n']} 项，论文 {r2['n_numbers']} 数，"
      f"可溯源 {r2['n_traced']}")

print()
print("  === 补丁 ===")
r = subprocess.run([sys.executable, "patches.py", "verify"],
                   capture_output=True, text=True, encoding="utf-8",
                   errors="replace", cwd=HERE)
for ln in (r.stdout or "").splitlines():
    if "已落实" in ln:
        print("    " + ln.strip())

print()
print("  === 通用性实测（上一轮结果）===")
st = os.path.join(HERE, "out", "scope_test", "paper.tex")
if os.path.exists(st):
    x = open(st, encoding="utf-8").read()
    bad = {w: x.lower().count(w) for w in
           ("thermal resistance", "pressure drop", "manifold",
            "pin-fin", "coolant", "heat sink")
           if x.lower().count(w)}
    print(f"    换化工题后仍出现热沉术语: {bad}")
    print(f"    污染合计 {sum(bad.values())} 处")
else:
    print("    没有 scope_test 输出")
