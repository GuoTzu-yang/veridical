#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rules.py —— 把竞赛不变量变成可执行检查（第 165 轮建）

起因
----
用户决定：**不改动 Purge**。所以 `prompt-inject.md` 这条宿主通道关闭，
「不变量只写在提示词里」的方案作废。

那知识怎么传递？答案：**不要把约束写成文字，写成检查**。

    提示词里的约束 → LLM 可能忘、可能跳读、可能自己找理由绕过
    检查器里的约束 → 物理上过不去（FAIL 就是 FAIL）

同一个约束，降级成代码检查反而更硬。这就是"自己的插件"该做的事。

能自动检查的 vs 只能标"需人工"
--------------------------------
| 不变量 | 能否自动检查 |
|---|---|
| I001 文字表述权重最大 | ❌ 权重是策略，不是文档属性 |
| I002 创新只有三类 | ✅ 声称创新时必须能归类 |
| I003 三模型（基准/主/对照） | ✅ 查文档里有没有三种模型的痕迹 |
| I004 三大检验 | ✅ 查三类检验各自有没有落地 |
| I005 核心建模人工核验 | ⚠️ 半自动：查有没有签字记录 |
| I006 AI 使用声明 | ✅ 查声明段落 |
| I007 按小问组织 | ✅ 查章节是否对应问题编号 |
| I008 页数/目录 | ✅ 查目录、数页数 |

自动检查 7 条，半自动 1 条。只有 I001 是纯策略，无法从文档反推。

用法
    python rules.py paper.tex          # 检查一份论文
    python rules.py paper.tex --json
    python rules.py selftest
