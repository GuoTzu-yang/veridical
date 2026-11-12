#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fence_mutation.py —— 变异测试：把围栏改坏，看接受测试会不会报错。

为什么需要它（第 123 轮，用户问「你怎么保证这根栏杆有效，而不是自己骗自己」）：

`fence_acceptance.py` 报「拦住 11/12」并不能证明围栏有效，因为：
  · 样本是我选的（全是我踩过的坑）—— 已知缺陷回放 ≠ 未知缺陷检出率
  · 期望是我定的（「S1 应放行」也只是我的理解）
  · **最要命的一条**：如果样本「复制」了围栏逻辑，把真围栏改坏，样本照样报拦住

前两条无法根除，第三条可以。办法就是**变异测试**：
对每道围栏做一个「让它永远通过」的改动，再看对应的接受测试样本是否变成「漏检」。
若改坏了还报「拦住」，说明那条测试根本没测到围栏 —— 它是假的。

本工具只验证「测试对围栏敏感」，不验证「围栏本身对不对」。

用法：
    python tools/fence_mutation.py
    python tools/fence_mutation.py --json
退出码：0 = 每条测试都对围栏敏感；1 = 有假测试。
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import arch_invariants as AI          # noqa: E402
import freeze                          # noqa: E402
import redteam                         # noqa: E402


def _mutants():
    """(说明, 所属模块, 属性名, 变异实现, 对应样本名, 变异后应变成)

    变异必须接受任意参数：`i11(spec=...)` / `i12(figdir=..., data_paths=...)`
    是带参数的，写死 `lambda: ...` 会 TypeError —— 那会被误读成「假测试」，
    实际是**变异器自己写错了**（第 123 轮踩过）。
    """
    return [
        ("freeze._match_written 永远放行", freeze, "_match_written",
         lambda *a, **k: True, "s2", "漏检"),
        ("arch_invariants.i11 永远成立", AI, "i11",
         lambda *a, **k: (True, "变异：永远成立"), "s12", "漏检"),
        ("arch_invariants.i12 永远成立", AI, "i12",
         lambda *a, **k: (True, "变异：永远成立"), "s6", "漏检"),
        ("redteam.check 永远 PASS", redteam, "check",
         lambda *a, **k: dict(ok=True, level="PASS", detail="变异：永远通过",
                              per_section={}), "s11", "漏检"),
    ]


def run_one(label, mod, attr, mutant, sample_name, expect_after):
    """把围栏改坏 → 跑样本 → 还原 → 看样本判定是否变成 expect_after。"""
    import fence_acceptance as FA
    fn = getattr(FA, sample_name, None)
    if fn is None:
        return dict(label=label, ok=False,
                    detail="找不到样本 %s" % sample_name)
    orig = getattr(mod, attr, None)
    if orig is None:
        return dict(label=label, ok=False,
                    detail="%s.%s 不存在" % (mod.__name__, attr))
    try:
        # 变异前：样本应「拦住」（expect=block 且 blocked=True）
        e0, b0, _ev0 = fn()
        # 变异后：围栏永远通过 → 样本应「拦不住」
        setattr(mod, attr, mutant)
        e1, b1, ev1 = fn()
    finally:
        setattr(mod, attr, orig)

    # 判定：
    #   · 变异前拦住、变异后拦不住 → 测试对围栏敏感（好）
    #   · 变异前拦住、变异后仍拦住 → **假测试**（样本没走真围栏）
    #   · 变异前就拦不住 → 样本本身有问题
    if not (e0 == "block" and b0):
        return dict(label=label, ok=False,
                    detail="变异前样本就没拦住（expect=%s blocked=%s）"
                           % (e0, b0))
    changed = not (e1 == "block" and b1)
    return dict(
        label=label, ok=changed,
        detail=("变异后：expect=%s blocked=%s（%s）｜%s"
                % (e1, b1, "敏感✓" if changed else "仍拦住=假测试",
                   str(ev1)[:56])))


def main(argv):
    rows = []
    for label, mod, attr, mutant, sample, expect_after in _mutants():
        try:
            rows.append(run_one(label, mod, attr, mutant, sample, expect_after))
        except Exception as e:                          # noqa: BLE001
            rows.append(dict(label=label, ok=False, detail="执行出错：%s" % e))

    if "--json" in argv:
        print(json.dumps(rows, ensure_ascii=False, indent=1))
        return 0 if all(r["ok"] for r in rows) else 1

    print("变异测试：%d 道围栏" % len(rows))
    print()
    bad = 0
    for r in rows:
        flag = "敏感" if r["ok"] else "**假测试**"
        if not r["ok"]:
            bad += 1
        print("  [%-6s] %-34s %s" % (flag, r["label"], r["detail"]))
    print()
    print("假测试：%d / %d" % (bad, len(rows)))
    if bad == 0:
        print("含义：把任一道围栏改坏，对应的接受测试都会报错 —— "
              "这些测试确实在测围栏，不是在测自己抄的副本。")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
