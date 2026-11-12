#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按 danus 的 P5/P6 条款检查我们的论文。

P5 模糊引用经典结果：「由某个 well-known / classical / standard 论证」，
   却没有具体引用 → 评委无法核对。
P6 自足陈述：「在标准假设下……」却没列假设 → 读者无法从这句话本身
   判断前提。
这两条都是能在 tex 里用正则查的，我们 15 项 gate 里原来没有。
"""
import os
import re

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
tex = open(os.path.join(HERE, "out", "fig", "paper.tex"),
           encoding="utf-8").read()

# 剥掉 LaTeX 命令，只留文字
body = re.sub(r"\\[a-zA-Z]+\*?(\[[^\]]*\])?(\{[^{}]*\})?", " ", tex)
body = re.sub(r"\s+", " ", body)

P5 = [
    r"\bwell[- ]known\b", r"\bclassical\b", r"\bstandard\s+(argument|result|"
    r"assumption|theory|method)\b", r"\bobvious(ly)?\b",
    r"\bit is known\b", r"\btextbook\b", r"\bfamously\b",
]
P6 = [
    r"[Uu]nder the (standard|usual|typical)",
    r"given the (usual|standard) (assumptions|hypotheses)",
    r"assuming (the )?(usual|standard|typical)",
]

print("  === P5 模糊引用经典结果 ===")
hits = []
for pat in P5:
    for m in re.finditer(pat, body, re.I):
        i = m.start()
        hits.append((m.group(0), body[max(0, i - 70):i + 80]))
print(f"    命中 {len(hits)} 处")
for w, ctx in hits[:8]:
    print(f"      [{w}] ...{ctx.strip()[:110]}...")

print()
print("  === P6 自足陈述 ===")
hits6 = []
for pat in P6:
    for m in re.finditer(pat, body, re.I):
        i = m.start()
        hits6.append((m.group(0), body[max(0, i - 60):i + 120]))
print(f"    命中 {len(hits6)} 处")
for w, ctx in hits6[:6]:
    print(f"      [{w}] ...{ctx.strip()[:120]}...")

print()
print("  === 现有的「强度标注」是否已覆盖 P6 ===")
print(f"    strong/weak 标注出现: {body.count('strong') + body.count('weak')} 次")
print(f"    'conservation of' 出现: {body.lower().count('conservation of')} 次")
m = re.search(r"The three indicators follow from.{0,220}", body)
print(f"    机理句: {m.group(0)[:200] if m else '没找到'}")
