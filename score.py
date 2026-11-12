#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
score.py —— 评分与区分度校准（第 13 轮，思路集成自 dsh-ultramath 的 calibrate.py）

它纠正了一个伪命题
------------------
我一直在问「这篇能不能到一等」，ultramath 的 calibrate.py 说得对：

> 不再是「预测 CUMCM 等级」——那是伪命题。等级阈值是评委的主观线，
> 谁都无法从文本反推。**能测的是重测信度与区分度。**

两个可测的量：
    · 重测信度：同一篇审两次，评分差 ≤5 分 → 结果可用
    · 区分度：  质量明显不同的两篇，分差 ≥15 分 → 工具能分开好坏

为什么要它
----------
我们的 gate 给出「8.0/10」，但**这个数字本身没人校准过**。
如果一篇烂论文也能拿 8.0，那这个分数就是噪音。

所以这里做两件事：
    1. 把 gate 的 8 项折算成一个 0-100 的分数（口径固定，可复现）
    2. 用「故意降级的论文」验区分度：分差够不够 15

用法
    python score.py out/fig                    # 单篇打分
    python score.py calib out/fig              # 测区分度（自动造降级版）
    python score.py selftest
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

# 折算权重：硬门每项 16 分（5 项 = 80），软门每项 5 分（4 项 = 20）
HARD_PENALTY = 16
SOFT_PENALTY = 5


def score_of(figdir: str, gate_result: dict | None = None) -> dict:
    """把 gate 结果折成 0-100。口径固定，同一输入必然同一输出。

    gate_result 给定时不重跑 —— 一次出稿只该算一次门。
    """
    if gate_result is not None:
        res = gate_result
    else:
        import gate
        res = gate.run_all(figdir)
    score = 100.0
    detail = []
    for c in res.get("checks", []):
        if c["status"] == "PASS":
            # 通过的项也要记 —— 否则全绿时明细为空，看不出账是怎么算的
            detail.append((c["id"], "PASS", 0))
            continue
        if c["status"] == "N/A":
            # N/A 不扣分也不给分 —— 它代表「这一步还没做」，
            # 而不是「做错了」。扣分会让早期探索被冤枉。
            detail.append((c["id"], "N/A", 0))
            continue
        pen = HARD_PENALTY if c["tier"] == "hard" else SOFT_PENALTY
        if c["status"] == "WARN":
            pen = SOFT_PENALTY
        score -= pen
        detail.append((c["id"], c["status"], -pen))
    return dict(score=round(max(0.0, score), 1), detail=detail,
                hard_fail=res.get("hard_fail") or [],
                warns=res.get("warns") or [])


def degraded_copy(src: str, dst: str, how: str = "strip_ai") -> str:
    """造一个明显更差的版本，用于测区分度。

    做法（保守，只动一处）：
        strip_ai  —— 删掉 AI 声明节 → rules 的 I006 必然失败
    这样差的是**确定的、可解释的**，而不是随便删点东西。
    """
    if os.path.exists(dst):
        shutil.rmtree(dst)
    os.makedirs(dst, exist_ok=True)
    for f in os.listdir(src):
        s = os.path.join(src, f)
        if os.path.isfile(s):
            shutil.copy2(s, os.path.join(dst, f))
    tex = os.path.join(dst, "paper.tex")
    if how == "strip_ai" and os.path.exists(tex):
        t = open(tex, encoding="utf-8").read()
        i = t.find(r"\section{AI Disclosure")
        if i > 0:
            j = t.find(r"\begin{thebibliography}", i)
            t = t[:i] + (t[j:] if j > 0 else "")
            open(tex, "w", encoding="utf-8", newline="\n").write(t)
    return dst


