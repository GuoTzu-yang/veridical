# -*- coding: utf-8 -*-
"""notation-auditor selfcheck: validate the delivered board artifacts.

Same checks the gate performs (so a local pass is meaningful):
  1. json parses; section/role exact; 4 probes
  2. every pass has tried with len >= 30
  3. every finding's evidence is a verbatim substring of the `where` file
  4. every finding has resolved text, and resolved contains 「未处理」 when the
     finding is still open
  5. mirrors: md exists and mentions each probe verdict
Read-only; prints PASS/FAIL per item and exits non-zero on any FAIL.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out" / "红队七板"
J = OUT / "notation-notation-auditor.json"
M = OUT / "notation-notation-auditor.md"
PROBES = [
    "每个符号是否只指一个对象（有无一词多义）",
    "有没有符号在正文使用前未定义",
    "符号表与正文是否一致（抽查 10 个）",
    "单位/量纲是否随符号一起写",
]

fails = []


def chk(ok, label, extra=""):
    print(("PASS  " if ok else "FAIL  ") + label + (("  :: " + extra) if extra else ""))
    if not ok:
        fails.append(label)


d = json.loads(J.read_text(encoding="utf-8"))
chk(d.get("section") == "notation", "section == notation", repr(d.get("section")))
chk(d.get("role") == "notation-auditor", "role == notation-auditor", repr(d.get("role")))
chk(d.get("verdict") in ("pass", "revise"), "verdict in {pass,revise}", repr(d.get("verdict")))
ps = d.get("probes") or []
chk(len(ps) == 4, "4 probes", str(len(ps)))
chk([p.get("probe") for p in ps] == PROBES, "probe texts match the board's four probes verbatim")

for i, p in enumerate(ps, 1):
    v = p.get("verdict")
    chk(v in ("pass", "finding"), f"P{i} verdict in {{pass,finding}}", repr(v))
    if v == "pass":
        t = p.get("tried") or ""
        chk(len(t) >= 30, f"P{i} pass.tried len>=30", str(len(t)))
        chk(bool(t.strip()), f"P{i} pass.tried non-empty")
    else:
        where = p.get("where") or ""
        ev = p.get("evidence") or ""
        chk(bool(where) and bool(ev), f"P{i} finding has where+evidence")
        chk(len(ev) >= 3, f"P{i} evidence len>=3", str(len(ev)))
        fp = ROOT / where
        chk(fp.exists(), f"P{i} where exists", where)
        if fp.exists():
            body = fp.read_text(encoding="utf-8")
            chk(ev in body, f"P{i} evidence verbatim in {where}", ev)

res = d.get("resolved") or ""
chk(bool(res.strip()), "resolved non-empty")
n_find = sum(1 for p in ps if p.get("verdict") == "finding")
if n_find:
    chk("未处理" in res or "已处理" in res, "resolved states handling status")

md = M.read_text(encoding="utf-8") if M.exists() else ""
chk(M.exists() and len(md) > 800, "md exists and is substantive", str(len(md)))
for i, p in enumerate(ps, 1):
    chk(p["verdict"] in md, f"md mentions P{i} verdict '{p['verdict']}'")

print("\n%d finding(s); %d check(s) failed" % (n_find, len(fails)))
sys.exit(1 if fails else 0)
