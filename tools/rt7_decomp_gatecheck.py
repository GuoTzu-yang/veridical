# -*- coding: utf-8 -*-
"""rt7_decomp_gatecheck.py —— 把本板的 json 塞进作者那份 redteam.json 的副本，
跑 redteam.check() 看四类硬条件是否真的过。

只读 out/final/redteam.json；只在临时目录里写副本。
"""
import io
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import redteam

MINE = os.path.join(HERE, "out", "红队七板", "analysis-decomposition.json")
SRC = os.path.join(HERE, "out", "final", "redteam.json")

mine = json.load(io.open(MINE, encoding="utf-8"))
base = json.load(io.open(SRC, encoding="utf-8"))

# 替换 analysis 那一项，其余六板保持作者原样
reviews = []
for r in base["reviews"]:
    if r.get("section") == "analysis":
        reviews.append(mine)
    else:
        reviews.append(r)
if not any(r.get("section") == "analysis" for r in reviews):
    reviews.insert(0, mine)

td = tempfile.mkdtemp(prefix="rt7_gate_")
json.dump(dict(reviews=reviews),
          io.open(os.path.join(td, "redteam.json"), "w", encoding="utf-8",
                  newline="\n"), ensure_ascii=False, indent=1)

res = redteam.check(td)
print("level  =", res["level"])
print("ok     =", res["ok"])
print("detail =", res["detail"])
print()
for s in redteam.SPEC:
    got = (res["per_section"].get(s) or [None])[0]
    if not got:
        continue
    vs = [p.get("verdict") for p in (got.get("probes") or [])]
    print("  %-16s %-26s %s" % (s, got.get("role"), vs))
print()
# 单独复验我的四项硬条件
problems = []
spec = redteam.SPEC["analysis"]
if mine.get("role") != spec["role"]:
    problems.append("role 不对")
if len(mine.get("probes") or []) < len(spec["probes"]):
    problems.append("探针数不足")
for i, p in enumerate(mine["probes"], 1):
    if p.get("verdict") == "pass" and len(str(p.get("tried") or "").strip()) < 30:
        problems.append("p%d pass 缺 tried" % i)
    if p.get("verdict") == "finding":
        w = str(p.get("where") or "").strip()
        ev = str(p.get("evidence") or "").strip()
        if not w or len(ev) < 3:
            problems.append("p%d finding 缺 where/evidence" % i)
        else:
            fp = os.path.join(HERE, w)
            body = io.open(fp, encoding="utf-8", errors="replace").read() if os.path.exists(fp) else ""
            if ev not in body:
                problems.append("p%d evidence 在 %s 里找不到" % (i, w))
if not str(mine.get("resolved") or "").strip():
    problems.append("有 finding 但 resolved 为空")
print("本板硬条件：", "全部通过" if not problems else problems)
shutil.rmtree(td, ignore_errors=True)
sys.exit(0 if not problems and res["level"] != "FAIL" else 1)
