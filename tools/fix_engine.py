import ast
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "mmkit.py")
s = open(P, encoding="utf-8").read()

OLD = ('            if _sh.which("pdflatex"):\n'
       '                _ok = False\n'
       '                for _ in range(2):      # 两遍，交叉引用才稳\n'
       '                    _p = _sp.run(\n'
       '                        ["pdflatex", "--enable-installer",')
assert OLD in s, "no pdflatex block"
NEW = ('            # 引擎按语言选：i18n 里每种语言自己声明了 engine。\n'
       '            # 原来硬编码 pdflatex，于是 --lang zh 的中文标题在\n'
       '            # pdflatex 下全变成 "Unicode character" 错误（43 个）——\n'
       '            # pdflatex 根本不认 Unicode，中文必须走 xelatex。\n'
       '            _engine = "pdflatex"\n'
       '            try:\n'
       '                _engine = _i18n.engine(ctx.get("lang") or "en")\n'
       '            except Exception:\n'
       '                _engine = "pdflatex"\n'
       '            if _sh.which(_engine):\n'
       '                _ok = False\n'
       '                for _ in range(2):      # 两遍，交叉引用才稳\n'
       '                    _p = _sp.run(\n'
       '                        [_engine, "--enable-installer",')
s = s.replace(OLD, NEW, 1)
ast.parse(s)
compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  engine now language-aware")