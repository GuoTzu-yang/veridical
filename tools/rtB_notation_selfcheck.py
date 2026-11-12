# -*- coding: utf-8 -*-
"""rtB_notation_selfcheck.py -- validate my own JSON against the stated gate rules.

Rules enforced:
  R1  top-level section == 'notation', role == 'notation-auditor'
  R2  exactly one probe entry per required probe text (4)
  R3  every probe verdict in {pass, finding}
  R4  every pass has tried with len >= 30
  R5  every finding has where + evidence, evidence len >= 3, and the marker is
      literally present in that file (gate greps it)
  R6  if any finding -> resolved non-empty
  R7  verdict in {pass, revise}; and it must be 'revise' if any finding exists
  R8  role not used by another board report in out/红队七板/
  R9  no stray/empty keys on the pass entry
Exit 0 only if all pass.
"""
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MINE = os.path.join(ROOT, "out", "红队七板", "notation-notation-auditor.json")

REQUIRED = [
    "每个符号是否只指一个对象（有无一词多义）",
    "有没有符号在正文使用前未定义",
    "符号表与正文是否一致（抽查 10 个）",
    "单位/量纲是否随符号一起写",
]

fails = []
oks = []


def ok(msg):
    oks.append(msg)
    print("  OK    %s" % msg)


def bad(msg):
    fails.append(msg)
    print("  FAIL  %s" % msg)


print("=" * 78)
print("SELF-CHECK of", MINE)
print("=" * 78)

if not os.path.exists(MINE):
    print("  FAIL  file missing")
    sys.exit(1)

d = json.load(io.open(MINE, encoding="utf-8"))

# R1
("OK" if d.get("section") == "notation" else None) or bad("section != notation")
if d.get("section") == "notation":
    ok("section == notation")
if d.get("role") == "notation-auditor":
    ok("role == notation-auditor")
else:
    bad("role mismatch: %r" % d.get("role"))

# R2
probes = d.get("probes") or []
got = [p.get("probe") for p in probes]
if len(probes) != 4:
    bad("probe count %d != 4" % len(probes))
else:
    ok("4 probes present")
for r in REQUIRED:
    if r in got:
        ok("required probe present: %s" % r[:24])
    else:
        bad("required probe MISSING: %s" % r)

# R3-R6
n_pass = n_find = 0
for p in probes:
    v = p.get("verdict")
    tag = (p.get("probe") or "?")[:26]
    if v not in ("pass", "finding"):
        bad("%s: verdict %r not in {pass,finding}" % (tag, v))
        continue
    if v == "pass":
        n_pass += 1
        t = p.get("tried") or ""
        if len(t) >= 30:
            ok("%s: pass, tried len=%d >= 30" % (tag, len(t)))
        else:
            bad("%s: pass but tried len=%d < 30 (INVALID PASS)" % (tag, len(t)))
        for k in ("where", "evidence", "tried_note"):
            if k in p:
                bad("%s: pass carries stray key %r" % (tag, k))
    else:
        n_find += 1
        where = p.get("where") or ""
        ev = p.get("evidence") or ""
        if not where:
            bad("%s: finding without where" % tag)
        if len(ev) < 3:
            bad("%s: finding evidence len=%d < 3" % (tag, len(ev)))
        if where and ev:
            fp = os.path.join(ROOT, where.replace("/", os.sep))
            if not os.path.exists(fp):
                bad("%s: where file missing: %s" % (tag, where))
            else:
                txt = io.open(fp, encoding="utf-8").read()
                if ev in txt:
                    ok("%s: finding evidence greps FOUND in %s" % (tag, where))
                else:
                    bad("%s: evidence NOT FOUND in %s: %r" % (tag, where, ev))
        if len(p.get("note") or "") < 20:
            bad("%s: finding note too thin" % tag)

# R6
res = d.get("resolved") or ""
if n_find and not res.strip():
    bad("findings exist but resolved empty")
elif n_find:
    ok("resolved non-empty (%d chars)" % len(res))

# R7
v = d.get("verdict")
if v not in ("pass", "revise"):
    bad("verdict %r invalid" % v)
elif n_find and v != "revise":
    bad("findings exist but verdict=%r (must be revise)" % v)
else:
    ok("verdict == %s (consistent: %d finding)" % (v, n_find))

# R8
others = []
bdir = os.path.join(ROOT, "out", "红队七板")
for fn in os.listdir(bdir):
    if not fn.endswith(".json") or fn == os.path.basename(MINE):
        continue
    try:
        od = json.load(io.open(os.path.join(bdir, fn), encoding="utf-8"))
    except Exception:
        continue
    others.append((fn, od.get("role")))
clash = [o for o in others if o[1] == d.get("role")]
if clash:
    bad("role reused by %s" % clash)
else:
    ok("role not reused (other board reports: %s)" % (others or "none"))

print("\n" + "=" * 78)
print("RESULT: %d ok, %d fail  (pass=%d finding=%d)" % (len(oks), len(fails), n_pass, n_find))
for f in fails:
    print("   !", f)
print("=" * 78)
sys.exit(0 if not fails else 1)
