#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lanes.py —— 多通道并行验证

旧架构（弃）
-----------
    判前 → 补证据 → 判后
    三档**串行**，取最弱一环。

    问题：串行取最弱等于「一条通道说不知道，整个结论就废」。
    那 24.7% 的推翻率里，有多少是"另一条通道其实能说清楚"？

新架构（本文件）
----------------
    N 条通道**并行**跑同一个结论，各给一票：
        SUPPORT / OPPOSE / UNKNOWN   + 强度 + 证据

    然后按票汇总，不是取 min()。

    为什么这更对：
      1. 一条通道失败不拖死全案
      2. 反对票能被单独看见（串行里"最弱一环"看不出方向）
      3. 「不知道」是信息，不是零分

投票规则（这是设计核心，不是实现细节）
------------------------------------
    o = 反对票数，u = 不知道票数，s = 支持票数，n = 总票数

      o > 0            → 最高只能给「中」（有反证就不许说强）
      u / n > 0.5      → 最高只能给「弱」（多数不知道 → 不许说知道）
      s == n           → 强
      其余             → 中

    去重规则（踩过坑，制度化）：
    每条通道声明 source。**同 source 的通道只算一票**。
    同一份数据切 5 折、换 3 个种子，是同一个 source，不是 5 票。

跑法
----
    python lanes.py selftest    # 自检（不需要数据）
    python lanes.py demo        # 用 APMCM 真题演示

**用户入口是 mmkit.py，不是这里。**
lanes.py 是库：mm.py 算结果，lanes.py 验结果，mmkit.py 把两半接起来。

