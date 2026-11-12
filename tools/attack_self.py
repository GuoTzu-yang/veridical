"""借 purge 的「攻击语料」思路，打自己的门（第 120 轮）。

purge 的 87 条补丁本质是一份**攻击目录**：每一类都是「怎么让宿主安静」。
这份目录的真正价值不是照做，而是反过来问：

  我自己的护栏，能被同样的手法弄哑吗？

下面三条是最容易得手的攻击，全部真实执行、结果如实打印：

A1 空稿攻击 —— 丢一个只有导言区的 paper.tex，`numbers` 会不会空过？
A2 自我冻结 —— 拿论文自身的数字生成冻结表，溯源率会不会变成 100%？
A3 只留文献 —— 只放 thebibliography，`biblio` 会不会判「全部绑定」？
"""
import io
import json
import os
import re
import sys
import tempfile

HERE = r"C:\Users\21246\Documents\deepseek-harness\default-workspace\model1-arch"
sys.path.insert(0, HERE)
import freeze                      # noqa: E402
import gate                        # noqa: E402

OUT = []


def probe(name: str, fn):
    td = tempfile.mkdtemp(prefix="atk_")
    try:
        verdict, detail = fn(td)
    except Exception as e:                          # noqa: BLE001
        verdict, detail = "EXC", "%s: %s" % (type(e).__name__, str(e)[:70])
    OUT.append((name, verdict, detail))
    print("%-14s %-6s %s" % (name, verdict, detail))


# ── A1 空稿 ────────────────────────────────────────────────────────
def a1(td):
    io.open(os.path.join(td, "paper.tex"), "w", encoding="utf-8").write(
        "\\documentclass{article}\\begin{document}\\end{document}\n")
    json.dump(dict(n=1, items=[dict(path="m", value=1.0)]),
              io.open(os.path.join(td, "冻结数字.json"), "w", encoding="utf-8"))
    r = gate.chk_numbers(td)
    leak = r["status"] in ("PASS", "N/A")
    return ("漏了" if leak else "挡住"), r["detail"][:60]


# ── A2 自我冻结 ────────────────────────────────────────────────────
def a2(td):
    tex = ("We report 0.9123 and 0.4501 and 0.7777 and 1.2345 here.\n")
    io.open(os.path.join(td, "paper.tex"), "w", encoding="utf-8").write(tex)
    # 攻击：把论文自己写的数当成"冻结值"
    items = [dict(path="self", value=float(v))
             for v in re.findall(r"\d+\.\d+", tex)]
    json.dump(dict(n=len(items), items=items),
              io.open(os.path.join(td, "冻结数字.json"), "w", encoding="utf-8"))
    r = gate.chk_numbers(td)
    leak = r["status"] == "PASS"
    return ("漏了" if leak else "挡住"), r["detail"][:70]


# ── A3 只留文献 ────────────────────────────────────────────────────
def a3(td):
    io.open(os.path.join(td, "paper.tex"), "w", encoding="utf-8").write(
        "\\begin{document}\n\\begin{thebibliography}{9}\n"
        "\\bibitem{a} A. Author. \\emph{Title One}. doi:10.1162/tacl_a_00638.\n"
        "\\end{thebibliography}\n\\end{document}\n")
    io.open(os.path.join(td, "lit_bound.json"), "w", encoding="utf-8").write(
        json.dumps(dict(n=1, bound=1, unbound=[], uncited=[])))
    r = gate.chk_biblio(td)
    leak = r["status"] == "PASS"
    return ("漏了" if leak else "挡住"), r["detail"][:60]


print("攻击自己的门（真实执行）")
probe("A1 空稿", a1)
probe("A2 自我冻结", a2)
probe("A3 只留文献", a3)

leaks = [n for n, v, _ in OUT if v == "漏了"]
print()
print("漏了 %d/3" % len(leaks))
json.dump([dict(name=n, verdict=v, detail=d) for n, v, d in OUT],
          io.open(os.path.join(HERE, "out", "attack_self.json"), "w",
                  encoding="utf-8", newline="\n"), ensure_ascii=False, indent=1)
