#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""paper.py：LaTeX 论文生成的自检。

重点不是"能拼出字符串"，而是这几条：
  · 生成的 LaTeX 必须**编译得动**（结构、转义、数学模式配对）
  · 中文列名必须英文化（英文论文里出现中文会炸）
  · 拿不到的数据要写 [TODO]，绝不编号
  · 匿名：不能出现姓名/学校
"""
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import paper  # noqa: E402

bad = 0
n = 0


def ck(name, cond, detail=""):
    global bad, n
    n += 1
    if cond:
        print(f"  [PASS] {name}" + (f"  — {detail}" if detail else ""))
    else:
        bad += 1
        print(f"  [FAIL] {name}" + (f"  — {detail}" if detail else ""))


print("=" * 74)
print("一、转义与术语翻译")
print("=" * 74)

ck("下划线被转义", paper.esc("a_b") == r"a\_b", paper.esc("a_b"))
ck("百分号被转义", paper.esc("50%") == r"50\%", paper.esc("50%"))
ck("& 被转义", paper.esc("A&B") == r"A\&B", paper.esc("A&B"))

ck("纯英文原样返回", paper.describe("temperature") == ("temperature", True),
   str(paper.describe("temperature")))
d, ok = paper.describe("针肋宽度比")
ck("中文列名能翻译", ok and "width" in d, d)
d, ok = paper.describe("无量纲热阻")
ck("热阻译成 thermal resistance", "thermal resistance" in d, d)
d, ok = paper.describe("无量纲温度非均匀性")
ck("相邻术语合并（温度+非均匀性）",
   "temperature" in d and "non-uniformity" in d, d)
d, ok = paper.describe("看不懂的中文列名")
ck("翻不出的返回 False 而非硬塞中文",
   ok is False and not paper.has_cjk(d), d)
d, ok = paper.describe("单个歧管单元内沿流向的针肋排数")
ck("长复合词取中心词（row count）",
   d.count("/") <= 3, d)

print()
print("=" * 74)
print("二、符号表 / 假设 / 公式")
print("=" * 74)

nt = paper.notation("无量纲热阻", ["针肋宽度比", "歧管深高比"])
ck("符号表含 y 和 x1,x2", len(nt["rows"]) == 3,
   str([r["symbol"] for r in nt["rows"]]))
ck("符号表是 LaTeX 表格",
   r"\begin{tabular}" in paper.notation_latex(nt))
ck("符号表用了三线表（booktabs）",
   r"\toprule" in paper.notation_latex(nt)
   and r"\bottomrule" in paper.notation_latex(nt))

a = paper.assumptions("regression", 84)
ck("回归假设 3~5 条", 3 <= len(a) <= 5, f"{len(a)} 条")
ck("小样本会补一条样本量说明",
   any("84" in s for s in a), [s[:40] for s in a if "84" in s][:1])
a2 = paper.assumptions("optimization", 100)
ck("不同类型给不同假设", a != a2, a2[0][:40])

obj = paper.objective_latex("thermal resistance", ["x_{1}", "x_{2}"],
                            True, ["x_{1} \\le 0.3"])
ck("目标函数含 min", r"\min" in obj)
ck("目标函数含 \\hat{y}（不是没定义的 g）",
   r"\hat{y}" in obj and "g(" not in obj)
ck("目标函数含约束", "s.t." in obj and "0.3" in obj)

print()
print("=" * 74)
print("三、拼出的完整论文能过结构检查")
print("=" * 74)

ctx = dict(


    mechanism_mode="full",

# 测试验证的是「完整机理」路径，显式指定 full；


# 生产默认是 auto（按题型识别）。
    title="Test Report", team="2600001",
    problem="a synthetic modelling problem",
    y="热阻", x=["宽度", "深高", "排数"], n_rows=84, n_cols=7,
    fit=dict(cands=[dict(label="linear", rmse=0.0074, gain_vs_linear=0.0),
                    dict(label="quadratic", rmse=0.0061,
                         gain_vs_linear=0.183)],
             best=dict(rmse=0.0061)),
    robustness=dict(base=dict(r2=0.62, bp=3.1, bp_crit=7.81),
                    n_stable=2, n_total=3, all_stable=False,
                    flips=["深高"]),
    eda=dict(per_col=[dict(name="宽度", mean=0.15, std=0.08,
                           min=0.0, max=0.3)]),
)
tex = paper.build(ctx)
info = paper.lint(tex)

ck("结构检查全过", info["ok"] is True, str(info["problems"]))
ck("章节齐全（Introduction / Assumptions / Formulation / "
   "Solution / Evaluation）",
   all(s in tex for s in ("Introduction", "Assumptions and Notations",
                          "Problem 1: How the geometry governs",
                          "Problem 2: Design selection", "Evaluation")))
ck("含摘要环境", r"\begin{abstract}" in tex)
ck("含参考文献", "thebibliography" in tex)
ck("含附录", r"\appendix" in tex)
ck("页眉只有队号", r"\fancyhead[C]{Team \#2600001}" in tex, "已匿名")
ck("没有姓名/学校字样",
   not any(x in tex for x in ("大学", "学院", "University", "College")))
ck("R² 的百分号已转义（不会再被当成注释）",
   r"\%" in tex and "62.00" in tex)
ck("数学模式 $ 成对", all(
    line.replace(r"\$", "").count("$") % 2 == 0
    for line in tex.splitlines() if not line.strip().startswith("%")),
   "逐行检查")

print()
print("=" * 74)
print("四、不给数据时写 [TODO] 而不是编")
print("=" * 74)

sparse = dict(title="Sparse", team="1", y="y", x=["a"], n_rows=10)
tex2 = paper.build(sparse)
info2 = paper.lint(tex2)
ck("缺数据时出现 [TODO]", info2["n_todo"] > 0, f"{info2['n_todo']} 处")
ck("缺数据时结构仍合法", info2["ok"] is True, str(info2["problems"]))
ck("缺数据时摘要不编 RMSE", "RMSE" not in tex2 or "TODO" in tex2)

print()
print("=" * 74)
print("五、lint 能抓到真错误")
print("=" * 74)

bad_tex = tex.replace(r"62.00\%", "62.00%")
w1 = paper.lint(bad_tex)
ck("lint 抓得到未转义 %",
   any("%" in p for p in w1["problems"]),
   str(w1["problems"])[:70])

bad2 = tex.replace(r"$x_{1}$", "$x_{1}", 1)
w2 = paper.lint(bad2)
ck("lint 抓得到数学模式不配对",
   any("$" in p for p in w2["problems"]),
   str(w2["problems"])[:70])

bad3 = tex.replace(r"\end{abstract}", "")
w3 = paper.lint(bad3)
ck("lint 抓得到环境不配对",
   any("环境" in p for p in w3["problems"]),
   str(w3["problems"])[:70])

bad4 = tex.replace("\\fancyhead[C]{Team",
                    "% Zhang San, Tsinghua University\n\\fancyhead[C]{Team", 1)
w4 = paper.lint(bad4)
ck("lint 抓得到身份信息",
   any("身份" in p for p in w4["problems"]),
   str(w4["problems"])[:70])

print()
print("=" * 74)
print(f"{'ALL PASS' if bad == 0 else 'FAILED'}  {n - bad} 通过 / {bad} 失败")
print("=" * 74)
raise SystemExit(0 if bad == 0 else 1)
