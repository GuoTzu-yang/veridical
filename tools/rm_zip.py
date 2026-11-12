import ast
import os
import re

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "paper.py")
s = open(P, encoding="utf-8").read()

# 删掉 _localize 里的 sections zip —— 章节标题现在由 i18n.sec() 在
# 生成时就定好了，再 zip 一遍是第二套机制（而且拿英文当模板）。
OLD = ('    en = _i18n.LANGS["en"]\n'
       '    target = _i18n.get(lang)\n'
       '    for a, b in zip(en["sections"], target["sections"]):\n'
       '        tex = tex.replace("\\\\section{" + a + "}", '
       '"\\\\section{" + b + "}")\n')
assert OLD in s, "no sections zip"
NEW = ('    target = _i18n.get(lang)\n'
       '    # 章节标题不再在这里替换：它们在生成时就由 i18n.sec() 取好了。\n'
       '    # 拿英文当模板 zip 一遍是第二套机制，改英文会连带改中文。\n')
s = s.replace(OLD, NEW, 1)

ast.parse(s)
compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  removed sections zip from _localize")