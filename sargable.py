#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
机制适用性：这个索引在这个谓词形式下原理上用得上吗

第三十四轮的阴性对照证明：判据的 e1（步骤清不清楚）和 e3（指标能不能验）
**预测不了结论会不会被推翻**。缺的那一维是「这个技术在这个上下文里成不成立」。

这一维不能拍脑袋。probe_sargable.py 实测了 15 种谓词形式，边界和常识不一样：

    age = 42                       → 用得上
    age + 0 = 42                   → 用不上   ← 竞赛题 #1538
    CAST(age AS SIGNED) = 42       → 用得上   ← 常识以为不行，其实行
    CAST(age AS CHAR) = '42'       → 用不上
    ABS(age - 42) = 0              → 用不上

关键区别不是「有没有被表达式包住」，而是**这个变换有没有改变类型**：
CAST(int AS SIGNED) 是恒等变换，优化器能看穿；CAST AS CHAR 真的改了类型。

本模块把这条规则写成代码，并用那 15 条实测数据做自测。

跑法：python sargable.py
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# 类型族：用于判断一个变换是不是「恒等变换」
# 注意 signed/unsigned 既是有符号整型的族名，也是 CAST 的目标类型名，
# 所以两个词都要收进来——CAST(int AS SIGNED) 是恒等变换，优化器看得穿。
_TYPE_FAMILY = {
    "signed": {"int", "integer", "bigint", "smallint", "tinyint", "mediumint",
               "signed"},
    "unsigned": {"int unsigned", "bigint unsigned", "smallint unsigned",
                 "tinyint unsigned", "mediumint unsigned", "unsigned"},
    "char": {"char", "varchar", "text", "tinytext", "mediumtext", "longtext"},
    "binary": {"binary", "varbinary", "blob"},
    "double": {"double", "float", "real"},
    "decimal": {"decimal", "numeric"},
    "date": {"date", "datetime", "timestamp"},
}

_ARITH = "+-*/%^"
_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def type_family(col_type: str | None) -> str | None:
    """把列类型映射到类型族；映射不了返回 None。"""
    if not col_type:
        return None
    t = col_type.lower().split("(")[0].strip()
    for fam, members in _TYPE_FAMILY.items():
        if t in members:
            return fam
    return None


@dataclass
class Usage:
    kind: str        # bare | arith | func
    func: str = ""   # func 时的函数名
    cast_target: str = ""   # CAST 的目标类型


def _find_func_before(text: str, pos: int) -> str:
    """pos 左边最近的一个 `NAME(` 里的 NAME。"""
    left = text[:pos].rstrip()
    if not left.endswith("("):
        return ""
    m = _IDENT.search(left[:-1][::-1][::-1])
    # 从 '(' 往前找标识符
    i = len(left) - 2
    while i >= 0 and (left[i].isalnum() or left[i] == "_"):
        i -= 1
    return left[i + 1:len(left) - 1]


def column_usages(pred: str, col: str) -> list[Usage]:
    """找出列在谓词里的每一种出现形式。"""
    out: list[Usage] = []
    for m in re.finditer(rf"\b{re.escape(col)}\b", pred, re.I):
        start, end = m.span()
        before = pred[:start].rstrip()
        after = pred[end:].lstrip()

        # 前面是 '(' 且 '(' 前是标识符 → 函数调用
        if before.endswith("("):
            fname = _find_func_before(pred, start)
            if fname:
                u = Usage("func", fname.upper())
                if u.func == "CAST":
                    mc = re.search(rf"CAST\s*\(\s*{re.escape(col)}\s+AS\s+([A-Za-z]+)",
                                   pred, re.I)
                    if mc:
                        u.cast_target = mc.group(1)
                out.append(u)
                continue

        # 紧邻算术运算符 → 算术表达式内
        if (before and before[-1] in _ARITH) or (after and after[0] in _ARITH):
            out.append(Usage("arith"))
            continue

        out.append(Usage("bare"))
    return out


