#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EXPLAIN 类样本：优化任务用「执行计划」当验证结果

为什么建这个（第六十六轮）：
    账本里有 18 条 degrade **永远没结论** —— 都是优化类任务。
    它们的规格挂的是 `CREATE INDEX` 这类**非幂等**操作，重跑必然失败。

    但优化任务的"成没成"，本来就不必靠重跑操作来验：
    **看执行计划就行。** EXPLAIN 是只读的、幂等的、答案明确的。

    「这条查询会不会走索引」是个能算出来的问题 —— 而且
    它正好检验 sargable 那套理论（sargable.py 有 15 条实测语料）。

跑法：
    python tests/collect_explain.py             # 只判不验（盲判）
    python tests/collect_explain.py --record    # 落账（success=None 挂起）
    然后 python ledger.py resolve-blind         结算
"""

from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from probe import query_rows                            # noqa: E402

DB = "bench_l3.t_ann"

# (编号, 主张, 谓词, 我预期的计划特征, 预判)
# 计划特征用大写子串匹配：命中 = 走索引，FULL SCAN = 没走。
CLAIMS = [
    ("E1", "age = 42 会走索引", "age = 42", "ix_", True),
    ("E2", "age + 0 = 42 不会走索引（算术破坏索引）", "age + 0 = 42", "FULL SCAN", True),
    ("E3", "age * 1 = 42 不会走索引", "age * 1 = 42", "FULL SCAN", True),
    ("E4", "CAST(age AS SIGNED) = 42 仍会走索引（类型没变）", "CAST(age AS SIGNED) = 42", "ix_", True),
    ("E5", "CAST(age AS CHAR) = '42' 不会走索引（类型变了）", "CAST(age AS CHAR) = '42'", "FULL SCAN", True),
    ("E6", "age BETWEEN 40 AND 45 会走索引", "age BETWEEN 40 AND 45", "ix_", True),
    ("E7", "age IS NULL 不会走索引", "age IS NULL", "FULL SCAN", True),
    ("E8", "id = 1 走主键", "id = 1", "TABLE GET", True),
    ("E9", "age > 40 会走索引", "age > 40", "ix_", True),
    ("E10", "CONCAT(age,'') = '42' 不会走索引", "CONCAT(age,'') = '42'", "FULL SCAN", True),
]


def plan_of(pred: str) -> tuple[bool, str]:
    """取这条谓词的执行计划文本。"""
    ok, rows = query_rows("EXPLAIN SELECT * FROM " + DB + " WHERE " + pred)
    if not ok:
        return False, rows[0] if rows else "取不到计划"
    return True, "\n".join(rows)


def _plan_rows(text: str) -> list[str]:
    """只取执行算子那几行，返回「算子 + 名字」串。

    实测的计划行长这样：
        |0 |TABLE RANGE SCAN|t_ann(ix_dg_age_eq)|50 |138|
    切完格：['0', 'TABLE RANGE SCAN', 't_ann(ix_dg_age_eq)', '50', '138']
    所以算子在第 2 格、索引名在第 3 格。

    为什么不能搜全文（第六十六轮自己踩的）：
        第一版在**整段**计划文本里找 "INDEX"，E9 明明是全表扫描却被判成走索引
        —— 因为下面 Outputs & filters 那几段里有这个词。
        一个字串在文档里出现过，不代表就是那个意思。
    """
    out = []
    for ln in text.splitlines():
        s = ln.strip()
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if len(cells) < 2:
            continue
        op = cells[1].upper()
        if any(k in op for k in ("SCAN", "GET", "LOOKUP")):
            name = cells[2] if len(cells) > 2 else ""
            out.append(cells[1] + " " + name)
    return out


def verify(pred: str, marker: str) -> tuple[bool, str]:
    """验证：**执行算子那一行**有没有预期特征。"""
    ok, text = plan_of(pred)
    if not ok:
        return False, text[:70]
    ops = _plan_rows(text)
    if not ops:
        return False, "计划里没找到算子行：" + text[:50]
    joined = " ".join(ops).upper()
    hit = marker.upper() in joined
    return hit, "算子=" + ops[0][:66]


def boundary_check() -> list[tuple[str, bool, str]]:
    """把 sargable 的边界做成可执行断言。

    第六十七轮：`sargable=True` 只说明"索引**可以**用"，
    不说明"引擎**会**用"。这里对每条谓词做一次形式判定 + 一次真实计划，
    把两者不一致的地方摆出来。

    断言要证明的是**边界存在**，不是"边界是 bug"——
    `age > 40` 命中 59% 的行，全表扫描本来就更便宜。
    """
    import sargable as S

    idx = {"age": "ix_dg_age_eq", "id": "PRIMARY"}
    cases = [
        ("age = 42", True, True),      # 形式可用 → 引擎真用了
        ("age + 0 = 42", False, False),  # 形式不可用 → 引擎没用
        ("age > 40", True, False),     # 形式可用 → 引擎**没用**（选择性）
        ("age IS NULL", True, True),   # 形式可用 → 引擎真用了
    ]
    out = []
    for pred, want_form, want_engine in cases:
        form, _why = S.sargable("SELECT * FROM t WHERE " + pred, idx)
        # 统一问「走了索引吗」——只用一个标记，避免变量名骗自己。
        # （第一版这里按 want_engine 选标记，结果 engine 的含义
        #   在两条之间偷偷变了，断言自己错了。）
        uses_index, detail = verify(pred, "ix_")
        out.append((pred, form is want_form and uses_index is want_engine,
                    f"形式可用={form} 引擎真用索引={uses_index}  {detail[:44]}"))
    return out


def main() -> int:
    print("=" * 92)
    print("EXPLAIN 类样本 · 优化任务用执行计划当验证结果")
    print("=" * 92)

    rows = []
    for cid, text, pred, marker, guess in CLAIMS:
        ok, why = verify(pred, marker)
        hit = (ok == guess)
        rows.append((cid, text, pred, marker, guess, ok, why, hit))
        print(f"  [{cid:<3}] {'命中' if hit else '错判'}  {text}")
        print(f"        预判={'成立' if guess else '不成立'}"
              f"   实测={'成立' if ok else '不成立'}   {why}")

    ok_n = sum(1 for r in rows if r[5])
    miss = sum(1 for r in rows if not r[7])
    print()
    print("=" * 92)
    print(f"  {len(rows)} 条：成立 {ok_n} / 不成立 {len(rows) - ok_n}"
          f"   我的预判错 {miss} 条")
    print("=" * 92)

    # 边界检查：证明 sargable=True 不等于"引擎会用"
    print()
    print("=" * 92)
    print("sargable 的边界 · 形式可用 ≠ 引擎会用")
    print("=" * 92)
    bchecks = boundary_check()
    bad = 0
    for pred, ok, detail in bchecks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {pred:<16} {detail}")
        bad += 0 if ok else 1
    print()
    if bad:
        print(f"[FAIL] {bad} 条与预期不符 —— 要么引擎换了策略，要么边界判断错了")
    else:
        print("[PASS] 四条都对：形式判定与引擎决策的差异被如实摆出来了")
        print("       其中 age > 40 就是那个反例——形式可用，引擎按选择性选全表扫描")

    if "--record" in sys.argv:
        _record(rows, blind=True)
    return 0 if bad == 0 else 1


def _record(rows, blind: bool = True) -> None:
    """落账。盲判时 success=None，等 resolve-blind 结算。"""
    import ledger as L
    from harness import Claim, run_gates, EvidenceEnv

    L.bind_production("EXPLAIN 类样本采集")
    env = EvidenceEnv(3)
    n = 0
    for cid, text, pred, marker, guess, ok, why, _hit in rows:
        if blind:
            # 盲判：只看谓词形式，不看计划。e3=1（有验法但没跑）
            c = Claim(cid, text, e1=2, e2=1, e3=1, kind="world")
            g = run_gates(c, env)
            # 把「还差什么」一起记下来（第七十三轮）：
            # 只记“判成 degrade”，复盘时只知道结论保留，不知道该补哪儿。
            from extend import what_would_help
            _ask = what_would_help(c, g["final"], g.get("blocked_at"), env)
            L.record(g["final"], task="EXPLAIN·" + cid + " " + text[:28],
                     note="谓词=" + pred,
                     success=None, exec_ok=None,
                     evidence="盲判：只看谓词形式，未取执行计划",
                     env_level=3, cause=g.get("cause"), origin="collect",
                     ask=_ask,
                     replay={"domain": "explain",
                             "task": {"sql": "EXPLAIN SELECT * FROM " + DB
                                             + " WHERE " + pred,
                                      "marker": marker}},
                     prejudged=False)
        else:
            c = Claim(cid, text, e1=2, e2=2, e3=2, kind="world",
                      refuted_by_test=(not ok))
            g = run_gates(c, env)
            L.record(g["final"], task="EXPLAIN·" + cid + " " + text[:28],
                     note="谓词=" + pred, success=ok,
                     conclusion_held=ok, exec_ok=True,
                     evidence=why[:70], env_level=3, cause=g.get("cause"),
                     origin="collect", prejudged=True)
        n += 1
    print()
    print(f"已记账 {n} 条（{'盲判，等 resolve-blind' if blind else '先验证后判'}）")


if __name__ == "__main__":
    raise SystemExit(main())
