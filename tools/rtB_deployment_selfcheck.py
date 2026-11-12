# -*- coding: utf-8 -*-
"""rtB deployment board - self check: does my own record satisfy the gate rules?

Read-only. Validates the JSON I am about to leave behind:
  - verdict in {pass, finding}
  - pass  -> tried >= 30 chars
  - finding -> where is a real file and evidence occurs verbatim in it
  - findings -> resolved non-empty
"""
import io
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REC = os.path.join(ROOT, "out", "红队七板", "deployment-operations-auditor.json")
MD = os.path.join(ROOT, "out", "红队七板", "deployment-operations-auditor.md")


def main():
    rec = json.load(io.open(REC, encoding="utf-8"))
    print("section=%s role=%s verdict=%s" % (rec["section"], rec["role"], rec["verdict"]))
    ok = True
    for i, p in enumerate(rec["probes"], start=1):
        v = p["verdict"]
        tried_len = len(p.get("tried", ""))
        line = "probe %d verdict=%-7s tried_len=%d" % (i, v, tried_len)
        if v == "pass" and tried_len < 30:
            line += "  <-- INVALID pass without tried"
            ok = False
        if v == "finding":
            where = p.get("where", "")
            ev = p.get("evidence", "")
            target = os.path.join(ROOT, where)
            exists = os.path.exists(target)
            if exists:
                body = io.open(target, encoding="utf-8", errors="replace").read()
                hit = ev in body
            else:
                hit = False
            line += "  where=%s exists=%s evidence_verbatim=%s" % (where, exists, hit)
            if not (exists and hit and len(ev) >= 3):
                line += "  <-- INVALID finding evidence"
                ok = False
        print(line)
    print("resolved set: %s (len=%d)" % (bool(rec.get("resolved")), len(rec.get("resolved", ""))))
    print("md exists: %s bytes=%d" % (os.path.exists(MD), os.path.getsize(MD) if os.path.exists(MD) else -1))
    md = io.open(MD, encoding="utf-8").read()
    for h in ("## 1. 运行方式表", "## 2. 时间预算表", "## 3. 处置表"):
        print("  md has %-16s %s" % (h, h in md))
    print("\nJSON valid, all rules satisfied:", ok)


if __name__ == "__main__":
    main()
