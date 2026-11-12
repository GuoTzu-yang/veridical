#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""修 bug：Problem 2 被误包进 _mech == "full" 块。

clean_rest.py 当时找「影响规律之后第一个空行」作为块尾，
但影响规律后面紧接着就是 Problem 2，没有空行分隔 ——
于是整个 Problem 2 节（15 个 L.append）都被包进了 if 里。

后果：brief 模式下（化工题）整节 Problem 2 消失，
required 检查立刻报「缺『目标函数与约束写成标准形式』」。
"""
import ast
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "paper.py")
L = open(P, encoding="utf-8").read().splitlines(keepends=True)

# 定位：if _mech == "full": 之后，Problem 2 的 section 行
i_if = None
i_p2 = None
for i, ln in enumerate(L):
    if i_if is None and ln.strip() == 'if _mech == "full":':
        i_if = i
    if i_if is not None and "Problem 2: Design selection" in ln:
        i_p2 = i
        break

assert i_if is not None and i_p2 is not None, f"定位失败 if={i_if} p2={i_p2}"
print(f"  if 在 {i_if + 1}，Problem 2 在 {i_p2 + 1}")

# 找 Problem 2 的结束：下一个缩进 <= 4 的非空非注释行
i_end = None
for k in range(i_p2, len(L)):
    ln = L[k]
    if not ln.strip() or ln.lstrip().startswith("#"):
        continue
    if len(ln) - len(ln.lstrip()) <= 4:
        i_end = k
        break
assert i_end is not None, "找不到块尾"
print(f"  Problem 2 结束在 {i_end + 1}")

# 把 i_p2 .. i_end-1 每行减 4 空格缩进
cnt = 0
for k in range(i_p2, i_end):
    ln = L[k]
    if ln.strip() == "":
        continue
    if ln.startswith("    "):
        L[k] = ln[4:]
        cnt += 1
print(f"  已把 {cnt} 行移出 if 块")

s = "".join(L)
ast.parse(s)
compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print(f"  paper.py {len(s.splitlines())} 行")
