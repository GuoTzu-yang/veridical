#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""跨领域编译验证：给 5 个新领域各造最小数据集，跑通 --compile。

为什么必须做
------------
上一轮只验证了 `domain.equations(det)` 能取到公式，**没验证渲染进
LaTeX 能编译**。那些公式里有容易出错的构造：

    \\bigl\\| r_i - r^{\\pm} \\bigr\\|_2     （双重竖线）
    \\begin{cases} 1 & i=s \\\\ -1 & i=t \\end{cases}
    \\mathcal{R}_0 = \\beta/\\gamma
    \\tfrac{1}{N}\\tfrac{dN}{dt}

没编译过就等于没验证。
"""
import os
import re
import subprocess
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(HERE, "out", "data")
OUT = os.path.join(HERE, "out", "domains")
os.makedirs(DATA, exist_ok=True)
os.makedirs(OUT, exist_ok=True)

rng = np.random.default_rng(7)
N = 24


def mk(path, cols):
    pd.DataFrame(cols).to_excel(path, index=False, sheet_name="Sheet1")


# ① evaluation：评分 / 指标 / 综合
cost = rng.uniform(10, 80, N)
qual = rng.uniform(50, 99, N)
lead = rng.uniform(3, 30, N)
score = 0.4 * qual + 0.35 * (100 - cost) + 0.25 * (30 - lead) + rng.normal(0, 2, N)
mk(os.path.join(DATA, "evaluation.xlsx"), {
    "方案编号": np.arange(1, N + 1), "采购成本": cost, "质量评分": qual,
    "交付周期": lead, "综合得分": score,
    "客户满意度": rng.uniform(60, 95, N), "售后成本": cost * 0.12 + rng.normal(0, 0.5, N),
})

# ② prediction：月份 / 趋势 / 销量
month = np.arange(1, N + 1)
sales = 120 + 3.2 * month + 6 * np.sin(month / 2.1) + rng.normal(0, 3, N)
mk(os.path.join(DATA, "prediction.xlsx"), {
    "月份": month, "单价": rng.uniform(8, 15, N),
    "广告投入": rng.uniform(20, 60, N), "销量": sales,
    "库存": rng.uniform(30, 90, N), "退货量": rng.uniform(0, 6, N),
})

# ③ network：起点 / 终点 / 距离
mk(os.path.join(DATA, "network.xlsx"), {
    "起点编号": rng.integers(1, 8, N), "终点编号": rng.integers(9, 16, N),
    "距离": rng.uniform(5, 60, N), "容量": rng.uniform(10, 100, N),
    "运输量": rng.uniform(1, 40, N), "单位成本": rng.uniform(2, 9, N),
})

# ④ queueing：到达 / 服务 / 等待
arrive = rng.uniform(20, 90, N)
desks = rng.integers(1, 6, N)
wait = 12.5 + 0.32 * arrive - 1.9 * desks + rng.normal(0, 1.2, N)
mk(os.path.join(DATA, "queueing.xlsx"), {
    "时段": np.arange(1, N + 1), "到达人数": arrive, "服务台数": desks,
    "等待时间": wait, "人工成本": 180 * desks + rng.normal(0, 20, N),
    "客户流失": rng.uniform(0, 12, N),
})

# ⑤ population：人口 / 增长
year = np.arange(2000, 2000 + N)
food = rng.uniform(100, 200, N)
pop = 80 + 2.4 * (year - 2000) - 0.0006 * (year - 2000) ** 2 + rng.normal(0, 1.5, N)
mk(os.path.join(DATA, "population.xlsx"), {
    "年份": year, "人口": pop, "食物供给": food,
    "资源消耗": pop * 1.8 + rng.normal(0, 3, N), "城市化率": rng.uniform(30, 70, N),
})

CASES = [
    ("evaluation", "采购成本,质量评分,交付周期", "综合得分",
     "综合得分,采购成本,交付周期", "供应商综合评价与选优"),
    ("prediction", "月份,单价,广告投入", "销量",
     "销量,库存,退货量", "销量预测与趋势分析"),
    ("network", "距离,容量,单位成本", "运输量",
     "运输量,距离,单位成本", "配送网络路径与流量优化"),
    ("queueing", "到达人数,服务台数", "等待时间",
     "等待时间,人工成本,客户流失", "服务台排队与窗口配置"),
    ("population", "年份,食物供给", "人口",
     "人口,资源消耗,城市化率", "人口增长趋势预测与资源承载"),
]

print(f"  数据集已写入 {DATA}")
print()
ok, fail = [], []
for name, xs, ys, mins, prob in CASES:
    xl = os.path.join(DATA, name + ".xlsx")
    tex = os.path.join(OUT, name, "paper.tex")
    os.makedirs(os.path.dirname(tex), exist_ok=True)
    r = subprocess.run(
        [sys.executable, "mmkit.py", "run", "--data", xl,
         "--y", ys, "--x", xs, "--min", mins, "--tex", tex,
         "--team", "2612345", "--problem", prob,
         "--compile", "--no-gate"],
        capture_output=True, text=True, encoding="utf-8",
        errors="replace", cwd=HERE)
    out = (r.stdout or "") + (r.stderr or "")
    log = os.path.join(OUT, name, "paper.log")
    errs = 0
    if os.path.exists(log):
        txt = open(log, encoding="utf-8", errors="replace").read()
        # 只算致命错误。图片缺失报的是
        # "Package pdftex.def Error: File `x.pdf' not found: using draft
        # setting" —— 那是降级不是失败；这个测试不负责出图。
        _fatal = [e for e in re.findall(r"^! (.+)$", txt, re.M)
                  if not e.startswith("Package pdftex.def Error")]
        errs = len(_fatal)
    eqs = 0
    if os.path.exists(tex):
        eqs = open(tex, encoding="utf-8").read().count("begin{equation}")
    pdf = os.path.join(OUT, name, "paper.pdf")
    okc = os.path.exists(pdf) and errs == 0 and eqs >= 2
    (ok if okc else fail).append(name)
    print(f"  {'OK  ' if okc else 'FAIL'} {name:<12}"
          f"equation={eqs:<3} 编译错误={errs:<3}"
          f"PDF={'有' if os.path.exists(pdf) else '无'}")
    if not okc:
        for ln in out.splitlines():
            if "错误" in ln or "失败" in ln:
                print("        " + ln.strip()[:90])
                break

print()
print(f"  {len(ok)}/{len(CASES)} 编译通过")
