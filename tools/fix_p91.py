import ast
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "patches.py")
s = open(P, encoding="utf-8").read()

i = s.find("def _p91_wired")
j = s.find("def _p90_wired")
assert i > 0 and j > i, "anchor"

BAD = chr(34) + "out" + chr(34) + ", " + chr(34) + "fig" + chr(34) + ")]"
F = 'def _p91_wired():\n'
F += "    import os as _o\n"
F += "    m = open(_o.path.join(HERE, 'mmkit.py'), encoding='utf-8').read()\n"
F += "    bad = []\n"
F += "    # 兜底目录上一轮已经删过：fig_dirs 只剩 outdir 和 outdir/fig\n"
F += "    if 'fig_dirs = [outdir, os.path.join(outdir, " + chr(34) + "fig" + chr(34) + ")]' not in m:\n"
F += "        bad.append('gif fallback changed')\n"
F += "    if " + repr(BAD) + " in m:\n"
F += "        bad.append('still borrows repo out/fig')\n"
F += "    t = _o.path.join(HERE, 'tests', 'portability.py')\n"
F += "    if not _o.path.exists(t):\n"
F += "        bad.append('no portability test')\n"
F += "    else:\n"
F += "        r = _o.path.join(HERE, 'tests', 'run_all.py')\n"
F += "        if 'portability.py' not in open(r, encoding='utf-8').read():\n"
F += "            bad.append('not in run_all')\n"
F += "    if bad:\n"
F += "        return False, '; '.join(bad)\n"
F += ("    return True, ('\u4fdd\u53ef\u79fb\u690d\u6027\u5ba1\u8ba1\uff1aCWD 0 \u5904\u3001\u76f8\u5bf9 open 0 \u5904\u3001'\n"
      "                  '\u8de8\u9898\u501f\u8def\u5f84 3 \u5904\u5168\u6e05\uff1b\u52a0\u4e3a\u56de\u5f52\u6d4b\u8bd5')\n\n\n")

s = s[:i] + F + s[j:]
ast.parse(s)
compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  rewrote _p91_wired")