# -*- coding: utf-8 -*-
"""restatement 板 · 自检：本板交付物是否满足 AGENTS.md 的判定/证据规矩。

只读 out/红队七板/restatement-scope-auditor.json 与被引用的被审文件。
判据（照抄 AGENTS.md）：
  · 每条探针 verdict ∈ {pass, finding}
  · 每条 pass 的 tried 长度 >= 30
  · 每条 finding 有 where（相对插件根的文件） + evidence（该文件里逐字存在、>= 3 字符）
  · 有 finding 必须有 resolved
"""
from __future__ import annotations

import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORT = os.path.join(ROOT, "out", "红队七板", "restatement-scope-auditor.json")


def rd(p):
    with io.open(p, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def main():
    rep = json.loads(rd(REPORT))
    bad = 0
    print("section=%s role=%s verdict=%s"
          % (rep.get("section"), rep.get("role"), rep.get("verdict")))
    probes = rep.get("probes") or []
    print("探针数 %d" % len(probes))
    if len(probes) != 4:
        print("  !! 探针数应为 4")
        bad += 1

    for i, p in enumerate(probes, 1):
        v = p.get("verdict")
        tried = p.get("tried") or ""
        where = p.get("where") or ""
        ev = p.get("evidence") or ""
        print("\n[%d] verdict=%s  probe=%s" % (i, v, (p.get("probe") or "")[:44]))
        if v not in ("pass", "finding"):
            print("   !! verdict 非法")
            bad += 1
        if v == "pass" and len(tried) < 30:
            print("   !! pass 但 tried 只有 %d 字" % len(tried))
            bad += 1
        if v == "finding":
            fp = os.path.join(ROOT, where)
            if not where or not os.path.isfile(fp):
                print("   !! where 不存在: %r" % where)
                bad += 1
            else:
                txt = rd(fp)
                hit = ev in txt
                print("   where=%s 存在=%s  evidence=%r 长度=%d  逐字命中=%s"
                      % (where, True, ev, len(ev), hit))
                if len(ev) < 3 or not hit:
                    print("   !! evidence 不合格")
                    bad += 1
        print("   tried 字数=%d" % len(tried))

    res = rep.get("resolved") or ""
    print("\nresolved 字数=%d" % len(res))
    if any(p.get("verdict") == "finding" for p in probes) and not res.strip():
        print("   !! 有 finding 但 resolved 为空")
        bad += 1

    print("\n结论：%s（不合格项 %d）" % ("OK" if bad == 0 else "有问题", bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
