#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
kb.py —— 知识加载器：全量 + 拓扑 + 自证（第 161 轮建）

为什么不是检索
--------------
用户指出：AI 拿不全外部知识（GitHub 学不通），而且"万一跳着看"。
检索范式必然跳读 —— 相似度选出来的 3 条，可能正好漏掉否定的第 4 条。

所以这里的设计是：
  不变量 → 全量加载（条数少，全读成本低）
  决策   → 按依赖拓扑加载（前置不在就不许加载后置）
  反模式 → 提案前强制查

三道防跳读机制
--------------
1. 不变量只有 8 条 → 不需要检索
2. 决策有 depends_on → 拓扑序
3. 每条可带 comprehension_check → 答不出=没读
"""

from __future__ import annotations

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
KB_ROOT = os.path.join(HERE, "kb")


def _load(name: str, default):
    p = os.path.join(KB_ROOT, name)
    if not os.path.exists(p):
        return default
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def load_invariants() -> list[dict]:
    """全量加载不变量。这不是检索，是必读清单。"""
    return _load("invariants.json", {}).get("invariants", [])


def load_all_invariants_doc() -> dict:
    """完整的不变量文档（含赛事事实、评审轴、题型）。"""
    return _load("invariants.json", {})


def topological_order(items: list[dict]) -> list[dict]:
    """按 depends_on 做拓扑排序。前置缺失就抛错，不许跳读。"""
    by_id = {i["id"]: i for i in items}
    done, out, visiting = set(), [], set()

    def visit(iid, chain):
        if iid in done:
            return
        if iid in visiting:
            raise ValueError(f"依赖成环：{' -> '.join(chain + [iid])}")
        if iid not in by_id:
            raise KeyError(
                f"缺少前置 {iid}（被 {' -> '.join(chain)} 依赖）。"
                f"不允许加载缺前置的后置条目 —— 这就是防跳读。")
        visiting.add(iid)
        for dep in by_id[iid].get("depends_on") or []:
            visit(dep, chain + [iid])
        visiting.discard(iid)
        done.add(iid)
        out.append(by_id[iid])

    for it in items:
        visit(it["id"], [])
    return out


def render_context(invariants=None, decisions=None) -> str:
    """把知识渲染成可以直接塞进 system prompt 的文本。"""
    doc = load_all_invariants_doc()
    inv = invariants if invariants is not None else doc.get("invariants", [])
    L = ["# 硬约束（必读，不可跳过）", ""]

    cf = doc.get("contest_facts") or {}
    if cf:
        L.append("## 赛事事实")
        for k, v in cf.items():
            if k.startswith("_"):
                continue
            L.append(f"- **{k}**：{v}")
        L.append("")

    axes = doc.get("judging_axes") or {}
    if axes:
        L.append("## 评审四轴（约分）")
        for k, v in axes.items():
            if k.startswith("_"):
                continue
            L.append(f"- **{k}** ~{v['weight']} 分 —— 看：{v['looks_for']}")
        L.append("")

    if inv:
        L.append("## 不变量")
        for it in inv:
            L.append(f"- **{it['id']}** {it['claim']}")
            if it.get("consequence"):
                L.append(f"  - 后果：{it['consequence']}")
            if it.get("check"):
                L.append(f"  - 检查：{it['check']}")
        L.append("")

    qs = doc.get("self_check_questions") or {}
    if qs:
        L.append("## 下结论前必须回答")
        for scene, questions in qs.items():
            if scene.startswith("_"):
                continue
            L.append(f"- **{scene}**")
            for q in questions:
                L.append(f"  - {q}")
        L.append("")

    if decisions:
        L.append("## 历史决策（按依赖序）")
        for d in topological_order(decisions):
            L.append(f"- **{d['id']}** {d.get('decision', '')}")
            if d.get("premise"):
                L.append(f"  - 前提：{d['premise']}")
        L.append("")

    return "\n".join(L)


def check_violation(tex: str) -> list[str]:
    """扫论文，看不变量有没有被违反。返回违规列表。"""
    v = []
    doc = load_all_invariants_doc()

    # I008：页数、目录
    if "\\tableofcontents" in tex:
        v.append("I008: 正文不要目录")

    # I002：创新必须能归类
    if "innovation" in tex.lower() or "novel" in tex.lower():
        if not any(k in tex.lower() for k in
                   ("algorithm improvement", "cross-domain",
                    "multi-model", "模型融合", "算法改进", "跨域")):
            v.append("I002: 声称创新但归不到三类之一"
                     "（算法改进/跨域迁移/多模型融合）")

    # I003：必须有对照模型
    has_baseline = any(k in tex for k in ("baseline model", "Baseline",
                                          "基准模型"))
    has_contrast = any(k in tex for k in ("comparison model", "contrast",
                                          "对照模型", "alternative structure"))
    if not (has_baseline and has_contrast):
        v.append("I003: 缺基准模型或对照模型（三模型缺一）")

    # I004：三大检验
    checks = {
        "误差分析": ("error analysis", "residual", "RMSE", "误差"),
        "灵敏度分析": ("sensitivity", "敏感性"),
        "稳健性检验": ("robustness", "稳健"),
    }
    for name, kws in checks.items():
        if not any(k in tex.lower() or k in tex for k in kws):
            v.append(f"I004: 缺{name}")

    # I006：AI 声明
    if not any(k in tex for k in ("AI 工具", "AI tool", "AI使用", "AI 使用")):
        v.append("I006: 缺 AI 工具使用声明")

    return v


def selftest() -> int:
    bad = 0
    n = 0

    def ck(name, cond, detail=""):
        nonlocal bad, n
        n += 1
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}"
              + (f"  — {detail}" if detail else ""))
        if not cond:
            bad += 1

    inv = load_invariants()
    ck("不变量可加载", len(inv) >= 8, f"{len(inv)} 条")
    ck("不变量条数足够少（全读成本低）", len(inv) <= 20, f"{len(inv)} 条")

    ctx = render_context()
    ck("上下文可渲染", len(ctx) > 500, f"{len(ctx)} 字符")
    ck("含评审四轴", "评审四轴" in ctx)
    ck("含自检问题", "下结论前必须回答" in ctx)

    # 拓扑排序
    items = [
        {"id": "A", "depends_on": []},
        {"id": "B", "depends_on": ["A"]},
        {"id": "C", "depends_on": ["B"]},
    ]
    order = [x["id"] for x in topological_order(items)]
    ck("拓扑序正确", order == ["A", "B", "C"], str(order))

    # 缺前置必须抛错（防跳读的核心）
    try:
        topological_order([{"id": "B", "depends_on": ["A"]}])
        ck("缺前置时应抛错", False, "没抛")
    except KeyError as e:
        ck("缺前置时抛错（防跳读）", True, str(e)[:40])

    # 成环必须抛错
    try:
        topological_order([
            {"id": "A", "depends_on": ["B"]},
            {"id": "B", "depends_on": ["A"]},
        ])
        ck("成环时应抛错", False, "没抛")
    except ValueError as e:
        ck("成环时抛错", True, str(e)[:30])

    # 违规检测
    bad_tex = "\\tableofcontents We claim novelty here. RMSE 0.01."
    v = check_violation(bad_tex)
    ck("检出「有目录」", any("I008" in x for x in v), str(v[:2]))
    ck("检出「创新归不了类」", any("I002" in x for x in v), str(v[:2]))
    ck("检出「缺对照模型」", any("I003" in x for x in v), str(v[:2]))
    ck("检出「缺灵敏度」", any("I004" in x and "灵敏度" in x for x in v))

    good_tex = (
        "AI 工具使用声明：使用了。baseline model and comparison model. "
        "error analysis RMSE. sensitivity analysis. robustness check. "
        "algorithm improvement.")
    vg = check_violation(good_tex)
    ck("合规论文无误报", not vg, str(vg))

    print(f"\n{'ALL PASS' if bad == 0 else 'FAILED'}  {n - bad}/{n}")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    raise SystemExit(selftest())
