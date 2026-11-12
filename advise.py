#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
advise.py —— 给一道题「定题」并给出方法链（第 90 轮建）

它解决什么问题
--------------
在这之前，插件是「你让它算什么就算什么」：
    --y FILT.NTU --x ...     它就做回归
没人问一句「这道题到底该做回归吗」。
2026 中文 A 题的核心是**时序预测 + 等级占比统计**，而插件只会回归 ——
所以「任意一道题直通论文」是假的：题目类型不对，方法再好也没用。

判据必须可核查
--------------
每一类判断都挂着具体数字（时间覆盖多少天、目标列有几个、取值数多少），
不写「看起来像时序题」。判错时用户能看出是哪条依据错了。

四类题，四条方法链
------------------
    forecast  时间序列预测   → 平稳性/趋势 → 多方法竞速 → 留出检验 → 区间
    explain   关系与解释     → 相关/VIF → 结构竞速 → 残差诊断 → 稳健性
    evaluate  综合评价       → 权重（熵权/AHP）→ 排序（TOPSIS/灰色关联）
    optimize  优化与决策     → 帕累托 → 约束求解 → 灵敏度
"""

from __future__ import annotations

import os

import numpy as np


def _time_span(values) -> dict:
    """时间轴覆盖度：能判出多少天、有没有整段缺口。"""
    try:
        v = np.asarray(values, dtype=float)
    except (TypeError, ValueError):
        return dict(ok=False)
    u = np.unique(v)
    if len(u) < 2:
        return dict(ok=False, n_unique=len(u))
    period = None
    for p in range(2, min(49, len(v) // 2 + 1)):
        a, b = v[:-p], v[p:]
        if len(a) >= 8 and float(np.mean(np.abs(a - b) < 1e-9)) > 0.90 \
                and float(np.unique(v).size) / len(v) < 0.06:
            period = p
            break
    days = len(v) / period if period else None
    return dict(ok=True, n_unique=len(u), period=period, days=days,
                monotonic=(float(np.mean(np.diff(v) > 0)) > 0.95))


def coverage_gaps(ds, time_col: str) -> dict:
    """按时间轴的周期找整段缺失（A 题 2026-02 整月 NTU 全空就是这种）。

    判法：时间轴按周期切块，统计每块里"所有数值列都是 NaN"的块数。
    但 DS 已经丢掉了含 NaN 的行，所以这里改用**块的连续性**判断：
    相邻块的时间差是否等于周期。
    """
    if time_col not in ds.num_names:
        return dict(ok=False)
    v = ds.col(time_col)
    u = np.unique(v)
    if len(u) < 3:
        return dict(ok=False, why="时间列取值太少")
    period = None
    for p in range(2, min(49, len(v) // 2 + 1)):
        a, b = v[:-p], v[p:]
        if len(a) >= 8 and float(np.mean(np.abs(a - b) < 1e-9)) > 0.90:
            period = p
            break
    if not period:
        return dict(ok=False, why="找不到周期，无法判断块连续性")
    blocks = [v[i:i + period] for i in range(0, len(v) - period + 1, period)]
    first_vals = [float(b[0]) for b in blocks if len(b) == period]
    # 块首值应当单调递增（时间前进）；回落说明跨天/跨月重置
    falls = sum(1 for i in range(1, len(first_vals))
                if first_vals[i] < first_vals[i - 1])
    return dict(ok=True, period=period, n_blocks=len(blocks),
                resets=falls,
                note=("时间轴在块首回落 %d 次 —— 若这是按天切块，回落次数应等于"
                      "天数-1；明显偏少说明中间有整段缺失" % falls))


def diagnose(ds, yname: str | None = None,
             xnames: list | None = None,
             objectives: list | None = None,
             statement: str = "",
             declared_kinds: list | None = None) -> dict:
    """判断这是什么类型的题，并给出方法链与风险。

    返回 kind / kinds / chains / evidence / risks，其中 evidence 每一条都能复核。

    第 106 轮改了两处：

    ① **"optimize" 以前不可达**。原来只有四个 kind 赋值：forecast /
       explain / evaluate / unclear —— 模块自己的文档里写着「optimize →
       帕累托 → 约束求解 → 灵敏度」，但那条链永远不会被选中。
       实测 23 道题里有 22 道带目标列（min/max），全是优化题，
       而 advise 21 道判成 explain、1 道 forecast，优化一条都没报出来。

    ② **单标签表达不了混合题**。本仓库的 `题型.json` 本来就是多标签
       （icm2006c=regression、multiobjective=optimization+multiobjective+regression），
       单标签把这些信息压扁了。现在返回 `kinds` 列表，`kind` 保留为主标签
       （第一个），老调用方不受影响。

    第 107 轮加了第三处：**题面**。
    只看数据结构的话，network / simulation / mechanism / multiobjective
    这四类一个都认不出来（实测题库 8 个题型标签里 advise 只能报 4 个）。
    而 `mmkit` 本来就有 `--problem`（题面），只是没喂进来。
    """
    n = ds.n_rows
    cols = list(ds.num_names)
    evidence = []
    risks = []

    objs = [str(o).strip() for o in (objectives or []) if str(o).strip()]
    # 目标名给的是**论文显示名**（如「等待时间」），数据里的真实列名可能不同
    # （如「平均等待」）—— 必须像 mmkit 其它地方那样用 ds.pick() 解析。
    # 直接按 `o in cols` 过滤会把目标全丢掉（实测 22 道题的目标一个没进去）。
    #
    # 逐个 pick，不要整体 pick：pick 里一个名字匹配不到就抛 KeyError，
    # 整体调用会让前面已经解析成功的目标一起丢。
    _picked = []
    for _o in objs:
        try:
            _p = ds.pick([_o])
        except Exception:                               # noqa: BLE001
            continue
        if _p and _p[0] in cols:
            _picked.append(_p[0])
    objs = _picked or [o for o in objs if o in cols]
    if objs:
        evidence.append("题里带了目标列（要做决策/寻优）：" + "、".join(objs))

    import mm
    tc = []
    try:
        tc = mm.time_cols(ds)
    except Exception:                                   # noqa: BLE001
        tc = []
    dg = []
    try:
        dg = ds.degenerate_cols()
    except Exception:                                   # noqa: BLE001
        dg = []

    # ---- 时间性 ----
    time_like = bool(tc)
    span = {}
    tch = {}
    if time_like:
        # 用 time_col_health 算周期：它按"每个时点出现次数"判，
        # 能容忍少量脏值。严格全等判据会被几行脏数据直接打掉
        # （A 题实测：5 行 TIME=5.87，把相等比例从 ~1.0 拉到 0.846）。
        try:
            tch = mm.time_col_health(ds, tc[0])
        except Exception:                               # noqa: BLE001
            tch = {}
        span = dict(n_unique=len(set(tch.get("good_values") or [])) or None,
                    period=tch.get("period"))
        evidence.append(
            f"有周期时间轴 {tc[0]}（合法时点 "
            f"{len(tch.get('good_values') or [])} 个，周期 "
            f"{span.get('period')}）")
        if tch.get("n_bad"):
            evidence.append(
                f"时间列有 {tch['n_bad']} 行非法值（"
                + ", ".join(f"{v:g}" for v in tch["bad_values"][:4])
                + "）—— 这些行的时间不可信")
            risks.append(
                f"{tc[0]} 列有 {tch['n_bad']} 行不是合法时点："
                f"做时序分析前必须先剔除或修正这些行")
    else:
        evidence.append(f"没有可识别的周期时间轴（检查过 {len(cols)} 列）")

    # ---- 第 107 轮：题面也能定题型 ----
    # 只看数据结构认不出 network/simulation/mechanism/multiobjective。
    # 题面是**题面**（人给的），不是从数据猜的，所以这里给每条结论都留出处。
    _st = str(statement or "")
    _low = _st.lower()
    _KW = [
        ("network", ("网络", "流量", "运输", "路径", "network", "transport",
                     "flow", "routing")),
        ("simulation", ("模拟", "仿真", "蒙特卡洛", "simulation", "monte carlo",
                        "simulate")),
        ("mechanism", ("机理", "机制", "微分方程", "控制方程", "mechanism",
                       "differential equation")),
        ("multiobjective", ("多目标", "帕累托", "多指标寻优", "目标冲突",
                            "pareto", "multi-objective", "multiobjective",
                            "conflict", "trade-off", "trade off")),
        ("prediction", ("预测", "外推", "展望", "forecast", "predict",
                        "extrapolat", "projection", "projected")),
        ("evaluation", ("评价", "评估", "排序", "供应商选择", "evaluat",
                        "scoring", "rank")),
        ("optimization", ("优化", "决策", "配置", "最优", "分配", "optimiz",
                          "decision", "allocat")),
    ]
    _from_stmt = []
    for _lab, _words in _KW:
        for _w in _words:
            if _w in _low:
                _from_stmt.append(_lab)
                break
    if _from_stmt:
        evidence.append("题面里出现的题型线索：" + "、".join(_from_stmt)
                        + "（依据：--problem 题面文本）")

    # ---- 第 108 轮：显式声明的题型优先 ----
    # 插件是**能力层**：题型是人（LLM）读完题面后告诉它的，比插件从
    # 数据结构猜要准。所以提供 --kind 覆盖，并把它的方法链也给上。
    _declared = [str(k).strip() for k in (declared_kinds or [])
                 if str(k).strip()]
    _declared = [k for k in _declared if k not in ("unclear",)]
    if _declared:
        evidence.append("调用方显式声明的题型：" + "、".join(_declared)
                        + "（依据：--types）")


    has_y = bool(yname and yname in cols)
    n_usable = len([c for c in cols if c not in dg and c not in tc])
    evidence.append(f"可用作变量的列 {n_usable} 个（已排除准常数 {dg}、"
                    f"时间轴 {tc}）")

    # ---- 判类型 ----
    if time_like and n >= 30 and span.get("period"):
        kind = "forecast"
        chains = [
            "mmkit.py forecast --data <数据> --y <指标> --horizon 5",
            "必要时先 mmkit.py merge 把多月数据合成一条时间序",
            "看「留出 RMSE」是否赢过朴素法；赢不过就不要写预测",
        ]
        if not span.get("monotonic") and span.get("resets", 0) == 0:
            try:
                g = coverage_gaps(ds, tc[0])
                if g.get("ok"):
                    evidence.append(g["note"])
                    if g["resets"] < 1 and span.get("days"):
                        risks.append(
                            "时间轴块首从不回落 —— 若数据本应按天循环，"
                            "说明块划分或排序有问题")
            except Exception:                           # noqa: BLE001
                pass
    elif has_y and n_usable >= 2:
        kind = "explain"
        chains = [
            f"mmkit.py run --data <数据> --y {yname} --x <因子>",
            "先看 hints 的偏相关（带样本量与解释力），再决定宣称哪些方向",
            "transform robustness 会指出哪些结论随尺度翻转",
        ]
    elif n_usable >= 3 and not has_y:
        kind = "evaluate"
        chains = [
            "mmkit.py plot --kind bar --cost <全部指标>   # 熵权",
            "mmkit.py ahp --ahp \"...\"                     # 主观权重（要过 CR<0.1）",
            "mmkit.py greyrel --matrix \"...\"              # 与理想解比形状",
            "mmkit.py fuzzy --weights ... --membership ...  # 含定性指标时",
        ]
    else:
        kind = "unclear"
        chains = ["信息不足以定题，先补 --y 或 --x"]

    # ---- 第 106 轮：多标签 + 让 optimize 分支可达 ----
    # 判定：主标签按原来的规则给（explain / forecast / evaluate / unclear），
    # 但只要题里带了目标列，就**追加** optimize —— 那正是
    # 「既要解释响应、又要对目标寻优」的混合题，单标签压不下。
    kinds = [kind]
    if objs and kind != "unclear" and "optimize" not in kinds:
        kinds.append("optimize")
        chains = list(chains) + [
            "mmkit.py solve --data <数据> --y <指标> --min " + ",".join(objs)
            + "   # 以目标为约束求解",
            "mmkit.py plot --kind pareto --min " + ",".join(objs)
            + "         # 帕累托前沿 + 膝点",
            "mmkit.py plot --kind sens --y <指标> --x <因子>  # 灵敏度",
        ]
    # ---- 第 108 轮：显式声明的题型并入 kinds（最高优先） ----
    for _lab in _declared:
        if _lab not in kinds:
            kinds.append(_lab)
    for _lab in _from_stmt:
        if _lab not in kinds:
            kinds.append(_lab)

    # 每个题型对应的方法链（声明的题型也给出路，别只贴标签）
    _CHAINS = {
        "network": ["mmkit.py graph --op flow --edges <边> --nodes <节点>"
                    "   # 最大流/最小割", "mmkit.py graph --op tsp --edges <边>"],
        "simulation": ["mmkit.py run --data <数据> --y <指标> --x <因子>"
                       "   # 蒙特卡洛抽样进同一套统计",
                       "看分布而不是均值：分位数 + 区间"],
        "mechanism": ["先用 plot --kind scatter 对机理方程的量纲与单调性核一遍",
                      "机理式与数据对拍：残差图 + 参数灵敏度"],
        "multiobjective": ["mmkit.py plot --kind pareto --min <目标1> --max <目标2>",
                           "膝点选取要给理由（不是随便挑一个）"],
        "prediction": ["mmkit.py forecast --data <数据> --y <指标> --horizon 5",
                       "留出 RMSE 要赢过朴素法，赢不过就别写预测"],
        "evaluation": ["mmkit.py plot --kind bar --cost <全部指标>   # 熵权",
                       "mmkit.py ahp --ahp \"...\"                     # 主观权重",
                       "mmkit.py greyrel --matrix \"...\"              # 与理想解比形状"],
        "optimization": ["mmkit.py solve --data <数据> --y <指标> --min <目标>",
                         "mmkit.py plot --kind pareto --min <目标>",
                         "mmkit.py plot --kind sens --y <指标> --x <因子>"],
        "regression": [f"mmkit.py run --data <数据> --y {yname} --x <因子>"],
        "explain": [f"mmkit.py run --data <数据> --y {yname} --x <因子>"],
        "forecast": ["mmkit.py forecast --data <数据> --y <指标> --horizon 5"],
        "evaluate": ["mmkit.py plot --kind bar --cost <全部指标>"],
    }
    for _lab in _declared + _from_stmt:
        for _c in _CHAINS.get(_lab, []):
            if _c not in chains:
                chains.append(_c)

    # ---- 通用风险 ----
    if n < 30:
        risks.append(f"只有 {n} 行 —— 任何系数都只能当指示性结果")
    if dg:
        risks.append(f"准常数列 {dg}：进模型只会制造噪声")
    if len(dg) >= max(1, len(cols) // 3):
        risks.append(
            f"准常数列占了 {len(dg)}/{len(cols)} —— "
            f"可能数据本身不适合建模（或单位/量纲不对）")

    return dict(kind=kind, kinds=kinds, chains=chains, evidence=evidence,
                risks=risks, objectives=objs,
                n_rows=n, n_cols=len(cols), time_cols=tc,
                degenerate=dg, has_y=has_y)