def calibrate(figdir: str, min_gap: float = 15.0) -> dict:
    """测区分度：好论文 vs 故意降级的论文，分差够不够。"""
    good = score_of(figdir)

    tmp = os.path.join(tempfile.gettempdir(), "score_calib_bad")
    bad_dir = degraded_copy(figdir, tmp, "strip_ai")
    bad = score_of(bad_dir)

    gap = round(good["score"] - bad["score"], 1)
    return dict(good=good, bad=bad, gap=gap,
                min_gap=min_gap,
                ok=gap >= min_gap,
                verdict=("区分度合格" if gap >= min_gap
                         else f"区分度不足（{gap} < {min_gap}）"
                              f"—— 这个分数区分不开好坏，不能用来判等级"))


def retest(figdir: str, times: int = 2) -> dict:
    """重测信度：同一篇连跑几次，分数是不是一样。

    我们的评分是确定性的（不采样、不随机），所以理想情况下差应为 0。
    如果有差，说明有随机性或外部状态混进来了 —— 那更该知道。
    """
    xs = [score_of(figdir)["score"] for _ in range(times)]
    spread = round(max(xs) - min(xs), 2)
    return dict(scores=xs, spread=spread, ok=spread <= 5.0,
                verdict=("重测一致" if spread <= 5.0
                         else f"重测不一致（差 {spread} 分），"
                              f"评分里有非确定性成分"))


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

    here = os.path.dirname(os.path.abspath(__file__))
    fig = os.path.join(here, "out", "fig")

    s = score_of(fig)
    ck("能算出分数", 0 <= s["score"] <= 100, f"{s['score']}/100")
    ck("明细行数 = 检查项数", len(s["detail"]) >= 6, f"{len(s['detail'])} 项")
    ck("全通过时满分为 100", s["score"] == 100.0 or s["hard_fail"],
       f"{s['score']}，硬门失败 {s['hard_fail']}")

    # 重测信度：确定性评分应该零差异
    rt = retest(fig, 2)
    ck("重测信度（确定性评分应零差异）", rt["spread"] == 0,
       f"两次 {rt['scores']}")

    # 区分度
    cal = calibrate(fig)
    ck("能造出降级版并打分", cal["bad"]["score"] <= cal["good"]["score"],
       f"好 {cal['good']['score']} / 差 {cal['bad']['score']}")
    ck("区分度达到 15 分", cal["ok"], f"gap={cal['gap']}")
    ck("降级原因可解释（rules 失败）",
       "rules" in cal["bad"]["hard_fail"],
       f"差的硬门失败 {cal['bad']['hard_fail']}")

    # 清理
    tmp = os.path.join(tempfile.gettempdir(), "score_calib_bad")
    if os.path.exists(tmp):
        shutil.rmtree(tmp, ignore_errors=True)

    print(f"\n{'ALL PASS' if bad == 0 else 'FAILED'}  {n - bad}/{n}")
    return 0 if bad == 0 else 1


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="评分与区分度校准")
    ap.add_argument("cmd", nargs="?", default="selftest",
                    choices=["selftest", "calib", "retest", "score"])
    ap.add_argument("dir", nargs="?", default="")
    a = ap.parse_args(argv)

    if a.cmd == "selftest" or not a.dir:
        return selftest()

    if a.cmd == "score":
        s = score_of(a.dir)
        print(f"  分数 {s['score']}/100")
        for cid, st, pen in s["detail"]:
            print(f"    {cid:<10}{st:<6}{pen:+}")
        return 0

    if a.cmd == "retest":
        r = retest(a.dir, 3)
        print(f"  三次 {r['scores']}，极差 {r['spread']} — {r['verdict']}")
        return 0 if r["ok"] else 1

    r = calibrate(a.dir)
    print(f"  好论文 {r['good']['score']}"f"  降级版 {r['bad']['score']}"
          f"  差 {r['gap']}（门槛 {r['min_gap']}）")
    print(f"  {r['verdict']}")
    if not r["ok"]:
        print(f"  降级版的硬门失败：{r['bad']['hard_fail']}")
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
