# -*- coding: utf-8 -*-
"""restatement 板 · 只读探针 4：redteam.check 对 out/final 的当前判定。

只读 paper.tex + out/final/redteam.json（redteam.check 只读两处文件）。
不调用任何写盘路径。
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import redteam  # noqa: E402


def main():
    print("=" * 72)
    print("[A] redteam.py 解析出来的板块（唯一真相源 = paper.tex 的 \\section）")
    secs = redteam.paper_sections(os.path.join(ROOT, "out", "final", "paper.tex")) \
        if hasattr(redteam, "paper_sections") else None
    print("   paper_sections(): %s" % (secs,))

    print("\n[B] roster 前 12 条（index / section / role）")
    try:
        for row in (redteam.roster(os.path.join(ROOT, "out", "final")) or [])[:12]:
            print("   #%-2s %-24s role=%-26s need=%s probes=%s"
                  % (row.get("index"), row.get("section"), row.get("role"),
                     row.get("need"), row.get("n_probes")))
    except Exception as e:
        print("   roster 失败: %r" % (e,))

    print("\n[C] redteam.check('out/final') 当前判定")
    try:
        r = redteam.check(os.path.join(ROOT, "out", "final"))
        print("   ok=%s level=%s" % (r.get("ok"), r.get("level")))
        print("   detail=%s" % r.get("detail"))
        ps = r.get("per_section") or {}
        print("   per_section 键: %s" % list(ps))
        for k, v in ps.items():
            if "restat" in str(k).lower():
                print("   >>> %s -> %s" % (k, json.dumps(v, ensure_ascii=False)[:300]))
    except Exception as e:
        print("   check 失败: %r" % (e,))


if __name__ == "__main__":
    main()
