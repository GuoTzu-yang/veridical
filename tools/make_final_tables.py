"""从 data.json + gate 现场输出，生成论文用的两张表（LaTeX），避免手抄数字。"""
import io
import json
import os
import subprocess
import sys

HERE = r"C:\Users\21246\Documents\deepseek-harness\default-workspace\model1-arch"
OUT = os.path.join(HERE, "out", "final")
PY = sys.executable
D = json.load(io.open(os.path.join(OUT, "data.json"), encoding="utf-8"))

# ── 表 A：22 项检查（现场从 gate 取 id/tier/detail）──
code = subprocess.run(
    [PY, "-c",
     "import sys;sys.path.insert(0,'.');import gate,json;"
     "r=gate.run_all('out/runs/queueing');"
     "print(json.dumps([{'id':c['id'],'tier':c['tier'],"
     "'status':c['status'],'detail':c['detail'][:64]} "
     "for c in r['checks']],ensure_ascii=False))"],
    capture_output=True, text=True, encoding="utf-8", errors="replace",
    cwd=HERE)
checks = json.loads(code.stdout)

lines = [r"\begin{longtable}{@{}llL{7.6cm}@{}}",
         r"\toprule",
         r"Check & Tier & What a failure means \\",
         r"\midrule", r"\endhead"]
for c in checks:
    tier = "hard" if c["tier"] == "hard" else "soft"
    lines.append("%s & %s & %s \\\\" % (
        r"\code{%s}" % c["id"], tier,
        c["detail"].replace("_", r"\_").replace("%", r"\%")
        .replace("&", r"\&").replace("#", r"\#")))
lines += [r"\bottomrule", r"\end{longtable}"]
io.open(os.path.join(OUT, "tab_checks.tex"), "w", encoding="utf-8",
        newline="\n").write("\n".join(lines) + "\n")
print("tab_checks.tex:", len(checks), "行")

# ── 表 B：23 题语料 ──
rows = [r for r in D["problems"] if r.get("pages")]
lines = [r"\begin{longtable}{@{}lrrrrr@{}}",
         r"\toprule",
         r"Problem & Pages & Figures & Tables & \multicolumn{2}{c}{Numbers traced (\%)} \\",
         r"\cmidrule(lr){5-6}",
         r" & & & & gate & verify \\",
         r"\midrule", r"\endhead"]
for r in sorted(rows, key=lambda x: x["name"]):
    g = r.get("gate_num_pct")
    v = r.get("num_pct")
    lines.append("%s & %s & %s & %s & %s & %s \\\\" % (
        r["name"].replace("_", r"\_"),
        r.get("pages", "-"), r.get("n_fig_env", "-"),
        r.get("n_tab_env", "-"),
        ("%.1f" % g) if g is not None else "-",
        ("%.1f" % v) if v is not None else "-"))
lines += [r"\bottomrule", r"\end{longtable}"]
io.open(os.path.join(OUT, "tab_corpus.tex"), "w", encoding="utf-8",
        newline="\n").write("\n".join(lines) + "\n")
print("tab_corpus.tex:", len(rows), "行")
