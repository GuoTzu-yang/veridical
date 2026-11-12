#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""triage_findings.py —— 把 40 条 finding 按处置状态摊开，并给出分类建议。

红队 finding 有三种命运，混在一起会让「32 条未处理」变成一句空话：

  fixed   正文/代码已改（`resolved` 写清改了哪里）
  blocked 外部条件不具备（缺数据集/缺题面原文/缺第二个编码者…），
          必须写 `blocked_reason`，且理由要能被复核
  open    可真修但没修

本工具对 open 的逐条打「修法候选」标签，**只是候选**，最终由人判：
  number       数字/计数与工件不一致（机械可核，改一个数）
  citation     引用/标签缺失或悬空（机械可核）
  wording      措辞强度超出证据（改一句话，风险中）
  missing      论文没写该有的东西（补一节/一段，风险高）
  external     外部条件不具备（题面原文/第二编码者/多作者语料）
  structural   需要改架构（如口径统一、消融重做）

用法：
    python tools/triage_findings.py
    python tools/triage_findings.py --json
"""
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import redteam                                   # noqa: E402

FINAL = os.path.join(HERE, "out", "final")

# 只在「note 里出现这些词」时才给的强候选。按可信度排序，先命中先用。
HINTS = (
    ("external", ("不存在外部", "找不到外部", "全仓找不到", "没有题面",
                  "外部题面", "缺数据集", "没有数据集", "第二编码者",
                  "未获批", "无法获取", "不适用（外部）")),
    ("number", ("对不上", "不一致", "与工件", "同源", "写 7", "写 8",
                "29", "30", "6.68", "five seconds", "两个总数",
                "与 data.json", "与冻结表", "计数")),
    ("citation", ("\\cite", "\\ref", "引用", "标签", "悬空", "未被引用")),
    ("wording", ("超出证据", "过度", "全称", "强度", "称", "proves",
                 "已证明", "no untraced", "at all")),
    ("structural", ("口径", "消融", "统一", "架构", "两套判据", "两处实现")),
    ("missing", ("没有写", "未写", "缺一", "缺失", "没交代", "没有交代",
                 "没有讨论", "没给")),
)


def classify(note):
    t = str(note)
    for tag, keys in HINTS:
        for k in keys:
            if k in t:
                return tag
    return "unclassified"


def main(argv):
    # 第 123 轮修：接受目录参数。原来写死 FINAL=out/final，
    # 于是 `triage_findings.py out/d2026c` 报的仍是 out/final 的 40 条/24 open，
    # 而 d2026c 实际是 30 条/全 open —— 与 redteam.roster 同一个坑（看错目录）。
    d = FINAL
    for a in argv[1:]:
        if not a.startswith("-"):
            d = a
            break
    j = json.load(io.open(os.path.join(d, "redteam.json"), encoding="utf-8"))
    rows = []
    for r in j["reviews"]:
        for p in r.get("probes") or []:
            if p.get("verdict") != "finding":
                continue
            # 第 123 轮：处置状态是 **finding 级**（见 redteam._finding_disp）。
            # 原来这里用 review 级的 _disposition(r)，于是「一条 review 里
            # 修好 1 条、另 3 条未修」会被整条报成同一个状态。
            disp = redteam._finding_disp(p, r)
            note = str(p.get("note") or "")
            rows.append(dict(
                section=r["section"], disp=disp,
                guess=classify(note) if disp == "open" else "",
                note=note[:150],
                where=str(p.get("where") or ""),
                evidence=str(p.get("evidence") or ""),
            ))
    if "--json" in argv:
        print(json.dumps(rows, ensure_ascii=False, indent=1))
        return 0

    from collections import Counter
    print("合计 %d 条" % len(rows))
    print("处置：", dict(Counter(x["disp"] for x in rows)))
    print("open 的修法候选：", dict(Counter(x["guess"] for x in rows
                                           if x["disp"] == "open")))
    print()
    for disp in ("open", "blocked", "fixed"):
        sub = [x for x in rows if x["disp"] == disp]
        if not sub:
            continue
        print("=" * 78)
        print("【%s】%d 条" % (disp, len(sub)))
        print("=" * 78)
        for i, x in enumerate(sub, 1):
            tag = ("[%s] " % x["guess"]) if x["guess"] else ""
            print("%2d. %-16s %s%s" % (i, x["section"], tag, x["note"][:110]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
