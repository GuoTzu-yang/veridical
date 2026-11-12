# -*- coding: utf-8 -*-
"""restatement 板 · scope-auditor 只读探针。

只读 out/final/paper.tex 与 out/final/*.json、schema.json、verify.py；
只打印，不写任何文件，不改任何源码。

用法： python tools/rtB_restatement_probe.py
"""
from __future__ import annotations

import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

PAPER = os.path.join(ROOT, "out", "final", "paper.tex")
FREEZE = os.path.join(ROOT, "out", "final", "冻结数字.json")
SCHEMA = os.path.join(ROOT, "schema.json")
GATEREP = os.path.join(ROOT, "out", "final", "gate-report.json")
RT = os.path.join(ROOT, "out", "final", "redteam.json")
CTX = os.path.join(ROOT, "out", "final", "context_metrics.json")

L0, L1 = 75, 170  # 1-based, inclusive：\section{Restatement of the problem} 段落


def rd(p):
    with io.open(p, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def head(t):
    print("\n" + "=" * 72)
    print(t)
    print("=" * 72)


def main():
    tex = rd(PAPER)
    all_lines = tex.splitlines()

    head("[1] 板块边界核对（L%d-L%d）" % (L0, L1))
    print("L%d: %s" % (L0, all_lines[L0 - 1]))
    print("L%d(下一节首行): %s" % (L1 + 1, all_lines[L1]))
    print("paper.tex 总行数: %d" % len(all_lines))

    sec = all_lines[L0 - 1:L1]
    body = "\n".join(sec)
    print("板块字数(char): %d" % len(body))

    head("[2] 板块内 \\cite / \\ref / 数字 · 原始清单")
    cites = re.findall(r"\\cite\{([^}]*)\}", body)
    print("cite 条数: %d  键: %s" % (len(cites), cites))
    refs = re.findall(r"\\ref\{([^}]*)\}", body)
    print("ref 条数: %d  键: %s" % (len(refs), refs))
    print("全文 cite 条数: %d" % len(re.findall(r"\\cite\{", tex)))

    head("[3] 板块内数字 token —— 用项目自己的分词器 verify.extract_numbers")
    try:
        import verify  # noqa: E402
        toks = verify.extract_numbers(body, skip_meta=True)
        print("verify.extract_numbers 抽出 %d 个候选数字:" % len(toks))
        for tk, ln in toks:
            print("   token=%-10s 精度=%s  行=%s" % (tk, verify._written_decimals(tk), ln[:70]))
    except Exception as e:  # 探针自身失败必须可见
        toks = []
        print("!! verify 导入/抽取失败: %r" % (e,))

    head("[4] 这些数字在 冻结数字.json（论文自己的溯源表）里有没有来源")
    fz = json.loads(rd(FREEZE))
    items = fz.get("items") or []
    vals = []
    for it in items:
        v = it.get("value")
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            vals.append((float(v), it.get("path")))
    print("冻结表条目: n=%s, 可比较数值 %d 个" % (fz.get("n"), len(vals)))
    for tk, ln in toks:
        try:
            v = float(tk)
        except ValueError:
            continue
        dec = verify._written_decimals(tk)
        hit = [(b, p) for b, p in vals if abs(round(b, dec) - v) <= 1e-12]
        print("   数字 %-8s (精度%s) -> 冻结表命中 %d 个 %s"
              % (tk, dec, len(hit), [p for _b, p in hit][:4]))

    head("[5] 全文数字溯源自评（同一条 trace 算法，只读调用）")
    try:
        outs = verify.load_outputs(os.path.join(ROOT, "out", "final"))
        r_all = verify.trace(tex, outs)
        r_sec = verify.trace(body, outs)
        print("全文 : %d/%d (%.1f%%) 未溯源 %d"
              % (r_all["n_numbers"] - r_all["n_untraced"], r_all["n_numbers"],
                 r_all["traced_ratio"] * 100, r_all["n_untraced"]))
        print("本板 : %d/%d (%.1f%%) 未溯源 %d"
              % (r_sec["n_numbers"] - r_sec["n_untraced"], r_sec["n_numbers"],
                 r_sec["traced_ratio"] * 100, r_sec["n_untraced"]))
        for u in r_sec["untraced"]:
            print("   本板未溯源: %s <- %s" % (u["token"], u["line"][:70]))
    except Exception as e:
        print("!! trace 失败: %r" % (e,))

    head("[6] 重述第 §Scope 段声称的能力族 vs schema.json 实际命令")
    sc = json.loads(rd(SCHEMA))
    cmds = sc.get("commands") or {}
    print("schema.n_commands = %s ; 实测键数 = %d" % (sc.get("n_commands"), len(cmds)))
    for name in sorted(cmds):
        d = (cmds[name] or {}).get("desc") or ""
        print("   %-12s %s" % (name, d[:58]))

    head("[7] gate 的板级检查：有没有 restatement 这一项")
    gr = json.loads(rd(GATEREP))
    checks = gr.get("checks") or []
    hard = [c for c in checks if c.get("tier") == "hard"]
    na = [c["id"] for c in checks if c.get("status") == "N/A"]
    print("gate 检查项 %d，硬门 %d，N/A %d %s"
          % (len(checks), len(hard), len(na), na))
    print("检查 id: %s" % [c["id"] for c in checks])
    print("有 restatement 检查项吗: %s"
          % any("restatement" in str(c.get("id", "")) for c in checks))

    head("[8] 作者自审 redteam.json：有没有 restatement 这一板")
    rtj = json.loads(rd(RT))
    revs = rtj.get("reviews") or []
    print("reviews 条数 %d" % len(revs))
    for r in revs:
        print("   section=%-18s role=%-24s verdict=%s"
              % (r.get("section"), r.get("role"), r.get("verdict")))
    print("存在 section==restatement 的记录吗: %s"
          % any(r.get("section") == "restatement" for r in revs))

    head("[9] context_metrics.json 对本板的计量")
    cm = json.loads(rd(CTX))
    for s in cm.get("sections") or []:
        if "Restatement" in s.get("section", ""):
            print(s)

    head("[10] 本板提到的三问 vs 摘要里的 Problem 1/2/3（逐行原文）")
    for i in range(1, 75):
        ln = all_lines[i - 1]
        if re.search(r"Problem \d|three questions|What we take as the task|honest limit", ln):
            print("L%-4d %s" % (i, ln))


if __name__ == "__main__":
    main()
