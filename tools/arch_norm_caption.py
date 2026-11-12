"""规范化所有 caption：合并成单行，并逐个检查花括号平衡。

背景
----
`arch_sync2.py` 的一条替换 old 末尾带 `}` 而 new 不带，吃掉了 TOPSIS 表
caption 的右花括号。随后我为修它给**所有跨行 caption** 补了 `}`，把 8 个本来
正确的 caption 弄坏了。

正确判别
--------
对每个 \\caption 起始行累计花括号：
  · 在本行内配平  → caption 原本就闭合在本行（真闭合，或我补的那一个）
  · 跨行才配平    → 行尾那个 `}` 是我误加的，应删除，并把 caption 合并成一行

合并成单行的额外好处：以后再用脚本检查 caption 平衡只需看单行，不会再误判。
"""
import os
import re

P = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 "out", "arch", "paper.tex")


def main():
    lines = open(P, encoding="utf-8").read().split("\n")
    out, i, fixed = [], 0, 0
    while i < len(lines):
        ln = lines[i]
        if "\\caption{" not in ln:
            out.append(ln)
            i += 1
            continue
        # 从本行起累计花括号
        seg = ln
        bal = seg.count("{") - seg.count("}")
        j = i
        while bal > 0 and j + 1 < len(lines):
            j += 1
            seg += " " + lines[j].strip()
            bal = seg.count("{") - seg.count("}")
        if bal != 0:
            raise SystemExit("caption 未闭合，起始行 %d" % (i + 1))
        # seg 现在是一个完整 caption（含可能跨行拼接的内容）
        if "\n" not in seg and seg.count("{") == seg.count("}"):
            pass
        # 若结束位置跨行，删除误加的行尾 `}`，并合并
        if j > i:
            head = ln.rstrip()
            if head.endswith("}"):
                head = head[:-1].rstrip()      # 去掉误加的 }
                fixed += 1
            seg = head + " " + " ".join(
                x.strip() for x in lines[i + 1:j + 1])
            # 重新配平（去掉 } 后可能少一个，补在末尾）
            if seg.count("{") != seg.count("}"):
                seg = seg + "}"
        out.append(" ".join(seg.split()))
        i = j + 1
    open(P, "w", encoding="utf-8", newline="\n").write("\n".join(out))
    print("规范化完成，修正跨行 caption %d 处" % fixed)

    # 复查
    t = open(P, encoding="utf-8").read()
    bad = 0
    for n, l in enumerate(t.split("\n"), 1):
        if "\\caption{" in l:
            b = l.count("{") - l.count("}")
            if b != 0:
                print("  [BAD] L%d 平衡=%d" % (n, b))
                bad += 1
    print("caption 平衡检查：%s" % ("全部 OK" if bad == 0 else "%d 处异常" % bad))


if __name__ == "__main__":
    main()
