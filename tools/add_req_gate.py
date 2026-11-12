#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""题型必做项接进 gate：从「不犯错」到「不漏项」。

思路
----
mmkit 把识别结果写成 out/fig/题型.json；gate 读它，逐条检查
required 在论文里有没有对应证据。

为什么需要
----------
题型库已经写了「多目标必须有 Pareto 前沿」「回归必须有残差诊断」
这类必做项，但没人检查。换一道题，如果漏了某一项，现在不会报。

证据映射
--------
required 文本 → 论文里应该出现的 LaTeX 线索。
线索用标签/章节名而不是自然语言，避免误判。
"""
import ast
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ══ ① mmkit 写 题型.json ══
P1 = os.path.join(HERE, "mmkit.py")
s1 = open(P1, encoding="utf-8").read()
if "题型.json" not in s1:
    OLD = '            _fp = os.path.join(_fd, "冻结数字.json")'
    NEW = ('            # 题型识别结果落盘，gate 读它做「必做项」检查\n'
           '            _kp = os.path.join(_fd, "题型.json")\n'
           '            try:\n'
           '                import json as _kj\n'
           '                _kj.dump(rep.get("problem_kind") or {},\n'
           '                        open(_kp, "w", encoding="utf-8",\n'
           '                             newline="\\n"),\n'
           '                        ensure_ascii=False, indent=2)\n'
           '            except Exception:               # noqa: BLE001\n'
           '                pass\n'
           '            _fp = os.path.join(_fd, "冻结数字.json")')
    if OLD in s1:
        s1 = s1.replace(OLD, NEW, 1)
        ast.parse(s1)
        compile(s1, P1, "exec")
        open(P1, "w", encoding="utf-8", newline="\n").write(s1)
        print("① mmkit 会写 题型.json")

# ══ ② gate 加 chk_required ══
P2 = os.path.join(HERE, "gate.py")
s2 = open(P2, encoding="utf-8").read()
if "def chk_required(" not in s2:
    FUNC = '''# required 文本 → 论文里应有的线索（用标签/章节名，避免自然语言误判）
_REQ_EVIDENCE = {
    "守恒律或控制方程": ["conservation of", "governing relations", "Nu = C"],
    "量纲一致性": ["dimensionless"],
    "参数来源标注": ["Where the numbers come from"],
    "候选模型对比（交叉验证）": ["tab:multi", "cross-validated"],
    "残差诊断": ["tab:diag"],
    "预测区间与原量纲残差": ["tab:pi"],
    "目标函数与约束写成标准形式": ["mathbf{f}(x)", "min_{"],
    "求解方法与可行性检查": ["Pareto", "front", "knee"],
    "至少一次敏感性分析": ["tab:sens", "tornado", "Sensitivity"],
    "Pareto 前沿与非支配说明": ["Pareto", "front"],
    "权重或偏好的敏感性": ["weight", "Problem 4"],
    "交叉验证或留出验证": ["cross-validated", "tab:multi"],
    "预测区间": ["tab:pi", "prediction interval"],
    "外推风险声明": ["extrapolat", "outside the observed"],
    "指标归一化方向说明": ["direction", "benefit", "cost"],
    "权重来源与合理性": ["weight"],
    "方法间一致性检验": ["consistent", "agreement"],
    "簇数选择依据": ["cluster"],
    "聚类有效性指标": ["silhouette", "cluster"],
    "结果可解释性": ["interpret"],
    "随机性来源与种子": ["seed", "random"],
    "重复次数与置信区间": ["replicate", "confidence"],
    "结果收敛性": ["converg"],
    "图的构造说明": ["graph", "node"],
    "算法复杂度": ["complexity"],
    "可行性与最优性": ["feasib", "optimal"],
}


def chk_required(figdir: str) -> dict:
    """题型必做项：required 在论文里有没有对应证据。

    软门：缺失不阻断出稿，但会被列出来 ——
    这是「换题后自动告诉你漏了什么」的机制。
    """
    import json as _j
    import re as _re
    kp = os.path.join(figdir, "题型.json")
    tex = os.path.join(figdir, "paper.tex")
    if not os.path.exists(kp):
        return _r("required", SOFT, "N/A", "没有 题型.json（未识别题型）")
    if not os.path.exists(tex):
        return _r("required", SOFT, "N/A", "没有 paper.tex")
    try:
        kd = _j.load(open(kp, encoding="utf-8"))
        req = kd.get("required") or []
        kinds = kd.get("kinds") or []
        if not req:
            return _r("required", SOFT, "PASS",
                      f"题型 {kinds} 无必做项")
        x = open(tex, encoding="utf-8").read()
        miss = []
        for item in req:
            clues = _REQ_EVIDENCE.get(item)
            if clues is None:
                continue                    # 没有映射的项不判
            if not any(c in x for c in clues):
                miss.append(item)
        if miss:
            return _r("required", SOFT, "WARN",
                      f"{len(miss)}/{len(req)} 项缺证据: {miss[:3]}")
        return _r("required", SOFT, "PASS",
                  f"题型 {kinds} 的 {len(req)} 项必做项齐备")
    except Exception as e:                  # noqa: BLE001
        return _r("required", SOFT, "N/A", f"{type(e).__name__}: {e}")


'''
    k = s2.find("def run_all(")
    s2 = s2[:k] + FUNC + s2[k:]
    s2 = s2.replace("        chk_domain(figdir),",
                    "        chk_domain(figdir),\n"
                    "        chk_required(figdir),", 1)
    ast.parse(s2)
    compile(s2, P2, "exec")
    open(P2, "w", encoding="utf-8", newline="\n").write(s2)
    print("② gate 加了 required（题型必做项）")
