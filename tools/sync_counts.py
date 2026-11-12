"""把 gate 的项数（22 → 23）在所有引用处对齐，并修 docstring 的转义警告。

为什么要有这个脚本：加了 chk_stamp 之后 gate 是 23 项，而论文、AGENTS、速查
还写着 22 —— 这种「源码改了、文档没跟」正是本项目一直在批的漂移。
"""
import io
import os
import re

HERE = r"C:\Users\21246\Documents\deepseek-harness\default-workspace\model1-arch"

QUOTE3 = '"' * 3


def fix_gate_docstring():
    p = os.path.join(HERE, "gate.py")
    s = io.open(p, encoding="utf-8").read()
    i = s.index("def chk_refs(figdir: str) -> dict:")
    j = s.index(QUOTE3, i)
    if s[j - 1] == "r":
        print("gate.py: docstring 已是 raw")
        return
    s = s[:j] + "r" + s[j:]
    io.open(p, "w", encoding="utf-8", newline="\n").write(s)
    print("gate.py: docstring 改为 raw（消掉 \\c 转义警告）")


def bump(path, pairs):
    p = os.path.join(HERE, path)
    if not os.path.exists(p):
        print(path, "不存在，跳过")
        return
    t = io.open(p, encoding="utf-8").read()
    hit = 0
    for old, new in pairs:
        if old in t:
            t = t.replace(old, new)
            hit += 1
    io.open(p, "w", encoding="utf-8", newline="\n").write(t)
    print("%-28s 替换 %d/%d 处" % (path, hit, len(pairs)))


fix_gate_docstring()

bump("AGENTS.md", [
    ("# 出稿前 22 项", "# 出稿前 23 项"),
    ("22 项质量门", "23 项质量门"),
])

bump("out/final/paper.tex", [
    ("every paper must pass a gate of 22 checks, 12 of them hard",
     "every paper must pass a gate of 23 checks, 12 of them hard"),
    ("gate of 22 checks, of which 12 are hard",
     "gate of 23 checks, of which 12 are hard"),
    ("22 problems through 22 checks", "23 problems through 23 checks"),
    (r"\item Twenty-two checks, twelve hard.",
     r"\item Twenty-three checks, twelve hard."),
])

bump("插件速查.md", [
    ("gate.py` | 22 项", "gate.py` | 23 项"),
])

# 论文里还有几处 "22 checks"，逐一列出残留，人工确认
t = io.open(os.path.join(HERE, "out", "final", "paper.tex"),
            encoding="utf-8").read()
left = [m.start() for m in re.finditer(r"22 checks|Twenty-two checks", t)]
print()
print("论文里仍写 22 checks 的处数:", len(left))
for i in left:
    print("   ...", t[max(0, i - 60):i + 30].replace("\n", " "))
