#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
contract.py —— LLM 提案的契约与校验（第 150 轮建）

问题
----
LLM 会提「用物理机理建模」这种话，但插件听不懂。
听不懂的提案等于没提，而 LLM 会以为提过了 —— 这是最危险的失败模式：
**它以为在推进，实际什么都没发生。**

解法
----
提案必须是**结构化 JSON**，且能映射成插件真实存在的命令。
映射不了就退回，把错误原文给它 —— 它下一轮才知道该改什么。

五条规则
--------
1. method 必须是插件真实子命令
2. method_args 的每个键必须是该子命令的真实参数
3. success_criteria 的每个指标名必须是插件能算的
4. falsifiable_assumption 必须非空（写不出来的假设是装饰）
5. 至少 3 条路线，且不能全部同构（三个变体不等于三条路线）
"""

from __future__ import annotations

import json

# 插件能算的指标（从 mm.py / mmkit.py 的实际输出里抄的）
METRICS = {
    "cv_rmse_max": "交叉验证 RMSE 上限（越小越好）",
    "cv_rmse_min": "交叉验证 RMSE 下限",
    "r2_min": "R² 下限",
    "r2_max": "R² 上限",
    "front_size_min": "帕累托前沿点数下限",
    "bp_max": "Breusch-Pagan 统计量上限",
    "coverage_min": "时间覆盖率下限",
    "n_rows_min": "可用行数下限",
}

REQUIRED = ("route_id", "title", "method", "method_args",
            "success_criteria", "falsifiable_assumption")


def validate(proposal: dict, cmds: set, arg_names: dict,
             metrics: set | None = None) -> list[str]:
    """校验一条提案。返回错误列表，空表示通过。

    arg_names: {子命令: {参数名集合}}，由 mmkit 的 argparse 反射得到。
    """
    metrics = metrics or set(METRICS)
    errs = []

    for k in REQUIRED:
        if k not in proposal:
            errs.append(f"缺字段 {k!r}")
        elif k == "method_args":
            # 空 dict 合法：selftest / advise / hints 确实不需要参数。
            # 但类型必须是 dict —— 给个字符串说明它没想清楚。
            if not isinstance(proposal.get(k), dict):
                errs.append("method_args 必须是 dict（可以为空 {}）")
        elif not proposal.get(k):
            errs.append(f"字段 {k!r} 为空")
    if errs:
        return errs

    m = str(proposal["method"])
    if m not in cmds:
        errs.append(f"method {m!r} 不是插件子命令。可用：{sorted(cmds)}")
        return errs

    # 参数名检查
    allowed = arg_names.get(m, set())
    for k in (proposal.get("method_args") or {}):
        kk = str(k).lstrip("-")
        if allowed and kk not in allowed:
            errs.append(
                f"{m} 没有参数 {k!r}。可用：{sorted(allowed)}")

    # 指标名检查
    for k in (proposal.get("success_criteria") or {}):
        if k not in metrics:
            errs.append(
                f"指标 {k!r} 插件算不了。可用：{sorted(metrics)}")

    # 可证伪性
    fa = str(proposal.get("falsifiable_assumption") or "").strip()
    if len(fa) < 8:
        errs.append(
            "falsifiable_assumption 太短 —— 必须写清"
            "「如果这条假设错，数据会呈现什么」")

    return errs


def _sig(p: dict) -> str:
    """路线的结构签名：同一签名 = 同构。

    只比 **method + 参数键集合**，不比参数值。
    因为「--x 宽度 / --x 深度 / --x 排数」是同一个单因子回归换了三次特征，
    不是三条路线。之前比了值，所以没挡住这种冒充。
    """
    args = p.get("method_args") or {}
    keys = tuple(sorted(str(k).lstrip("-") for k in args))
    return f"{p.get('method')}|{','.join(keys)}"


def check_diversity(proposals: list[dict], min_round: int = 3,
                    min_distinct: int = 2) -> list[str]:
    """路线不能全是同一个东西的变体。

    反例（实测容易发生的）：
        A: --y 热阻 --x 宽度
        B: --y 热阻 --x 深度
        C: --y 热阻 --x 排数
    这三条其实是「一次单因子回归」，不是三条路线。
    判据：结构签名去重后 < min_round 就退回。
    """
    if len(proposals) < min_round:
        return [f"只提了 {len(proposals)} 条，至少 {min_round} 条"]
    sigs = {_sig(p) for p in proposals}
    if len(sigs) < min_distinct:
        return [
            f"{len(proposals)} 条提案只有 {len(sigs)} 种结构 —— "
            f"其余是同构变体（比如只换了 --x 的顺序）。"
            f"请给出真正不同的建模路线（不同方法族、不同目标、不同约束）。"]
    return []


def validate_batch(proposals: list[dict], cmds: set,
                   arg_names: dict) -> dict:
    """批量校验。返回 {ok, per_route_errors, batch_errors}。"""
    per = {}
    for p in proposals:
        e = validate(p, cmds, arg_names)
        if e:
            per[str(p.get("route_id") or "?")] = e
    return dict(ok=not per and not check_diversity(proposals),
                per_route_errors=per,
                batch_errors=check_diversity(proposals))


def reflect_cmds() -> tuple[set, dict]:
    """读 schema.json 拿到「有哪些子命令、各接受什么参数」。

    为什么不再反射 argparse：mmkit 是「单一 parser + if a.cmd == 分派」，
    没有 subparsers，反射不到每个子命令接受哪些参数（实测 run 拿到 0 个）。
    schema.py 用静态分析解决，这里只消费它的结果。

    返回 (cmds, {cmd: {参数名集合（不带 --）}})。
    """
    import json
    import os
    here = os.path.dirname(os.path.abspath(__file__))
    p = os.path.join(here, "schema.json")
    if not os.path.exists(p):
        # 退化：至少给出子命令名，让 validate 能说「不认识这个 method」
        import re
        src = open(os.path.join(here, "mmkit.py"), encoding="utf-8").read()
        return set(re.findall(r'a\.cmd == "(\w+)"', src)) | {"run"}, {}
    sc = json.load(open(p, encoding="utf-8"))
    cmds, args = set(), {}
    for name, spec in (sc.get("commands") or {}).items():
        cmds.add(name)
        args[name] = {str(k).lstrip("-") for k in (spec.get("args") or {})}
    # 全局参数所有子命令都能用
    glob = {str(k).lstrip("-") for k in (sc.get("global_args") or {})}
    for name in args:
        args[name] |= glob
    return cmds, args


def selftest() -> int:
    """自测：契约必须能挡住四类常见瞎想。"""
    bad = 0
    n = 0

    def ck(name, cond, detail=""):
        nonlocal bad, n
        n += 1
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}"
              + (f"  — {detail}" if detail else ""))
        if not cond:
            bad += 1

    cmds, argn = reflect_cmds()
    ck("反射出子命令", "run" in cmds and "plot" in cmds,
       f"{len(cmds)} 个")

    good = dict(route_id="A", title="linear", method="run",
                method_args={"--y": "热阻", "--x": "宽度"},
                success_criteria={"cv_rmse_max": 0.01},
                falsifiable_assumption="若宽度无影响，偏相关应≈0")
    ck("合法提案通过", not validate(good, cmds, argn))

    p1 = dict(good, method="不存在的命令")
    ck("挡住不存在的 method", len(validate(p1, cmds, argn)) > 0,
       validate(p1, cmds, argn)[0][:40] if validate(p1, cmds, argn) else "")

    p2 = dict(good, success_criteria={"玄学指标": 1})
    ck("挡住拼不出的指标", len(validate(p2, cmds, argn)) > 0)

    p3 = dict(good, falsifiable_assumption="")
    ck("挡住空的可证伪陈述", len(validate(p3, cmds, argn)) > 0)

    # 三个变体
    variants = [dict(good, route_id=x, method_args={"--y": "热阻", "--x": x})
                for x in ("宽度", "深度", "排数")]
    e = check_diversity(variants)
    ck("挡住「三个变体冒充三条路线」", len(e) > 0, e[0][:50] if e else "")

    real = [good,
            dict(good, route_id="B", method="forecast",
                 method_args={"--y": "热阻"}),
            dict(good, route_id="C", method="plot",
                 method_args={"--kind": "pareto"})]
    ck("三条真正不同的路线通过", not check_diversity(real))

    print(f"\n{'ALL PASS' if bad == 0 else 'FAILED'}  {n - bad}/{n}")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    raise SystemExit(selftest())
