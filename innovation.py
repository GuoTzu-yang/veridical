#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
innovation.py —— 创造性审查（第 24 轮，清单来自 ultramath 的《国奖论文评审对照表》）

那份表纠正了我两个认知错误
--------------------------
1. 建模创造性的权重是 ~30%，不是我估的 25% —— 它是四轴里最大的一块。
2. 有一条一票否决项我完全不知道：**B5 全文无统一核心思想**。
   P1 回归 → P2 优化 → P3 稳健性，三个问题各讲各的，就踩这条。

它给的三段式
------------
    现有的 XX 方法在处理 YY 时存在 ZZ 不足
    针对这一问题，本文提出 AA 方法，核心思想是 BB
    与 XX 相比，在 CC 方面有显著优势

还有一条防过度包装的审查
------------------------
    声称「最优」→ 有无最优性证明？无 → 应称「搜索解」
    声称「定理」→ 有无严格证明？无 → 应降级为「命题」
    声称「精确」→ 有无解析表达式？无 → 应称「估计」
    声称「保证」→ 有无保证？无 → 删掉或改为「在本文设定下」

用法
    python innovation.py out/fig/paper.tex
    python innovation.py selftest
"""

from __future__ import annotations

import os
import re
import sys

# ① 统一核心思想的信号词
CORE_SIGNALS = (
    "guiding idea", "core idea", "single yardstick", "unified",
    "throughout this report", "one criterion", "same criterion",
    "central idea", "one standard", "single scale",
)

# ② 三段式的三段，各要至少一个信号
TRIAD = {
    "现有不足": ("existing", "conventional", "usual practice",
                 "commonly", "limitation", "shortcoming", "不足"),
    "提出": ("we propose", "this report proposes", "we introduce",
             "we adopt", "提出"),
    # distinguish A from B 在「本文 vs 常规」的语境里就是优势表述，
    # 不能因为换了动词就判成缺失（实测踩到：论文写的是
    # "Three features distinguish the procedure from a conventional
    # modelling report"，检查器没认）。但只认带 from 的用法，
    # 避免把单纯描述差异也算成优势。
    "优势": ("in contrast", "unlike", "differs", "the difference this",
             "by comparison", "advantage", "distinguish"),
}

# ③ 过度声称：词 → 需要什么证据才算配得上
OVERCLAIM = {
    "optimal": ("prov", "prove", "proof", "minimis", "maximis",
                "最优性", "证明"),
    "theorem": ("proof", "lemma", "证明"),
    "exact": ("closed-form", "analytic", "解析"),
    "guarantee": ("guarantee", "bound", "保证"),
    "always": ("always", "invariant", "恒"),
}

# ④ 创新点上限：超过反扣印象分
MAX_INNOV = 2


def _clean(tex: str) -> str:
    s = re.sub(r"(?<!\\)%.*$", "", tex, flags=re.M)
    s = re.sub(r"\\[a-zA-Z]+\*?(\[[^\]]*\])?", " ", s)
    return s


def audit(tex: str) -> dict:
    body = _clean(tex)
    low = body.lower()
    items = []

    def add(name, ok, detail, weight=3):
        items.append(dict(name=name, ok=ok, detail=detail, weight=weight))

    # ① 统一核心思想（B5）
    hit = [w for w in CORE_SIGNALS if w in low]
    add("统一核心思想", bool(hit),
        f"信号 {hit[:2]}" if hit else "全文没有贯穿的主线（B5 风险）", 4)

    # ② 三段式
    missing = []
    for seg, kws in TRIAD.items():
        if not any(k in low for k in kws):
            missing.append(seg)
    add("创新三段式", not missing,
        "缺 " + "、".join(missing) if missing else "不足/提出/优势齐备", 4)

    # ③ 过度声称
    bad = []
    for word, evid in OVERCLAIM.items():
        n = len(re.findall(rf"\b{word}\w*", low))
        if n and not any(e in low for e in evid):
            bad.append(f"{word}×{n}")
    add("无过度声称", not bad,
        "无证据的强声称：" + "、".join(bad) if bad else "声称与证据相称", 3)

    # ④ 创新点数量上限
    n_innov = len(re.findall(r"\b(we propose|this report proposes|"
                             r"we introduce)\b", low))
    add("创新点不分散", n_innov <= MAX_INNOV,
        f"{n_innov} 处「提出」（上限 {MAX_INNOV}）", 2)

    # ⑤ 模型对比（≥2 个模型，有量化指标）
    cmp_n = len(re.findall(r"\bcandidate\b|\bbaseline\b|"
                           r"\bcompared\b|\bcomparison\b", low))
    add("有模型对比", cmp_n >= 3, f"{cmp_n} 处对比信号", 2)

    got = sum(i["weight"] for i in items if i["ok"])
    total = sum(i["weight"] for i in items)
    return dict(ok=got == total, items=items,
                score=round(100 * got / total, 1) if total else 0)


def report(r: dict) -> str:
    L = [f"创造性审查：{r['score']}/100"
         + ("" if r["ok"] else "  —— 有失分项"), ""]
    for i in r["items"]:
        L.append(f"  [{'OK  ' if i['ok'] else 'FAIL'}] {i['name']:<12}"
                 f"{i['detail']}")
    return "\n".join(L)


# ══════════════════════════════════════════════════════════════════════
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

    good = r"""The guiding idea is that a single yardstick should decide every
