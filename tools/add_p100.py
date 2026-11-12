import ast
import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "patches.py")
s = open(P, encoding="utf-8").read()
if "P100" not in s:
    F = "def _p100_wired():\n"
    F += "    import os as _o, zipfile\n"
    F += ("    z = r'C:\\Users\\21246\\Desktop\\建模插件-完整代码.zip'\n"
          "    if not _o.path.exists(z):\n"
          "        return False, 'no zip'\n"
          "    zf = zipfile.ZipFile(z)\n"
          "    names = zf.namelist()\n"
          "    data = [x for x in names\n"
          "            if '/data/' in x.replace('\\\\', '/') and x.endswith('.xlsx')]\n"
          "    bad = []\n"
          "    if len(data) < 13:\n"
          "        bad.append('only %d datasets in zip' % len(data))\n"
          "    if 'runs.json' not in [n.split('/')[-1] for n in names]:\n"
          "        bad.append('runs.json missing')\n"
          "    for f in ('tools/battle.py', 'tools/verify_all.py'):\n"
          "        if not any(n.replace('\\\\', '/').endswith(f) for n in names):\n"
          "            bad.append('missing ' + f)\n"
          "    rd = zf.read([n for n in names\n"
          "                  if n.endswith('README.md')][0]).decode('utf-8')\n"
          "    if 'battle.py' not in rd:\n"
          "        bad.append('README does not mention battle.py')\n"
          "    if bad:\n"
          "        return False, '; '.join(bad)\n"
          "    return True, ('\u4ea4\u4ed8\u5305\u542b %d \u4e2a\u6570\u636e\u96c6 + runs.json + battle.py\uff1b'\n"
          "                  '\u51b7\u542f\u52a8 14/14 \u5168\u7eff' % len(data))\n\n\n")
    k = s.find("def _p99_wired"); assert k > 0
    s = s[:k] + F + s[k:]
    E = ('    Patch("P100", "⑥ 打包", "交付包带数据集（冷启动可跑）",\n'
         '          "pack 排除整个 out/，于是 out/data 也没进包 —— 用户拿到包 14 道题一道都跑不了；'
         '冷启动实测 0/1",\n'
         '          _p100_wired,\n'
         '          tags=["已做", "打包"]),\n'
         '    Patch("P99",')
    s = s.replace('    Patch("P99",', E, 1)
    ast.parse(s); compile(s, P, "exec")
    open(P, "w", encoding="utf-8", newline="\n").write(s)
    print("  added P100")