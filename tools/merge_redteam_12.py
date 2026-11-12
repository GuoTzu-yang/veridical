#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""merge_redteam_12.py —— 把 12 板的独立审核合并成 out/final/redteam.json。

规矩：论文有几个板块就有几个审核。板块数从 `paper.tex` 的 \\section 解析
（`redteam.paper_sections`），不是写死。

用法：
    python tools/merge_redteam_12.py            # 合并并校验
    python tools/merge_redteam_12.py --dry-run  # 只看会合并什么

合并口径：
  · 按 json 里的 `section` 字段认，不靠文件名（本轮出现过两种命名）
  · 一板只取一条；同一 section 有多个文件时取 finding 最多的那条并告警
  · 旧记录（作者自己写的 7 条）留档到 out/_backup_r122/redteam_author_7.json
"""
import glob
import io
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import redteam                                   # noqa: E402


def load_all(src_dir):
    got, dup = {}, []
    for p in sorted(glob.glob(os.path.join(src_dir, "*.json"))):
        try:
            j = json.load(io.open(p, encoding="utf-8"))
        except Exception as e:                   # noqa: BLE001
            print("  ⚠ 跳过坏文件 %s：%s" % (os.path.basename(p), e))
            continue
        s = str(j.get("section") or "").strip()
        if not s:
            print("  ⚠ 跳过无 section 的文件 %s" % os.path.basename(p))
            continue
        nf = sum(1 for x in (j.get("probes") or [])
                 if x.get("verdict") == "finding")
        if s in got:
            dup.append((s, os.path.basename(p)))
            prev = got[s]
            prev_nf = sum(1 for x in (prev.get("probes") or [])
                          if x.get("verdict") == "finding")
            if nf <= prev_nf:
                print("  ⚠ %s 有多个审核文件，保留 finding 更多的 %s"
                      % (s, prev.get("_from")))
                continue
            print("  ⚠ %s 有多个审核文件，改用 %s（finding %d > %d）"
                  % (s, os.path.basename(p), nf, prev_nf))
        j["_from"] = os.path.basename(p)
        got[s] = j
    return got, dup


def main(argv):
    dry = "--dry-run" in argv
    src = os.path.join(HERE, "out", "红队七板")
    dst = os.path.join(HERE, "out", "final", "redteam.json")
    if not os.path.isdir(src):
        print("没有 %s" % src)
        return 2

    need = [k for k, _t in redteam.paper_sections(os.path.join(HERE, "out", "final"))]
    got, dup = load_all(src)

    print("论文板块 %d 个，找到审核 %d 个" % (len(need), len(got)))
    missing = [k for k in need if k not in got]
    extra = [k for k in got if k not in need]
    if missing:
        print("  **缺**：%s" % ", ".join(missing))
    if extra:
        print("  多余（论文里没有这一节）：%s" % ", ".join(extra))

    reviews = []
    for k in need:
        if k not in got:
            continue
        j = got[k]
        j.pop("_from", None)
        # 补齐 verdict 字段
        if not j.get("verdict"):
            j["verdict"] = ("revise" if any(
                x.get("verdict") == "finding" for x in (j.get("probes") or []))
                else "pass")
        reviews.append(j)

    n_probes = sum(len(r.get("probes") or []) for r in reviews)
    n_findings = sum(1 for r in reviews for x in (r.get("probes") or [])
                     if x.get("verdict") == "finding")
    print("  合并后：%d 条 review，%d 条探针，%d 条 finding"
          % (len(reviews), n_probes, n_findings))
    if dry:
        for r in reviews:
            print("    %-16s %-26s %s"
                  % (r["section"], r["role"],
                     "".join("P" if x.get("verdict") == "pass" else "F"
                             for x in r.get("probes") or [])))
        return 0

    # 旧记录留档（作者自己写的 7 条），只在第一次合并时做
    bk = os.path.join(HERE, "out", "_backup_r122", "redteam_author_7.json")
    if os.path.exists(dst) and not os.path.exists(bk):
        os.makedirs(os.path.dirname(bk), exist_ok=True)
        shutil.copy2(dst, bk)
        print("  旧记录留档 → %s" % os.path.relpath(bk, HERE))

    with io.open(dst, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(dict(reviews=reviews), fh, ensure_ascii=False, indent=1)
    print("  已写 %s" % os.path.relpath(dst, HERE))

    # 立刻用 gate 的同一判据自检
    r = redteam.check(os.path.join(HERE, "out", "final"))
    print("  redteam.check → [%s] %s" % (r["level"], r["detail"][:400]))
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
