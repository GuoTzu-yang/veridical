import ast
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "i18n.py")
s = open(P, encoding="utf-8").read()

BLOCK = '''

# ══════════════════════════════════════════════════════════════════════
#  章节标题：每种语言一份**独立**的文本
#
#  为什么不用「英文原文 + 后处理替换」
#  ----------------------------------
#  替换式做法（拿英文当模板逐句 replace）会让两种语言互相干扰：
#  改一句英文，两种语言的输出都跟着变；中文里想调整语序也没法调，
#  因为中文是从英文派生的。
#  这里每种语言各写各的，英文那份**逐字照抄现在的论文**，
#  中文那份独立撰写。两者之间没有运行时依赖。
#
#  占位符用 <<name>> 而不是 {name}：LaTeX 正文里 { } 是分组括号，
#  用 str.format 会把它们全当占位。
# ══════════════════════════════════════════════════════════════════════

SECT = {
    "en": {
        "limitations": "Limitations",
        "intro": "Introduction",
        "assumptions": "Assumptions and Notations",
        "mech": "Mechanistic basis",
        "p1": "Problem 1: How the geometry governs <<y>>",
        "p2": "Problem 2: Design selection under constraints",
        "p3": "Problem 3: How stable are the conclusions?",
        "p4": "Problem 4: Does the choice survive a change of priorities?",
        "p5": "Problem 5: Can this design be manufactured?",
        "eval": "Evaluation",
        "disclosure": "AI Disclosure and Human Verification",
        "code": "Core Code",
    },
    "zh": {
        "limitations": "局限性",
        "intro": "引言",
        "assumptions": "模型假设与符号说明",
        "mech": "机理基础",
        "p1": "第 1 问：几何结构如何决定 <<y>>",
        "p2": "第 2 问：约束条件下的方案选择",
        "p3": "第 3 问：结论有多稳定",
        "p4": "第 4 问：优先级变化后结论是否依然成立",
        "p5": "第 5 问：该方案能否被制造出来",
        "eval": "模型评价",
        "disclosure": "AI 使用声明与人工核验",
        "code": "核心代码",
    },
}

# 各语言自己的段落文本（摘要、结论、表头、图注……）。
# 结构同 SECT：每种语言一份，不共享模板。
BODY = {
    "en": {},
    "zh": {},
}


def is_en(lang: str) -> bool:
    """是不是英文。"""
    return not lang or str(lang).lower().startswith("en")


def name(lang: str, orig: str, en: str = "") -> str:
    """按语言取名称：英文用 en（英文化后的名字），中文用原名。

    这是「两种语言互不干扰」的关键入口 —— 列名、模型名、指标名
    全部走它。中文版不该出现 thermal resistance 这种英文列名，
    英文版也不该出现「产量」。
    """
    return en if is_en(lang) else orig


def sec(lang: str, key: str, **kw) -> str:
    """取章节标题。找不到就回落英文。"""
    t = SECT.get(_lk(lang), {}).get(key)
    if t is None:
        t = SECT["en"].get(key, key)
    return _fill(t, kw)


def body(lang: str, key: str, **kw) -> str:
    """取段落文本。找不到就回落英文。"""
    t = BODY.get(_lk(lang), {}).get(key)
    if t is None:
        t = BODY["en"].get(key, "")
    return _fill(t, kw)


def _lk(lang: str) -> str:
    return str(lang or DEFAULT).lower().replace("_", "-")[:2]


def _fill(t: str, kw: dict) -> str:
    for k, v in kw.items():
        t = t.replace("<<" + k + ">>", str(v))
    return t
'''

if "def _lk(" not in s:
    s = s.rstrip("\n") + "\n" + BLOCK
    ast.parse(s)
    compile(s, P, "exec")
    open(P, "w", encoding="utf-8", newline="\n").write(s)
    print("  added SECT / BODY / is_en / name / sec / body")
else:
    print("  already present")