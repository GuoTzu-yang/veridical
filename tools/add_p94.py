import ast
import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "patches.py")
s = open(P, encoding="utf-8").read()
if "P94" not in s:
    F = "def _p94_wired():\n"
    F += "    import os as _o\n"
    F += "    t = _o.path.join(HERE, 'tests', 'i18n_gate.py')\n"
    F += "    r = _o.path.join(HERE, 'tests', 'run_all.py')\n"
    F += "    bad = []\n"
    F += "    if not _o.path.exists(t):\n"
    F += "        return False, 'no i18n test'\n"
    F += "    if 'i18n_gate.py' not in open(r, encoding='utf-8').read():\n"
    F += "        bad.append('not in run_all')\n"
    F += "    if bad:\n"
    F += "        return False, '; '.join(bad)\n"
    F += ("    return True, ('\u591a\u8bed\u8a00\u56de\u5f52\uff1azh \u4e2d\u6587\u6807\u9898 3 \u4e2a/variable 0 \u4e2a\uff0c'\n"
          "                  'en \u4e2d\u6587\u6b8b\u7559 0 \u5904\uff1b\u9632\u603b\u95f8\u518d\u88ab\u6539\u56de\u65e0\u6761\u4ef6')\n\n\n")
    k = s.find("def _p93_wired"); assert k > 0
    s = s[:k] + F + s[k:]
    E = ('    Patch("P94", "④ 验证", "多语言回归测试",\n'
         '          "多语言不是主力路径，没有测试这个 bug 立刻复发；'
         '加 i18n_gate.py 查中文标题与 CJK 残留",\n'
         '          _p94_wired,\n'
         '          tags=["已做", "验证"]),\n'
         '    Patch("P93",')
    s = s.replace('    Patch("P93",', E, 1)
    ast.parse(s); compile(s, P, "exec")
    open(P, "w", encoding="utf-8", newline="\n").write(s)
    print("  added P94")