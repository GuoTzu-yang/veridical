#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
评估判据本身：它到底能不能区分成败

前面三十轮一直在造框架、攒样本，但从没算过一件事：

    **判 pass 的任务，真有那么高成功率吗？**
    **判 reject 的，真都失败了吗？**
    **判 degrade 的，是不是等于没判？**

账本里现在有 44 条 v2 样本，够算这些了。

三个指标：
  精确率   判 pass 里真成功的比例 / 判 reject 里真失败的比例
  覆盖率   被判 pass 或 reject（= 给出了确定结论）的比例
  单调性   pass > degrade > reject 是否成立

跑法：python evaluate_model.py [版本号]
"""

from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)          # 架构本体所在目录
sys.path.insert(0, ROOT)

import ledger as L  # noqa: E402
from harness import MODEL_VERSION  # noqa: E402


def main() -> int:
    ver = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else None

    print("=" * 82)
    print("判据自评 · 它能不能区分成败")
    print("=" * 82)

    for lvl in (2, 3, None):
        tag = f"L{lvl}" if lvl is not None else "全部环境"
        # 自然池：剔除阴性对照组。对外的精确率必须以这个为准——
        # 对照组是故意构造的，混进来会把 pass 精确率从 89% 拉到 78%。
        s = L.stats(lvl, ver if ver is not None else MODEL_VERSION,
                    exclude_control=True)
        if s["total"] == 0:
            print(f"\n{tag}：无样本")
            continue

        rows = [
            e for e in L.entries()
            if e.get("success") is not None
            and (lvl is None or e.get("env_level") == lvl)
            and e.get("version") == (ver if ver is not None else MODEL_VERSION)
            and e.get("group") not in L.CONTROL_GROUPS
        ]
        if not rows:
            print(f"\n{tag}：无已结算样本")
            continue

        n = len(rows)
        print(f"\n{tag}  v{ver if ver is not None else MODEL_VERSION}   样本 {n} 条")
        print("  " + "-" * 74)

        # 混淆矩阵
        mat: dict[str, dict[str, int]] = {}
        for e in rows:
            v = e["verdict"]
            if v == "degrade":
                v = f"degrade/{e.get('cause') or '?'}"
            ok = "成功" if e["success"] else "失败"
            mat.setdefault(v, {"成功": 0, "失败": 0})[ok] += 1

        print(f"  {'判定':<16}{'成功':>6}{'失败':>6}{'合计':>6}{'成功率':>9}")
        for v in sorted(mat):
            c = mat[v]
            tot = c["成功"] + c["失败"]
            rate = c["成功"] / tot if tot else 0
            print(f"  {v:<16}{c['成功']:>6}{c['失败']:>6}{tot:>6}{rate:>9.1%}")

        # 精确率
        print()
        pass_ok = mat.get("pass", {"成功": 0, "失败": 0})
        rej = {k: 0 for k in ("成功", "失败")}
        for v, c in mat.items():
            if v.startswith("reject"):
                for k in rej:
                    rej[k] += c[k]
        deg = {"成功": 0, "失败": 0}
        for v, c in mat.items():
            if v.startswith("degrade"):
                for k in deg:
                    deg[k] += c[k]

        p_tot = pass_ok["成功"] + pass_ok["失败"]
        r_tot = rej["成功"] + rej["失败"]
        d_tot = deg["成功"] + deg["失败"]

        if p_tot:
            print(f"  pass 精确率   {pass_ok['成功']}/{p_tot} = "
                  f"{pass_ok['成功']/p_tot:.1%}  （判 pass 里真成功的比例）")
        if r_tot:
            print(f"  reject 精确率  {rej['失败']}/{r_tot} = "
                  f"{rej['失败']/r_tot:.1%}  （判 reject 里真失败的比例）")
        if d_tot:
            print(f"  degrade 成功率 {deg['成功']}/{d_tot} = "
                  f"{deg['成功']/d_tot:.1%}  （中间档，越接近 50% 越说明它没信息）")

        # 覆盖率
        decided = p_tot + r_tot
        print(f"\n  覆盖率        {decided}/{n} = {decided/n:.1%}  "
              f"（给出确定结论的比例，其余是 degrade）")

        # 结论复查：degrade 的正确度量
        cc = s.get("conclusion_check", {})
        checked = [(k, b) for k, b in sorted(cc.items())
                   if b["verified"] + b["overturned"] > 0]
        if checked:
            print(f"\n  结论复查（第三十二轮起记，只对做过复查的样本算）")
            for k, b in checked:
                ck = b["verified"] + b["overturned"]
                rate = b["overturned"] / ck if ck else 0
                print(f"    {k:16s} 复查 {ck}/{b['n']}  成立 {b['verified']}  "
                      f"推翻 {b['overturned']}  推翻率 {rate:.0%}")

        # 单调性
        seq = []
        if p_tot:
            seq.append(("pass", pass_ok["成功"] / p_tot))
        if d_tot:
            seq.append(("degrade", deg["成功"] / d_tot))
        if r_tot:
            seq.append(("reject", rej["成功"] / r_tot))
        mono = all(seq[i][1] >= seq[i + 1][1] for i in range(len(seq) - 1))
        print(f"  单调性        {'✓ 成立' if mono else '✗ 不成立'}   "
              + " ≥ ".join(f"{k} {v:.1%}" for k, v in seq))

    print()
    print("=" * 82)
    print("实验分组对照（阴性对照）")
    print("=" * 82)
    print("  group=a 普通优化任务，判 degrade")
    print("  group=b SARGable 任务，判 degrade")
    print("  group=c **和 b 完全同一批任务**，只把 e1/e3 调高 → 判 pass")
    print("  group=d **还是同一批任务**，再加「机制适用性」这一维")
    print()
    for g, desc in (("a", "普通优化 / degrade"), ("b", "SARGable / degrade"),
                    ("c", "SARGable / pass（对照）"),
                    ("d", "SARGable / +机制适用性")):
        s = L.stats(3, ver if ver is not None else MODEL_VERSION, g)
        cc = s.get("conclusion_check", {})
        for k, b in sorted(cc.items()):
            ck = b["verified"] + b["overturned"]
            if not ck:
                continue
            rate = b["overturned"] / ck
            print(f"  {g}  {desc:26s} 复查 {ck}  推翻 {b['overturned']}  "
                  f"推翻率 {rate:.0%}")
    print()
    print("  读法：")
    print("    a vs b  两组都判 degrade，推翻率却差很多 → 判据没抓住真正决定成败的属性")
    print("    b vs c  同一批任务两种判法，推翻率相同     → 标签不改变现实，")
    print("                                                e1/e3 在这批任务上没有判别力")
    print("    c vs d  加上「机制适用性」后，被推翻的结论全部被判 reject，")
    print("            成立的结论全部仍判 pass → 这一维补上了真东西")
    print()
    print("怎么读这些数：")
    print("  pass 精确率低 → 判据太乐观，会把做不成的说成做得成")
    print("  reject 精确率低 → 判据太悲观，会误杀能成的任务")
    print("  degrade 成功率接近 50% → 这一档等于没判，只是把不确定推给下游")
    print("  覆盖率低 → 大部分任务都落在 degrade，判据没帮上忙")
    print()
    print("  结论推翻率高 → degrade 的「带保留」标注是必要的，")
    print("                  判 degrade 的任务里，结论真的会被推翻")
    print("  结论推翻率低 → 这一档要么太保守，要么造的样本太容易")
    print("=" * 82)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
