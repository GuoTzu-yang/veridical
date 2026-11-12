import ast, os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "paper.py")
s = open(P, encoding="utf-8").read()
# 1) 去掉 Evaluation 前的调用（连同 _tex_lower 预计算）
OLD = ("    ctx[\"_tex_lower\"] = \"\\n\".join(L).lower()\n"
       "    L += _claim_ledger(ctx)\n")
assert OLD in s, "no call pair"
s = s.replace(OLD, "", 1)
# 2) 在 build 的 return 前插入（那时 L 已含全文，probes 才搜得准）
i = s.rfind("    return \"\\n\".join(L)")
if i < 0:
    for m in __import__("re").finditer(r"^    return .*join\(L\).*$", s, __import__("re").M):
        i = m.start()
assert i > 0, "no return"
INS = ("    # 「声明-证据」放在最后：probes 要在**全文**里搜，早放会把\n"
       "    # 后半部分才出现的证据（如 closed-form）误判成没做。\n"
       "    ctx[\"_tex_lower\"] = \"\\n\".join(L).lower()\n"
       "    L += _claim_ledger(ctx)\n\n")
s = s[:i] + INS + s[i:]
ast.parse(s); compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  moved to end")