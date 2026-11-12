import ast, os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "gate.py")
s = open(P, encoding="utf-8").read()
OLD = 'COMPILE_ERR = re.compile(r"(?m)^!\\s|Emergency stop|Fatal error")'
assert OLD in s, "no COMPILE_ERR"
NEW = ('# 图片缺失报的是 "! Package pdftex.def Error: File `x.pdf\' not found:\n'
       '# using draft setting" —— 行首也是 !，但它只是降级（用方框代替图），\n'
       '# 不是编译失败。图缺不缺由 chk_figures 单独管。\n'
       'COMPILE_ERR = re.compile(\n'
       '    r"(?m)^!\\s(?!Package pdftex\\.def Error)|Emergency stop|Fatal error")')
s = s.replace(OLD, NEW, 1)
ast.parse(s); compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  compile check now ignores draft-setting")