"""算上下文载荷，写 out/final/context_metrics.json（第 115 轮）。

独立成文件的原因：把它塞进 freeze_paper_numbers.py 的字符串里，
反斜杠会被多打一层，`max_load` 直接算成 0 —— 这种坑本会话已踩过四次。
"""
import io
import json
import os
import re
import statistics as st

HERE = r"C:\Users\21246\Documents\deepseek-harness\default-workspace\model1-arch"
OUT = os.path.join(HERE, "out", "final")

SEC = re.compile(r"\n\\(?:sub)?section\{([^}]*)\}")
NUM = re.compile(r"(?<![\w.])-?\d+\.\d+(?![\w.])")

tex = io.open(os.path.join(OUT, "paper.tex"), encoding="utf-8").read()
plain = re.sub(r"\[[^\]]*\]", " ", tex)          # 版式参数不是主张
plain = re.sub(r"\\begin\{thebibliography\}.*?\\end\{thebibliography\}", " ",
               plain, flags=re.S)

rows = []
parts = SEC.split("\n" + plain)
for i in range(1, len(parts), 2):
    title = parts[i]
    body = parts[i + 1] if i + 1 < len(parts) else ""
    uniq = {round(float(t), 6) for t in NUM.findall(body)}
    rows.append(dict(section=title, distinct=len(uniq),
                     tokens=max(1, len(body) // 4)))

nonzero = [r["distinct"] for r in rows if r["distinct"] > 0]
all_uniq = {round(float(t), 6) for t in NUM.findall(plain)}
frozen_path = os.path.join(OUT, "冻结数字.json")
n_frozen = 0
if os.path.exists(frozen_path):
    n_frozen = len(json.load(io.open(frozen_path, encoding="utf-8")).get("items", []))

res = dict(
    paper_tokens=max(1, len(plain) // 4),
    n_distinct_all=len(all_uniq),
    n_frozen=n_frozen,
    max_load=max(nonzero) if nonzero else 0,
    median_load=int(st.median(nonzero)) if nonzero else 0,
    n_sections_with_numbers=len(nonzero),
    n_sections=len(rows),
    top=[r for r in sorted(rows, key=lambda x: -x["distinct"])[:5]],
    sections=rows)
json.dump(res, io.open(os.path.join(OUT, "context_metrics.json"), "w",
                       encoding="utf-8", newline="\n"),
          ensure_ascii=False, indent=1)
print("paper_tokens=%d  distinct=%d  max_load=%d  median(nonzero)=%d  "
      "sections_with_numbers=%d/%d  frozen=%d"
      % (res["paper_tokens"], res["n_distinct_all"], res["max_load"],
         res["median_load"], res["n_sections_with_numbers"],
         res["n_sections"], res["n_frozen"]))
