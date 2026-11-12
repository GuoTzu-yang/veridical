import ast, os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "paper.py")
s = open(P, encoding="utf-8").read()
OLD = "            if any(pr in tex for pr in probes):\n                continue"
assert OLD in s, "no probe loop"
NEW = ("            if any(_probe_hit(pr, tex) for pr in probes):\n"
       "                continue")
s = s.replace(OLD, NEW, 1)

# 插入 _probe_hit（放在 _methods_missing 之前）
F = "def _probe_hit(pr, tex):\n"
F += "    \"\"\"一条 probe 是否命中。\n\n"
F += "    纯字母/数字/空格的 probe 用**词边界**匹配：\n"
F += "        'ward' 不能让 'towards' 命中，\n"
F += "        'dual' 不能让 'residual'/'individual' 命中。\n"
F += "    这两处是实测的假阳性 —— 一旦假阳性，「没做」就被当成「做了」，\n"
F += "    而 claims 这一节存在的意义正是不许这种事情发生。\n"
F += "    含特殊字符的 probe（如 'np-hard' 的连字符）按子串匹配。\n"
F += "    \"\"\"\n"
F += "    import re as _r\n"
F += "    pr = str(pr)\n"
F += "    if _r.fullmatch(r\"[a-z0-9 ]+\", pr):\n"
F += "        return _r.search(r\"\\b\" + _r.escape(pr) + r\"\\b\", tex) is not None\n"
F += "    return pr in tex\n\n\n"
k = s.find("def _methods_missing")
assert k > 0, "no _methods_missing"
s = s[:k] + F + s[k:]
ast.parse(s); compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  probe_hit wired")