import ast
import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "patches.py")
s = open(P, encoding="utf-8").read()
OLD = '          _call("verify.py", ["selftest"], "ALL PASS"),'
assert OLD in s, "no anchor"
NEW = ('          # verify.py 的 main() 现在把第一个位置参数当 tex 路径，\n'
       '          # 传 "selftest" 会被当成文件名去 open。无参数才是自测。\n'
       '          _call("verify.py", [], "ALL PASS"),')
s = s.replace(OLD, NEW, 1)
ast.parse(s); compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  P12 判据已修")