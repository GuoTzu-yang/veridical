#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把题型识别接进 mmkit 的 ctx。

没有这一步，paper.py 里 ctx.get("problem_kind") 拿到空 dict，
_need_full 恒为 False，所有题都走 brief ——
连热沉题自己的 R_th 公式和影响规律都被砍掉了（实测）。
"""
import ast
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "mmkit.py")
s = open(P, encoding="utf-8").read()

# ── ① 加 _kind_ctx 函数 ──
if "_kind_ctx" not in s:
    HELPER = '''

def _kind_ctx(problem, ds, xs, ycol):
    """题型识别：题目描述 + 全部数值列 → 题型与所需模块。

    识别结果决定 paper.py 走 full / brief / none 哪条机理分支。
    """
    try:
        import kind as _kind
        cols = [str(c) for c in (getattr(ds, "num_names", None) or [])]
        return _kind.detect(problem or "", cols, ycol)
    except Exception:                               # noqa: BLE001
        return {}

'''
    k = s.find("def _pi_ctx(")
    assert k > 0, "找不到 _pi_ctx"
    s = s[:k] + HELPER + s[k:]
    print("① _kind_ctx 已加")

# ── ② ctx 里挂上 ──
if "problem_kind=_kind_ctx" not in s:
    # 找 ctx 里 pred_int 那一行，跟在它后面
    import re
    m = re.search(r"\n(\s+)pred_int=_pi_ctx\([^)]*\),", s)
    assert m, "找不到 pred_int= 行"
    ind = m.group(1)
    ins = (f"\n{ind}problem_kind=_kind_ctx("
           f"getattr(a, 'problem', ''), ds, xs, ycol),"
           f"\n{ind}mechanism_mode=getattr(a, 'mechanism', 'auto'),")
    s = s[:m.end()] + ins + s[m.end():]
    print("② ctx 已挂 problem_kind / mechanism_mode")

# ── ③ 加 --mechanism 参数 ──
if '"--mechanism"' not in s:
    import re
    m = re.search(r'\n(\s+)ap\.add_argument\("--no-gate"', s)
    if m:
        ind = m.group(1)
        ins = (f'\n{ind}ap.add_argument("--mechanism", default="auto",\n'
               f'{ind}                    choices=["auto", "full", "brief", "none"],\n'
               f'{ind}                    help="机理段：auto 按题型选，full 完整，"'
               f'\n{ind}                         "brief 只留方向，none 跳过")')
        s = s[:m.start()] + ins + s[m.start():]
        print("③ 加了 --mechanism 参数")
    else:
        print("! ③ 找不到 --no-gate 锚点")

ast.parse(s)
compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print(f"  mmkit.py {len(s.splitlines())} 行")