def sargable(sql: str, indexed_cols: dict[str, str]) -> tuple[bool | None, str]:
    """判断谓词里的索引列**在形式上**能不能用上索引。

    返回 (能用, 理由)。None = 判不了（没有可判的列 / 类型不明）。

    ⚠ 边界（第六十七轮实测确定，别读过头）：
        本函数回答的是「谓词形有没有破坏索引可用性」，
        **它不回答引擎会不会真用这个索引。**

        实测反例（2026-11，bench_l3.t_ann 5000 行，age 上有 ix_dg_age_eq）：

            age = 42      → TABLE RANGE SCAN(ix_dg_age_eq)   形式上可用，真用了
            age > 40      → TABLE FULL SCAN                  形式上可用，**没用**
            age IS NULL   → TABLE RANGE SCAN(ix_dg_age_eq)   形式上也没破坏

        `age > 40` 命中 59% 的行，优化器按**选择性**判全表扫描更便宜。
        这是选择性问题，不是 sargable 问题。

    所以：
        sargable=True   → 「索引**可以**用」      （必要不充分）
        sargable=False  → 「索引**一定**用不上」  （这条是硬的）
    """
    m = re.search(r"\bwhere\b(.*?)(?:\border\s+by\b|\blimit\b|\bgroup\s+by\b|$)",
                  sql, re.I | re.S)
    if not m:
        return None, "没有 WHERE 子句，无从判断"
    pred = m.group(1)

    relevant = [c for c in indexed_cols if re.search(rf"\b{re.escape(c)}\b", pred, re.I)]
    if not relevant:
        return None, "谓词里没有索引列"

    worst: str | None = None
    for col in relevant:
        usages = column_usages(pred, col)
        if not usages:
            continue
        for u in usages:
            if u.kind == "bare":
                continue
            if u.kind == "arith":
                worst = (f"列 {col} 被算术表达式包住，索引原理上用不上"
                         if worst is None else worst)
                continue
            # func
            if u.func == "CAST":
                src = type_family(indexed_cols.get(col))
                dst = type_family(u.cast_target)
                if src and dst and src == dst:
                    continue          # 恒等变换，优化器能看穿 → 当作可用
                worst = (f"列 {col} 被 CAST 成 {u.cast_target or '未知类型'}，类型变了，索引用不上"
                         if worst is None else worst)
                continue
            worst = (f"列 {col} 被函数 {u.func}() 包住，索引原理上用不上"
                     if worst is None else worst)

    if worst:
        return False, worst
    return True, "索引列在谓词里是裸引用，可用索引"


# ---------------------------------------------------------------------------
# 自测：用 probe_sargable.py 实测出来的 15 条真实数据
# ---------------------------------------------------------------------------
TT = {"age": "int", "category5": "int", "id": "bigint"}

GROUND_TRUTH = [
    # (谓词, 实测能否用上索引)
    ("age = 42", True),
    ("age > 50", True),
    ("age + 0 = 42", False),
    ("age * 1 = 42", False),
    ("age - 0 = 42", False),
    ("age + 0 > 40", False),
    ("age * age = 42", False),
    ("CAST(age AS SIGNED) = 42", True),
    ("CAST(age AS CHAR) = '42'", False),
    ("ABS(age - 42) = 0", False),
    ("YEAR(age) = 42", False),
    ("age IN (41,42,43)", True),
    ("age BETWEEN 41 AND 43", True),
    ("age = 42 OR FALSE", True),
    ("age NOT IN (42)", True),
]


def selftest() -> int:
    print("=" * 76)
    print("机制适用性 · 自测（对 15 条实测数据）")
    print("=" * 76)
    print(f"  {'谓词':<30}{'实测':>8}{'规则':>8}  一致")
    print("  " + "-" * 66)
    hit = 0
    for pred, truth in GROUND_TRUTH:
        got, reason = sargable(f"SELECT * FROM t WHERE {pred}", TT)
        ok = got is truth
        hit += 1 if ok else 0
        print(f"  {pred:<30}{('用上' if truth else '用不上'):>8}"
              f"{('用上' if got else '用不上' if got is False else '判不了'):>8}"
              f"  {'✓' if ok else '✗'} {reason[:28]}")
    print()
    print("=" * 76)
    print(f"准确率: {hit}/{len(GROUND_TRUTH)} = {hit/len(GROUND_TRUTH)*100:.0f}%")
    print("=" * 76)
    return 0 if hit == len(GROUND_TRUTH) else 1


if __name__ == "__main__":
    raise SystemExit(selftest())
