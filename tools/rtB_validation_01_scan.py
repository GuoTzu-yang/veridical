# -*- coding: utf-8 -*-
"""探针2/3 词表扫描（只读，只打印）。
在 paper.tex 的 validation 段（L477-L676）与全文两个范围内，
查找 (a) 多重比较/窗口/族错误率的交代；(b) 区间估计的交代。
只打印命中行与计数，不写文件。"""
import os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
p = os.path.join(ROOT, "out", "final", "paper.tex")
lines = open(p, encoding="utf-8").read().splitlines()

LO, HI = 477, 676  # 1-based inclusive

MULTI = [
    r"multiple\s+compar", r"multiplicity", r"family[- ]wise", r"Bonferroni",
    r"Holm", r"Benjamini", r"Hochberg", r"false\s+discovery", r"\bFDR\b",
    r"FWER", r"p[- ]?value", r"significan", r"Type\s+I", r"alpha\s+level",
    r"window", r"windows", r"number of (?:checks|tests|comparisons)",
]
INTERVAL = [
    r"confidence\s+interval", r"\bCI\b", r"credible\s+interval", r"interval",
    r"standard\s+error", r"\bSE\b", r"bootstrap", r"percentile",
    r"upper\s+bound", r"lower\s+bound", r"rule of three", r"Wilson",
    r"\$\\pm\$", r"\\pm", r"error\s+bar", r"uncertaint",
]

def scan(name, pats, lo, hi, label):
    print("=" * 72)
    print(f"[{label}] {name}  lines {lo}-{hi}")
    total = 0
    for i, ln in enumerate(lines[lo - 1:hi], start=lo):
        hits = [pt for pt in pats if re.search(pt, ln, re.I)]
        if hits:
            total += 1
            print(f"  L{i}: {ln.strip()[:150]}")
            print(f"        <- {hits}")
    print(f"  matched lines: {total}")
    return total

m_board = scan("MULTI", MULTI, LO, HI, "板内")
m_all = scan("MULTI", MULTI, 1, len(lines), "全文")
i_board = scan("INTERVAL", INTERVAL, LO, HI, "板内")
i_all = scan("INTERVAL", INTERVAL, 1, len(lines), "全文")

print("=" * 72)
print("n_lines_total:", len(lines))
print("SUMMARY multi_board=%d multi_all=%d interval_board=%d interval_all=%d"
      % (m_board, m_all, i_board, i_all))