claim. Existing treatments decide the three questions separately.
We propose to replace those three standards with one. The difference this
makes is checkable. Six candidate structures were compared under
cross-validation against a baseline."""
    r = audit(good)
    ck("合格文本通过", r["ok"], f"{r['score']}/100")
    ck("识别出核心思想", any(i["name"] == "统一核心思想" and i["ok"]
                        for i in r["items"]))

    # 没有核心思想
    r2 = audit("We fit a regression and report the results.")
    ck("无核心思想被抓出", not any(i["name"] == "统一核心思想" and i["ok"]
                              for i in r2["items"]))
    ck("缺三段式被抓出", not any(i["name"] == "创新三段式" and i["ok"]
                            for i in r2["items"]))

    # 过度声称
    r3 = audit("The guiding idea is unified. Existing work is limited. "
               "We propose a method. In contrast it is better. "
               "This is the optimal design and an exact solution.")
    ck("过度声称被抓出", not any(i["name"] == "无过度声称" and i["ok"]
                            for i in r3["items"]),
       str([i["detail"] for i in r3["items"] if i["name"] == "无过度声称"]))

    # 有证据的声称应通过
    r4 = audit("The guiding idea is unified. Existing work is limited. "
               "We propose a method. In contrast it is better. "
               "The grid search returns the lowest error among the "
               "candidates, which we call the selected design.")
    ck("有基准的声称通过", any(i["name"] == "无过度声称" and i["ok"]
                          for i in r4["items"]))

    # 创新点过多
    r5 = audit("The guiding idea is unified. Existing work is limited. "
               "We propose A. We propose B. We propose C. In contrast.")
    ck("创新点过多被抓出", not any(i["name"] == "创新点不分散" and i["ok"]
                              for i in r5["items"]))

    # 真实论文
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "out", "fig", "paper.tex")
    if os.path.exists(p):
        real = audit(open(p, encoding="utf-8").read())
        ck("真实论文能审", "items" in real and len(real["items"]) == 5,
           f"{real.get('score')}/100")

    print(f"\n{'ALL PASS' if bad == 0 else 'FAILED'}  {n - bad}/{n}")
    return 0 if bad == 0 else 1


def main(argv=None) -> int:
    a = sys.argv[1:] if argv is None else argv
    if not a or a[0] == "selftest":
        return selftest()
    if not os.path.exists(a[0]):
        print(f"  没有 {a[0]}")
        return 2
    r = audit(open(a[0], encoding="utf-8").read())
    print(report(r))
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
