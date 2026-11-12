# -*- coding: utf-8 -*-
"""Probe 4b (evaluation board): re-derive the defect taxonomy straight from the
engineering log, using the *collector's own* rule, and compare all three objects
that are supposed to agree:

  tab:taxonomy (hand-typed in paper.tex)  vs
  data.json defect_taxonomy (emitted)     vs
  recomputation from OPTIMIZATION-优化记录.md (this script)

Also re-measures record_bytes the way a reader would (plain file size).

Read-only. Prints only. Writes nothing.
"""
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(ROOT, "OPTIMIZATION-优化记录.md")
DATA = os.path.join(ROOT, "out", "final", "data.json")
PAPER = os.path.join(ROOT, "out", "final", "paper.tex")

# Verbatim from tools/collect_paper_data.py L201-209.
CLASSES = {
    "vacuous-check": ("恒真", "恒为", "永不", "不可达", "从没被赋值",
                      "空判据", "摆设", "不能失败"),
    "silent-default": ("默认", "自动", "静默", "悄悄", "没人负责"),
    "duplicate-logic": ("两套", "分叉", "不一致", "同义", "漂移", "重复"),
    "self-report": ("自报", "样本量", "报成", "打印成", "数字不对"),
    "self-test-broken": ("崩溃", "IndexError", "自检不在", "不在回归链"),
    "contract-unenforced": ("契约", "校验", "没验", "绕过"),
}


def main():
    print("=" * 78)
    print("PROBE 4b  recount the taxonomy from the log")
    print("=" * 78)

    rec = io.open(LOG, encoding="utf-8").read()
    parts = re.split(r"^# 优化记录（第 (\d+) 轮）", rec, flags=re.M)
    rounds = [(parts[i], parts[i + 1]) for i in range(1, len(parts), 2)]
    print("log file on disk ............... %d bytes (%.1f KiB)"
          % (os.path.getsize(LOG), os.path.getsize(LOG) / 1024.0))
    print("len(rec.encode('utf-8')) ...... %d bytes (%.1f KiB)   <- newline-normalised"
          % (len(rec.encode("utf-8")), len(rec.encode("utf-8")) / 1024.0))
    print("rounds parsed by the regex ..... %d" % len(rounds))
    print()

    mine = {k: [] for k in CLASSES}
    for rn, body in rounds:
        for k, kws in CLASSES.items():
            if any(w in body for w in kws):
                mine[k].append(int(rn))

    data = json.load(open(DATA, encoding="utf-8"))
    emitted = {k: v["n_rounds"] for k, v in data["defect_taxonomy"].items()}

    # paper table
    paper = {}
    for ln in open(PAPER, encoding="utf-8").read().splitlines():
        m = re.match(r"^(Silent default|Duplicated logic|Vacuous check|"
                     r"Self-report inflation|Contract unenforced|Self-test broken)"
                     r"\s*&\s*(\d+)\s*&", ln.strip())
        if m:
            paper[m.group(1)] = int(m.group(2))
    keymap = {"silent-default": "Silent default", "duplicate-logic": "Duplicated logic",
              "vacuous-check": "Vacuous check", "self-report": "Self-report inflation",
              "contract-unenforced": "Contract unenforced",
              "self-test-broken": "Self-test broken"}

    print("%-22s %-8s %-8s %-8s  %s" % ("class", "recount", "data.json", "paper", "agree?"))
    print("-" * 78)
    bad = 0
    for k in sorted(CLASSES):
        rc = len(set(mine[k]))
        em = emitted.get(k)
        pa = paper.get(keymap[k])
        ok = (rc == em == pa)
        if not ok:
            bad += 1
        print("%-22s %-8d %-8s %-8s  %s" % (k, rc, em, pa, "yes" if ok else "NO"))
    print("-" * 78)
    print("totals: recount=%d  data.json=%d  paper=%d"
          % (sum(len(set(v)) for v in mine.values()),
             sum(emitted.values()), sum(paper.values())))
    print("rows that do not agree across all three objects: %d" % bad)
    print()

    print("vacuous-check round ids, recomputed: %s" % sorted(set(mine["vacuous-check"])))
    print("vacuous-check round ids, data.json : %s"
          % data["defect_taxonomy"]["vacuous-check"]["rounds"])
    print()

    print("=" * 78)
    print("Can any taxonomy instance be tied to a CODE CHANGE?")
    print("=" * 78)
    keys = set()
    for v in data["defect_taxonomy"].values():
        keys.update(v.keys())
    print("fields available per class in data.json: %s" % sorted(keys))
    print("  -> no patch id, no commit id, no file:line.  A round index only.")
    print("  ablate_provenance.py present: %s"
          % os.path.exists(os.path.join(ROOT, "tools", "ablate_provenance.py")))

    print()
    print("VERDICT INPUT:")
    print("  a plain file-size measurement of the '129 kB log' gives %.0f kB, not 129"
          % (os.path.getsize(LOG) / 1000.0))
    print("  taxonomy rows disagreeing: %d" % bad)


if __name__ == "__main__":
    main()
