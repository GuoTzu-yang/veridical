import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "MMKIT-使用说明.md")
s = open(P, encoding="utf-8").read()

BLOCK = """
### 最少需要几个数值列

`run` 至少需要 **2 个数值列**：1 个 `--y` + 1 个 `--x`。
少于 2 个就没法建模，这不是实现限制，是没有第二个变量就没有关系可估。

三道真实赛题实测（都在 `external/` 里，不是造的）：

| 题目 | 规模 | 数值列 | 结果 |
|---|---|---|---|
| 华数杯 2023 C | 410 行 × 15 列 | **13** | 通过，判 `regression` |
| 高教杯 2024 C | 107 行 × 2 列 | **2** | 通过，但只能单因子 |
| 五一杯 2025 C | 5000 行 × 4 列 | **1**（时间） | **不适用**——是用户行为日志，不是可回归的结构化表 |

**只有 2 个数值列时**，论文里会多出一节说明为什么没有做 one-at-a-time 的
灵敏度扫描（扫的就是那一个系数本身），并指出用交叉验证的离散度替代。
这一节是自动生成的，不需要手工补。

**1 个数值列**或**纯日志/纯分类数据**，这个工具不适用 —— 它做的是
「找关系、定形式、给区间」，不是事件序列分析。

"""

anchor = "实测对照（同一份真实水质数据）："
assert anchor in s, "no anchor"
if "最少需要几个数值列" not in s:
    s = s.replace(anchor, BLOCK.strip() + "\n\n" + anchor, 1)
    with open(P, "w", encoding="utf-8", newline="\n") as f:
        f.write(s)
    print("  added capability boundary (with real-data evidence)")
else:
    print("  already present")