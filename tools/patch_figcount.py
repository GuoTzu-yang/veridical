"""补采：每篇论文里的图环境/表环境/includegraphics 计数。"""
import io
import json
import os
import re

HERE = r"C:\Users\21246\Documents\deepseek-harness\default-workspace\model1-arch"
P = os.path.join(HERE, "out", "final", "data.json")
D = json.load(io.open(P, encoding="utf-8"))

FIG_RE = re.compile(r"\\begin\{figure")
TAB_RE = re.compile(r"\\begin\{table")
INC_RE = re.compile(r"\\includegraphics")
CAP_RE = re.compile(r"\\caption\{")

for row in D["problems"]:
    tex = os.path.join(HERE, row["out"], "paper.tex")
    if not os.path.exists(tex):
        row["n_fig_env"] = None
        continue
    t = io.open(tex, encoding="utf-8").read()
    row["n_fig_env"] = len(FIG_RE.findall(t))
    row["n_tab_env"] = len(TAB_RE.findall(t))
    row["n_includegraphics"] = len(INC_RE.findall(t))
    row["n_caption"] = len(CAP_RE.findall(t))
    row["tex_bytes"] = len(t.encode("utf-8"))

json.dump(D, io.open(P, "w", encoding="utf-8", newline="\n"),
          ensure_ascii=False, indent=1)

vals = [(r["name"], r.get("n_fig_env"), r.get("n_tab_env"),
         r.get("n_includegraphics"), r.get("pages")) for r in D["problems"]]
ok = [v for v in vals if v[1] is not None]
print("图环境数范围: %d-%d" % (min(v[1] for v in ok), max(v[1] for v in ok)))
print("表环境数范围: %d-%d" % (min(v[2] for v in ok), max(v[2] for v in ok)))
print("includegraphics 范围: %d-%d" % (min(v[3] for v in ok),
                                       max(v[3] for v in ok)))
print()
for v in sorted(ok, key=lambda t: t[1])[:5]:
    print("  %-16s fig=%s tab=%s inc=%s pages=%s" % v)
print("  ...")
for v in sorted(ok, key=lambda t: -t[1])[:3]:
    print("  %-16s fig=%s tab=%s inc=%s pages=%s" % v)
