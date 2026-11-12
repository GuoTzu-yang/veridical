import ast
import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "orchestrate.py")
s = open(P, encoding="utf-8").read()
OLD = ('    cols = [str(c) for c in (ctx.get("columns") or [])]\n'
       '    data = ctx.get("data") or ""\n'
       '    cmds = ctx.get("commands") or {}')
assert OLD in s, "no anchor"
NEW = ('    cols = [str(c) for c in (ctx.get("columns") or [])]\n'
       '    data = ctx.get("data") or ""\n'
       '    cmds = ctx.get("commands") or {}\n'
       '    # 调用方（比如手工构造 ctx 的测试）可能没带能力清单；\n'
       '    # 这里自己补一份，免得整条 propose 静默返回 0 条。\n'
       '    if not cmds:\n'
       '        try:\n'
       '            import schema as _sc\n'
       '            cmds = _sc.build()["commands"]\n'
       '        except Exception:                       # noqa: BLE001\n'
       '            cmds = {}\n'
       '    # 列名同理：没带就从数据里读\n'
       '    if not cols and data:\n'
       '        try:\n'
       '            import mm as _mm\n'
       '            cols = list(_mm.DS(data).num_names)\n'
       '        except Exception:                       # noqa: BLE001\n'
       '            cols = []')
s = s.replace(OLD, NEW, 1)
ast.parse(s); compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  rule_propose 现在自补 commands/columns")