"""

from __future__ import annotations

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def _norm(tex: str) -> str:
    return tex.lower()


# ══════════════════════════════════════════════════════════════════════
#  每条规则：(id, 名称, 检查函数, 说明)
#  检查函数返回 (ok: bool, detail: str)
# ══════════════════════════════════════════════════════════════════════
def _r_i002(t):
    """创新只有三类：算法改进 / 跨域迁移 / 多模型融合。"""
    low = _norm(t)
    claims = [w for w in ("innovation", "novel", "创新", "贡献")
              if w in low or w in t]
    if not claims:
        return True, "没声称创新，不适用"
    kws = ("algorithm improvement", "算法改进", "改进算法",
           "cross-domain", "跨域", "迁移",
           "multi-model", "model fusion", "多模型", "模型融合", "融合")
    hit = [k for k in kws if k.lower() in low or k in t]
    if hit:
        return True, f"创新归到：{hit[:3]}"
    return False, ("声称创新，但归不到三类之一"
                   "（算法改进/跨域迁移/多模型融合）")


def _r_i003(t):
    """必须有基准模型 / 主模型 / 对照模型。"""
    low = _norm(t)
    base = any(k in low or k in t for k in
               ("baseline model", "baseline", "基准模型", "基础模型"))
    main = any(k in low or k in t for k in
               ("main model", "primary model", "主模型"))
    ctrl = any(k in low or k in t for k in
               ("comparison model", "contrast model", "对照模型",
                "alternative structure", "rival model"))
    miss = [n for n, v in (("基准", base), ("主", main), ("对照", ctrl))
            if not v]
    if miss:
        return False, f"缺 {'/'.join(miss)} 模型（三模型缺一）"
    return True, "三种模型齐备"


def _r_i004(t):
    """三大检验：误差分析 / 灵敏度分析 / 稳健性检验。"""
    low = _norm(t)
    groups = {
        "误差分析": ("error analysis", "residual", "rmse", "误差", "残差"),
        "灵敏度分析": ("sensitivity", "敏感性", "灵敏度"),
        "稳健性检验": ("robustness", "稳健"),
    }
    miss = []
    for name, kws in groups.items():
        if not any(k in low or k in t for k in kws):
            miss.append(name)
    if miss:
        return False, f"缺 {'/'.join(miss)}（缺一不能标 validated）"
    return True, "三项齐备"


def _r_i005(t):
    """核心建模人工核验。

    不认关键词，认**结构**：必须同时出现
        (a) 人的指代      team / we / 参赛队
        (b) 核验动作      verif / check / recompute / review / sign off
        (c) 被核验对象    number / result / assumption / 数值 / 结论
    只出现「人工核验」四个字但没说核验了什么，不算。
    """
    low = _norm(t)
    actors = ("team", "we ", "our ", "参赛队", "作者")
    acts = ("verif", "check", "recomput", "review", "sign off",
            "cross-check", "核对", "复核", "核验")
    objects = ("number", "result", "assumption", "value", "conclusion",
               "数值", "结果", "假设", "结论")

    a = [x for x in actors if x in low or x in t]
    b = [x for x in acts if x in low or x in t]
    c = [x for x in objects if x in low or x in t]
    miss = []
    if not a:
        miss.append("没说谁核验的")
    if not b:
        miss.append("没有核验动作")
    if not c:
        miss.append("没说核验了什么")
    if miss:
        return False, ("核验记录不完整：" + "、".join(miss)
                       + "（竞赛规则要求核心建模由参赛队主导并人工核验）")
    return True, f"有核验记录（主体 {a[:2]} / 动作 {b[:2]} / 对象 {c[:2]}）"


def _r_i006(t):
    """AI 使用声明。"""
    low = _norm(t)
    kws = ("ai 工具使用", "ai工具使用", "ai tool usage", "ai usage",
           "ai 使用", "ai使用", "use of ai", "生成式 ai")
    if any(k.lower() in low or k in t for k in kws):
        return True, "有 AI 声明"
    return False, "缺 AI 工具使用声明（用了/没用二选一，参考文献前必须有）"


def _r_i007(t):
    """按小问组织：章节应能对应问题编号。"""
    # 找形如 "Problem 1" / "问题 1" / "Q1" 的标题
    hits = re.findall(
        r"(?:problem|question|问题|task)\s*([1-9])", _norm(t))
    subs = len(re.findall(r"\\subsection\{", t))
    if not hits:
        return False, "没找到按小问组织的痕迹（Problem 1 / 问题 1）"
    return True, f"识别到 {len(set(hits))} 个小问，{subs} 个小节"


def _r_i008(t):
    """正文 ≤30 页，摘要 ≤1 页，不要目录。"""
    problems = []
    if "\\tableofcontents" in t:
        problems.append("有目录")
    n_sec = len(re.findall(r"\\section\{", t))
    if n_sec > 12:
        problems.append(f"{n_sec} 个一级节，可能超出 30 页")
    if problems:
        return False, "；".join(problems)
    return True, f"{n_sec} 个一级节，无目录"


RULES = [
    ("I002", "创新只有三类", _r_i002),
    ("I003", "三模型（基准/主/对照）", _r_i003),
    ("I004", "三大检验", _r_i004),
    ("I005", "核心建模人工核验", _r_i005),
    ("I006", "AI 使用声明", _r_i006),
    ("I007", "按小问组织", _r_i007),
    ("I008", "版式（无目录/节数）", _r_i008),
]

MANUAL = [
    ("I001", "文字表述权重 35%（四轴最大）",
     "策略性约束，无法从文档反推。人工判断：摘要/结构/图表是否到位"),
]


def check(tex: str) -> dict:
    """跑全部可自动检查的规则。"""
    results = []
    for rid, name, fn in RULES:
        try:
            ok, detail = fn(tex)
        except Exception as e:                      # noqa: BLE001
            ok, detail = False, f"检查器异常：{type(e).__name__}: {e}"
        results.append(dict(id=rid, name=name, ok=ok, detail=detail))
    passed = sum(1 for r in results if r["ok"])
    return dict(results=results, passed=passed, total=len(results),
                manual=MANUAL,
                ok=passed == len(results))


def report(r: dict) -> str:
    L = [f"竞赛规则检查：{r['passed']}/{r['total']} 通过", ""]
    for x in r["results"]:
        L.append(f"  [{'PASS' if x['ok'] else 'FAIL'}] {x['id']} "
                 f"{x['name']}")
        if x["detail"]:
            L.append(f"         {x['detail']}")
    if r["manual"]:
        L.append("")
        L.append("  需人工判断（无法自动检查）：")
        for rid, name, why in r["manual"]:
            L.append(f"  [人工] {rid} {name}")
            L.append(f"         {why}")
    return "\n".join(L)


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

    # 空文档：几乎所有规则都该 FAIL
    r = check("")
    ck("空文档不通过", not r["ok"], f"{r['passed']}/{r['total']}")
    ck("空文档报缺三模型",
       any(not x["ok"] and "模型" in x["detail"] for x in r["results"]))
    ck("空文档报缺 AI 声明",
       any(not x["ok"] and "AI" in x["detail"] for x in r["results"]))

    # 合规文档：应该全过
    good = r"""
    \section{Summary}
    AI 工具使用声明：使用了生成式 AI 辅助数据处理。
    \section{问题 1} \subsection{思路} \subsection{建模}
    \section{问题 2}
    We use a baseline model, a main model, and a comparison model.
    Innovation: algorithm improvement over the standard QR solver.
    人工核验：全部数值由参赛队复算确认。
    error analysis with RMSE, sensitivity analysis, robustness check.
    """
    g = check(good)
    ck("合规文档全过", g["ok"], f"{g['passed']}/{g['total']}")
    for x in g["results"]:
        if not x["ok"]:
            ck(f"  {x['id']} 应通过但失败", False, x["detail"])

    # 三条典型违规
    r1 = check("We claim novelty here.")
    ck("抓到「声称创新但归不了类」",
       any(not x["ok"] and x["id"] == "I002" for x in r1["results"]))

    r2 = check("\\tableofcontents")
    ck("抓到「有目录」",
       any(not x["ok"] and x["id"] == "I008" for x in r2["results"]))

    r3 = check("We use a main model only.")
    ck("抓到「缺基准/对照」",
       any(not x["ok"] and x["id"] == "I003" for x in r3["results"]))

    # I001 必须标人工，不能假装能自动检查
    ck("I001 被标为人工检查", any(m[0] == "I001" for m in r["manual"]))

    print(f"\n{'ALL PASS' if bad == 0 else 'FAILED'}  {n - bad}/{n}")
    return 0 if bad == 0 else 1


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="竞赛规则检查")
    ap.add_argument("tex", nargs="?", help="论文 .tex 路径")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    if not a.tex or a.tex == "selftest":
        return selftest()
    if not os.path.exists(a.tex):
        print(f"  文件不存在：{a.tex}")
        return 2
    tex = open(a.tex, encoding="utf-8", errors="replace").read()
    r = check(tex)
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        print(report(r))
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
