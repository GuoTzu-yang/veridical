import ast
import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "schema.py")
s = open(P, encoding="utf-8").read()
OLD = "        cmds[cmd] = dict(args=args,"
assert OLD in s, "no anchor"
NEW = ('        cmds[cmd] = dict(desc=DESC.get(cmd, ""), args=args,')
s = s.replace(OLD, NEW, 1)
ast.parse(s)
compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  desc 已接入命令条目")