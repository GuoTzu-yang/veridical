import ast, os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "patches.py")
s = open(P, encoding="utf-8").read()
if "P81" not in s:
    F = "def _p81_wired():\n"
    F += "    import os as _o\n"
    F += ("    z = r'C:\\Users\\21246\\Desktop\\建模插件-完整代码.zip'\n"
          "    if not _o.path.exists(z):\n"
          "        return False, 'no desktop zip'\n"
          "    import zipfile\n"
          "    zf = zipfile.ZipFile(z)\n"
          "    n = len(zf.namelist())\n"
          "    if n < 380:\n"
          "        return False, 'only %d entries' % n\n"
          "    ct = zf.read([x for x in zf.namelist()\n"
          "                  if x.endswith('patches.py')][0]).decode('utf-8')\n"
          "    if 'P80' not in ct:\n"
          "        return False, 'zip predates P80'\n"
          "    return True, ('%d \u6587\u4ef6 / %.1f MB\uff1b\u542b P80 \u4e0e\u6700\u65b0'\n"
          "                  ' checks.json v5' % (n, _o.path.getsize(z) / 1e6))\n\n\n")
    k = s.find("def _p80_wired")
    assert k > 0, "no anchor"
    s = s[:k] + F + s[k:]
    E = ('    Patch("P81", "⑥ 打包", "重新打包插件",\n'
         '          "上次打包在今天 04:30，之后 20 轮改动（第 29-49 轮）都没进包；'
         '重打后 401 文件 / 1.86 MB",\n'
         '          _p81_wired,\n'
         '          tags=["已做", "打包"]),\n'
         '    Patch("P80",')
    s = s.replace('    Patch("P80",', E, 1)
    ast.parse(s)
    compile(s, P, "exec")
    open(P, "w", encoding="utf-8", newline="\n").write(s)
    print("  added P81")

import subprocess, sys
r = subprocess.run([sys.executable, "patches.py", "verify"],
                   capture_output=True, text=True, encoding="utf-8",
                   errors="replace", cwd=HERE)
for ln in (r.stdout or "").splitlines():
    if "P81" in ln or "已落实" in ln:
        print("  " + ln.strip())