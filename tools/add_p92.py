import ast
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "patches.py")
s = open(P, encoding="utf-8").read()
if "P92" not in s:
    F = "def _p92_wired():\n"
    F += "    import os as _o\n"
    F += "    bad = []\n"
    F += "    d = _o.path.join(HERE, 'out', 'data')\n"
    F += "    if not _o.path.isdir(d):\n"
    F += "        return False, 'no out/data'\n"
    F += "    n = len([x for x in _o.listdir(d) if x.endswith('.xlsx')])\n"
    F += "    if n < 10:\n"
    F += "        bad.append('only %d datasets in out/data' % n)\n"
    F += "    if _o.path.isdir(_o.path.join(HERE, 'out', 'kinds')):\n"
    F += "        bad.append('out/kinds still exists')\n"
    F += "    t = open(_o.path.join(HERE, 'tools', 'test_domains.py'), encoding='utf-8').read()\n"
    F += "    if 'DATA = os.path.join(HERE, \"out\", \"data\")' not in t:\n"
    F += "        bad.append('test_domains does not write to out/data')\n"
    F += "    if bad:\n"
    F += "        return False, '; '.join(bad)\n"
    F += ("    return True, ('out/ \u5206\u4e3a data/(\u6570\u636e) + domains/(\u4ea7\u7269) + fig/(\u9ed8\u8ba4\u9898)\uff1b'\n"
          "                  '\u5220\u6389 3 \u4e2a\u4e34\u65f6\u4ea7\u7269\u76ee\u5f55\uff1b%d \u4e2a\u6570\u636e\u96c6\u5f52\u4f4d' % n)\n\n\n")
    k = s.find("def _p91_wired"); assert k > 0
    s = s[:k] + F + s[k:]
    E = ('    Patch("P92", "⑥ 打包", "out/ 目录结构整理",\n'
         '          "数据与产物混在一起是这几轮路径反复出错的根源；'
         '现在数据统一在 out/data/，产物在 out/domains/，删掉 3 个临时目录",\n'
         '          _p92_wired,\n'
         '          tags=["已做", "打包"]),\n'
         '    Patch("P91",')
    s = s.replace('    Patch("P91",', E, 1)
    ast.parse(s)
    compile(s, P, "exec")
    open(P, "w", encoding="utf-8", newline="\n").write(s)
    print("  added P92")

import subprocess, sys
r = subprocess.run([sys.executable, "patches.py", "verify"],
                   capture_output=True, text=True, encoding="utf-8",
                   errors="replace", cwd=HERE)
for ln in (r.stdout or "").splitlines():
    if "P92" in ln or "已落实" in ln:
        print("  " + ln.strip())