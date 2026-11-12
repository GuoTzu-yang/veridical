# -*- coding: utf-8 -*-
"""conclusion 板只读探针 4：与作者既有记录（out/final/redteam.json）的交叉核对。
只读，只打印。"""
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAPER = os.path.join(ROOT, "out", "final", "paper.tex")
RT = os.path.join(ROOT, "out", "final", "redteam.json")


def main():
    with io.open(PAPER, "r", encoding="utf-8", errors="replace") as fh:
        lines = fh.read().splitlines()
    with io.open(RT, "r", encoding="utf-8") as fh:
        rt = json.load(fh)

    secs = [i + 1 for i, ln in enumerate(lines) if ln.lstrip().startswith(r"\section{")]
    print("=== 0. 论文 \\section 数（= 应有审核板数）===")
    print("  n_sections = %d  at lines %s" % (len(secs), secs))
    names = [lines[i - 1].strip() for i in secs]
    for k, nm in enumerate(names, 1):
        print("   %2d %s" % (k, nm))

    print("")
    print("=== 1. redteam.json 已审 section 清单 ===")
    reviewed = [r.get("section") for r in rt.get("reviews", [])]
    print("  reviewed = %s" % reviewed)
    print("  n_reviewed = %d / n_sections = %d" % (len(reviewed), len(secs)))
    print("  conclusion in reviewed ? %s" % ("conclusion" in reviewed))
    missing = [n for n in ["restatement", "analysis", "assumptions", "notation",
                           "method_argument", "validation", "results",
                           "self_correction", "deployment", "evaluation",
                           "conclusion", "claims"] if n not in reviewed]
    print("  (参考) 未以这些名出现的板: %s" % missing)

    print("")
    print("=== 2. 与 section=='claims' 记录的逐探针对比（本板内含 §claims 表）===")
    for r in rt.get("reviews", []):
        if r.get("section") != "claims":
            continue
        print("  role=%s verdict=%s" % (r.get("role"), r.get("verdict")))
        for p in r.get("probes", []):
            print("   - [%s] %s" % (p.get("verdict"), p.get("probe")))
            print("       note: %s" % p.get("note"))
            if p.get("tried"):
                print("       tried: %s" % p.get("tried"))
        print("  resolved: %s" % r.get("resolved"))

    print("")
    print("=== 3. 核对 claims 板 pass 依据里那句「局限一节」是否真的存在 ===")
    for w in ["Limitations", "limitation", "one author", "one corpus",
              "one log", "log 口径", "局限"]:
        rows = [i + 1 for i, ln in enumerate(lines) if w in ln]
        print("  %-14s -> %s" % (w, rows[:10] if rows else "NONE"))
    print("  -- 是否有独立 Limitations 节 --")
    has_lim = any(ln.lstrip().startswith(r"\section{Limitation") for ln in lines)
    print("  \\section{Limitation...} exists = %s" % has_lim)

    print("")
    print("=== 4. 'one author' / 'one corpus' 所在行原文 ===")
    for i, ln in enumerate(lines):
        low = ln.lower()
        if "one author" in low or "one corpus" in low or "one project" in low:
            print("%5d| %s" % (i + 1, ln.strip()))

    print("")
    print("=== 5. 结论表第三列（Not supported）每条的正文出处 ===")
    for i in range(1148, 1200):
        if i >= len(lines):
            break
        if r"&" in lines[i] or "unsupported" in lines[i].lower():
            print("%5d| %s" % (i + 1, lines[i].strip()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
