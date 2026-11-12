# -*- coding: utf-8 -*-
"""conclusion 板只读探针 2：题面各问 × 结论条目 对照；论文自述三问 × 结论 对照。只读、只打印。"""
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAPER = os.path.join(ROOT, "out", "final", "paper.tex")
PROBLEM = os.path.join(ROOT, "out", "c2026_problem.txt")


def load(path):
    with io.open(path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read().splitlines()


def main():
    lines = load(PAPER)
    start = None
    for i, ln in enumerate(lines):
        if ln.strip().startswith(r"\section{Conclusion}"):
            start = i
            break
    end = None
    for j in range(start + 1, len(lines)):
        if lines[j].lstrip().startswith(r"\section{"):
            end = j
            break
    concl_text = "\n".join(lines[start:end])
    full_text = "\n".join(lines)
    low = concl_text.lower()

    print("=== A. 题面（2026 MCM Problem C, DWTS）各问清单 ===")
    print("  题面文件: out/c2026_problem.txt (存在=%s)" % os.path.exists(PROBLEM))
    questions = [
        ("Q1", "为每位选手、其参赛的每一周估计 fan vote 总量（建模）"),
        ("Q2", "该估计是否与每周实际淘汰一致？给一致性度量"),
        ("Q3", "fan vote 估计的不确定性有多大？是否每个选手/每周都相同？给度量"),
        ("Q4", "rank 与 percentage 两种合并法逐季对比；差异是否存在；哪种更偏向 fan vote"),
        ("Q5", "争议选手（S2 Rice / S4 Cyrus / S11 Palin / S27 Bones）两种方法是否同结果"),
        ("Q6", "加入「评委从 bottom two 中选一个淘汰」对结果的影响"),
        ("Q7", "推荐哪种合并法用于未来赛季，为什么；是否建议加入 bottom-two 机制"),
        ("Q8", "pro dancer 与名人特征（age/industry 等）的影响模型：影响多大；对评委分与 fan vote 是否同向"),
        ("Q9", "提出更公平/更好的新系统，并论证制片方应采纳"),
        ("Q10", "报告 ≤25 页，含 1-2 页给制片方的 memo"),
    ]
    for qid, text in questions:
        print("  %-4s %s" % (qid, text))

    print("")
    print("=== B. 题面各问在 conclusion 段（L%d-L%d）的命中 ===" % (start + 1, end))
    kw = {
        "Q1": ["fan vote", "fanvote", "fan-vote", "estimate", "contestant", "star"],
        "Q2": ["eliminat", "consisten", "agreement", "correctly estimate"],
        "Q3": ["uncertain", "certainty", "confidence interval", "credible", "posterior"],
        "Q4": ["rank", "percentage", "percent", "combine", "two approaches", "season"],
        "Q5": ["Rice", "Cyrus", "Palin", "Bones", "controvers"],
        "Q6": ["bottom two", "bottom-two", "judges choose", "judges chose"],
        "Q7": ["recommend", "future season", "producers"],
        "Q8": ["dancer", "partner", "age", "industry", "celebrity characteristic"],
        "Q9": ["fair", "fairer", "better system", "propose another"],
        "Q10": ["memo", "25 page", "summary sheet", "producer"],
    }
    for qid, words in kw.items():
        hits = {}
        for w in words:
            n = low.count(w.lower())
            if n:
                hits[w] = n
        print("  %-4s conclusion_hits=%s  -> %s"
              % (qid, hits if hits else "{}", "HIT" if hits else "MISS"))

    print("")
    print("=== C. 题面关键词在全文（含结论）的命中行号 ===")
    for qid, words in kw.items():
        rows = []
        for w in words:
            for i, ln in enumerate(lines):
                if w.lower() in ln.lower():
                    rows.append((w, i + 1))
                    break
        print("  %-4s %s" % (qid, rows[:6] if rows else "NONE"))

    print("")
    print("=== D. 论文自述三问（Restatement L89-L98）在 conclusion 的收束情况 ===")
    self_q = {
        "P1 什么该被验证、在哪里（数字四分类）":
            ["decompos", "classif", "four classes", "computed", "structural",
             "token", "what must be verified", "where to put checks"],
        "P2 机制在规模上是否有效、效果是否可归因":
            ["ablation", "23/23", "attribut", "scale", "23 problems", "mechanism"],
        "P3 检查器自身是否可信":
            ["six classes", "six defect", "self-test", "checker", "audit", "vacuous"],
    }
    for name, words in self_q.items():
        hits = {w: low.count(w.lower()) for w in words if low.count(w.lower())}
        print("  %-46s %s" % (name, hits if hits else "{} -> MISS"))

    print("")
    print("=== E. 结论段是否出现「本文不回答题面第 N 问」类声明 ===")
    decl = ["problem c", "dwts", "dancing with the stars", "out of scope",
            "not the question", "different task", "we do not answer",
            "this paper does not", "memo", "producer"]
    found = {w: low.count(w) for w in decl if low.count(w)}
    print("  declaration hits: %s" % (found if found else "NONE"))

    print("")
    print("=== F. 结论散文段（L1151-L1164）逐句主张清单 ===")
    prose = []
    buf = ""
    for i in range(start, end):
        ln = lines[i]
        if ln.lstrip().startswith("\\subsection") or ln.lstrip().startswith("\\begin{table"):
            break
        buf += " " + ln.strip()
    for s in re.split(r"(?<=[.;:])\s+", buf):
        s = s.strip()
        if len(s) > 12:
            prose.append(s)
    for k, s in enumerate(prose, 1):
        print("  S%d %s" % (k, s))
    print("  散文段句子数: %d" % len(prose))

    print("")
    print("=== G. 结论里出现的可核对断言（数/量词）与正文是否互指 ===")
    checks = [
        ("29 checks", "L1176 Claim：通过 29 项检查"),
        ("23/23", "L1177 23/23 problems green"),
        ("one command", "L1177 reproducible by one command"),
        ("Two scopes", "L1180 两个口径"),
        ("five problems", "L1183 五个题做消融"),
        ("7 of 7", "L1186 七个标签全可达"),
        ("15 of 22", "L1186 15/22 全分类"),
        ("30 rounds", "L1189 30 轮"),
        ("129\\,kB", "L1189 129 kB 日志"),
        ("51 of 51", "L1192 覆盖 51/51"),
        ("three defects", "L1192 同时暴露三缺陷"),
    ]
    for t, note in checks:
        c = concl_text.count(t)
        o = full_text.count(t) - c
        print("  %-14s conclusion=%d elsewhere=%d  | %s" % (t, c, o, note))

    print("")
    print("=== H. 'ledger' / 'one command' / 'single command' 全文命中 ===")
    for w in ["ledger", "one command", "single command", "one entry point",
              "verify_all", "collect_paper_data"]:
        rows = [i + 1 for i, ln in enumerate(lines) if w.lower() in ln.lower()]
        print("  %-20s -> %s" % (w, rows[:12] if rows else "NONE"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
