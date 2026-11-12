# -*- coding: utf-8 -*-
"""conclusion 板只读探针：把结论段里出现的每个数字/短语，回查它在正文别处是否出现过。
只读 out/final/paper.tex，只打印。不写任何文件。"""
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAPER = os.path.join(ROOT, "out", "final", "paper.tex")

# 板边界：\section{Conclusion} 起，到下一个 \section 之前
START_MARK = r"\section{Conclusion}"

ENC = "utf-8"


def load():
    with io.open(PAPER, "r", encoding=ENC, errors="replace") as fh:
        return fh.read().splitlines()


def find_span(lines):
    start = None
    for i, ln in enumerate(lines):
        if ln.strip().startswith(START_MARK):
            start = i
            break
    if start is None:
        return None, None
    end = None
    for j in range(start + 1, len(lines)):
        if lines[j].lstrip().startswith(r"\section{"):
            end = j
            break
    if end is None:
        end = len(lines)
    return start, end  # 0-based, end exclusive


def main():
    lines = load()
    start, end = find_span(lines)
    print("=== 0. 边界 ===")
    print("paper: %s" % PAPER)
    print("total_lines: %d" % len(lines))
    if start is None:
        print("FATAL: \\section{Conclusion} not found")
        return 2
    print("conclusion span (1-based): L%d .. L%d" % (start + 1, end))
    print("conclusion text lines: %d" % (end - start))

    concl = lines[start:end]
    concl_text = "\n".join(concl)
    rest = lines[:start] + lines[end:]
    rest_text = "\n".join(rest)
    # 结论之后的部分（Reproducibility 等）单独一份，便于判断"只在结论出现"是否其实写在后文
    tail_text = "\n".join(lines[end:])
    head_text = "\n".join(lines[:start])

    print("")
    print("=== 1. 结论段逐行 ===")
    for i in range(start, end):
        print("%5d| %s" % (i + 1, lines[i]))

    # 结论中出现的「数字型 token」自动抽取
    print("")
    print("=== 2. 自动抽取：结论段里所有数字 token ===")
    nums = re.findall(r"\d+(?:\.\d+)?", concl_text)
    from collections import Counter
    cnt = Counter(nums)
    for k in sorted(cnt, key=lambda x: (-cnt[x], x)):
        print("  token=%-8s conclusion_hits=%d" % (k, cnt[k]))

    # 需要人工核对的短语 / 数字（探针2：新信息）
    print("")
    print("=== 3. 关键 token 回查：结论 vs 正文其余部分 ===")
    print("   (hits_elsewhere=0 且 结论中有 -> 结论独有，属「新信息」嫌疑)")
    tokens = [
        "29 checks",
        "29\\,checks",
        "29",
        "12 hard",
        "23/23",
        "23 problems",
        "129",
        "30 repair",
        "30 rounds",
        "51 of 51",
        "51",
        "7 of 7",
        "15 of 22",
        "21 against 6",
        "1 against 6",
        "five problems",
        "two scopes",
        "six classes",
        "six defect",
        "seven specific errors",
        "one command",
        "One corpus",
        "one corpus",
        "one author",
        "One project",
        "independent rater",
        "inter-rater",
        "not make it wise",
        "only a checker",
        "passes mean something",
        "passed everything",
    ]
    for t in tokens:
        n_concl = concl_text.count(t)
        n_head = head_text.count(t)
        n_tail = tail_text.count(t)
        flag = ""
        if n_concl > 0 and (n_head + n_tail) == 0:
            flag = "  <== 结论独有"
        print("  %-24s conclusion=%-2d before=%-3d after=%-3d%s"
              % (t, n_concl, n_head, n_tail, flag))

    # 关键 token 在正文的命中行号（便于写 evidence）
    print("")
    print("=== 4. 关键 token 的正文命中行号（前 8 处，排除结论段）===")
    watch = ["29 checks", "23/23", "129", "30 repair", "30 rounds", "51 of 51",
             "51 ", "7 of 7", "15 of 22", "21 against 6", "five problems",
             "two scopes", "six defect classes", "seven specific errors",
             "one command", "not make it wise"]
    for t in watch:
        hits = []
        for i, ln in enumerate(lines):
            if start <= i < end:
                continue
            if t in ln:
                hits.append(i + 1)
        print("  %-22s -> %s" % (t, hits[:8] if hits else "NONE"))

    # 结论段中的模态/强度词（探针3 原料）
    print("")
    print("=== 5. 结论段的强度词与限定词计数 ===")
    strength = ["all ", "only", "everything", "mean something", "guarantee",
                "prove", "proves", "always", "never", "every", "six classes"]
    hedge = ["may", "might", "cannot", "can not", "still", "one corpus",
             "untested", "not supported", "no independent", "weakness", "limit"]
    print("  -- strength --")
    for w in strength:
        print("     %-16s %d" % (w, concl_text.lower().count(w.lower())))
    print("  -- hedge --")
    for w in hedge:
        print("     %-16s %d" % (w, concl_text.lower().count(w.lower())))

    # 结论里出现的 \ref / \label
    print("")
    print("=== 6. 结论段的 \\ref 与 \\label ===")
    for m in re.finditer(r"\\(ref|label)\{([^}]+)\}", concl_text):
        print("  %s{%s}" % (m.group(1), m.group(2)))
    # 这些 ref 是否都有定义
    all_labels = set(re.findall(r"\\label\{([^}]+)\}", "\n".join(lines)))
    refs = re.findall(r"\\ref\{([^}]+)\}", concl_text)
    for r in refs:
        print("  ref %-20s defined=%s" % (r, r in all_labels))
    return 0


if __name__ == "__main__":
    sys.exit(main())
