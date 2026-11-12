#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""建题型库 + 题型识别器（「任意题直通」的第一层）。

数据来源
--------
· 139 张国赛案例卡的 index.csv（problem_types / validation_methods 真实频次）
· ultramath 33 个技能的方法名

设计
----
每个题型一条记录：
    triggers        题目描述里出现就算命中（高权重）
    data_features   列名/数据形态特征（低权重）
    required        该题型的必做项（对应 gate 检查）
    mechanism       是否需要机理段（true/false/optional）
    corpus          在 139 个案例里出现的次数（用来判断主类有多常见）

关键原则
--------
**识别不出题型时不输出机理段** —— 宁缺勿错。
现在 paper.py 是无条件输出热沉机理，换一道化工题就满篇「thermal resistance」。
"""
import ast
import csv
import json
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "kb", "methods")
os.makedirs(OUT, exist_ok=True)

# ── 从案例库统计真实频次，作为 corpus 字段 ──
IDX = os.path.join(HERE, "kb", "external", "cumcm-pro", "cases", "index.csv")
freq = {}
if os.path.exists(IDX):
    for r in csv.DictReader(open(IDX, encoding="utf-8-sig")):
        for t in (r.get("problem_types") or "").replace("｜", "|").split("|"):
            t = t.strip()
            if t:
                freq[t] = freq.get(t, 0) + 1

KINDS = {
    "optimization": {
        "name": "优化 / 规划",
        "triggers": ["最优", "最大", "最小", "成本", "利润", "收益",
                     "分配", "排班", "选址", "调度", "方案", "设计",
                     "optimal", "minim", "maxim", "cost", "profit"],
        "aliases": ["优化", "单目标优化", "非线性优化", "线性规划",
                    "整数规划", "动态规划", "启发式优化", "全局优化"],
        "data_features": ["成本", "价格", "产量", "时间", "资源"],
        "required": ["目标函数与约束写成标准形式", "求解方法与可行性检查",
                     "至少一次敏感性分析"],
        "mechanism": "optional",
        "note": "元启发式之前先建模型并检查精确/凸/混合整数求解器",
    },
    "multiobjective": {
        "name": "多目标优化",
        "triggers": ["多目标", "权衡", "冲突", "兼顾", "折中",
                     "trade-off", "pareto"],
        "aliases": ["多目标优化", "双目标", "多目标规划", "多目标"],
        "data_features": [],
        "required": ["写明目标向量而非加权和", "Pareto 前沿与非支配说明",
                     "权重或偏好的敏感性"],
        "mechanism": "optional",
        "note": "不要平均多目标直到方向/单位/尺度/偏好含义明确",
    },
    "prediction": {
        "name": "预测",
        "triggers": ["预测", "未来", "趋势", "时序", "时间序列",
                     "forecast", "predict"],
        "aliases": ["预测", "时间序列", "趋势预测", "预测类"],
        "data_features": ["时间", "日期", "年份", "月份", "day", "date"],
        "required": ["交叉验证或留出验证", "预测区间", "外推风险声明"],
        "mechanism": "false",
        "note": "小数据不要推深度学习",
    },
    "evaluation": {
        "name": "评价 / 排序",
        "triggers": ["评价", "排序", "评分", "权重", "综合", "排名",
                     "evaluation", "ranking"],
        "aliases": ["评价", "综合评价", "评价类", "排序"],
        "data_features": ["指标", "得分", "评分"],
        "required": ["指标归一化方向说明", "权重来源与合理性",
                     "方法间一致性检验"],
        "mechanism": "false",
        "note": "AHP/熵权/CRITIC/PCA/TOPSIS 不要一起用除非各有独立角色",
    },
    "regression": {
        "name": "回归 / 参数-响应映射",
        "triggers": ["拟合", "回归", "映射", "关系", "影响", "因素",
                     "相关性", "regression", "mapping"],
        "aliases": ["回归", "回归分析", "数据分析", "参数估计",
                    "统计分析", "关联分析"],
        "data_features": ["参数", "因子", "指标"],
        "required": ["候选模型对比（交叉验证）", "残差诊断",
                     "预测区间与原量纲残差"],
        "mechanism": "optional",
        "note": "相关不等于因果；不要跨子问题强制同一个模型",
    },
    "clustering": {
        "name": "聚类 / 分类",
        "triggers": ["聚类", "分类", "分群", "划分", "识别",
                     "cluster", "classif"],
        "aliases": ["聚类", "分类", "聚类分析", "判别"],
        "data_features": [],
        "required": ["簇数选择依据", "聚类有效性指标", "结果可解释性"],
        "mechanism": "false",
        "note": "",
    },
    "mechanism": {
        "name": "机理建模 / 微分方程",
        "triggers": ["机理", "物理", "微分", "演化", "扩散", "守恒",
                     "动力学", "传染病", "传热", "流动",
                     "differential", "dynamic"],
        "aliases": ["机理建模", "机理", "机理/动力学", "机理模型",
                    "微分方程", "动力学", "系统动力学"],
        "data_features": [],
        "required": ["守恒律或控制方程", "量纲一致性", "参数来源标注",
                     "解析解特例或数值稳定性验证"],
        "mechanism": "true",
        "note": "所有变量必须有物理定义和量纲",
    },
    "simulation": {
        "name": "仿真 / 随机模拟",
        "triggers": ["仿真", "模拟", "蒙特卡洛", "随机", "元胞",
                     "simulation", "monte carlo"],
        "aliases": ["仿真", "蒙特卡洛", "元胞自动机", "随机模拟"],
        "data_features": [],
        "required": ["随机性来源与种子", "重复次数与置信区间",
                     "结果收敛性"],
        "mechanism": "optional",
        "note": "",
    },
    "network": {
        "name": "图论 / 网络",
        "triggers": ["网络", "路径", "连通", "节点", "图论",
                     "network", "graph", "path"],
        "aliases": ["网络", "图论", "图论类", "路径规划"],
        "data_features": ["起点", "终点", "距离", "边"],
        "required": ["图的构造说明", "算法复杂度", "可行性与最优性"],
        "mechanism": "false",
        "note": "",
    },
}

for k, spec in KINDS.items():
    spec["corpus"] = sum(freq.get(a, 0) for a in spec["aliases"])

payload = dict(
    version=1,
    note="题型库：由 139 张国赛案例卡的 problem_types 频次 + "
         "ultramath 33 技能的题型名归纳。识别不出时不输出机理段。",
    total_cases=139,
    kinds=KINDS,
)
p = os.path.join(OUT, "index.json")
json.dump(payload, open(p, "w", encoding="utf-8", newline="\n"),
          ensure_ascii=False, indent=2)
print(f"  题型库写入 {p}")
print()
print(f"  {'题型':<28}{'案例数':>6}  需要机理")
for k, s in sorted(KINDS.items(), key=lambda x: -x[1]["corpus"]):
    print(f"  {k:<28}{s['corpus']:>6}  {s['mechanism']}")
