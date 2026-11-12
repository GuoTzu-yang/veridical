"""rtB / results board: independently recompute the taxonomy + log size.

Read-only. Re-implements collect_paper_data.py's rules and compares
against out/final/data.json and against what paper.tex prints.
"""
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FINAL = os.path.join(ROOT, "out", "final")
os.chdir(ROOT)

LOG = "OPTIMIZATION-优化记录.md"
print("=== log file on disk ===")
print("  path:", LOG)
print("  exists:", os.path.exists(LOG))
raw = open(LOG, "rb").read()
print("  bytes on disk      :", len(raw))
print("  == data.json record_bytes ?", len(raw) == 132523, "(data.json says 132523)")
print("  as KiB (1024)      : %.1f" % (len(raw) / 1024))
print("  as kB  (1000)      : %.1f" % (len(raw) / 1000))
print("  paper prints       : 129 kB")

rec = io.open(LOG, encoding="utf-8").read()
parts = re.split(r"^# 优化记录（第 (\d+) 轮）", rec, flags=re.M)
rounds = [(parts[i], parts[i + 1]) for i in range(1, len(parts), 2)]
print("\n=== rounds ===")
print("  recomputed n_record_rounds:", len(rounds), "(data.json says 30)")
print("  round numbers:", [int(r[0]) for r in rounds])

CLASSES = {
    "vacuous-check": ("恒真", "恒为", "永不", "不可达", "从没被赋值",
                      "空判据", "摆设", "不能失败"),
    "silent-default": ("默认", "自动", "静默", "悄悄", "没人负责"),
    "duplicate-logic": ("两套", "分叉", "不一致", "同义", "漂移", "重复"),
    "self-report": ("自报", "样本量", "报成", "打印成", "数字不对"),
    "self-test-broken": ("崩溃", "IndexError", "自检不在", "不在回归链"),
    "contract-unenforced": ("契约", "校验", "没验", "绕过"),
}
tax = {k: [] for k in CLASSES}
for rn, body in rounds:
    for k, kws in CLASSES.items():
        if any(w in body for w in kws):
            tax[k].append(int(rn))

d = json.load(open(os.path.join(FINAL, "data.json"), encoding="utf-8"))
PAPER_TABLE = {  # what Results table rows print (paper.tex L731-L742)
    "silent-default": 14,
    "duplicate-logic": 13,
    "vacuous-check": 7,
    "self-report": 6,
    "contract-unenforced": 5,
    "self-test-broken": 2,
}
print("\n=== class | paper table | data.json | recomputed-from-source ===")
bad = []
for k in ["silent-default", "duplicate-logic", "vacuous-check",
          "self-report", "contract-unenforced", "self-test-broken"]:
    p = PAPER_TABLE[k]
    a = d["defect_taxonomy"][k]["n_rounds"]
    r = len(set(tax[k]))
    flag = ""
    if p != a or p != r:
        flag = "   <<< MISMATCH"
        bad.append(k)
    print("  %-20s %8d %11d %13d%s" % (k, p, a, r, flag))
print("\nvacuous-check rounds in data.json:", d["defect_taxonomy"]["vacuous-check"]["rounds"])
print("vacuous-check rounds recomputed  :", sorted(set(tax["vacuous-check"])))
print("mismatching classes:", bad if bad else "none")
