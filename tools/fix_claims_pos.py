import ast, os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "paper.py")
L = open(P, encoding="utf-8").read().splitlines(True)
# 1) 删掉错插的两行（338-339，1-based）
del L[337:339]
src = "".join(L)
# 2) 在 build 的 return tex 之前插入
OLD = "    return tex   # 必须返回 tex"
assert OLD in src, "no return tex"
INS = ("    # 「声明-证据」放在 build 最后：probes 要在**全文**里搜，\n"
       "    # 早放会把后半部分才出现的证据（closed-form 等）误判成没做。\n"
       "    ctx[\"_tex_lower\"] = tex.lower()\n"
       "    tex = tex + \"\\n\" + \"\\n\".join(_claim_ledger(ctx))\n")
src = src.replace(OLD, INS + OLD, 1)
ast.parse(src); compile(src, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(src)
print("  fixed")