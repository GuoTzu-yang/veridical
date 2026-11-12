#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
19 道题的证据可得性普查（全部为本地实测数据）

回答一个问题：**这套环境里，到底有几道题具备开工条件？**

判据（与 model1 架构一致，不另立标准）：
  验收可得  —— bench/case_<编号>.sql 是否存在（task 卡自检第 1 条硬要求）
  解析可得  —— docs/*.md 是否提到该编号
  原文可得  —— issues_detail.json 里 body 是否完整（>2000 字符）
  线索可得  —— 标题里是否出现源码树中可定位的路径关键词

跑法：python survey_19.py
"""

from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
COMP = os.path.join(os.path.dirname(os.path.dirname(ROOT)), "seekdb-2026-competition")


def load_json(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def main() -> int:
    tasks_dir = os.path.join(COMP, "tasks")
    files = sorted(f for f in os.listdir(tasks_dir) if f.startswith("issue-") and f.endswith(".md"))
    nums = [int(re.search(r"issue-(\d+)", f).group(1)) for f in files]

    detail = {x["number"]: x for x in load_json(os.path.join(COMP, "data", "issues_detail.json"))}
    tree = load_json(os.path.join(COMP, "data", "tree_2026competition.json"))
    tree_blob = "\n".join(tree).lower()

    docs_text = ""
    docs_dir = os.path.join(COMP, "docs")
    for f in os.listdir(docs_dir):
        if f.endswith(".md"):
            docs_text += open(os.path.join(docs_dir, f), encoding="utf-8", errors="replace").read()

    # 提测记录：bench/records.csv 里该编号是否填过数据
    rec_text = open(os.path.join(COMP, "bench", "records.csv"), encoding="utf-8-sig",
                    errors="replace").read()
    recorded = set()
    for ln in rec_text.splitlines()[1:]:
        parts = ln.split(",")
        if parts and parts[0].strip() and any(p.strip() for p in parts[1:]):
            recorded.add(int(parts[0]))

    bench_files = set(os.listdir(os.path.join(COMP, "bench")))

    def has_section(n: int) -> bool:
        """独立解析章节：行首标题里带该编号（排除正文里的『和 #1440 同源』这类引用）。"""
        return bool(re.search(rf"^#{{2,3}}\s+.*?#{n}\b", docs_text, re.M))

    rows = []
    for n, f in zip(nums, files):
        d = detail.get(n, {})
        body = d.get("body") or ""
        title = d.get("title") or ""
        has_case = f"case_{n}.sql" in bench_files
        in_docs = has_section(n)
        body_ok = len(body) > 2000
        # 标题里的英文词能否在源码树里找到对应路径
        words = re.findall(r"[A-Za-z][a-z]{4,}", title)
        clue = [w for w in words if w.lower() in tree_blob][:3]
        rows.append({
            "n": n, "title": title[:44], "body": len(body),
            "comments": d.get("comments", 0),
            "case": has_case, "docs": in_docs,
            "record": n in recorded, "clue": clue,
        })

    print("=" * 108)
    print(f"{'编号':<7}{'body':>6}{'评论':>5}  {'验收':<5}{'提测':<5}{'解析':<5}{'线索':<20}标题")
    print("=" * 108)
    for r in rows:
        print(f"{r['n']:<7}{r['body']:>6}{r['comments']:>5}  "
              f"{'有' if r['case'] else '缺':<5}{'有' if r['record'] else '缺':<5}"
              f"{'有' if r['docs'] else '缺':<5}"
              f"{(','.join(r['clue']) if r['clue'] else '无'):<20}{r['title']}")
    print("=" * 108)

    n = len(rows)
    has_case = sum(1 for r in rows if r["case"])
    has_docs = sum(1 for r in rows if r["docs"])
    has_clue = sum(1 for r in rows if r["clue"])
    has_rec = sum(1 for r in rows if r["record"])
    full = sum(1 for r in rows if r["case"] and r["docs"] and r["clue"])

    print(f"\n总数 {n}")
    print(f"  验收用例可得   {has_case}/{n}")
    print(f"  提测记录已填   {has_rec}/{n}")
    print(f"  独立解析章节   {has_docs}/{n}")
    print(f"  可定位线索     {has_clue}/{n}")
    print(f"  三项齐全       {full}/{n}")

    print("\n判定（按 model1 的闸门口径）：")
    print(f"  能直接开工并验收的: {full} 道")
    print(f"  只能静态分析的:     {has_docs - has_case if has_docs > has_case else 0} 道"
          f"（有解析无验收手段）")
    print(f"  连解析都没有的:     {n - has_docs} 道")

    out = {"n": n, "has_case": has_case, "has_rec": has_rec, "has_docs": has_docs,
           "has_clue": has_clue, "full": full, "rows": rows}
    p = os.path.join(ROOT, "_survey_19.json")
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)
    print(f"\n结果已落盘: {os.path.basename(p)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
