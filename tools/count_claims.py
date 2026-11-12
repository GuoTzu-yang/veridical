"""列出论文里所有「自指数量」断言，供逐条核对。

为什么需要
----------
第 18 轮发现两处真实错误：
  · 「The four cases named in the problem」实际表里只有 2 行
  · 「The last three rows」实际是 4 行
这类错误的共同点是：**句子里的数量指向文档自身的结构**（几行、几例、第几节），
而正文一改、表一增删，数字就悄悄错位。它们不影响编译、不影响 gate 的数字溯源，
因为「4」和「3」都是普通整数，而冻结表里两个都存在。

工具不做自动判定（哪个才对要靠人看表和题面），只负责**把它们全列出来**。
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5,
}

PATTERNS = [
    # 自指结构
    (r"the last (\w+) (?:rows|cases|weeks|paragraphs|items)", "末尾 N 项"),
    (r"the (?:first|last) (\w+) (?:rows|cases|weeks)", "首/末 N 项"),
    (r"the (?:other|remaining) (\w+) ", "其余 N 项"),
    (r"in (\w+) of the (?:\\d+|\w+)", "N of M"),
    (r"(\w+) of the (?:\\d+|[\w]+) (?:weeks|rows|cases|contestants|seasons)", "N of M(结构)"),
    # 交叉引用（LaTeX 里应该用 \ref）
    (r"Table\s+(\d+)", "硬编码表号"),
    (r"Section\s+(\d+)", "硬编码节号"),
    (r"Figure\s+(\d+)", "硬编码图号"),
    (r"equation\s+\((\d+)\)", "硬编码公式号"),
    # 枚举数量
    (r"the (\w+) (?:cases|examples|contestants|reasons|steps|RULES|conditions)", "N 个对象"),
    (r"(\w+) (?:independent )?(?:checks|cases|rules)", "N 个检查/案例"),
]


def main(path=None):
    path = path or os.path.join(HERE, "out", "d2026c", "paper.tex")
    t = open(path, encoding="utf-8").read()
    body = t.split(r"\begin{document}")[-1]
    # 去掉注释行
    body = "\n".join(ln for ln in body.split("\n")
                     if not ln.lstrip().startswith("%"))
    lines = body.split("\n")
    hits = []
    for pat, label in PATTERNS:
        for m in re.finditer(pat, body, re.I):
            # 找所在行号
            upto = body[:m.start()]
            ln = upto.count("\n") + 1
            ctx = body[max(0, m.start() - 40):m.end() + 50].replace("\n", " ")
            hits.append((ln, label, m.group(0), ctx))
    hits.sort()
    seen = set()
    print("自指数量断言清单（共 %d 处，去重后）" % len(hits))
    print("=" * 96)
    for ln, label, frag, ctx in hits:
        key = (ln, frag)
        if key in seen:
            continue
        seen.add(key)
        print("\n  L%-4d [%s]  %s" % (ln, label, frag))
        print("        …%s…" % ctx.strip()[:110])
    print("\n" + "=" * 96)
    print("核对方法：每条都要回到表/节去看实际数量。")
    print("  · 末尾/首部 N 项 → 数表格里连续同类行的个数")
    print("  · N of M          → M 是分母（周数/样本数），N 是其中符合的个数")
    print("  · 硬编码表号/节号 → 应改成 \\ref{}，否则增删章节后全错")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else None))
