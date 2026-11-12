#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""rt7_ops_outmap.py —— 第六板（deployment / operations-auditor）只读取证。

回答两件事：
1) runs.json 里每道题的 out 落在哪里；跑 battle.py 时**它自己的判据**
   （battle._outside_template_root）会放行还是跳过。
2) 被跳过的题，目录里有没有「只有人手才有」的产物，以及有没有快照可恢复。

只读：不写任何产物，不改源码。唯一副作用是 import battle（无 __main__ 执行）。

用法：python tools/rt7_ops_outmap.py
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "tools"))

import battle as B  # noqa: E402  只 import，不调用 main()

RUNS = os.path.join(HERE, "runs.json")
BACKUP = os.path.join(HERE, "out", "runs_backup_r4")

# 「只有人手才有」的标记：出现在事故记录里，模板 mmkit run 不会写这些
HAND_MARKS = ["evidence.json", "model_stats.json", "paper.before_style.tex"]


def has_hand_marks(d):
    return [m for m in HAND_MARKS if os.path.exists(os.path.join(d, m))]


def main():
    cfg = json.load(io.open(RUNS, encoding="utf-8"))
    rows = []
    for name, c in cfg.items():
        out_rel = c.get("out", "")
        d = os.path.join(HERE, out_rel)
        abserr = B._outside_template_root(d)
        exists = os.path.isdir(d)
        rows.append(dict(
            name=name,
            out=out_rel,
            exists=exists,
            inside=out_rel.replace("\\", "/").startswith("out/runs/"),
            skip=bool(abserr),
            why=abserr,
            hand=has_hand_marks(d) if exists else [],
            backup=os.path.isdir(os.path.join(BACKUP, name)),
            deliverable_flag=(json.load(io.open(os.path.join(d, "declaration.json"),
                                                encoding="utf-8")).get("deliverable")
                              if os.path.exists(os.path.join(d, "declaration.json"))
                              else "no-file"),
        ))

    n = len(rows)
    out_side = [r for r in rows if not r["inside"]]
    skipped = [r for r in rows if r["skip"]]
    print("runs.json 题数：%d" % n)
    print("out 落在 out/runs/ 内：%d" % (n - len(out_side)))
    print("out 落在 out/runs/ 之外：%d  → %s"
          % (len(out_side), ", ".join(r["name"] for r in out_side) or "无"))
    print("battle 判据会跳过：%d  → %s"
          % (len(skipped), ", ".join(r["name"] for r in skipped) or "无"))
    print()
    print("%-16s %-26s %-6s %-6s %-6s %s"
          % ("题", "out", "存在", "跳过", "快照", "人手标记 / declaration"))
    print("-" * 96)
    for r in rows:
        print("%-16s %-26s %-6s %-6s %-6s %s%s"
              % (r["name"], r["out"], "Y" if r["exists"] else "N",
                 "**Y**" if r["skip"] else ".", "Y" if r["backup"] else ".",
                 ",".join(r["hand"]) or "(无)",
                 "  decl=%s" % r["deliverable_flag"]))
    print()
    print("快照覆盖率（out/runs_backup_r4 下有同名目录的题）：%d/%d"
          % (sum(1 for r in rows if r["backup"]), n))

    out_json = os.path.join(HERE, "out", "rt7_ops_outmap.json")
    with io.open(out_json, "w", encoding="utf-8", newline="\n") as f:
        json.dump(dict(n=n, rows=rows), f, ensure_ascii=False, indent=1)
    print("已写 %s" % os.path.relpath(out_json, HERE))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
