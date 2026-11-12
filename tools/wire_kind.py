#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把题型识别接进流程，并让机理节按题型分支。

改造前
------
    L += [r"\\section{Mechanistic basis}", ""]      # 无条件
    ... R_th = R_cond + R_conv, Nu = hD_h/k_f ...   # 热沉专用公式

换一道化工题，这一段原样输出，PDF 里 33 处热沉术语，
而摘要开头是「chemical reactor yield」。自相矛盾。

改造后
------
    full  ：机理工题（识别为 mechanism）→ 完整守恒律版
    brief ：参数映射/优化类 → 只留「守恒律给方向 + 符号检验」
    none  ：识别不出 → 跳过
    默认 auto：按识别结果选 full/brief，识别不出则 brief

brief 版保留的东西
------------------
· 「这些因子通过某个守恒律进入响应，方向可检验」这一段（通用）
· 符号检验表（数据驱动，本来就通用）
· 强度标注的假设（来自 kb/cards，不含题目专有名词）

去掉的东西
----------
· R_th = R_cond + R_conv 之类的具体公式（热沉专用）
· _PHYS_STRENGTH 那 6 条流体假设名（steady/incompressible/…）
"""
import ast
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ══ ① mmkit：把题型识别结果放进 ctx ══
P1 = os.path.join(HERE, "mmkit.py")
s1 = open(P1, encoding="utf-8").read()
if "problem_kind=_kind_ctx" not in s1:
    HELPER = '''

def _kind_ctx(problem, ds, xs, ycol):
    """题型识别：题目描述 + 列名 → 题型与所需模块。"""
    try:
        import kind as _kind
        cols = [str(c) for c in (ds.num_names or [])]
        return _kind.detect(problem or "", cols, ycol)
    except Exception:                               # noqa: BLE001
        return {}


'''
    k = s1.find("def _pi_ctx(")
    s1 = s1[:k] + HELPER + s1[k:]
    s1 = s1.replace("            pred_int=_pi_ctx(ds, min_cols, xs),",
                    "            pred_int=_pi_ctx(ds, min_cols, xs),\n"
                    "            problem_kind=_kind_ctx(problem, ds, xs, ycol),\n"
                    "            mechanism_mode=getattr(a, 'mechanism', 'auto'),", 1)
    ast.parse(s1)
    compile(s1, P1, "exec")
    open(P1, "w", encoding="utf-8", newline="\n").write(s1)
    print("① mmkit 接入题型识别")

# ══ ② mmkit 加 --mechanism 参数 ══
if "--mechanism" not in s1:
    OLD = '    ap.add_argument("--no-gate", action="store_true"'
    NEW = ('    ap.add_argument("--mechanism", default="auto",\n'
           '                    choices=["auto", "full", "brief", "none"],\n'
           '                    help="机理段：auto 按题型选，full 完整，'
           'brief 只留方向，none 跳过")\n'
           '    ap.add_argument("--no-gate", action="store_true"')
    if OLD in s1:
        s1 = s1.replace(OLD, NEW, 1)
        ast.parse(s1)
        open(P1, "w", encoding="utf-8", newline="\n").write(s1)
        print("② 加了 --mechanism 参数")

# ══ ③ paper.py：机理节按模式分支 ══
P2 = os.path.join(HERE, "paper.py")
s2 = open(P2, encoding="utf-8").read()
ANCHOR = '    L += [r"\\section{Mechanistic basis}", ""]'
if ANCHOR in s2 and "_mech_mode" not in s2:
    GUARD = '''    # ── 机理节按题型分支 ──
    # 原来无条件输出热沉专用的 R_th/Nu 公式，换一道题就满篇污染。
    _kd = ctx.get("problem_kind") or {}
    _mm_mode = str(ctx.get("mechanism_mode") or "auto").lower()
    _need_full = bool(_kd.get("mechanism_needed"))
    if _mm_mode == "auto":
        _mech = "full" if _need_full else "brief"
    else:
        _mech = _mm_mode
    _mc = _mm_mode == "auto" and False   # 占位，保持后续缩进结构
    L.append("")

'''
    s2 = s2.replace(ANCHOR, GUARD + "    if _mech != \"none\":\n"
                    + ANCHOR, 1)
    ast.parse(s2)
    compile(s2, P2, "exec")
    open(P2, "w", encoding="utf-8", newline="\n").write(s2)
    print("③ paper.py 机理节加了分支前置")

print("  下一步：把热沉专用公式包进 if _mech == 'full'")
