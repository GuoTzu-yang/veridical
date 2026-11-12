import ast
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "patches.py")
s = open(P, encoding="utf-8").read()
if "P85" not in s:
    F = "def _p85_wired():\n"
    F += "    import os as _o\n"
    F += ("    p = open(_o.path.join(HERE, 'paper.py'), encoding='utf-8').read()\n"
          "    g = open(_o.path.join(HERE, 'gate.py'), encoding='utf-8').read()\n")
    F += "    bad = []\n"
    F += "    if 's.replace(\"_\", \" \")' not in p:\n"
    F += "        bad.append('describe still keeps underscores')\n"
    F += "    if '\u6ca1\u6709 paper.pdf\uff0c\u53ea\u6709 tex \u4e0d\u7b97\u51fa\u7a3f' not in g:\n"
    F += "        bad.append('chk_pdf still reports N/A')\n"
    F += "    if bad:\n"
    F += "        return False, '; '.join(bad)\n"
    F += ("    return True, ('\u4e0b\u5212\u7ebf\u4e00\u6b21\u4ea7\u751f 15 \u5904\u7f16\u8bd1\u9519\u8bef\uff1b'\n"
          "                  'pdf \u7f3a\u5931\u4ece N/A \u6539\u4e3a FAIL\uff0812 \u9898\u5168\u7eff\uff09')\n\n\n")
    k = s.find("def _p84_wired")
    assert k > 0, "no anchor"
    s = s[:k] + F + s[k:]
    E = ('    Patch("P85", "④ 验证", "列名下划线 + pdf 硬门",\n'
         '          "yield_per_mu 的 _ 被当数学下标 → 15 处 Missing $；'
         'chk_pdf 缺文件报 N/A 让硬门形同虚设",\n'
         '          _p85_wired,\n'
         '          tags=["已做", "验证"]),\n'
         '    Patch("P84",')
    s = s.replace('    Patch("P84",', E, 1)
    ast.parse(s)
    compile(s, P, "exec")
    open(P, "w", encoding="utf-8", newline="\n").write(s)
    print("  added P85")

import subprocess, sys
r = subprocess.run([sys.executable, "patches.py", "verify"],
                   capture_output=True, text=True, encoding="utf-8",
                   errors="replace", cwd=HERE)
for ln in (r.stdout or "").splitlines():
    if "P85" in ln or "已落实" in ln:
        print("  " + ln.strip())