单一入口这条规则已经落实（第 77 轮）：
本项目曾经有 mm.py / solve_mm.py / craft.py 三个都能验数模结论的入口，
改一处漏两处。现在 solve_mm.py 和 craft.py 已删，备份在
`_removed_20261108/`；它们独有的两项能力（多种子竞速、异方差 BP 数值）
已迁进 mmkit.py 的 race_seeds()。
"""

from __future__ import annotations

import io
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

SUPPORT, OPPOSE, UNKNOWN = "support", "oppose", "unknown"


# ══════════════════════════════════════════════════════════════════════
#  基础类型
# ══════════════════════════════════════════════════════════════════════
class Vote:
    """一条通道的票。strength ∈ [0,1]，用来在同向票里分强弱。

    veto（第 15 轮补）：这条通道的反对票是否一票否决。

    为什么必须加：APMCM 真题上跑出来的事 ——
        direction 通道明确反对（偏相关 +0.64，主张却要求负），
        但 cv/boot/holdout/resid/extrap/perturb 六条一起说"模型没问题"，
        多数票把方向错误淹掉了，最终只判 degrade 不判 reject。

    教训：**"模型拟合好"和"结论方向对"不是同一个维度上的证据。**
    前者说一千遍，也驳不倒后者的一次反证。
    veto 通道的反对票必须越过票数，直接定案。
    """

    __slots__ = ("verdict", "strength", "why", "lane", "source", "veto")

    def __init__(self, verdict: str, strength: float = 0.5,
                 why: str = "", lane: str = "", source: str = "",
                 veto: bool = False):
        if verdict not in (SUPPORT, OPPOSE, UNKNOWN):
            raise ValueError(verdict)
        self.verdict = verdict
        self.strength = float(np.clip(strength, 0.0, 1.0))
        self.why = why
        self.lane = lane
        self.source = source or lane
        self.veto = veto

    def __repr__(self):
        return f"<{self.lane}:{self.verdict[:3]} {self.strength:.2f}" \
               f"{'!' if self.veto else ''}>"


class Claim:
    """要验的结论。

    第 3 轮补的方向字段：这是本文件第 1 版最大的架构漏洞 ——
    七条通道验的全是「线性模型能不能描述这份数据」，
    **没有一条在验"结论本身对不对"**。

    "X 增，Y 降" 和 "X 增，Y 增" 是同一个模型的两种主张，
    模型拟合好，两条都能通吃。不验方向，就等于没验结论。

    sign=None  只验模型（旧行为）
    sign={i:+1/-1}  还要验第 i 个自变量对 y 的偏效应方向
    """

    def __init__(self, cid: str, text: str, X=None, y=None, meta=None,
                 sign=None):
        self.cid = cid
        self.text = text
        self.X = None if X is None else np.asarray(X, float)
        self.y = None if y is None else np.asarray(y, float)
        self.meta = dict(meta or {})
        self.sign = dict(sign or {})


# ══════════════════════════════════════════════════════════════════════
#  通道
# ══════════════════════════════════════════════════════════════════════
LANES: dict[str, dict] = {}


def lane(name: str, source: str, veto: bool = False):
    """登记一条通道。

    source 决定"独立票"的粒度；veto 决定反对票是否一票否决。
    只有"验结论本身"的通道才配 veto —— 比如方向、量纲一致性。
    "模型好不好"这类通道不配：它们驳不倒一句具体的主张。
    """
    def deco(fn):
        LANES[name] = dict(fn=fn, name=name, source=source, veto=veto)
        return fn
    return deco


def _design(X, kind):
    n, p = X.shape
    ones = np.ones((n, 1))
    if kind == "linear":
        return np.hstack([ones, X])
    if kind == "quad":
        cols = [ones, X]
        cols += [(X[:, i] ** 2).reshape(-1, 1) for i in range(p)]
        cols += [(X[:, i] * X[:, j]).reshape(-1, 1)
                 for i in range(p) for j in range(i + 1, p)]
        return np.hstack(cols)
    raise ValueError(kind)


def _fit_linear(X, y, kind="linear", ridge=0.0):
    A = _design(X, kind)
    AtA = A.T @ A
    if ridge > 0:
        AtA = AtA + ridge * np.eye(AtA.shape[0])
    try:
        coef = np.linalg.solve(AtA, A.T @ y)
    except np.linalg.LinAlgError:
        coef, *_ = np.linalg.lstsq(A, y, rcond=None)
    return coef, A @ coef


@lane("direction", source="data", veto=True)
def lane_direction(c: Claim) -> Vote:
    """通道 0（第 3 轮补）：结论方向对不对。

    这是唯一一条真正在验「结论」而不是「模型」的通道。

    做法：偏相关。把 y 和 X_j 都对其他 X 回归，取残差的相关系数。
    为什么不用简单相关：三个自变量互相关时，简单相关会把别人的效应
    算到这一个头上 —— 那正是辛普森悖论的入口。
    """
    if c.X is None or c.y is None:
        return Vote(UNKNOWN, why="没给数据", lane="direction")
    if not c.sign:
        return Vote(UNKNOWN, why="这条主张没声明方向", lane="direction")

    X, y = c.X, c.y
    n, p = X.shape
    coef, pred = _fit_linear(X, y)

    wrong = []
    right = []
    unk = []
    for j, want in c.sign.items():
        j = int(j)
        # 偏相关：y 与 X_j 各自对「其余自变量」回归后的残差相关
        others = np.delete(X, j, axis=1)
        A = np.hstack([np.ones((n, 1)), others]) if others.size else \
            np.ones((n, 1))
        ry = y - A @ np.linalg.lstsq(A, y, rcond=None)[0]
        rx = X[:, j] - A @ np.linalg.lstsq(A, X[:, j], rcond=None)[0]
        denom = math.sqrt(float(np.sum(rx ** 2)) * float(np.sum(ry ** 2)))
        if denom <= 0:
            unk.append(j)
            continue
        pc = float(np.sum(rx * ry)) / denom
        if abs(pc) < 0.05:
            unk.append(j)
        elif (pc > 0) == (want > 0):
            right.append((j, pc))
        else:
            wrong.append((j, pc))

    if wrong:
        return Vote(OPPOSE, min(1.0, 0.6 + 0.1 * len(wrong)),
                    "方向反了：" + "，".join(f"x{j} 偏相关{p:+.2f}≠期望"
                                            for j, p in wrong),
                    lane="direction")
    if unk:
        return Vote(UNKNOWN, 0.4,
                    "看不出方向：" + "，".join(f"x{j}" for j in unk),
                    lane="direction")
    return Vote(SUPPORT, min(1.0, 0.5 + 0.15 * len(right)),
                "方向对：" + "，".join(f"x{j} 偏相关{p:+.2f}" for j, p in right),
                lane="direction")


@lane("cv", source="data")
def lane_cv(c: Claim, k=5, seed=0) -> Vote:
    """通道 1：K 折交叉验证 —— 泛化能力。"""
    if c.X is None or c.y is None:
        return Vote(UNKNOWN, why="没给数据", lane="cv")
    n = len(c.y)
    if n < k * 2:
        return Vote(UNKNOWN, why=f"样本 {n} 太少，折不出 {k} 折", lane="cv")
    idx = np.arange(n)
    np.random.default_rng(seed).shuffle(idx)
    errs = []
    for f in np.array_split(idx, k):
        tr = np.setdiff1d(idx, f)
        coef, _ = _fit_linear(c.X[tr], c.y[tr])
        pred = _design(c.X[f], "linear") @ coef
        errs.append(float(np.sqrt(np.mean((pred - c.y[f]) ** 2))))
    errs = np.array(errs)
    rmse, sd = float(errs.mean()), float(errs.std(ddof=1))
    cv = sd / rmse if rmse > 0 else 0.0
    if cv < 0.25:
        return Vote(SUPPORT, 1.0 - cv, f"CV RMSE={rmse:.4f}，折间波动 {cv:.1%}",
                    lane="cv")
    if cv > 0.6:
        return Vote(OPPOSE, min(1.0, cv), f"折间波动 {cv:.1%}，模型不稳",
                    lane="cv")
    return Vote(UNKNOWN, 1.0 - cv, f"波动 {cv:.1%} 居中，判不了", lane="cv")


@lane("boot", source="data")
def lane_bootstrap(c: Claim, n=400, seed=0) -> Vote:
    """通道 2：自助法 —— 结论的稳定性。

    第 1 轮踩的坑：用 `std(coef)/|mean(coef)|` 衡量稳定。
    系数里有一个接近 0 的（截距或某个弱项），分母贴近 0，比值爆到 416%，
    于是一份好好的数据被判"不稳"。

    **比值型指标遇上接近 0 的分母就是幻觉来源。**
    改法：不看系数本身，看**预测值**的波动 —— 预测值有物理量纲，
    用 y 的标准差归一化，不会出现除以接近 0 的情况。
    """
    if c.X is None or c.y is None:
        return Vote(UNKNOWN, why="没给数据", lane="boot")
    rng = np.random.default_rng(seed)
    N = len(c.y)
    preds = []
    for _ in range(n):
        i = rng.integers(0, N, N)
        try:
            coef, _ = _fit_linear(c.X[i], c.y[i])
            preds.append(_design(c.X, "linear") @ coef)
        except Exception:
            continue
    if len(preds) < n // 2:
        return Vote(UNKNOWN, why="重采样成功率过低", lane="boot")
    P = np.array(preds)
    sd = P.std(0)
    scale = float(c.y.std(ddof=1)) or 1.0
    worst = float(np.max(sd) / scale)
    if worst < 0.15:
        return Vote(SUPPORT, max(0.0, 1.0 - worst * 3),
                    f"重采样后预测值抖动 {worst:.1%}（相对 y 的 std）", lane="boot")
    if worst > 0.5:
        return Vote(OPPOSE, min(1.0, worst * 2),
                    f"预测值抖动 {worst:.0%}，结论不稳", lane="boot")
    return Vote(UNKNOWN, max(0.0, 1.0 - worst), f"抖动 {worst:.1%} 居中",
                lane="boot")


@lane("holdout", source="data")
def lane_holdout(c: Claim, frac=0.25, seed=0) -> Vote:
    """通道 3：留出集 —— 训练/测试分离，最朴素的诚实检验。"""
    if c.X is None or c.y is None:
        return Vote(UNKNOWN, why="没给数据", lane="holdout")
    n = len(c.y)
    if n < 20:
        return Vote(UNKNOWN, why=f"{n} 行太少，留出会太薄", lane="holdout")
    idx = np.arange(n)
    np.random.default_rng(seed).shuffle(idx)
    cut = int(n * (1 - frac))
    tr, te = idx[:cut], idx[cut:]
    coef, _ = _fit_linear(c.X[tr], c.y[tr])
    pred = _design(c.X[te], "linear") @ coef
    rmse_te = float(np.sqrt(np.mean((pred - c.y[te]) ** 2)))
    coef2, _ = _fit_linear(c.X, c.y)
    pred_tr = _design(c.X, "linear") @ coef2
    rmse_tr = float(np.sqrt(np.mean((pred_tr - c.y) ** 2)))
    ratio = rmse_te / rmse_tr if rmse_tr > 0 else float("inf")
    if ratio < 1.5:
        return Vote(SUPPORT, 1.0 - min(1.0, (ratio - 1) / 0.5),
                    f"留出/训练 RMSE 比 {ratio:.2f}", lane="holdout")
    if ratio > 3.0:
        return Vote(OPPOSE, 1.0, f"留出 RMSE 是训练的 {ratio:.1f} 倍，过拟合",
                    lane="holdout")
    return Vote(UNKNOWN, 0.5, f"比值 {ratio:.2f} 居中", lane="holdout")


@lane("resid", source="data")
def lane_residual(c: Claim) -> Vote:
    """通道 4：残差诊断 —— 模型假设成不成立。"""
    if c.X is None or c.y is None:
        return Vote(UNKNOWN, why="没给数据", lane="resid")
    coef, pred = _fit_linear(c.X, c.y)
    r = c.y - pred
    n = len(r)
    # 1) 残差与预测值相关 = 结构没抽干净
    A = np.hstack([np.ones((n, 1)), pred.reshape(-1, 1)])
    cc, *_ = np.linalg.lstsq(A, r, rcond=None)
    rp = A @ cc
    ss_res = float(np.sum((r - rp) ** 2))
    ss_tot = float(np.sum((r - r.mean()) ** 2))
    r2_structure = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
    # 2) 异方差：残差平方对预测值回归
    e2 = r ** 2
    cc2, *_ = np.linalg.lstsq(A, e2, rcond=None)
    p2 = A @ cc2
    ss2 = float(np.sum((e2 - p2) ** 2))
    st2 = float(np.sum((e2 - e2.mean()) ** 2))
    bp = n * (1 - ss2 / st2) if st2 > 0 else 0.0
    bad = []
    if r2_structure > 0.1:
        bad.append(f"残差还能被预测值解释 {r2_structure:.1%}")
    if bp > 7.81:
        bad.append(f"异方差 BP={bp:.2f}>7.81")
    if bad:
        return Vote(OPPOSE, min(1.0, r2_structure * 2 + bp / 50),
                    "；".join(bad), lane="resid")
    return Vote(SUPPORT, 1.0 - r2_structure,
                f"无残余结构（R²={r2_structure:.3f}），无强异方差（BP={bp:.2f}）",
                lane="resid")


@lane("extrap", source="data")
def lane_extrap(c: Claim) -> Vote:
    """通道 5：外推域 —— 结论的适用范围有多大。

    第 9 轮重写。第一版有两个错：

    1) 只数「落在边界 2% 内的点数」。均匀网格设计（比如实验设计表）
       边界点天然很多，于是无脑 SUPPORT —— 但网格设计的**中间格子**
       根本没采样过，外推风险恰恰在那里。

    2) 没区分"连续变量"和"离散设计"。离散取值（0/0.1/0.2/0.3）
       意味着"0.25 这个点从没测过"，它不是插值，是外推。

    改法：按列判断是离散设计还是连续变量，分别算覆盖率。
    """
    if c.X is None:
        return Vote(UNKNOWN, why="没给数据", lane="extrap")
    X = c.X
    n, p = X.shape
    discrete, continuous = [], []
    for j in range(p):
        u = np.unique(X[:, j])
        if len(u) <= 10:
            discrete.append((j, len(u)))
        else:
            continuous.append(j)

    problems = []
    if discrete:
        # 离散列：可能取值组合数 vs 实际采到的组合数
        combos = int(np.prod([k for _, k in discrete]))
        seen = len({tuple(np.round(X[i, [j for j, _ in discrete]], 9))
                    for i in range(n)})
        cover = seen / combos if combos else 0.0
        if cover < 0.05:
            problems.append(f"离散设计只覆盖 {seen}/{combos} 个组合"
                            f"（{cover:.2%}）")
        if cover < 0.6:
            return Vote(OPPOSE, min(1.0, 1 - cover),
                        "；".join(problems) or "离散组合覆盖不足，"
                        "没测过的组合不能算插值", lane="extrap")
    if continuous:
        # 连续列：看极值附近有没有点
        for j in continuous:
            lo, hi = X[:, j].min(), X[:, j].max()
            span = hi - lo
            if span <= 0:
                continue
            w = 0.05 * span
            near_edge = np.sum((X[:, j] <= lo + w) | (X[:, j] >= hi - w))
            if near_edge == 0:
                problems.append(f"x{j} 极值附近 0 个点，端点行为无依据")
        if problems:
            return Vote(OPPOSE, 0.7, "；".join(problems), lane="extrap")

    return Vote(SUPPORT, 0.8,
                f"{len(discrete)} 个离散列组合覆盖充分，"
                f"{len(continuous)} 个连续列端点有样本", lane="extrap")


@lane("perturb", source="data")
def lane_perturb(c: Claim, delta=0.01, seed=0) -> Vote:
    """通道 6：扰动 —— 结论对小噪声的耐受度。"""
    if c.X is None or c.y is None:
        return Vote(UNKNOWN, why="没给数据", lane="perturb")
    rng = np.random.default_rng(seed)
    coef0, _ = _fit_linear(c.X, c.y)
    base = float(np.linalg.norm(coef0))
    worst = 0.0
    for _ in range(50):
        Xn = c.X + rng.normal(0, delta, c.X.shape) * c.X.std(0)
        try:
            coef, _ = _fit_linear(Xn, c.y)
        except Exception:
            continue
        d = float(np.linalg.norm(coef - coef0)) / (base + 1e-12)
        worst = max(worst, d)
    if worst < 0.3:
        return Vote(SUPPORT, 1.0 - worst, f"{delta:.0%} 噪声下系数最大偏移 {worst:.1%}",
                    lane="perturb")
    if worst > 1.0:
        return Vote(OPPOSE, 1.0, f"噪声下系数偏移 {worst:.0%}，结论不稳",
                    lane="perturb")
    return Vote(UNKNOWN, 0.4, f"偏移 {worst:.1%} 居中", lane="perturb")


@lane("rival", source="model")
def lane_rival(c: Claim) -> Vote:
    """通道 7：对手模型 —— 有没有更简单的解释？

    source="model"：它和上面六条**不是同一个来源**，
    因为它比的是"另一种模型"，不是"同一模型换切法"。
    """
    if c.X is None or c.y is None:
        return Vote(UNKNOWN, why="没给数据", lane="rival")
    n = len(c.y)
    if n <= c.X.shape[1] + 3:
        return Vote(UNKNOWN, why="样本不够比两个模型", lane="rival")
    _, pred1 = _fit_linear(c.X, c.y)
    rmse1 = float(np.sqrt(np.mean((pred1 - c.y) ** 2)))
    # 零模型：只用均值
    rmse0 = float(np.sqrt(np.mean((c.y - c.y.mean()) ** 2)))
    if rmse0 <= 0:
        return Vote(UNKNOWN, why="因变量无变异", lane="rival")
    gain = (rmse0 - rmse1) / rmse0
    # 第 18 轮：强度标定。原来 strength=min(1,gain)，改善 36% 只给 0.36，
    # 而 36% 的解释力在建模里已经算可用。改成 50% 改善封顶。
    if gain > 0.3:
        return Vote(SUPPORT, min(1.0, gain / 0.5),
                    f"比均值模型好 {gain:.1%}（强度按 50% 改善封顶）",
                    lane="rival")
    if gain < 0.05:
        return Vote(OPPOSE, 1.0, f"只比均值模型好 {gain:.1%}，等于没解释",
                    lane="rival")
    return Vote(UNKNOWN, gain / 0.5, f"改善 {gain:.1%} 有限", lane="rival")


# ══════════════════════════════════════════════════════════════════════
#  跨主张一致性（第 17 轮）
# ══════════════════════════════════════════════════════════════════════
def cross_check(items: list) -> list[dict]:
    """找出**互相矛盾却都被支持**的主张。

    items: [(cid, Claim, verdict_dict), ...]

    为什么需要：APMCM 真题上 B1「深高比↑热阻↓」和 B1r「深高比↑热阻↑」
    曾经**同时被判支持** —— 因为每条主张各自验各自的，没人管全局。

    两条互斥的主张不可能同时成立。出现这种情况，
    至少一条的方法出了问题（通常是方向通道没接上，或数据被污染）。
    这是**多档并进**比串行三关多出来的能力：串行只看单条，
    并行才看得见"这几条凑在一起自相矛盾"。
    """
    out = []
    for i in range(len(items)):
        cid_a, ca, va = items[i]
        for j in range(i + 1, len(items)):
            cid_b, cb, vb = items[j]
            # 两条都被支持（没被推翻、不是 reject）
            if va.get("refuted") or vb.get("refuted"):
                continue
            if va.get("final") not in ("pass", "degrade"):
                continue
            if vb.get("final") not in ("pass", "degrade"):
                continue
            shared = set(ca.sign) & set(cb.sign)
            for k in shared:
                if ca.sign[k] == -cb.sign[k]:
                    out.append(dict(a=cid_a, b=cid_b, var=int(k),
                                    sign_a=ca.sign[k], sign_b=cb.sign[k],
                                    why=f"{cid_a} 与 {cid_b} 对 x{k} 的方向相反，"
                                        f"却都被支持"))
    return out


def fmt_cross(conflicts: list[dict]) -> str:
    if not conflicts:
        return "    没有互斥主张同时对得上 —— 这一组自洽"
    lines = ["    发现互斥主张同时对得上（至少一条有问题）："]
    for c in conflicts:
        lines.append(f"      · {c['why']}")
    lines.append("    处理：这类冲突不能靠加权解决，只能回去查方向通道。")
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════
#  缓存（第 10 轮）
# ══════════════════════════════════════════════════════════════════════
_CACHE: dict[str, dict] = {}
_CACHE_HIT = [0, 0]          # [命中, 未命中]


def fingerprint(c: Claim) -> str:
    """按内容取指纹。同一份数据 + 同一条主张 → 同一个 key。

    用内容而不是 cid：cid 一样但数据换了的，必须重算。
    """
    import hashlib
    h = hashlib.sha256()
    if c.X is not None:
        h.update(np.ascontiguousarray(c.X, dtype=float).tobytes())
    if c.y is not None:
        h.update(np.ascontiguousarray(c.y, dtype=float).tobytes())
    h.update(repr(sorted(c.sign.items())).encode())
    h.update(repr(sorted(c.meta.items())).encode())
    return f"{c.cid}|{h.hexdigest()[:20]}"


def _copy_vote(v: Vote) -> Vote:
    """整票复制。缓存进出都必须走这里。

    为什么单独抽出来：原来缓存往返写的是
        Vote(v.verdict, v.strength, v.why, v.lane, v.source)
    —— 只传五个位置参数，**veto 被静默丢掉**。实测后果：
        direction 通道带 veto 反对 → 首次运行 grade=弱（vetoed=True）
        同一主张命中缓存        → grade=中（vetoed=False）
    同一份输入、同一份数据，判决随缓存状态改变，而且变的是危险方向
    （否决被多数票淹掉，正是第 15 轮加 veto 要防的事）。
    抽成一个函数，以后 Vote 加字段时只有一处要改。
    """
    return Vote(v.verdict, v.strength, v.why, v.lane, v.source, v.veto)


def run_cached(c: Claim, lanes=None, parallel=True, timeout=60.0,
               use_cache=True) -> list[Vote]:
    """第 10 轮的缓存层。

    为什么需要：建模时会反复验同一条主张（改阈值、改布局、改报告格式），
    每次都重跑 8 条通道，其中 bootstrap 400 次重采样最贵。
    缓存把「改展示」和「改判断」分开 —— 改展示不该重算证据。
    """
    if not use_cache:
        return run_lanes(c, lanes, parallel, timeout)
    key = fingerprint(c) + "|" + ",".join(lanes if lanes else sorted(LANES))
    if key in _CACHE:
        _CACHE_HIT[0] += 1
        return [_copy_vote(v) for v in _CACHE[key]]
    _CACHE_HIT[1] += 1
    votes = run_lanes(c, lanes, parallel, timeout)
    _CACHE[key] = [_copy_vote(v) for v in votes]
    return votes


def cache_stats() -> dict:
    hit, miss = _CACHE_HIT
    return dict(hit=hit, miss=miss, n_entries=len(_CACHE),
                hit_rate=hit / (hit + miss) if hit + miss else 0.0)


def cache_clear() -> None:
    _CACHE.clear()
    _CACHE_HIT[0] = _CACHE_HIT[1] = 0


# ══════════════════════════════════════════════════════════════════════
#  接入闸门（第 12 轮）
# ══════════════════════════════════════════════════════════════════════
GRADE_TO_E2 = {"强": 1, "中": 1, "弱": 0, "无": 0}


def to_verdict(claim: Claim, agg: dict, reproduced=False) -> dict:
    """把通道汇总翻译成架构闸门的判决。

    第 12 轮发现一个**架构矛盾**，值得记下来：

        8 条通道全部支持，C 还是只有 4 → 只能 degrade，永远到不了 pass。
        因为 e3 卡在 1：所有通道跑的都是**同一份数据**，
        「换 8 种方法切同一份数据」不叫复现，复现是
        「换台机器/换份数据/换个人，重算出同一个数」。

    这不是缺陷，是闸门在守一句实话：**单份数据的内部一致性，
    撑不起"这条结论可复现"**。

    所以：
        reproduced=False → e3=1 → 最高 degrade（C=4）
        reproduced=True  → e3=2 → 可以 pass（C=5）

    `reproduced` 必须由调用方**明确声明**并给出依据（重跑记录、
    第二份数据源、独立实现）。默认 False —— 门槛就是要人自己迈。
    """
    from harness import Claim as HClaim, EvidenceEnv, run_gates
    has_oppose = agg.get("vetoed", False) or any(
        ps["verdict"] == OPPOSE for ps in agg["per_source"])
    e2 = GRADE_TO_E2.get(agg["grade"], 0)
    e3 = 2 if reproduced else 1
    hc = HClaim(claim.cid, claim.text, e1=2, e2=e2, e3=e3, kind="world",
                refuted_by_test=has_oppose)
    g = run_gates(hc, EvidenceEnv(3))
    return dict(cid=claim.cid, text=claim.text, grade=agg["grade"],
                final=g["final"], C=g["C"], refuted=has_oppose,
                reproduced=reproduced,
                blocked_at=g.get("blocked_at"), why=agg["why"])


# ══════════════════════════════════════════════════════════════════════
#  汇总
# ══════════════════════════════════════════════════════════════════════
def _run_one(nm: str, c: Claim) -> Vote:
    spec = LANES.get(nm)
    if spec is None:
        return Vote(UNKNOWN, why=f"没有这条通道 {nm}", lane=nm)
    try:
        v = spec["fn"](c)
        if not isinstance(v, Vote):
            v = Vote(UNKNOWN, why=f"{nm} 返回了 {type(v).__name__}", lane=nm)
        if not v.lane:
            v.lane = nm
        v.source = spec["source"]        # ← 以登记表为准，覆盖通道自己的声明
        v.veto = spec.get("veto", False)
        return v
    except Exception as e:
        return Vote(UNKNOWN, why=f"{nm} 抛异常：{type(e).__name__}: {e}",
                    lane=nm, source=spec["source"],
                    veto=spec.get("veto", False))


def run_lanes(c: Claim, lanes=None, parallel=True, timeout=60.0) -> list[Vote]:
    """跑所有通道。

    第 7 轮：真并行。原来叫"并行"其实是 for 循环，名不副实。
        线程池在这件事上是有效的 —— numpy 的 BLAS 调用会释放 GIL，
        而且每条通道算的是不同东西，没有共享写。

    第 8 轮：超时。一条通道卡住（大矩阵 bootstrap、病态矩阵求逆）
        会让整个判定挂住。给每条通道一个期限，超了就记 UNKNOWN ——
        不知道比永远等下去强。

    顺序保证：结果永远按 `names` 的顺序返回，不按完成顺序。
    否则同一个输入两次跑出不同顺序，日志对不上。
    """
    names = list(lanes if lanes else LANES)
    out: list[Vote | None] = [None] * len(names)

    if not parallel or len(names) <= 1:
        for i, nm in enumerate(names):
            out[i] = _run_one(nm, c)
        return out                                        # type: ignore

    from concurrent.futures import ThreadPoolExecutor, TimeoutError as FTime
    # 第 8 轮补的那个坑：不能用 `with ThreadPoolExecutor(...)`。
    # `with` 退出时走 shutdown(wait=True)，会一直等挂起的线程跑完 ——
    # 于是"超时"只体现在结果上（拿到 UNKNOWN），主流程还是被拖住。
    # 实测：挂 3s 的通道，加了 timeout=0.3 仍然耗 3.00s。
    ex = ThreadPoolExecutor(max_workers=min(len(names), 8))
    try:
        futs = [(i, nm, ex.submit(_run_one, nm, c))
                for i, nm in enumerate(names)]
        for i, nm, f in futs:
            try:
                out[i] = f.result(timeout=timeout)
            except FTime:
                src = LANES.get(nm, {}).get("source", nm)
                out[i] = Vote(UNKNOWN,
                              why=f"{nm} 超时（上限 {timeout * 1000:.0f}ms）",
                              lane=nm, source=src)
            except Exception as e:
                out[i] = Vote(UNKNOWN,
                              why=f"{nm} 收票失败：{type(e).__name__}",
                              lane=nm, source=LANES.get(nm, {}).get("source", nm))
    finally:
        ex.shutdown(wait=False, cancel_futures=True)
    return out                                            # type: ignore


def aggregate(votes: list[Vote]) -> dict:
    """按 source 去重后投票汇总。

    去重不是"优化"，是**正确性**：
    同一份数据切 5 折 → 5 条通道，但它们说的是同一件事。
    不按 source 去重，样本被自己重复投票，置信度虚高。

    第 4~6 轮修了三处：
      4) 强度参与了决策（原来算了不用，白算）
      5) 同源平票不再一律 UNKNOWN —— 有反对票时反对优先
      6) 「强」要求支持方强度够，不许 6 条弱支持凑出一个强

    第 15 轮补的 veto：
        带 veto 的通道只要有一票 OPPOSE，直接定案，不看票数。
        理由见 Vote 的类注释 —— 方向错被多数票淹没是实跑出来的事故。
    """
    # 第 15 轮：veto 先过
    veto_oppose = [v for v in votes if v.veto and v.verdict == OPPOSE]
    if veto_oppose:
        srcs = {v.source for v in veto_oppose}
        return dict(grade="弱", why=f"{len(veto_oppose)} 票否决："
                    + "；".join(v.why[:50] for v in veto_oppose),
                    tally={SUPPORT: 0, OPPOSE: len(srcs), UNKNOWN: 0},
                    n_sources=len(srcs), per_source=[], votes=votes,
                    mean_support_strength=0.0, vetoed=True,
                    veto_lanes=[v.lane for v in veto_oppose])

    by_src: dict[str, list[Vote]] = {}
    for v in votes:
        by_src.setdefault(v.source, []).append(v)

    tally = {SUPPORT: 0, OPPOSE: 0, UNKNOWN: 0}
    per_source = []
    for src, vs in by_src.items():
        cnt = {SUPPORT: 0, OPPOSE: 0, UNKNOWN: 0}
        for v in vs:
            cnt[v.verdict] += 1
        # 第 5 轮：同源内怎么合成一票
        #   反对 >= 支持  → OPPOSE（有反证就要留痕，不许被支持票淹掉）
        #   支持 > 反对   → SUPPORT
        #   其余          → UNKNOWN
        if cnt[OPPOSE] > 0 and cnt[OPPOSE] >= cnt[SUPPORT]:
            eff = OPPOSE
        elif cnt[SUPPORT] > cnt[OPPOSE]:
            eff = SUPPORT
        else:
            eff = UNKNOWN
        tally[eff] += 1
        ss = [v.strength for v in vs if v.verdict == SUPPORT]
        per_source.append(dict(source=src, verdict=eff, n_lanes=len(vs),
                               detail=cnt,
                               support_strength=(sum(ss) / len(ss)) if ss else 0.0))

    n = sum(tally.values())
    s, o, u = tally[SUPPORT], tally[OPPOSE], tally[UNKNOWN]
    # 第 4 轮：强度参与决策
    sup_strength = (sum(ps["support_strength"] for ps in per_source
                        if ps["verdict"] == SUPPORT) / s) if s else 0.0

    if n == 0:
        grade, why = "无", "一条通道都没跑成"
    elif o > 0:
        grade, why = "中", f"{o} 个来源反对"
    elif u / n > 0.5:
        grade, why = "弱", f"{u}/{n} 个来源不知道"
    elif s == n:
        # 第 6 轮：全票支持还要看强度，弱支持凑不出强结论
        if sup_strength >= 0.5:
            grade, why = "强", f"{s}/{n} 全支持，平均强度 {sup_strength:.2f}"
        elif sup_strength >= 0.3:
            grade, why = "中", f"{s}/{n} 全支持，但强度只有 {sup_strength:.2f}"
        else:
            grade, why = "弱", f"{s}/{n} 全支持，强度太低 {sup_strength:.2f}"
    else:
        grade, why = "中", f"{s}/{n} 支持，{u} 未知"

    return dict(grade=grade, why=why, tally=tally, n_sources=n,
                per_source=per_source, mean_support_strength=sup_strength,
                votes=votes, vetoed=False, veto_lanes=[])


def fmt_aggregate(agg: dict) -> str:
    lines = []
    for ps in agg["per_source"]:
        d = ps["detail"]
        lines.append(f"    {ps['source']:<8}{ps['n_lanes']} 条通道 → "
                     f"{ps['verdict']:<8}"
                     f"(支持{d[SUPPORT]} 反对{d[OPPOSE]} 未知{d[UNKNOWN]})")
    lines.append(f"    汇总：{agg['grade']}  —— {agg['why']}")
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════
#  自检
# ══════════════════════════════════════════════════════════════════════
def selftest() -> int:
    sys.stdout.reconfigure(encoding="utf-8") if hasattr(sys.stdout, "reconfigure") else None
    n_ok = n_bad = 0

    def ck(name, cond, detail=""):
        nonlocal n_ok, n_bad
        if cond:
            n_ok += 1
            print(f"  [PASS] {name}" + (f"  — {detail}" if detail else ""))
        else:
            n_bad += 1
            print(f"  [FAIL] {name}" + (f"  — {detail}" if detail else ""))

    print("=" * 80)
    print("lanes.py 自检")
    print("=" * 80)

    rng = np.random.default_rng(0)
    X = rng.uniform(0, 1, (120, 3))
    y = 2.0 * X[:, 0] - 1.0 * X[:, 1] + 0.5 * X[:, 2] + rng.normal(0, 0.05, 120)
    good = Claim("C1", "这个关系可以用线性模型描述", X=X, y=y)

    print("\n一、通道定义")
    ck("八条通道都登记了", len(LANES) == 8, f"{sorted(LANES)}")
    ck("source 声明齐全", all(v["source"] for v in LANES.values()))
    ck("有两个独立 source",
       len({v["source"] for v in LANES.values()}) == 2,
       str({v["source"] for v in LANES.values()}))

    # 带方向的主张：x0 正向、x1 负向
    good_dir = Claim("C1d", "x0 正相关、x1 负相关", X=X, y=y,
                     sign={0: +1, 1: -1})

    print("\n二、方向通道（第 3 轮补的那条）")
    v_dir = lane_direction(good_dir)
    ck("方向对时给支持", v_dir.verdict == SUPPORT, v_dir.why)
    bad_dir = Claim("C1r", "x0 负相关（实际是正的）", X=X, y=y, sign={0: -1})
    v_bad = lane_direction(bad_dir)
    ck("方向反时给反对", v_bad.verdict == OPPOSE, v_bad.why)
    no_dir = Claim("C1n", "没说方向", X=X, y=y)
    ck("没声明方向时给 UNKNOWN",
       lane_direction(no_dir).verdict == UNKNOWN,
       lane_direction(no_dir).why)

    print("\n三、好数据上各通道该说什么")
    votes = run_lanes(good_dir)
    by = {v.lane: v for v in votes}
    ck("cv 支持", by["cv"].verdict == SUPPORT, by["cv"].why)
    ck("boot 支持", by["boot"].verdict == SUPPORT, by["boot"].why)
    ck("holdout 支持", by["holdout"].verdict == SUPPORT, by["holdout"].why)
    ck("resid 支持", by["resid"].verdict == SUPPORT, by["resid"].why)
    ck("rival 支持", by["rival"].verdict == SUPPORT, by["rival"].why)

    agg = aggregate(votes)
    ck("好数据汇总为强", agg["grade"] == "强", agg["why"])
    ck("三个来源（data 计一次 + model 一次）",
       agg["n_sources"] == 2, f"n_sources={agg['n_sources']}")

    print("\n三、去重规则")
    only_data = [v for v in votes if v.source == "data"]
    agg_d = aggregate(only_data)
    ck("同 source 六条通道只算一票",
       agg_d["n_sources"] == 1, f"6 条通道 → {agg_d['n_sources']} 票")
    ck("去重后不虚高",
       agg_d["grade"] in ("强", "中"), agg_d["why"])

    print("\n四、坏数据该被拦")
    y_bad = rng.normal(0, 1, 120)           # 纯噪声，和 X 无关
    bad = Claim("C2", "这个关系可以用线性模型描述", X=X, y=y_bad)
    vb = run_lanes(bad)
    byb = {v.lane: v for v in vb}
    ck("rival 在纯噪声上反对", byb["rival"].verdict == OPPOSE, byb["rival"].why)
    aggb = aggregate(vb)
    ck("有反对票时不给强", aggb["grade"] != "强", aggb["why"])
    ck("指出反对来源", any(ps["verdict"] == OPPOSE
                           for ps in aggb["per_source"]))

    print("\n五、缺数据要说不知道，不说话")
    empty = Claim("C3", "没数据也要能判", X=None, y=None)
    ve = run_lanes(empty)
    ck("全部通道返回 UNKNOWN",
       all(v.verdict == UNKNOWN for v in ve),
       f"{len(ve)} 条")
    agge = aggregate(ve)
    ck("无数据记为弱，不记为强", agge["grade"] in ("弱", "无"), agge["why"])

    print("\n六、通道崩溃不拖死全案")
    def boom(_c):
        raise RuntimeError("故意炸")
    LANES["_boom"] = dict(fn=boom, name="_boom", source="xx")
    try:
        v_boom = run_lanes(good, lanes=["cv", "_boom", "rival"])
        ck("炸掉的通道记 UNKNOWN",
           {v.lane: v for v in v_boom}["_boom"].verdict == UNKNOWN)
        ck("其他通道照常出票",
           sum(1 for v in v_boom if v.verdict != UNKNOWN) >= 2)
    finally:
        LANES.pop("_boom", None)

    print("\n七、样本太少要拒绝判")
    tiny = Claim("C4", "太小", X=X[:4], y=y[:4])
    vt = run_lanes(tiny)
    ck("cv 在 4 行上返回 UNKNOWN",
       {v.lane: v for v in vt}["cv"].verdict == UNKNOWN,
       {v.lane: v for v in vt}["cv"].why)

    print("\n八、强度必须参与决策（第 4、6 轮）")
    weak = [Vote(SUPPORT, 0.1, lane="a", source="s1"),
            Vote(SUPPORT, 0.1, lane="b", source="s2")]
    aggw = aggregate(weak)
    ck("两条弱支持不给强", aggw["grade"] != "强", aggw["why"])
    strong = [Vote(SUPPORT, 0.9, lane="a", source="s1"),
              Vote(SUPPORT, 0.9, lane="b", source="s2")]
    aggs = aggregate(strong)
    ck("两条强支持给强", aggs["grade"] == "强", aggs["why"])
    mid = [Vote(SUPPORT, 0.35, lane="a", source="s1"),
           Vote(SUPPORT, 0.35, lane="b", source="s2")]
    ck("中等强度给中", aggregate(mid)["grade"] == "中", aggregate(mid)["why"])

    print("\n九、同源平票不再一律 UNKNOWN（第 5 轮）")
    split = [Vote(SUPPORT, 0.8, lane="a", source="s1"),
             Vote(OPPOSE, 0.8, lane="b", source="s1")]
    aggsplit = aggregate(split)
    ck("同源 1 支持 1 反对 → 反对优先",
       aggsplit["per_source"][0]["verdict"] == OPPOSE,
       str(aggsplit["per_source"][0]))
    ck("这种情况下不给强", aggsplit["grade"] != "强", aggsplit["why"])

    two_sup = [Vote(SUPPORT, 0.8, lane="a", source="s1"),
               Vote(SUPPORT, 0.8, lane="b", source="s1"),
               Vote(OPPOSE, 0.8, lane="c", source="s1")]
    ck("同源 2 支持 1 反对 → 支持占多数",
       aggregate(two_sup)["per_source"][0]["verdict"] == SUPPORT,
       str(aggregate(two_sup)["per_source"][0]))

    print("\n十、真并行（第 7 轮）与超时（第 8 轮）")
    import time

    def slow_factory(tag):
        def f(_c):
            time.sleep(0.15)
            return Vote(SUPPORT, 0.9, why=f"{tag} 睡完", lane=tag)
        return f
    for i in range(4):
        LANES[f"_s{i}"] = dict(fn=slow_factory(f"_s{i}"), name=f"_s{i}",
                               source=f"_sl{i}")
    try:
        slow_names = [f"_s{i}" for i in range(4)]
        t0 = time.time()
        run_lanes(good, lanes=slow_names, parallel=False)
        t_seq = time.time() - t0
        t0 = time.time()
        run_lanes(good, lanes=slow_names, parallel=True)
        t_par = time.time() - t0
        ck("并行确实比串行快", t_par < t_seq * 0.6,
           f"串行 {t_seq*1000:.0f}ms → 并行 {t_par*1000:.0f}ms")
    finally:
        for i in range(4):
            LANES.pop(f"_s{i}", None)

    def hang(_c):
        time.sleep(3.0)
        return Vote(SUPPORT, 1.0, lane="_hang")
    LANES["_hang"] = dict(fn=hang, name="_hang", source="hang")
    try:
        t0 = time.time()
        vh = run_lanes(good, lanes=["cv", "_hang", "rival"], timeout=0.3)
        el = time.time() - t0
        ck("超时通道被记 UNKNOWN",
           {v.lane: v for v in vh}["_hang"].verdict == UNKNOWN,
           {v.lane: v for v in vh}["_hang"].why)
        ck("超时没有拖死全案", el < 2.0, f"总耗时 {el:.2f}s（挂起通道要 3s）")
        ck("其他通道仍出票",
           {v.lane: v for v in vh}["cv"].verdict != UNKNOWN)
    finally:
        LANES.pop("_hang", None)

    print("\n十一、顺序稳定（并行不改顺序）")
    o1 = [v.lane for v in run_lanes(good, parallel=True)]
    o2 = [v.lane for v in run_lanes(good, parallel=False)]
    ck("并行与串行给出同一顺序", o1 == o2, f"{o1[:3]}...")
    ck("顺序就是登记顺序", o1 == list(LANES), "不是完成顺序")

    print("\n十二、extrap 对离散设计的判定（第 9 轮）")
    # 网格设计：3×4×2 = 24 组合，随机抽 12 组（固定种子，结果可复现）
    allc = [[a, b, c_] for a in (0, 1, 2) for b in (0, 1, 2, 3)
            for c_ in (0, 1)]
    pick = np.random.default_rng(42).choice(len(allc), 12, replace=False)
    gx = np.array([allc[i] for i in pick], float)
    uniq = [len(np.unique(gx[:, j])) for j in range(3)]
    ck("测试数据每列都覆盖多个取值",
       len(uniq) == 3 and all(u >= 2 for u in uniq),
       f"每列取值数 {uniq}，{len(gx)} 组")
    gy = gx[:, 0] * 2.0 + np.linspace(0, 0.1, len(gx))
    vg = lane_extrap(Claim("G1", "网格", X=gx, y=gy))
    ck("离散组合覆盖 50% → 反对", vg.verdict == OPPOSE, vg.why)
    # 全组合都采到
    fx = np.array([[a, b] for a in (0, 1, 2) for b in (0, 1)], float)
    fy = fx[:, 0] + fx[:, 1] * 0.5 + np.arange(len(fx)) * 1e-3
    vf = lane_extrap(Claim("G2", "全组合", X=fx, y=fy))
    ck("离散组合全覆盖 → 支持", vf.verdict == SUPPORT, vf.why)
    # 连续变量
    vc = lane_extrap(good)
    ck("连续变量 → 支持", vc.verdict == SUPPORT, vc.why)

    print("\n十三、缓存（第 10 轮）")
    cache_clear()
    c_t = Claim("K1", "缓存测试", X=X, y=y, sign={0: +1})
    r1 = run_cached(c_t, use_cache=True)
    r2 = run_cached(c_t, use_cache=True)
    ck("第二次走缓存", cache_stats()["hit"] == 1,
       str(cache_stats()))
    ck("缓存结果与原结果一致",
       [v.verdict for v in r1] == [v.verdict for v in r2])
    ck("缓存不改变票数", len(r1) == len(r2) == len(LANES))
    # 数据变了必须重算
    c_t2 = Claim("K1", "缓存测试", X=X * 1.5, y=y, sign={0: +1})
    run_cached(c_t2, use_cache=True)
    ck("数据变了不命中缓存", cache_stats()["hit"] == 1,
       str(cache_stats()))
    # 缓存对象不能是同一个引用（否则改一个影响另一个）
    r1[0].verdict = "tampered"
    r3 = run_cached(c_t, use_cache=True)
    ck("缓存与返回是副本，不是同一对象",
       r3[0].verdict != "tampered", f"缓存里={r3[0].verdict}")
    cache_clear()

    print("\n十四、接闸门（第 12 轮）")
    agg_ok = aggregate(run_lanes(good_dir))
    v_ok = to_verdict(good_dir, agg_ok)
    # 关键知识：全通道支持也不够 pass —— e3 卡在 1
    ck("全通道支持 + 未重跑 → 只能 degrade",
       v_ok["final"] == "degrade", f"{v_ok['final']} C={v_ok['C']}")
    ck("未重跑时 C 停在 4",
       v_ok["C"] == 4, f"C={v_ok['C']}（e1=2 e2=1 e3=1）")
    v_rep = to_verdict(good_dir, agg_ok, reproduced=True)
    ck("声明重跑后 → pass",
       v_rep["final"] == "pass", f"{v_rep['final']} C={v_rep['C']}")
    ck("重跑把 C 抬到 5", v_rep["C"] == 5, f"C={v_rep['C']}")
    ck("是否重跑被记进结果",
       v_ok["reproduced"] is False and v_rep["reproduced"] is True)

    bad2 = Claim("C9", "纯噪声也能解释", X=X, y=y_bad, sign={0: +1})
    agg_bad = aggregate(run_lanes(bad2))
    v_bad2 = to_verdict(bad2, agg_bad)
    ck("有反对来源 → reject", v_bad2["final"] == "reject",
       f"{v_bad2['final']} refuted={v_bad2['refuted']}")
    ck("reject 时给出 blocked_at", v_bad2["blocked_at"] is not None,
       str(v_bad2["blocked_at"]))
    ck("被推翻时重跑也救不回来",
       to_verdict(bad2, agg_bad, reproduced=True)["final"] == "reject",
       "refuted 是一票否决，e3 抬不动它")

    print("\n十五、veto 通道：方向错不许被多数票淹没（第 15 轮）")
    mixed = [Vote(SUPPORT, 0.9, "模型拟合好", lane="cv", source="data"),
             Vote(SUPPORT, 0.9, "模型拟合好", lane="boot", source="data"),
             Vote(SUPPORT, 0.9, "模型拟合好", lane="holdout", source="data"),
             Vote(SUPPORT, 0.9, "模型拟合好", lane="resid", source="data"),
             Vote(OPPOSE, 0.7, "方向反了", lane="direction", source="data",
                  veto=True)]
    aggm = aggregate(mixed)
    ck("veto 反对票一票否决", aggm["vetoed"] is True, aggm["why"][:50])
    ck("否决时不给强/中", aggm["grade"] == "弱", aggm["grade"])
    ck("记录是哪条通道否决的",
       aggm["veto_lanes"] == ["direction"], str(aggm["veto_lanes"]))
    ck("否决时闸门给 reject",
       to_verdict(good_dir, aggm)["final"] == "reject",
       to_verdict(good_dir, aggm)["final"])

    soft = [Vote(SUPPORT, 0.9, "好", lane="cv", source="s1"),
            Vote(SUPPORT, 0.9, "好", lane="boot", source="s1"),
            Vote(OPPOSE, 0.7, "但这里不稳", lane="holdout", source="s1")]
    aggs = aggregate(soft)
    ck("普通反对票不一票否决", aggs["vetoed"] is False, aggs["why"])

    print("\n十六、真数据上 veto 是否生效")
    Xa, ya, _ = load_apmcm()
    if Xa is not None:
        b1 = Claim("B1", "歧管深高比增大，热阻下降", X=Xa, y=ya, sign={1: -1})
        agg_b1 = aggregate(run_lanes(b1))
        ck("真题 B1 被 direction 否决", agg_b1["vetoed"] is True,
           agg_b1["why"][:60])
        v_b1 = to_verdict(b1, agg_b1)
        ck("真题 B1 判 reject 而不是 degrade",
           v_b1["final"] == "reject", f"{v_b1['final']} C={v_b1['C']}")
        b2 = Claim("B2", "针肋宽度比增大，热阻下降", X=Xa, y=ya, sign={0: -1})
        v_b2 = to_verdict(b2, aggregate(run_lanes(b2)))
        ck("真题 B2（方向对）不被否决", v_b2["refuted"] is False,
           v_b2["final"])
    else:
        ck("真数据可用（没找到附件则跳过）", True, "跳过")

    print("\n十七、跨主张一致性（第 17 轮）")
    # 两条互斥主张都被支持 → 必须报冲突
    c_a = Claim("X1", "x0 增 y 增", X=X, y=y, sign={0: +1})
    c_b = Claim("X2", "x0 增 y 减", X=X, y=y, sign={0: -1})
    fake_ok = dict(final="degrade", refuted=False, C=4)
    conf = cross_check([("X1", c_a, fake_ok), ("X2", c_b, fake_ok)])
    ck("互斥主张都被支持 → 报冲突", len(conf) == 1, str(conf)[:80])
    ck("冲突指出是哪两条",
       bool(conf) and conf[0]["a"] == "X1" and conf[0]["b"] == "X2",
       str(conf[0]) if conf else "")
    fake_bad = dict(final="reject", refuted=True, C=3)
    ck("一条被推翻时不报冲突",
       len(cross_check([("X1", c_a, fake_ok), ("X2", c_b, fake_bad)])) == 0)
    c_same = Claim("X3", "x0 增 y 增（重复）", X=X, y=y, sign={0: +1})
    ck("方向一致不报冲突",
       len(cross_check([("X1", c_a, fake_ok), ("X3", c_same, fake_ok)])) == 0)
    c_other = Claim("X4", "x1 增 y 减", X=X, y=y, sign={1: -1})
    ck("不同自变量不报冲突",
       len(cross_check([("X1", c_a, fake_ok), ("X4", c_other, fake_ok)])) == 0)

    print("\n十八、强度标定（第 18 轮）")
    vr = lane_rival(good)
    ck("rival 强度随解释力上升", vr.strength >= 0.5,
       f"{vr.verdict} strength={vr.strength:.2f}")
    ck("rival 强度不超过 1", vr.strength <= 1.0, f"{vr.strength:.2f}")

    print("\n十九、缓存往返不许丢票面信息（第 91 轮）")
    # 原来缓存往返用五个位置参数重建 Vote，veto 被静默丢弃：
    # 首次 grade=弱/vetoed=True，命中缓存变 grade=中/vetoed=False。
    _v = Vote(OPPOSE, 0.6, "方向相反", "direction", "d", True)
    _v2 = _copy_vote(_v)
    ck("_copy_vote 保留 veto", _v2.veto is True, str(_v2.veto))
    ck("_copy_vote 六个字段全等",
       (_v.verdict, _v.strength, _v.why, _v.lane, _v.source, _v.veto)
       == (_v2.verdict, _v2.strength, _v2.why, _v2.lane, _v2.source, _v2.veto))
    _set1 = [_v, Vote(SUPPORT, 0.9, "ok", "cv", "s1"),
             Vote(SUPPORT, 0.9, "ok", "rival", "s2")]
    _set2 = [_copy_vote(x) for x in _set1]
    _a1, _a2 = aggregate(_set1), aggregate(_set2)
    ck("缓存往返后汇总一致",
       _a1["grade"] == _a2["grade"] and _a1["vetoed"] == _a2["vetoed"],
       f"{_a1['grade']}/{_a1['vetoed']} vs {_a2['grade']}/{_a2['vetoed']}")

    print()
    print("=" * 80)
    print(f"{'ALL PASS' if n_bad == 0 else 'FAILED'}  {n_ok} 通过 / {n_bad} 失败")
    print("=" * 80)
    return 0 if n_bad == 0 else 1


def load_apmcm():
    """读 APMCM 2026 B 题附件。返回 (X, y, names)。

    第 80 轮：原来这里自己写了一份 `glob("**/附件 2*.xlsx", recursive=True)`，
    和 mm.py 里那份一样慢（同样要遍历 29.8 万个文件的知识库）。
    现在统一走 datapath —— 慢搜索只留一份实现。
    """
    import openpyxl
    import datapath
    path = datapath.find_xlsx(prefer="附件 2")
    if not path:
        return None, None, None
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb.active
    X, y = [], []
    for r in ws.iter_rows(min_row=3, values_only=True):
        if r[0] is None:
            continue
        try:
            X.append([float(r[1]), float(r[2]), float(r[3])])
            y.append(float(r[4]))
        except (TypeError, ValueError):
            continue
    return (np.array(X), np.array(y),
            ["针肋宽度比", "歧管深高比", "针肋排数"])


def demo() -> int:
    """用真题跑一遍多通道验证，证明通道在真数据上有判断力。"""
    X, y, names = load_apmcm()
    if X is None:
        print("没找到 APMCM 附件，跳过 demo")
        return 0
    print("=" * 84)
    print(f"多通道验证 · APMCM 2026 B 题（{len(y)} 组 × {X.shape[1]} 个自变量）")
    print("=" * 84)
    print(f"  自变量：{names}")
    print()

    # 题目的五条结构-性能关系，逐条验方向
    tests = [
        ("B1", "歧管深高比增大，热阻下降", {1: -1}),
        ("B2", "针肋宽度比增大，热阻下降", {0: -1}),
        ("B5", "针肋排数增多，热阻下降", {2: -1}),
        ("B1r", "歧管深高比增大，热阻上升（故意反着写）", {1: +1}),
    ]
    rows = []
    for cid, text, sign in tests:
        c = Claim(cid, text, X=X, y=y, sign=sign)
        votes = run_lanes(c)
        agg = aggregate(votes)
        v = to_verdict(c, agg)
        rows.append((cid, text, votes, agg, v))

        print(f"【{cid}】{text}")
        for vote in votes:
            mark = {SUPPORT: "✓", OPPOSE: "✗", UNKNOWN: "?"}[vote.verdict]
            print(f"    {mark} {vote.lane:<10}{vote.verdict:<8}"
                  f"{vote.strength:.2f}  {vote.why[:60]}")
        print(f"    ── 按来源汇总")
        print(fmt_aggregate(agg))
        print(f"    ── 闸门：{v['final']}  C={v['C']}"
              + ("  〔被推翻〕" if v["refuted"] else ""))
        print()

    # 关键对照：B1 和 B1r 是同一个模型下的两种主张
    print("=" * 84)
    print("对照：同一个模型，两条相反的主张")
    print("=" * 84)
    for cid, text, votes, agg, v in rows:
        if cid in ("B1", "B1r"):
            d = {x.lane: x for x in votes}.get("direction")
            print(f"  {cid:<5}{text[:40]:<42}"
                  f"方向通道={d.verdict:<8}{v['final']}")
    print()
    print("  说明：两条主张的 cv/boot/holdout/rival 完全一样（同一模型），")
    print("        只有 direction 通道能分开它们 —— 这就是为什么必须有那条通道。")

    # 跨主张一致性检查
    print()
    print("=" * 84)
    print("跨主张一致性（第 17 轮）")
    print("=" * 84)
    conflicts = cross_check([(cid, Claim(cid, text, X=X, y=y, sign=sign), v)
                             for cid, text, sign, v
                             in [(r[0], r[1], t[2], r[4])
                                 for r, t in zip(rows, tests)]])
    print(fmt_cross(conflicts))

    # 汇总
    n_veto = sum(1 for *_, v in rows if v["refuted"])
    print()
    print("=" * 84)
    print(f"  {len(rows)} 条主张：{n_veto} 条被否决，"
          f"{len(rows) - n_veto} 条未被否决")
    print("  全部判 degrade 或 reject —— 因为 e3 卡在 1（没跨环境重跑）")
    print("  这不是缺陷：单份数据的内部一致性撑不起「可复现」")
    print("=" * 84)
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "demo":
        raise SystemExit(demo())
    raise SystemExit(selftest())
