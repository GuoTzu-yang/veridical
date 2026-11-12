"""生成论文表：未溯源数字的五类剖析（从 untraced_corpus.json 出）。

数据源是 `untraced.py --corpus` 的输出，不是旧的 anatomy.json ——
后者是「只分类了打印前 15 条」的那版，红队 F1 已经指出它分母不全。
"""
import io
import json
import os

HERE = r"C:\Users\21246\Documents\deepseek-harness\default-workspace\model1-arch"
OUT = os.path.join(HERE, "out", "final")
A = json.load(io.open(os.path.join(HERE, "out", "untraced_corpus.json"),
                      encoding="utf-8"))

KEYS = [("A_struct", "Structural", "row/table/section indices, sample size $n$",
         "the data layout; no computation should produce it"),
        ("B_config", "Configuration", r"$\alpha=0.05$, thresholds, confidence levels",
         "a tool convention, declared once in the method"),
        ("C_year", "Temporal label", "1950, 1974--1979",
         "a data label, taken from the input file"),
        ("E_data", "Tabulated data", "values copied from the input table", "the input file; input provenance, not computation"),
        ("D_computed", "Computed", "coefficients, RMSE, percentages",
         "**the only class that must have a source**")]

tot = {}
for k, _n, _e, _r in KEYS:
    tot[k] = sum(a.get(k, 0) for a in A)
n_all = sum(tot.values())

L = [r"\begin{tabular}{@{}llL{3.4cm}L{3.6cm}r@{}}",
     r"\toprule",
     r"Class & Example & Where the number legitimately comes from & Share of untraced \\",
     r"\midrule"]
for k, name, ex, src in KEYS:
    # 用 f-string：`\\%` → `\%`，`\\\\` → `\\`（% 格式化会把这两个转义算错）
    pct = 100.0 * tot[k] / max(1, n_all)
    L.append(f"{name} & {ex} & {src} & {tot[k]} ({pct:.1f}\\% of {n_all}) \\\\")
L += [r"\midrule",
      r"\multicolumn{3}{@{}l}{all untraced tokens over 23 papers} & %d \\" % n_all,
      r"\bottomrule", r"\end{tabular}"]
io.open(os.path.join(OUT, "tab_anatomy.tex"), "w", encoding="utf-8",
        newline="\n").write("\n".join(L) + "\n")

print("tab_anatomy.tex 已写")
for k, n, _e, _s in KEYS:
    print("   %-12s %4d" % (n, tot[k]))
print("   合计 %d" % n_all)
