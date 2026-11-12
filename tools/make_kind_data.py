#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""造 clustering / multiobjective 两个数据集。

这两个题型至今没有任何一道题触发过 —— 它们各自 3 条检查项
（簇数依据 / 稳定性 / 距离度量；前沿覆盖 / 选点规则）从未被验证。
"""
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "out", "data")
os.makedirs(OUT, exist_ok=True)
rng = np.random.default_rng(11)
N = 36

# ① clustering：客户分群
spend = rng.gamma(2.5, 900, N)
freq = spend / 180 + rng.normal(0, 2.2, N)
recency = np.clip(120 - freq * 3 + rng.normal(0, 12, N), 1, None)
cats = np.clip(freq / 4 + rng.normal(0, 1, N), 1, 12)
age = rng.uniform(20, 62, N)
member = np.clip(spend / 700, 1, 5)
value = 0.45 * spend + 22 * freq - 0.6 * recency + rng.normal(0, 30, N)
pd.DataFrame({
    "客户编号": np.arange(1, N + 1), "消费金额": spend, "购买频次": freq,
    "最近购买天数": recency, "品类数": cats, "年龄": age,
    "会员等级": member, "客户价值": value,
}).to_excel(os.path.join(OUT, "clustering.xlsx"), index=False,
            sheet_name="Sheet1")

# ② multiobjective：生产计划，产量/成本/能耗互相冲突
qty = rng.uniform(100, 900, N)
cost = 40 + 0.30 * qty + rng.normal(0, 6, N)
energy = 12 + 0.055 * qty + rng.normal(0, 1.8, N)
quality = 98 - 0.012 * qty + rng.normal(0, 0.9, N)
delivery = 4 + 0.008 * qty + rng.normal(0, 0.7, N)
benefit = 0.9 * qty - 1.6 * cost - 2.4 * energy + 8 * quality - 3 * delivery
pd.DataFrame({
    "批次": np.arange(1, N + 1), "产量": qty, "单位成本": cost,
    "能耗": energy, "合格率": quality, "交付周期": delivery,
    "综合效益": benefit,
}).to_excel(os.path.join(OUT, "multiobjective.xlsx"), index=False,
            sheet_name="Sheet1")

print("  clustering.xlsx     %d 行" % N)
print("  multiobjective.xlsx %d 行" % N)