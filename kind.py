#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""题型识别器：题目描述 + 列名 → 题型。

这是「任意题直通」的第一层。识别出题型后：
  · 决定要不要输出机理段（识别不出 = 不输出，宁缺勿错）
  · 决定该做哪些必做项（对应 gate 检查）
  · 决定该检索哪些历史案例（案例库 search.py）

为什么不能跳过这一层
--------------------
现在 paper.py 无条件输出热沉机理。拿化工题跑，PDF 里 33 处
「thermal resistance / pressure drop / manifold」——
而摘要开头却是「chemical reactor yield」。自相矛盾。
"""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
IDX = os.path.join(HERE, "kb", "methods", "index.json")

_cache = {}


def load(path=IDX):
    if path not in _cache:
        _cache[path] = json.load(open(path, encoding="utf-8"))
    return _cache[path]


def detect(problem_desc="", cols=None, y=None, min_score=2,
            n_obj=None, n_rows=None, has_time=False):
    """返回 dict：kinds（有序）、scores、mechanism_needed、required。

    problem_desc 可以是英文或中文；cols 是列名列表。

    除了文字和列名，还看**结构信号** —— 它们比列名可靠得多：
    列名是用户自己起的（pop2005 / life2005 谁都猜不出题型），
    但「有几个目标」「有没有时间维度」「多少行」是数据本身的性质。
    实测 ICM 2006 C 的题面和列名都判不出类型，加上结构信号后
    判成 multiobjective（两个目标：人口与预期寿命）。
    """
    d = load()
    kinds = d["kinds"]
    text = str(problem_desc or "").lower()
    coltext = " ".join(str(c) for c in (cols or [])).lower()
    if y:
        coltext += " " + str(y).lower()

    scores, detail = {}, {}
    for kid, spec in kinds.items():
        s = 0
        hit = []
        for t in spec.get("triggers", []):
            if t.lower() in text:
                s += 2
                hit.append(t)
            elif t.lower() in coltext:
                s += 1
                hit.append(t + "(列)")
        for f in spec.get("data_features", []):
            if f.lower() in coltext:
                s += 1
                hit.append(f + "(特征)")
        # ── 结构信号 ──
        # 多目标（--min 给了 2 个以上）→ multiobjective 候选
        # 有时间列 → prediction 候选
        # 结构信号给 2 分（和题面触发词同权）：它是数据本身的性质，
        # 比列名可靠。给 1 分的话永远够不到 min_score=2 ——
        # ICM 2006 C 就是三个信号各 1 分、一个都不成立。
        if kid == "multiobjective" and (n_obj or 0) >= 2:
            s += 2
            hit.append("多目标(%d)" % n_obj)
        if kid == "prediction" and has_time:
            s += 2
            hit.append("时间维度")
        if kid == "regression" and (n_rows or 0) >= 30:
            s += 2
            hit.append("样本量 %d" % n_rows)
        if s:
            scores[kid] = s
            detail[kid] = hit

    ordered = sorted(scores.items(), key=lambda x: -x[1])
    picked = [k for k, v in ordered if v >= min_score]

    mech = False
    if picked:
        # 只要有一个命中题型要求机理，就要机理；全是 false 才不要
        flags = [kinds[k]["mechanism"] for k in picked]
        mech = any(f == "true" for f in flags)

    req = []
    for k in picked:
        for r in kinds[k].get("required", []):
            if r not in req:
                req.append(r)

    return dict(
        kinds=picked,
        scores={k: v for k, v in ordered},
        detail=detail,
        mechanism_needed=mech,
        required=req,
        top=(ordered[0][0] if ordered else None),
        confident=bool(ordered and ordered[0][1] >= 4),
    )


def summary(res):
    """人读的一行摘要。"""
    if not res["kinds"]:
        return "题型：未识别（将不输出机理段）"
    names = []
    d = load()["kinds"]
    for k in res["kinds"][:3]:
        names.append(f"{d[k]['name']}({res['scores'][k]})")
    return ("题型：" + " > ".join(names)
            + f"；机理段{'需要' if res['mechanism_needed'] else '不需要'}")


def selftest():
    bad = n = 0

    def ck(name, cond, detail=""):
        nonlocal bad, n
        n += 1
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}"
              + (f"  — {detail}" if detail else ""))
        if not cond:
            bad += 1

    # ① 热沉题：应当识别为 优化 + 参数映射，且不需要机理
    hs = detect("heat sink design under constraints",
                ["热阻", "压降", "温度非均匀性", "宽度", "深高", "排数"])
    ck("热沉题识别出题型", bool(hs["kinds"]), summary(hs))
    ck("热沉题含 optimization", "optimization" in hs["kinds"] or
       "multiobjective" in hs["kinds"])
    ck("热沉题需要机理段", hs["mechanism_needed"] is True,
       f"mechanism_needed={hs['mechanism_needed']}")

    # ② 化工题：同样不应要机理（没有守恒律描述）
    ch = detect("chemical reactor yield optimization",
                ["反应温度", "操作压力", "停留时间", "产量", "能耗", "次品率"])
    ck("化工题识别出题型", bool(ch["kinds"]), summary(ch))
    ck("化工题不需要机理段", ch["mechanism_needed"] is False, summary(ch))

    # ③ 明确的机理工题：应当要机理
    me = detect("污染物在河流中的扩散与演化，需建立微分方程",
                ["浓度", "时间", "位置"])
    ck("机理工题需要机理段", me["mechanism_needed"] is True,
       summary(me))

    # ④ 空描述：不识别，不输出机理
    em = detect("", [])
    ck("空输入不识别", em["kinds"] == [] and not em["mechanism_needed"])

    print(f"\n{'ALL PASS' if bad == 0 else 'FAILED'}  {n - bad}/{n}")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "selftest":
        raise SystemExit(selftest())
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    print("  热沉:", summary(detect("heat sink",
                                    ["热阻", "压降", "温度", "宽度"])))
    print("  化工:", summary(detect("chemical reactor yield",
                                    ["产量", "能耗", "次品率"])))
