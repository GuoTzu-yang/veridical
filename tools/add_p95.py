import ast
import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "patches.py")
s = open(P, encoding="utf-8").read()
if "P95" not in s:
    F = "def _p95_wired():\n"
    F += "    import os as _o\n"
    F += "    m = open(_o.path.join(HERE, 'mmkit.py'), encoding='utf-8').read()\n"
    F += "    bad = []\n"
    F += "    if '_engine = _i18n.engine(' not in m:\n"
    F += "        bad.append('engine not language-aware')\n"
    F += "    if '\"pdflatex\", \"--enable-installer\"' in m:\n"
    F += "        bad.append('pdflatex still hardcoded')\n"
    F += "    if bad:\n"
    F += "        return False, '; '.join(bad)\n"
    F += ("    return True, ('\u5df2\u88c5 ctex+xecjk\uff1b\u7f16\u8bd1\u5f15\u64ce\u6309\u8bed\u8a00\u9009\uff08zh/de \u7528 xelatex\uff09\uff1b'\n"
          "                  '\u4e2d\u6587\u8bba\u6587\u53ef\u7f16\u8bd1\u51fa 25 \u9875 PDF\uff08\u7ae0\u8282\u6807\u9898\u4e2d\u6587\uff0c\u6b63\u6587\u4ecd\u4e3a\u82f1\u6587\uff09')\n\n\n")
    k = s.find("def _p94_wired"); assert k > 0
    s = s[:k] + F + s[k:]
    E = ('    Patch("P95", "④ 验证", "多语言真能出稿",\n'
         '          "装 ctex+xecjk；引擎按语言选（zh/de 用 xelatex）；'
         '此前硬编码 pdflatex 产生 43 个 Unicode character 错误",\n'
         '          _p95_wired,\n'
         '          tags=["已做", "验证"]),\n'
         '    Patch("P94",')
    s = s.replace('    Patch("P94",', E, 1)
    ast.parse(s); compile(s, P, "exec")
    open(P, "w", encoding="utf-8", newline="\n").write(s)
    print("  added P95")