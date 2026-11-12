#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""案例检索：题型 + 方法 → 相似历史案例，带「迁移规则」。

为什么重写
----------
上一版按 index.csv 的整行 blob 做关键词匹配，结果「多目标」被映射成
「优化」，所有含优化的案例都命中，排序没有区分度。

实测发现：`data_features` 是每张卡独有的自由文本（139 种各 1 次），
不是可枚举标签，不能当检索键。真正可检索的是：
    problem_types   204 种标签，可归并到 9 类
    models          算法名（Pareto / 交叉验证 / 敏感性…）
    validation_methods

所以改用：题型命中为主，方法命中为辅，再从卡片里抽「迁移规则」。
"""
import csv
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
CASES = os.path.join(HERE, "kb", "external", "cumcm-pro", "cases")
IDX = os.path.join(CASES, "index.csv")

# kind.py 的 9 类 → 案例 problem_types 里的说法
ALIAS = {
    "optimization": ["优化", "规划", "非线性优化", "线性规划",
                     "整数规划", "全局优化", "动态优化", "单目标"],
    "multiobjective": ["多目标", "双目标", "多目标优化", "多目标规划"],
    "prediction": ["预测", "时间序列", "趋势"],
    "evaluation": ["评价", "排序", "综合评价", "评价类"],
    "regression": ["回归", "数据分析", "参数估计", "统计分析", "关联分析"],
    "clustering": ["聚类", "分类", "判别"],
    "mechanism": ["机理", "动力学", "微分方程", "机理建模", "系统动力学"],
    "simulation": ["仿真", "蒙特卡洛", "元胞", "随机模拟"],
    "network": ["网络", "图论", "路径"],
}

# 方法命中的加分词（出现在案例 models 字段里）
METHOD_HINT = {
    "pareto": ["pareto", "非支配", "多目标"],
    "cv": ["交叉验证", "交叉验证"],
    "sens": ["敏感性", "灵敏度", "稳健", "鲁棒"],
    "resid": ["残差", "诊断", "同方差"],
    "interval": ["置信区间", "预测区间"],
    "surrogate": ["代理模型", "响应面", "回归", "拟合"],
}

_cache = {"rows": None}


def _rows():
    if _cache["rows"] is None:
        _cache["rows"] = (list(csv.DictReader(open(IDX, encoding="utf-8-sig")))
                          if os.path.exists(IDX) else [])
    return _cache["rows"]


def _types(row):
    raw = (row.get("problem_types") or "").replace("｜", "|")
    return [t.strip() for t in raw.split("|") if t.strip()]


def find(kinds=None, methods=None, cols=None, problem="", top=3):
    """按题型与方法检索相似案例。

    kinds    来自 kind.detect 的列表，如 ["mechanism","regression"]
    methods  我们做过的方法，如 ["pareto","cv","sens"]
    """
    kinds = kinds or []
    methods = methods or []
    rows = _rows()
    if not rows:
        return []

    scored = []
    for r in rows:
        ts = _types(r)
        blob = " ".join(str(r.get(k) or "") for k in
                        ("models", "validation_methods", "core_problem",
                         "title")).lower()
        s = 0
        why = []
        # ① 题型命中：每命中一类 +3
        for k in kinds:
            if any(a in t for a in ALIAS.get(k, [k]) for t in ts):
                s += 3
                why.append(k)
        # ② 方法命中：每命中一个 +2
        for m in methods:
            if any(h.lower() in blob for h in METHOD_HINT.get(m, [])):
                s += 2
                why.append(m)
        # ③ 题面词命中（弱信号）+1
        if problem:
            for w in re.split(r"[\s,;/]+", str(problem).lower()):
                if len(w) >= 4 and w in blob:
                    s += 1
                    why.append(w)
                    break
        if s:
            scored.append((s, why, r))

    scored.sort(key=lambda x: -x[0])
    out = []
    for s, why, r in scored[:top]:
        out.append(dict(score=s, why=why, case_id=r.get("case_id"),
                        year=r.get("year"), title=r.get("title"),
                        types=r.get("problem_types"),
                        models=r.get("models"),
                        validation=r.get("validation_methods"),
                        transfer=_transfer(r.get("card_path"))))
    return out


def _transfer(card_path):
    """从案例卡里抽「迁移规则」四段。"""
    if not card_path:
        return {}
    p = os.path.join(CASES, os.path.basename(str(card_path)))
    if not os.path.exists(p):
        return {}
    try:
        t = open(p, encoding="utf-8").read()
    except OSError:
        return {}
    m = re.search(r"#+\s*迁移规则.{0,6}\n(.*?)(?=\n#|\Z)", t, re.S)
    if not m:
        return {}
    body = m.group(1)
    out = {}
    for key, pat in (("lessons", "可迁移经验"),
                     ("do_not_copy", "不应该机械复制"),
                     ("tags", "相似题检索标签"),
                     ("limits", "适用边界")):
        mm = re.search(r"【" + pat + r"[^】]*】(.*?)(?=【|\Z)", body, re.S)
        if mm:
            out[key] = re.sub(r"\s+", " ", mm.group(1)).strip()
    return out


if __name__ == "__main__":
    import sys
    r = find(kinds=["mechanism", "regression", "optimization"],
             methods=["pareto", "cv", "sens"], top=2)
    for x in r:
        print(f"  [{x['score']}] {x['case_id']} {x['year']} {x['title'][:34]}")
        print(f"      类型: {x['types']}")
        print(f"      命中: {x['why']}")
        tr = x.get("transfer") or {}
        for k in ("lessons", "limits"):
            if tr.get(k):
                print(f"      {k}: {tr[k][:150]}")
        print()
