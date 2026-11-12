# -*- coding: utf-8 -*-
"""conclusion 板自检：校验交付 JSON 的规则（只读，只打印）。
规则：4 条探针；pass 必须有 >=30 字符 tried；finding 必须有 where+evidence，
且 evidence 在 where 指向的文件里逐字存在（>=3 字符）；有 finding 必须有 resolved。"""
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "out", "红队七板", "conclusion-conclusion-auditor.json")
MD = os.path.join(ROOT, "out", "红队七板", "conclusion-conclusion-auditor.md")


def main():
    ok = True
    print("=== 1. JSON 可解析 ===")
    try:
        with io.open(OUT, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        print("  OK  json.load succeeded")
    except Exception as exc:  # noqa: BLE001
        print("  FAIL  %s" % exc)
        return 1

    print("")
    print("=== 2. 顶层字段 ===")
    for k in ["section", "role", "probes", "resolved", "verdict"]:
        print("  %-10s present=%s -> %r"
              % (k, k in data, data.get(k) if k != "probes" else ("n=%d" % len(data.get(k, [])))))
    if data.get("section") != "conclusion":
        print("  FAIL section != conclusion"); ok = False
    if data.get("role") != "conclusion-auditor":
        print("  FAIL role != conclusion-auditor"); ok = False
    if data.get("verdict") not in ("pass", "revise"):
        print("  FAIL verdict invalid"); ok = False

    print("")
    print("=== 3. 逐探针校验 ===")
    n_finding = 0
    for k, p in enumerate(data.get("probes", []), 1):
        v = p.get("verdict")
        tried = p.get("tried") or ""
        where = p.get("where") or ""
        ev = p.get("evidence") or ""
        print("  P%d verdict=%s tried_len=%d" % (k, v, len(tried)))
        if v not in ("pass", "finding"):
            print("     FAIL verdict 非法"); ok = False
        if v == "pass":
            if len(tried) < 30:
                print("     FAIL pass 的 tried < 30 字符"); ok = False
            else:
                print("     OK   pass 的 tried 长度合格")
        if v == "finding":
            n_finding += 1
            if not where:
                print("     FAIL finding 缺 where"); ok = False
            elif not os.path.exists(os.path.join(ROOT, where)):
                print("     FAIL where 文件不存在: %s" % where); ok = False
            if len(ev) < 3:
                print("     FAIL evidence < 3 字符"); ok = False
            if where and ev:
                path = os.path.join(ROOT, where)
                if os.path.exists(path):
                    with io.open(path, "r", encoding="utf-8", errors="replace") as fh:
                        body = fh.read()
                    hits = body.count(ev)
                    print("     evidence=%r 命中 %d 次" % (ev, hits))
                    if hits == 0:
                        print("     FAIL evidence 不在文件里逐字存在"); ok = False
        # 题面原文（probe 字段）必须非空
        if not (p.get("probe") or "").strip():
            print("     FAIL probe 为空"); ok = False

    print("")
    print("=== 4. resolved / 交付形态 ===")
    print("  n_finding = %d" % n_finding)
    print("  resolved_len = %d" % len(data.get("resolved") or ""))
    if n_finding > 0 and not (data.get("resolved") or "").strip():
        print("  FAIL 有 finding 但 resolved 为空"); ok = False
    print("  md exists = %s" % os.path.exists(MD))

    print("")
    print("=== 5. 最终 ===")
    print("  VERDICT = %s" % ("pass" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
