import ast
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "patches.py")
s = open(P, encoding="utf-8").read()
if "P93" not in s:
    F = "def _p93_wired():\n"
    F += "    import os as _o\n"
    F += ("    m = open(_o.path.join(HERE, 'mmkit.py'), encoding='utf-8').read()\n")
    F += "    bad = []\n"
    F += "    if 'if _lang_now.startswith(\"en\"):' not in m:\n"
    F += "        bad.append('cjk gate not language-aware')\n"
    F += "    if '\u9700\u8981\u5b8f\u5305' not in m:\n"
    F += "        bad.append('no missing-package warning')\n"
    F += "    if bad:\n"
    F += "        return False, '; '.join(bad)\n"
    F += ("    return True, ('CJK \u603b\u95f8\u6539\u4e3a\u4ec5\u82f1\u6587\u6a21\u5f0f\u751f\u6548\uff1b'\n"
          "                  '\u4e4b\u524d\u5b83\u628a --lang zh \u7684\u4e2d\u6587\u6807\u9898\u66ff\u6210 variable\uff0c'\n"
          "                  '\u591a\u8bed\u8a00\u529f\u80fd\u88ab\u81ea\u5df1\u52a0\u7684\u5b89\u5168\u7f51\u95f7\u6b7b')\n\n\n")
    k = s.find("def _p92_wired"); assert k > 0
    s = s[:k] + F + s[k:]
    E = ('    Patch("P93", "④ 验证", "CJK 总闸按语言生效",\n'
         '          "--lang zh 的章节标题刚被 _localize 换成中文，下一行就被总闸'
         '替成 variable；多语言被自己的安全网闷死",\n'
         '          _p93_wired,\n'
         '          tags=["已做", "验证"]),\n'
         '    Patch("P92",')
    s = s.replace('    Patch("P92",', E, 1)
    ast.parse(s)
    compile(s, P, "exec")
    open(P, "w", encoding="utf-8", newline="\n").write(s)
    print("  added P93")

import subprocess, sys
r = subprocess.run([sys.executable, "patches.py", "verify"],
                   capture_output=True, text=True, encoding="utf-8",
                   errors="replace", cwd=HERE)
for ln in (r.stdout or "").splitlines():
    if "P93" in ln or "已落实" in ln:
        print("  " + ln.strip())