# -*- coding: utf-8 -*-
"""restatement 板 · 只读探针 3：结构化计数（供对照表用）。

只读 out/final/paper.tex、gate.py 文本；只打印。
"""
from __future__ import annotations

import io
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAPER = os.path.join(ROOT, "out", "final", "paper.tex")
GATE = os.path.join(ROOT, "gate.py")


def rd(p):
    with io.open(p, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def main():
    lines = rd(PAPER).splitlines()

    print("=" * 72)
    print("[A] 本板（L75-L170）结构：正文 vs 相关工作 各占多少行")
    board = lines[74:170]
    pw = [i for i, l in enumerate(board, start=75) if l.startswith("\\subsection")]
    print("subsection 起始行: %s" % pw)
    split = pw[0] if pw else 171
    print("重述正文   L75-L%d = %d 行" % (split - 1, split - 75))
    print("相关工作   L%d-L170 = %d 行" % (split, 171 - split))
    print("相关工作占比 %.1f%%" % ((171 - split) * 100.0 / 96))

    print("\n[B] 本板 \\paragraph 段落清单")
    for i, l in enumerate(board, start=75):
        m = re.match(r"\\paragraph\{(.+?)\}", l)
        if m:
            print("   L%-4d %s" % (i, m.group(1)))

    print("\n[C] 本板 enumerate 里的问题条数")
    en = []
    inenum = False
    for i, l in enumerate(board, start=75):
        if l.startswith("\\begin{enumerate}"):
            inenum = True
        elif l.startswith("\\end{enumerate}"):
            inenum = False
        elif inenum and l.startswith("\\item"):
            en.append((i, l.strip()))
    for i, t in en:
        print("   L%-4d %s" % (i, t[:78]))
    print("   合计 %d 条问题" % len(en))

    print("\n[D] 本板前向 \\ref 到哪一节")
    refs = re.findall(r"\\ref\{([^}]*)\}", "\n".join(board))
    print("   %s" % refs)
    labels = {}
    for i, l in enumerate(lines, start=1):
        m = re.search(r"\\label\{([^}]*)\}", l)
        if m:
            labels[m.group(1)] = i
    for r in refs:
        print("   %s -> paper.tex L%s" % (r, labels.get(r)))

    print("\n[E] 全文 12 个 \\section 与三问的对应（人工判断见 md）")
    secs = [(i, l) for i, l in enumerate(lines, start=1)
            if re.match(r"^\\section\{", l)]
    for n, (i, l) in enumerate(secs, start=1):
        print("   §%-2d L%-5d %s" % (n, i, l))

    print("\n[F] gate.py 里的 redteam 检查：怎么数「几个板块」")
    g = rd(GATE)
    for m in re.finditer(r"def (chk_redteam|_redteam)[^\n]*", g):
        print("   hit: %s" % m.group(0))
    idx = g.find("redteam")
    for m in re.finditer(r"\n[^\n]*redteam[^\n]*", g):
        s = m.group(0).strip()
        if len(s) < 200:
            print("   %s" % s[:150])


if __name__ == "__main__":
    main()
