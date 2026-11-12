#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""造 simulation 题的数据集（最后一个未覆盖的题型）。

要点
----
题面必须含 simulation / monte carlo / random 等触发词，同时**避开**
optimization 的触发词（cost / design / 方案 / 优化 / 最大 / 最小），
否则会被判成优化题 —— queueing 就是这样被判成 optimization 的。
"""
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "out", "data")
os.makedirs(OUT, exist_ok=True)
rng = np.random.default_rng(23)
N = 40

lam = rng.uniform(0.4, 0.95, N)          # 到达率 / 服务率，利用率先算
mu = rng.uniform(1.0, 1.6, N)
rho = lam / mu
Lq = rho ** 2 / np.maximum(1 - rho, 0.02)      # M/M/1 平均队长
Wq = Lq / np.maximum(lam, 0.05)
servers = rng.integers(1, 4, N)
reps = rng.integers(200, 1200, N)

pd.DataFrame({
    "模拟轮次": np.arange(1, N + 1),
    "到达率": lam,
    "服务率": mu,
    "服务台数": servers,
    "重复次数": reps,
    "平均队长": Lq + rng.normal(0, 0.06, N),
    "平均等待": Wq + rng.normal(0, 0.05, N),
    "系统利用率": rho,
}).to_excel(os.path.join(OUT, "simulation.xlsx"), index=False,
            sheet_name="Sheet1")
print("  simulation.xlsx  %d 行" % N)
print("  题面建议: monte carlo simulation of queue length")