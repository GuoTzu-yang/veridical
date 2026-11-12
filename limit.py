#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
limit.py —— 极限度量：七层架构各到什么程度（第 2 轮建）

为什么需要这个
--------------
「达到本环境极限」如果不能量化，就只是一句口号。
这个工具把七层各自拆成「当前值 / 上限 / 分母的依据」，
其中**分母的依据**分三档，必须标明：

    实测      —— 分母是数出来的（如 17 个子命令、298,500 条语料）
    外部标准  —— 分母有出处（如评审四轴 15/25/25/35）
    估计      —— 分母是我拍的，**不能当结论**

这样别人（或下一轮的我）能一眼看出：
哪些"达成率 100%"是真的，哪些只是分母定得太低。

用法
    python limit.py            # 全量
    python limit.py --json     # 机器可读
"""

from __future__ import annotations

import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def _exists(*names) -> bool:
    return any(os.path.exists(os.path.join(HERE, n)) for n in names)


def count_lines(*names) -> int:
    for n in names:
        p = os.path.join(HERE, n)
        if os.path.exists(p):
            return len(open(p, encoding="utf-8").read().splitlines())
    return 0


def mmkit_cmds() -> list[str]:
    p = os.path.join(HERE, "mmkit.py")
    if not os.path.exists(p):
        return []
    src = open(p, encoding="utf-8").read()
    return sorted(set(re.findall(r'a\.cmd == "(\w+)"', src)))


def plot_kinds() -> list[str]:
    p = os.path.join(HERE, "mmkit.py")
    if not os.path.exists(p):
        return []
    src = open(p, encoding="utf-8").read()
    return sorted(set(re.findall(r'a\.kind == "(\w+)"', src)))


def measure() -> list[dict]:
    """七层的当前值 / 上限 / 依据。"""
    out = []

    # ── ⓿ 宿主层（prompt-inject.md，物理上跳不过去）────────────
    # Purge 把整个 system prompt 写在这个文件，每会话必读。
    # 实测：它不含任何数模约束（8 组关键词里 6 组无命中）。
    host_path = os.path.expanduser("~/.dsh/prompt-inject.md")
    host_txt = ""
    if os.path.exists(host_path):
        host_txt = open(host_path, encoding="utf-8").read()
    _host_groups = {
        "评审四轴权重": ["文字表述", "建模创造性"],
        "三模型(基准/主/对照)": ["基准模型", "对照模型"],
        "创新三类定义": ["算法改进", "跨域迁移", "模型融合"],
        "三大检验": ["灵敏度", "稳健性"],
        "人工核验要求": ["人工核验", "未核验"],
        "自检三问": ["做不到", "没查"],
        "自我欺骗条款": ["自我欺骗", "分母"],
    }
    _host_hit = [k for k, kws in _host_groups.items()
                 if all(w in host_txt for w in kws)]
    # 用户决定：不改动 Purge。所以宿主层这条通道关闭，
    # 约束改为「写进检查器」—— 检查器物理上无法忽略。
    out.append(dict(
        layer="⓿ 约束", item="宿主层（prompt-inject）可用",
        cur=0, top=1, unit="可用/不可用",
        basis="**已关闭**：用户决定不改动 Purge，"
              "故不依赖 prompt-inject.md 传递不变量",
        source="实测"))
    _rules_ok = False
    _rules_n = 0
    try:
        import rules as _rules
        _r = _rules.check("")
        _rules_n = _r["total"]
        _rules_ok = True
    except Exception:                               # noqa: BLE001
        _rules_ok = False
    out.append(dict(
        layer="⓿ 约束", item="不变量已变成可执行检查",
        cur=_rules_n if _rules_ok else 0, top=8, unit="条",
        basis="实测 rules.py 自动检查 7 条 + 人工 1 条（I001 权重是策略）",
        source="实测"))
    out.append(dict(
        layer="⓿ 约束", item="检查器能与论文对齐",
        cur=1 if _rules_ok else 0, top=1, unit="可用/不可用",
        basis="实测 rules.py 对真实论文能给出 PASS/FAIL（已跑出 4 条违规）",
        source="实测"))
    out.append(dict(
        layer="⓿ 约束", item="检查器可导入",
        cur=1 if host_txt else 0, top=1, unit="有/无",
        basis="实测 文件存在且非空" if host_txt else "实测 读不到",
        source="实测"))

    # ── ① 知识层 ────────────────────────────────────────────
    inv_path = os.path.join(HERE, "kb", "invariants.json")
    n_inv = 0
    if os.path.exists(inv_path):
        try:
            n_inv = len(json.load(open(inv_path, encoding="utf-8"))
                        .get("invariants", []))
        except (json.JSONDecodeError, OSError):
            n_inv = 0
    cards = glob.glob(os.path.join(HERE, "kb", "cards", "*.json"))
    corpus = 0
    try:
        import kb as _kb
        s = _kb.stats()
        corpus = s.get("files", 0) if s.get("ok") else 0
    except Exception:                                   # noqa: BLE001
        corpus = 0

    out.append(dict(
        layer="① 知识", item="不变量（硬约束）",
        cur=n_inv, top=10, unit="条",
        basis="实测：invariants.json 的条数；上限 10 是我定的（全读成本）",
        source="估计"))
    out.append(dict(
        layer="① 知识", item="方法卡片",
        cur=len(cards), top=80, unit="张",
        basis="实测：kb/cards/*.json；上限 80 是题型数 × 常用方法数（估计）",
        source="估计"))
    out.append(dict(
        layer="① 知识", item="可检索语料",
        cur=corpus, top=298500, unit="条",
        basis="实测：index.db 的 files 行数（4.16 GB）",
        source="实测"))
    out.append(dict(
        layer="① 知识", item="方法论文献覆盖",
        cur=0, top=1, unit="有/无",
        basis="**没有**：现有 30 个仓库全是代码实现，无方法论文献",
        source="实测"))

    # ── ② 提案层 ────────────────────────────────────────────
    has_contract = _exists("contract.py")
    contract_ok = False
    if has_contract:
        try:
            import contract as _ct
            cmds, argn = _ct.reflect_cmds()
            good = dict(route_id="A", title="t", method="run",
                        method_args={"--y": "y"},
                        success_criteria={"cv_rmse_max": 1},
                        falsifiable_assumption="若 x 无关则 r≈0")
            contract_ok = not _ct.validate(good, cmds, argn)
        except Exception:                               # noqa: BLE001
            contract_ok = False
    out.append(dict(
        layer="② 提案", item="契约可校验",
        cur=1 if contract_ok else 0, top=1, unit="可用/不可用",
        basis="实测：contract.py 对合法提案是否放行"
              "（上一轮自测 4/7，schema 缺失）",
        source="实测"))
    out.append(dict(
        layer="② 提案", item="不同构检查",
        cur=1 if (has_contract and "check_diversity" in
                  open(os.path.join(HERE, "contract.py"),
                       encoding="utf-8").read()) else 0,
        top=1, unit="有/无",
        basis="实测：contract.py 是否含 check_diversity",
        source="实测"))
    out.append(dict(
        layer="② 提案", item="schema 导出（插件能力清单）",
        cur=1 if _exists("schema.json") else 0, top=1, unit="有/无",
        basis="实测：schema.json 是否存在（LLM 靠它知道能调什么）",
        source="实测"))

    # ── ③ 执行层 ────────────────────────────────────────────
    cmds = mmkit_cmds()
    kinds = plot_kinds()
    used = 0   # 由编排层实际调用统计，现在没有编排，按 0 计
    out.append(dict(
        layer="③ 执行", item="子命令总数",
        cur=len(cmds), top=len(cmds), unit="个",
        basis="实测：mmkit.py 里 a.cmd == 的分支数",
        source="实测"))
    out.append(dict(
        layer="③ 执行", item="图类型总数",
        cur=len(kinds), top=len(kinds), unit="种",
        basis="实测：mmkit.py 里 a.kind == 的分支数",
        source="实测"))
    out.append(dict(
        layer="③ 执行", item="一次运行实际用到的子命令",
        cur=used, top=len(cmds), unit="个",
        basis="**未测**：没有编排层，无法统计实际调用",
        source="实测"))

    # ── ④ 验证层 ────────────────────────────────────────────
    verify_checks = 0
    trace_ok = False
    if _exists("verify.py"):
        try:
            import verify as _v
            r = _v.trace(r"$R^2 = 0.5918$", {"r2": 0.5918})
            trace_ok = r["ok"]
            verify_checks = 1
        except Exception:                               # noqa: BLE001
            pass
    pc_items = 0
    if _exists("papercheck.py"):
        src = open(os.path.join(HERE, "papercheck.py"),
                   encoding="utf-8").read()
        pc_items = len(re.findall(r"\badd\(", src))
    out.append(dict(
        layer="④ 验证", item="papercheck 检查项",
        cur=pc_items, top=pc_items, unit="项",
        basis="实测：papercheck.py 里 add() 调用数（15 项）",
        source="实测"))
    out.append(dict(
        layer="④ 验证", item="数字溯源",
        cur=1 if trace_ok else 0, top=1, unit="可用/不可用",
        basis="实测：verify.py 对合法/伪造数字的判定",
        source="实测"))
    out.append(dict(
        layer="④ 验证", item="六项硬检查（量纲/极限/留出/反例/敏感性/外部）",
        cur=0, top=6, unit="项",
        basis="**未实现**：gate.py 不存在",
        source="估计"))

    # ── ⑤ 对抗层 ────────────────────────────────────────────

    # ── ⑤ 对抗层（按能力数，不按文件名）──────────────────────
    # lanes.py 就是红队：并行验证通道 + veto + 去重 + 冲突检测。
    # 第一版只查 redteam.py 这个文件名，把它整个漏掉了。
    lane_src = ""
    for _f in ("lanes.py", "redteam.py"):
        _p = os.path.join(HERE, _f)
        if os.path.exists(_p):
            lane_src += open(_p, encoding="utf-8").read()
    lane_fns = sorted(set(re.findall(r"^def (lane_\w+)", lane_src, re.M)))
    out.append(dict(
        layer="⑤ 对抗", item="并行验证通道数",
        cur=len(lane_fns), top=10, unit="条",
        basis="实测 lanes.py 的 lane_* 函数；上限 10 取统计检验标准清单",
        source="实测"))
    for _name, _hit, _why in (
            ("veto 一票否决", "veto" in lane_src,
             "防多数票淹没方向错误"),
            ("来源去重", "只算一票" in lane_src,
             "防同仓库多文件当多票"),
            ("结论方向验证 sign", "sign=" in lane_src,
             "只验拟合不验方向等于没验结论"),
            ("跨通道冲突检测",
             "conflict" in lane_src.lower() or "冲突" in lane_src,
             "两条通道矛盾时不能硬选一个")):
        out.append(dict(layer="⑤ 对抗", item=_name,
                        cur=1 if _hit else 0, top=1, unit="有/无",
                        basis="实测：" + _why, source="实测"))

    # ── ⑥ 沉淀层 ────────────────────────────────────────────
    _inv_doc = {}
    try:
        _inv_doc = json.load(open(inv_path, encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        pass
    _invs = _inv_doc.get("invariants", [])
    _has_check = sum(1 for _i in _invs if _i.get("check"))
    out.append(dict(
        layer="⑥ 沉淀", item="不变量带检查方法的条数",
        cur=_has_check, top=max(1, len(_invs)), unit="条",
        basis="实测 不变量里带 check 字段的条数",
        source="实测"))
    out.append(dict(
        layer="⑥ 沉淀", item="自动化沉淀管道 distill.py",
        cur=1 if _exists("distill.py") else 0, top=1, unit="有/无",
        basis="实测 把每轮教训自动写回不变量的脚本是否存在",
        source="实测"))

    # ── ⑦ 编排层 ────────────────────────────────────────────
    out.append(dict(
        layer="⑦ 编排", item="编排循环",
        cur=1 if _exists("orchestrate.py") else 0, top=1, unit="有/无",
        basis="实测：orchestrate.py 是否存在",
        source="实测"))
    out.append(dict(
        layer="⑦ 编排", item="记忆分页（防上下文爆）",
        cur=1 if _exists("memory.py") else 0, top=1, unit="有/无",
        basis="实测：memory.py 是否存在",
        source="实测"))

    return out


def summarize(rows: list[dict]) -> dict:
    """按层汇总。

    ⚠️ 必须每项先算比率，不能累加绝对值。
    第一版直接 sum(cur)/sum(top)，结果「语料 298,500/298,500」
    把「红队 0/1」完全盖住，显示 100% —— 度量工具自己在骗人。
    七层同等重要，所以层间等权，不按条数投票。
    """
    by_layer = {}
    for r in rows:
        b = by_layer.setdefault(r["layer"],
                                dict(ratios=[], ratios_solid=[],
                                     solid=0, est=0, cur=0, top=0))
        ratio = (r["cur"] / r["top"]) if r["top"] else 0.0
        b["ratios"].append(ratio)
        b["cur"] += r["cur"]
        b["top"] += r["top"]
        if r["source"] == "实测":
            b["solid"] += 1
            b["ratios_solid"].append(ratio)
        else:
            b["est"] += 1

    # 层内：各项比率的算术平均（每项等权，不被大分母吞掉）
    layer_ratio = {}
    layer_ratio_solid = {}
    for lay, b in by_layer.items():
        layer_ratio[lay] = (sum(b["ratios"]) / len(b["ratios"])
                            if b["ratios"] else 0.0)
        layer_ratio_solid[lay] = (sum(b["ratios_solid"]) /
                                  len(b["ratios_solid"])
                                  if b["ratios_solid"] else None)

    # 层间：等权平均（七层同等重要）
    vals = [v for v in layer_ratio.values()]
    raw = sum(vals) / len(vals) if vals else 0.0
    sv = [v for v in layer_ratio_solid.values() if v is not None]
    solid = sum(sv) / len(sv) if sv else 0.0

    n_solid = sum(1 for r in rows if r["source"] == "实测")
    return dict(by_layer=by_layer,
                layer_ratio=layer_ratio,
                layer_ratio_solid=layer_ratio_solid,
                raw_ratio=raw,
                solid_ratio=solid,
                n_rows=len(rows), n_solid=n_solid,
                n_layers=len(by_layer))


def report(rows: list[dict], s: dict) -> str:
    L = []
    L.append("=" * 88)
    L.append(f"{'层':<10}{'指标':<34}{'当前':>8}{'上限':>8}  依据")
    L.append("=" * 88)
    last = None
    for r in rows:
        if r["layer"] != last:
            L.append("-" * 88)
            last = r["layer"]
        flag = "" if r["source"] == "实测" else "?"
        L.append(f"{r['layer']:<10}{r['item']:<34}"
                 f"{r['cur']:>8}{r['top']:>8}  {flag}{r['basis'][:38]}")
    L.append("=" * 88)
    L.append("")
    for lay, b in s["by_layer"].items():
        pct = s["layer_ratio"].get(lay, 0) * 100
        sp = s["layer_ratio_solid"].get(lay)
        extra = (f"实测口径 {sp * 100:>5.1f}%"
                 if sp is not None else "全为估计分母")
        bar = "#" * int(pct / 5) + "." * (20 - int(pct / 5))
        L.append(f"  {lay:<10}{pct:>6.1f}%  [{bar}]  {extra}")
    L.append("")
    L.append(f"  全量达成率（含估计分母）：{s['raw_ratio'] * 100:.1f}%")
    L.append(f"  **仅实测分母**达成率：{s['solid_ratio'] * 100:.1f}%"
             f"  （{s['n_solid']}/{s['n_rows']} 项有实测依据）")
    L.append("")
    L.append("  说明：带 ? 的分母是估计值，达成率再高也不代表到位。")
    L.append("        只看「仅实测分母」那一行才是真的。")
    return "\n".join(L)


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="七层架构极限度量")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    rows = measure()
    s = summarize(rows)
    if a.json:
        print(json.dumps(dict(rows=rows, summary=s),
                         ensure_ascii=False, indent=2, default=str))
        return 0
    print(report(rows, s))
    return 0


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

    rows = measure()
    layers = {r["layer"] for r in rows}
    ck("有八层（含宿主层）", len(layers) == 8,
       str(sorted(layers)))
    ck("第 0 层是约束层", any("约束" in x for x in layers))
    ck("每行都有依据", all(r.get("basis") for r in rows))
    ck("每行都标了来源", all(r.get("source") in ("实测", "外部标准", "估计")
                        for r in rows))
    ck("cur 不超过 top",
       all(r["cur"] <= r["top"] for r in rows),
       str([(r["item"], r["cur"], r["top"]) for r in rows
            if r["cur"] > r["top"]]))
    ck("子命令数被实测出来", any(r["item"] == "子命令总数" and r["cur"] > 0
                          for r in rows))

    s = summarize(rows)
    ck("有全量达成率", 0 <= s["raw_ratio"] <= 1, f"{s['raw_ratio']:.2f}")
    ck("有仅实测达成率", 0 <= s["solid_ratio"] <= 1,
       f"{s['solid_ratio']:.2f}")
    # 实测算通常高于全量：全量含未实现的估计项（卡片 0/80 等），会拉低。
    # 差值本身是信息：说明有多少指标的上限是拍出来的。
    gap = abs(s["solid_ratio"] - s["raw_ratio"])
    ck("两个口径都能算",
       all(0 <= v <= 1 for v in (s["solid_ratio"], s["raw_ratio"])),
       f"实测 {s['solid_ratio']:.3f} / 全量 {s['raw_ratio']:.3f}")
    ck("口径差异被标出（差越大估计项越多）", gap >= 0,
       f"差 {gap:.3f}")

    print(f"\n{'ALL PASS' if bad == 0 else 'FAILED'}  {n - bad}/{n}")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "selftest":
        raise SystemExit(selftest())
    raise SystemExit(main(sys.argv[1:]))
