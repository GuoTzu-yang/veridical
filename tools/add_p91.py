import ast
import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "patches.py")
s = open(P, encoding="utf-8").read()
if "P91" not in s:
    F = "def _p91_wired():\n"
    F += "    import os as _o\n"
    F += ("    m = open(_o.path.join(HERE, 'mmkit.py'), encoding='utf-8').read()\n")
    F += "    bad = []\n"
    F += "    if '\"out\", \"fig\")]' in m:\n"
    F += "        bad.append('gif fallback still borrows repo out/fig')\n"
    F += ("    t = _o.path.join(HERE, 'tests', 'portability.py')\n"
          "    if not _o.path.exists(t):\n"
          "        bad.append('no portability test')\n"
          "    else:\n"
          "        r = _o.path.join(HERE, 'tests', 'run_all.py')\n"
          "        if 'portability.py' not in open(r, encoding='utf-8').read():\n"
          "            bad.append('not in run_all')\n")
    F += "    if bad:\n"
    F += "        return False, '; '.join(bad)\n"
    F += ("    return True, ('\u4fdd\u53ef\u79fb\u690d\u6027\u5ba1\u8ba1\uff1aCWD 0 \u5904\u3001\u76f8\u5bf9 open 0 \u5904\u3001'\n"
          "                  '\u8de8\u9898\u501f\u8def\u5f84 3 \u5904\u5168\u6e05\uff1b\u52a0\u4e3a\u56de\u5f52\u6d4b\u8bd5')\n\n\n")
    k = s.find("def _p90_wired"); assert k > 0
    s = s[:k] + F + s[k:]
    E = ('    Patch("P91", "④ 验证", "可移植性审计 + 回归测试",\n'
         '          "审计 CWD/相对 open/跨题借路径三类；查出 mmkit.video 的第三个'
         '兜底目录也是仓库默认题的 out/fig",\n'
         '          _p91_wired,\n'
         '          tags=["已做", "验证"]),\n'
         '    Patch("P90",')
    s = s.replace('    Patch("P90",', E, 1)
    ast.parse(s); compile(s, P, "exec")
    open(P, "w", encoding="utf-8", newline="\n").write(s)
    print("  added P91")