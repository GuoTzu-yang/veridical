# -*- coding: utf-8 -*-
"""探针1 复核（只读，只打印）：
(1) 补扫「校正/未校正」类措辞；(2) 用 tab_corpus.tex 复算汇总统计，
    与正文 L485-L490 的 91.9% / 91.0% / 76.3% 对照；
(3) 复算 200/1482 抽样比例、混淆矩阵各类边际与零事件上界（rule of three / Wilson）。"""
import os, re, statistics

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
paper = os.path.join(ROOT, "out", "final", "paper.tex")
corpus = os.path.join(ROOT, "out", "final", "tab_corpus.tex")
conf = os.path.join(ROOT, "out", "final", "tab_confusion.tex")

lines = open(paper, encoding="utf-8").read().splitlines()

# ---------- (1) 校正类措辞 ----------
PATS = [r"correct(?:ion|ed|ing)?\b", r"adjust(?:ed|ment)?\b", r"unadjusted",
        r"nominal", r"per-check", r"23\s*\$?\\times\$?\s*23", r"\b529\b",
        r"at the 5\\?% level", r"one minus", r"any of the"]
print("=" * 74)
print("[1] 校正/未校正措辞扫描（全文）")
n = 0
for i, ln in enumerate(lines, start=1):
    hit = [pt for pt in PATS if re.search(pt, ln, re.I)]
    if hit:
        n += 1
        print(f"  L{i}: {ln.strip()[:140]}   <- {hit}")
print("  matched:", n)

# ---------- (2) tab_corpus 复算 ----------
print("=" * 74)
print("[2] tab_corpus.tex 复算")
rows = []
for ln in open(corpus, encoding="utf-8"):
    m = re.match(r"^([A-Za-z_0-9\\]+)\s*&\s*(\d+)\s*&\s*-\s*&\s*-\s*&\s*([\d.]+)\s*&\s*([\d.]+)\s*\\\\", ln.strip())
    if m:
        rows.append((m.group(1), int(m.group(2)), float(m.group(3)), float(m.group(4))))
print("  parsed rows:", len(rows))
gate = [r[2] for r in rows]
ver = [r[3] for r in rows]
print("  gate  : n=%d min=%.1f max=%.1f median=%.1f" % (len(gate), min(gate), max(gate), statistics.median(gate)))
print("  verify: n=%d min=%.1f max=%.1f median=%.1f" % (len(ver), min(ver), max(ver), statistics.median(ver)))
print("  verify weakest row:", min(rows, key=lambda r: r[3]))
print("  gate   weakest row:", min(rows, key=lambda r: r[2]))
print("  正文 claim: gate 全部 >= 91.9 / verify median 91.0 / verify weakest 76.3")
print("  逐条对照: 91.9<=gate_min? %s | median==91.0? %s | weakest==76.3? %s"
      % (91.9 <= min(gate), abs(statistics.median(ver) - 91.0) < 0.05, abs(min(ver) - 76.3) < 0.05))
print("  pages 列 min/max:", min(r[1] for r in rows), max(r[1] for r in rows))

# ---------- (3) 抽样与零事件 ----------
print("=" * 74)
print("[3] 200/1482 抽样与零事件")
N, n = 1482, 200
print("  sampling fraction: %.4f (%.2f%%)" % (n / N, 100 * n / N))
p_hat = 195 / 200
se = (p_hat * (1 - p_hat) / n) ** 0.5
print("  p_hat=%.4f  SE=%.4f  naive 95%% CI = [%.4f, %.4f]" % (p_hat, se, p_hat - 1.96 * se, p_hat + 1.96 * se))
# Wilson
z = 1.96
den = 1 + z * z / n
centre = (p_hat + z * z / (2 * n)) / den
half = z * ((p_hat * (1 - p_hat) / n + z * z / (4 * n * n)) ** 0.5) / den
print("  Wilson 95%% CI = [%.4f, %.4f]  (width %.2f pp)" % (centre - half, centre + half, 200 * half))
print("  rule of three for 0/138: upper 95%% bound = 3/138 = %.4f (%.2f%%)" % (3 / 138, 300 / 138))
print("  smallest class in confusion matrix: data=9 -> its rate CI is uninformative")

# ---------- (4) 混淆矩阵核账 ----------
print("=" * 74)
print("[4] tab_confusion.tex 逐格核账")
tot = 0
diag = 0
for ln in open(conf, encoding="utf-8"):
    m = re.match(r"^(struct|config|year|data|computed)\s*&\s*(\d+)\s*&\s*(\d+)\s*&\s*(\d+)\s*&\s*(\d+)\s*&\s*(\d+)\s*\\\\", ln.strip())
    if m:
        v = [int(m.group(k)) for k in range(2, 7)]
        tot += sum(v)
        diag += v[["struct", "config", "year", "data", "computed"].index(m.group(1))]
        print("  %-9s row=%s sum=%d" % (m.group(1), v, sum(v)))
print("  grand total=%d (claim 200: %s) | diagonal=%d (claim 195: %s)"
      % (tot, tot == 200, diag, diag == 195))
