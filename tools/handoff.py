#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""handoff.py —— 刷新 HANDOFF.md 的「状态」段（第 124 轮）。

**为什么需要它**：`AGENTS.md` 已经 20 KB，`插件速查.md` 也越来越长。
新会话读不完，于是又会凭记忆做事。所以另起一份一页纸的交接，
但**状态部分不许手抄** —— 手抄的状态第二天就是错的。

做法：跑真实仪表，把结果填进 `HANDOFF.md` 的 `<!-- AUTO -->` 段，
`<!-- /AUTO -->` 之外的手写内容原样保留。

用法：
    python tools/handoff.py            # 刷新并打印
    python tools/handoff.py --dry      # 只打印将要写入的状态段
退出码：0 = 刷新成功（**不代表状态全绿**）。
"""
import io
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable
DOC = os.path.join(HERE, "HANDOFF.md")
BEGIN = "<!-- AUTO -->"
END = "<!-- /AUTO -->"


def _run(args, timeout=400):
    try:
        p = subprocess.run([PY] + args, cwd=HERE, capture_output=True,
                           text=True, encoding="utf-8", errors="replace",
                           timeout=timeout)
        return (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired:
        return "__TIMEOUT__"
    except Exception as e:                          # noqa: BLE001
        return "__ERR__ %s" % e


def _gate_counts(figdir="out/final"):
    """从 gate 输出里数硬/软门的绿红，不做二次判断 —— 只复述。"""
    out = _run(["gate.py", figdir])
    hard_ok = len(re.findall(r"\[OK\s*\]\s*硬", out))
    hard_fail = len(re.findall(r"\[FAIL\]\s*硬", out))
    soft_ok = len(re.findall(r"\[OK\s*\]\s*软", out))
    soft_fail = len(re.findall(r"\[FAIL\]\s*软", out))
    soft_warn = len(re.findall(r"\[WARN\]\s*软", out))
    na = len(re.findall(r"\[\-\s*\]", out))
    total = re.search(r"checks.*?(\d+)", out)
    m = re.search(r"硬门失败\s*(\d+)", out)
    hard_fail_n = m.group(1) if m else "?"
    m2 = re.search(r"警告\s*(\d+)", out)
    warn_n = m2.group(1) if m2 else "?"
    # 红项点名
    reds = re.findall(r"\[FAIL\]\s*(?:硬|软)\s+(\S+)", out)
    return dict(hard_ok=hard_ok, hard_fail=hard_fail, soft_ok=soft_ok,
                soft_fail=soft_fail, soft_warn=soft_warn, na=na,
                hard_fail_n=hard_fail_n, warn_n=warn_n, reds=reds)


def _one_line(args, pat, label, timeout=400):
    out = _run(args, timeout)
    if out.startswith("__TIMEOUT__"):
        return "%s **超时**（>%ds）" % (label, timeout)
    out = out.replace("\r\n", "\n")
    m = re.search(pat, out)
    return "%s %s" % (label, m.group(0).strip() if m else "**读不到**")


def build_status():
    g = _gate_counts()
    lines = []
    lines.append("```")
    lines.append("gate（out/final，35 项）")
    lines.append("  硬门  OK %d / FAIL %d     硬门失败 %s，警告 %s"
                 % (g["hard_ok"], g["hard_fail"], g["hard_fail_n"], g["warn_n"]))
    lines.append("  软门  OK %d / FAIL %d / WARN %d / 不适用 %d"
                 % (g["soft_ok"], g["soft_fail"], g["soft_warn"], g["na"]))
    if g["reds"]:
        lines.append("  红项  " + ", ".join(g["reds"]))
    lines.append("")
    lines.append(_one_line(["verify.py", os.path.join("out", "final", "paper.tex")],
                           r"数字溯源：\S+", "溯源"))
    lines.append(_one_line(["tools/arch_invariants.py"], r"不成立：\S+ / \d+", "架构不变式"))
    lines.append(_one_line(["tools/flywheel.py", "--snapshot"] if False else
                           ["tools/fig_visual.py", "out/final"],
                           r"A/B 无问题|个问题", "图的机械检查"))
    lines.append(_one_line(["tools/quality_doors.py", "selftest"],
                           r"自校通过：.*", "质量门自校"))
    lines.append("```")
    return "\n".join(lines)


def main(argv):
    dry = "--dry" in argv
    status = build_status()
    if dry:
        print(status)
        return 0
    if not os.path.exists(DOC):
        print("没有 HANDOFF.md，先建一个带 %s / %s 标记的骨架" % (BEGIN, END))
        return 2
    t = io.open(DOC, encoding="utf-8", newline="").read()
    if BEGIN not in t or END not in t:
        print("HANDOFF.md 里没有 %s / %s 标记" % (BEGIN, END))
        return 2
    new = re.sub(re.escape(BEGIN) + r".*?" + re.escape(END),
                 BEGIN + "\n" + status + "\n" + END, t, flags=re.S)
    io.open(DOC, "w", encoding="utf-8", newline="").write(new)
    print("已刷新 HANDOFF.md 的状态段")
    print()
    print(status)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
