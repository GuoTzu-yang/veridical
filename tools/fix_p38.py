import ast
import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "patches.py")
s = open(P, encoding="utf-8").read()
OLD = ('    miss = [k for k, v in {\n'
       '        "机理节": "Mechanistic basis" in p,')
assert OLD in s, "no anchor"
NEW = ('    # 章节标题的文本搬到 i18n.py 的 SECT 里了（英文那份逐字照抄），\n'
       '    # 所以判据也跟着走 —— 否则重构一次就误报。\n'
       '    it = open(os.path.join(HERE, "i18n.py"), encoding="utf-8").read()\n'
       '    miss = [k for k, v in {\n'
       '        "机理节": ("Mechanistic basis" in p or\n'
       '                   \'"mech": "Mechanistic basis"\' in it),')
s = s.replace(OLD, NEW, 1)
ast.parse(s); compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  fixed P38 judgement")