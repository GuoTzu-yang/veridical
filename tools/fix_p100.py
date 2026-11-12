import ast
import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "patches.py")
s = open(P, encoding="utf-8").read()
OLD = ("    rd = zf.read([n for n in names\n"
       "                  if n.endswith('README.md')][0]).decode('utf-8')\n"
       "    if 'battle.py' not in rd:\n"
       "        bad.append('README does not mention battle.py')")
assert OLD in s, "no anchor"
NEW = ("    # pack.py 写的是 README-如何运行.md（根目录那个 README.md 是\n"
       "    # 255 KB 的架构文档，不是使用说明）。判据要看对文件。\n"
       "    _rd = [n for n in names if n.endswith('README-如何运行.md')]\n"
       "    if not _rd:\n"
       "        bad.append('no README-如何运行.md')\n"
       "    else:\n"
       "        rd = zf.read(_rd[0]).decode('utf-8')\n"
       "        if 'battle.py' not in rd:\n"
       "            bad.append('usage README does not mention battle.py')")
s = s.replace(OLD, NEW, 1)
ast.parse(s); compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  fixed P100 judgement")