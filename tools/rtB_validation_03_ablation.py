# -*- coding: utf-8 -*-
"""探针4 + 稳健性（只读，只打印）：
(1) 解析 paper.tex 内联 ablation 表，核对百分比与分数是否自洽、"Orphan tokens" 列语义；
(2) 把 ablation 的 5 题与 tab_corpus 的 verify 列对照（同一题两个数是否一致）；
(3) 定位两个"零效应"消融的原话；
(4) 用 tab_corpus 的 Pages 与 verify 率算 Spearman，检验 fig17 的断言
    「longer reports are not the less traceable ones」。"""
import os, re, itertools

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
paper = os.path.join(ROOT, "out", "final", "paper.tex")
corpus = os.path.join(ROOT, "out", "final", "tab_corpus.tex")
lines = open(paper, encoding="utf-8").read().splitlines()

print("=" * 76)
print("[1] ablation 表（paper.tex 内联，L617-L634）解析")
abl = []
for i in range(616, 634):
    ln = lines[i]
    m = re.match(r"^\s*([A-Za-z_0-9\\]+)\s*&\s*([\d.]+)\\%\s*\((\d+)/(\d+)\)\s*&\s*([\d.]+)\\%\s*\((\d+)/(\d+)\)\s*&\s*(\d+)\s*\\\\",
                 ln.strip())
    if m:
        abl.append(dict(name=m.group(1), w=float(m.group(2)), wk=int(m.group(3)), wn=int(m.group(4)),
                        wo=float(m.group(5)), wok=int(m.group(6)), won=int(m.group(7)),
                        orphan=int(m.group(8))))
for a in abl:
    chk_w = 100 * a["wk"] / a["wn"]
    chk_o = 100 * a["wok"] / a["won"]
    print(f"  {a['name']:<12} with={a['w']:.1f}% ({a['wk']}/{a['wn']}={chk_w:.2f}%)  "
          f"without={a['wo']:.1f}% ({a['wok']}/{a['won']}={chk_o:.2f}%)  "
          f"orphan_col={a['orphan']} == with_den? {a['orphan']==a['wn']}  "
          f"== without_den? {a['orphan']==a['won']}")
print("  n_problems:", len(abl))
if abl:
    print("  drop range: %.1f -> %.1f  (ratio min %.2f, max %.2f)"
          % (min(a['w'] for a in abl), max(a['wo'] for a in abl),
             min(a['wo'] / a['w'] for a in abl), max(a['wo'] / a['w'] for a in abl)))
    print("  paired drop (pp):", [round(a['w'] - a['wo'], 1) for a in abl])
    print("  absolute residual tokens:", [(a['name'], a['wn'] - a['wok'], round((a['wn'] - a['wok']) / a['wn'] * 100, 1)) for a in abl])

print("=" * 76)
print("[2] ablation 的 with-table 值与 tab_corpus 的 verify 列对照")
cv = {}
for ln in open(corpus, encoding="utf-8"):
    m = re.match(r"^([A-Za-z_0-9\\]+)\s*&\s*(\d+)\s*&\s*-\s*&\s*-\s*&\s*([\d.]+)\s*&\s*([\d.]+)\s*\\\\", ln.strip())
    if m:
        cv[m.group(1).replace("\\_", "_")] = (float(m.group(3)), float(m.group(4)))
for a in abl:
    key = a["name"].replace("\\_", "_")
    got = cv.get(key)
    if got:
        print(f"  {key:<12} ablation_with={a['w']:.1f}  corpus_verify={got[1]:.1f}  "
              f"delta={a['w']-got[1]:+.1f}  corpus_gate={got[0]:.1f}")
    else:
        print(f"  {key:<12} NOT FOUND in tab_corpus")

print("=" * 76)
print("[3] 三个机制的消融效应（原话定位）")
for i in range(579, 600):
    t = lines[i - 1].strip()
    if any(k in t for k in ["strongest", "changes no aggregate", "changes no content", "removes three", "12.2"]):
        print(f"  L{i}: {t[:150]}")
for i in range(605, 620):
    t = lines[i - 1].strip()
    if any(k in t for k in ["ablation", "incidental", "weaker", "attributable", "present in every"]):
        print(f"  L{i}: {t[:150]}")

print("=" * 76)
print("[4] 稳健性：Pages vs verify 率的 Spearman（tab_corpus 全 23 题）")
pairs = []
for ln in open(corpus, encoding="utf-8"):
    m = re.match(r"^([A-Za-z_0-9\\]+)\s*&\s*(\d+)\s*&\s*-\s*&\s*-\s*&\s*([\d.]+)\s*&\s*([\d.]+)\s*\\\\", ln.strip())
    if m:
        pairs.append((m.group(1).replace("\\_", "_"), int(m.group(2)), float(m.group(4))))
n = len(pairs)
def rank(v):
    order = sorted(range(len(v)), key=lambda i: v[i])
    r = [0.0] * len(v)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
            j += 1
        avg = (i + j) / 2 + 1
        for k in range(i, j + 1):
            r[order[k]] = avg
        i = j + 1
    return r
rx = rank([p[1] for p in pairs])
ry = rank([p[2] for p in pairs])
mx, my = sum(rx) / n, sum(ry) / n
num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
d1 = sum((a - mx) ** 2 for a in rx) ** 0.5
d2 = sum((b - my) ** 2 for b in ry) ** 0.5
rho = num / (d1 * d2)
print(f"  n={n}  Spearman rho(pages, verify) = {rho:.4f}")
print("  断言 L671-673: 'longer reports are not the less traceable ones'")
print("  逐题（pages, verify）：")
for p in sorted(pairs, key=lambda t: t[1]):
    print(f"    {p[0]:<20} pages={p[1]:>2}  verify={p[2]:.1f}")
print("  极值对照: 最长 %s(pages=%d, verify=%.1f) | 最弱 %s(verify=%.1f, pages=%d)"
      % (max(pairs, key=lambda t: t[1])[0], max(p[1] for p in pairs),
         [p[2] for p in pairs if p[1] == max(q[1] for q in pairs)][0],
         min(pairs, key=lambda t: t[2])[0], min(p[2] for p in pairs),
         [p[1] for p in pairs if p[2] == min(q[2] for q in pairs)][0]))
