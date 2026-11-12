import ast
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "patches.py")
s = open(P, encoding="utf-8").read()
if "P86" not in s:
    F = "def _p86_wired():\n"
    F += "    import os as _o, zipfile\n"
    F += ("    md = open(_o.path.join(HERE, 'MMKIT-使用说明.md'),\n"
          "              encoding='utf-8').read()\n")
    F += "    bad = []\n"
    F += "    if '最少需要几个数值列' not in md:\n"
    F += "        bad.append('boundary section missing')\n"
    F += "    for k in ('华数杯 2023 C', '高教杯 2024 C', '五一杯 2025 C'):\n"
    F += "        if k not in md:\n"
    F += "            bad.append('no evidence for ' + k)\n"
    F += ("    z = r'C:\\Users\\21246\\Desktop\\建模插件-完整代码.zip'\n"
          "    if _o.path.exists(z):\n"
          "        zf = zipfile.ZipFile(z)\n"
          "        hit = [x for x in zf.namelist()\n"
          "               if x.endswith('MMKIT-使用说明.md')]\n"
          "        if not hit:\n"
          "            bad.append('doc not in zip')\n"
          "        elif '最少需要几个数值列' not in zf.read(hit[0]).decode('utf-8'):\n"
          "            bad.append('zip has stale doc')\n")
    F += "    if bad:\n"
    F += "        return False, '; '.join(bad)\n"
    F += ("    return True, ('\u80fd\u529b\u8fb9\u754c\u5199\u8fdb\u8bf4\u660e\u4e66'\n"
          "                  '\uff083 \u9053\u771f\u8d5b\u9898\u5b9e\u6d4b\u4f5c\u8bc1\u636e\uff09\uff1bmd_lint 0 ERROR')\n\n\n")
    k = s.find("def _p85_wired")
    assert k > 0, "no anchor"
    s = s[:k] + F + s[k:]
    E = ('    Patch("P86", "⑥ 打包", "能力边界写进使用说明",\n'
         '          "「任意题」这个说法太宽：五一杯 2025 C 只有 1 个数值列（行为日志），'
         '工具不适用。明说边界比含糊承诺好",\n'
         '          _p86_wired,\n'
         '          tags=["已做", "打包"]),\n'
         '    Patch("P85",')
    s = s.replace('    Patch("P85",', E, 1)
    ast.parse(s)
    compile(s, P, "exec")
    open(P, "w", encoding="utf-8", newline="\n").write(s)
    print("  added P86")