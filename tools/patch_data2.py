"""补算 data2.json 里解析失败的两项：本文章节权重 + 补丁账本。"""
import io
import json
import os
import re
import subprocess
import sys

HERE = r"C:\Users\21246\Documents\deepseek-harness\default-workspace\model1-arch"
OUT = os.path.join(HERE, "out", "final")
P = os.path.join(OUT, "data2.json")
D2 = json.load(io.open(P, encoding="utf-8"))

t = io.open(os.path.join(OUT, "paper.tex"), encoding="utf-8").read()
parts = re.split(r"\n\\section\{([^}]*)\}", "\n" + t)
secs = []
for i in range(1, len(parts), 2):
    body = parts[i + 1] if i + 1 < len(parts) else ""
    secs.append(dict(
        title=parts[i],
        words=len(re.findall(r"[A-Za-z][A-Za-z'\-]+", body)),
        figs=body.count("\\begin{figure}"),
        tabs=body.count("\\begin{table}")))
D2["sections"] = secs
print("小节:", len(secs))
for s in secs:
    print("   %-46s %5d 词  fig=%d tab=%d"
          % (s["title"][:46], s["words"], s["figs"], s["tabs"]))

# 补丁账本：用 verify 的口径（已落实/总数）
r = subprocess.run([sys.executable, "patches.py", "verify"], capture_output=True,
                   text=True, encoding="utf-8", errors="replace", cwd=HERE,
                   timeout=300)
m = re.search(r"(\d+)/(\d+)", (r.stdout or "") + (r.stderr or ""))
D2["patch_ledger"] = (dict(done=int(m.group(1)), total=int(m.group(2)))
                      if m else {})
print("补丁:", D2["patch_ledger"])

json.dump(D2, io.open(P, "w", encoding="utf-8", newline="\n"),
          ensure_ascii=False, indent=1)
print("已更新 data2.json")
