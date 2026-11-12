#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""audit_findings.py —— 把 40 条 finding 逐条摊开，并机械核对它们的证据。

红队写的 finding 也会误判（第 122 轮就出现过一次：它说「1e6 上限让最可疑的
数免检」，实测那些数经 ×100 分支能正确匹配）。所以 finding 进账本之前，
先做三件事：

  1. 证据存在性：`evidence` 在 `where` 文件里逐字存在吗？（gate 已经查这一条）
  2. 证据相关性：那个标记**真的支撑**这条主张吗？—— 机械做不了全部，
     但可以做「标记出现次数」与「标记所在行」的定位，供人判。
  3. 可修性：这条 finding 指向的是「论文写错」「论文没写」还是
     「外部条件不具备」（如没有题面原文），修法完全不同。

用法：
    python tools/audit_findings.py            # 全部
    python tools/audit_findings.py --json     # 结构化
    python tools/audit_findings.py --only results
"""
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

FINAL = os.path.join(HERE, "out", "final")


def locate(path, needle):
    """在文件里找 needle，返回 [(行号, 该行前 100 字)]。"""
    p = os.path.join(HERE, path)
    if not os.path.exists(p):
        return None, []
    try:
        lines = io.open(p, encoding="utf-8", errors="replace").read().splitlines()
    except Exception:                                   # noqa: BLE001
        return None, []
    hit = [(i + 1, ln.strip()[:100])
           for i, ln in enumerate(lines) if needle in ln]
    return len(lines), hit


def main(argv):
    j = json.load(io.open(os.path.join(FINAL, "redteam.json"), encoding="utf-8"))
    only = ""
    if "--only" in argv:
        only = argv[argv.index("--only") + 1]
    rows = []
    for r in j["reviews"]:
        sec = r["section"]
        if only and sec != only:
            continue
        for p in r.get("probes") or []:
            if p.get("verdict") != "finding":
                continue
            w = str(p.get("where") or "")
            ev = str(p.get("evidence") or "")
            nlines, hit = locate(w, ev) if w and ev else (None, [])
            rows.append(dict(
                section=sec, role=r["role"],
                probe=str(p.get("probe") or "")[:40],
                where=w, evidence=ev,
                file_exists=nlines is not None,
                n_hits=len(hit),
                hits=hit[:3],
                note=str(p.get("note") or ""),
                resolved=str(r.get("resolved") or ""),
            ))
    if "--json" in argv:
        print(json.dumps(rows, ensure_ascii=False, indent=1))
        return 0

    print("finding 总数：%d" % len(rows))
    bad = [x for x in rows if not x["file_exists"] or x["n_hits"] == 0]
    print("证据落空：%d 条" % len(bad))
    print()
    for i, x in enumerate(rows, 1):
        flag = "OK " if x["file_exists"] and x["n_hits"] else "**证据落空**"
        print("─" * 78)
        print("%2d. [%-16s] %s" % (i, x["section"], flag))
        print("    主张：%s" % x["note"][:150])
        print("    证据：%s  ← %s（命中 %d 处）"
              % (x["evidence"][:40], x["where"], x["n_hits"]))
        for ln, txt in x["hits"]:
            print("          L%-5d %s" % (ln, txt[:90]))
        print("    处置：%s" % (x["resolved"][:100] or "(空)"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
