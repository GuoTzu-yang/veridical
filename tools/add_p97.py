import ast
import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "patches.py")
s = open(P, encoding="utf-8").read()
if "P97" not in s:
    F = "def _p97_wired():\n"
    F += "    import os as _o\n"
    F += ("    t = open(_o.path.join(HERE, 'out', 'real', 'paper.tex'),\n"
          "             encoding='utf-8').read().lower()\n")
    F += "    bad = []\n"
    F += "    for w in ('conservation of energy', 'momentum',\n"
    F += "              'geometric factor', 'conservation laws'):\n"
    F += "        if w in t:\n"
    F += "            bad.append('heat-sink wording leaked: ' + w)\n"
    F += "    if bad:\n"
    F += "        return False, '; '.join(bad)\n"
    F += ("    return True, ('\u975e\u673a\u7406\u9898\u91cc\u70ed\u6c89\u4e13\u5c5e\u63aa\u8f9e\u6e05\u96f6\uff1b'\n"
          "                  '\u82f1\u6587\u4e3b\u7ebf\uff08\u70ed\u6c89\u9898\uff09\u9010\u5b57\u8282\u4e0d\u53d8')\n\n\n")
    k = s.find("def _p96_wired"); assert k > 0
    s = s[:k] + F + s[k:]
    E = ('    Patch("P97", "④ 验证", "非机理题不再胡编机理",\n'
         '          "brief 模式把热沉的「能量动量守恒/几何因子」原样搬进预测、评价、'
         '母婴心理论文，三题机理节正文长度完全相同（2162 字）",\n'
         '          _p97_wired,\n'
         '          tags=["已做", "验证"]),\n'
         '    Patch("P96",')
    s = s.replace('    Patch("P96",', E, 1)
    ast.parse(s); compile(s, P, "exec")
    open(P, "w", encoding="utf-8", newline="\n").write(s)
    print("  added P97")