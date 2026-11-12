import ast, os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "paper.py")
s = open(P, encoding="utf-8").read()
OLD = ('            _PARA_SEEN.append((_k, " ".join(str(txt).split())))\n'
       '            _t = _PARA_OVERRIDES.get(_k, txt)\n'
       '            L.append(_t)')
assert OLD in s, "no anchor"
NEW = ('            _t = _PARA_OVERRIDES.get(_k, txt)\n'
       '            # 记「实际用的文本」，不是模板原文 —— 否则 skeleton\n'
       '            # 导出后看不出哪段被替换过（实测踩过）。\n'
       '            _PARA_SEEN.append((_k, " ".join(str(_t).split())))\n'
       '            L.append(_t)')
s = s.replace(OLD, NEW, 1)
ast.parse(s); compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  dump_skeleton 现在记实际文本")