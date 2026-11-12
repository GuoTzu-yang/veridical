import ast
import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "paper.py")
s = open(P, encoding="utf-8").read()

# ① 模块级：段落覆盖表 + 骨架收集
if "_PARA_OVERRIDES" not in s:
    i = s.find("def build(")
    assert i > 0
    H = '''# ══════════════════════════════════════════════════════════════════════
#  LLM 注入正文的接口
#
#  paper.py 生成的是「结构 + 数字 + 表格 + 图」。正文段落（摘要、稳健性、
#  结论）本来也由它写死，于是 22 道题的论文骨架一模一样（实测重复率
#  67%–85%）。
#
#  这里给正文留一个后门：**LLM 可以按段落替换**，模板继续出数字和表格。
#  没有覆盖时行为完全不变（22 道题的回归因此不受影响）。
#
#  键怎么定：用**段落原文的前 40 个字符**（内容寻址）。
#  这样 LLM 只要读过 `mmkit.py skeleton` 导出的原文，就能对上号，
#  不需要记任何人为编号。
# ══════════════════════════════════════════════════════════════════════

_PARA_OVERRIDES = {}     # {原文前 40 字: 替换文本}
_PARA_SEEN = []          # [(key, 原文)]，skeleton 用


def para_key(txt: str) -> str:
    """段落的内容寻址键：前 40 个非空字符。"""
    t = " ".join(str(txt or "").split())
    return t[:40]


def set_overrides(d: dict | None):
    """装入 LLM 写的段落。None 表示清空（回到纯模板）。"""
    global _PARA_OVERRIDES, _PARA_SEEN
    _PARA_OVERRIDES = dict(d or {})
    _PARA_SEEN = []


def dump_skeleton() -> list:
    """本次 build 见到的所有段落（key, 原文）。"""
    return list(_PARA_SEEN)


'''
    s = s[:i] + H + s[i:]

# ② _para 支持覆盖 + 记录
OLD = ('    def _para(txt):\n'
       '        if txt:\n'
       '            L.append(txt)\n'
       '            L.append("")')
assert OLD in s, "no _para"
NEW = ('    def _para(txt):\n'
       '        # 正文可被 LLM 覆盖；没覆盖就用模板原文（行为不变）。\n'
       '        if txt:\n'
       '            _k = para_key(txt)\n'
       '            _PARA_SEEN.append((_k, " ".join(str(txt).split())))\n'
       '            _t = _PARA_OVERRIDES.get(_k, txt)\n'
       '            L.append(_t)\n'
       '            L.append("")')
s = s.replace(OLD, NEW, 1)
ast.parse(s); compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  _para 支持 override + 骨架收集")