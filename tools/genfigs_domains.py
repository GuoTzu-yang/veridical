#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""给 5 个领域各生成一套图（mmkit plot 是通用的，16 种 kind）。"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable

CASES = [
    ("evaluation", "采购成本,质量评分,交付周期", "综合得分",
     "综合得分,采购成本,交付周期"),
    ("prediction", "月份,单价,广告投入", "销量", "销量,库存,退货量"),
    ("network", "距离,容量,单位成本", "运输量", "运输量,距离,单位成本"),
    ("queueing", "到达人数,服务台数", "等待时间", "等待时间,人工成本,客户流失"),
    ("population", "年份,食物供给", "人口", "人口,资源消耗,城市化率"),
    ("clustering", "消费金额,购买频次,最近购买天数", "客户价值",
     "客户价值,消费金额,最近购买天数"),
    ("multiobjective", "产量,单位成本,能耗", "综合效益",
     "产量,单位成本,能耗"),
    ("simulation", "到达率,服务率,服务台数", "平均队长",
     "平均队长,平均等待,系统利用率"),
]

# 这些图只需要 --data/--y/--x/--min，通用
# flow 画的是「技术路线图」（problem reading -> ... -> review），
# 与数据无关，所以每道题都能用；它和 --kind flow 的网络流图不是一回事。
KINDS = ("hist", "box", "corr", "resid", "qq", "pred", "sens",
         "cand", "tornado", "surfaces", "pareto", "flow")


def main():
    ok = fail = 0
    for name, xs, ys, mins in CASES:
        d = os.path.join(HERE, "out", "domains", name)
        figd = os.path.join(d, "fig")
        os.makedirs(figd, exist_ok=True)
        d = os.path.join(HERE, "out", "domains", name)
        xl = os.path.join(HERE, "out", "data", name + ".xlsx")
        if not os.path.exists(xl):
            xl = os.path.join(HERE, "out", "data", name + ".xlsx")
        got = []
        for k in KINDS:
            # --out-png 要的是**不含扩展名**的 basename：
            # 传 "hist.pdf" 会生成 hist.pdf.png + hist.pdf.pdf。
            out = os.path.join(figd, k)
            r = subprocess.run(
                [PY, "mmkit.py", "plot", "--kind", k, "--data", xl,
                 "--y", ys, "--x", xs, "--min", mins,
                 "--out-png", out],
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", cwd=HERE)
            if (os.path.exists(out + ".pdf")
                    and os.path.getsize(out + ".pdf") > 1000):
                got.append(k)
                ok += 1
            else:
                fail += 1
        print(f"  {name:<12}{len(got)}/{len(KINDS)}  {got}")
    print()
    print(f"  成功 {ok} 张 / 失败 {fail} 张")


if __name__ == "__main__":
    main()