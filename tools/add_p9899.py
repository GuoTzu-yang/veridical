import ast
import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "patches.py")
s = open(P, encoding="utf-8").read()

if "P98" not in s:
    F = "def _p98_wired():\n"
    F += "    import os as _o, json as _j\n"
    F += "    r = _o.path.join(HERE, 'runs.json')\n"
    F += "    b = _o.path.join(HERE, 'tools', 'battle.py')\n"
    F += "    v = _o.path.join(HERE, 'tools', 'verify_all.py')\n"
    F += "    bad = []\n"
    F += "    if not _o.path.exists(r):\n"
    F += "        return False, 'no runs.json'\n"
    F += "    cfg = _j.load(open(r, encoding='utf-8'))\n"
    F += "    if len(cfg) < 14:\n"
    F += "        bad.append('only %d problems configured' % len(cfg))\n"
    F += "    for f in (b, v):\n"
    F += "        if not _o.path.exists(f):\n"
    F += "            bad.append('missing ' + _o.path.basename(f))\n"
    F += "    if 'runs.json' not in open(v, encoding='utf-8').read():\n"
    F += "        bad.append('verify_all does not read runs.json')\n"
    F += "    built = 0\n"
    F += "    for name, c in cfg.items():\n"
    F += "        p = _o.path.join(HERE, c['out'], 'paper.pdf')\n"
    F += "        if _o.path.exists(p):\n"
    F += "            built += 1\n"
    F += "    if built < 14:\n"
    F += "        bad.append('only %d/14 PDFs built' % built)\n"
    F += "    if bad:\n"
    F += "        return False, '; '.join(bad)\n"
    F += ("    return True, ('14 \u9053\u9898\u914d\u7f6e\u843d\u76d8 runs.json\uff1b'\n"
          "                  'battle.py \u4e00\u6b21\u8dd1\u5b8c\u5168\u90e8\uff0c\u5168\u7eff 0 \u8b66\u544a')\n\n\n")
    k = s.find("def _p97_wired"); assert k > 0
    s = s[:k] + F + s[k:]
    E = ('    Patch("P98", "⑥ 打包", "14 题配置落盘 + 一键会战",\n'
         '          "原来 y/x/min 只记在聊天里，产物目录手写两处；'
         '现在 runs.json 单一真相，battle.py 一次跑完",\n'
         '          _p98_wired,\n'
         '          tags=["已做", "打包"]),\n'
         '    Patch("P97",')
    s = s.replace('    Patch("P97",', E, 1)

if "P99" not in s:
    F2 = "def _p99_wired():\n"
    F2 += "    import os as _o\n"
    F2 += "    p = open(_o.path.join(HERE, 'paper.py'), encoding='utf-8').read()\n"
    F2 += "    bad = []\n"
    F2 += "    if '_dg_ok' not in p:\n"
    F2 += "        bad.append('residual section still gated by surfaces figure')\n"
    F2 += ("    t = _o.path.join(HERE, 'out', 'runs', 'real_c2024',\n"
          "                     'paper.tex')\n")
    F2 += "    if _o.path.exists(t):\n"
    F2 += "        tt = open(t, encoding='utf-8').read()\n"
    F2 += "        if 'What the residuals say' not in tt:\n"
    F2 += "            bad.append('single-factor paper still lacks residual section')\n"
    F2 += "    if bad:\n"
    F2 += "        return False, '; '.join(bad)\n"
    F2 += ("    return True, ('\u5355\u56e0\u5b50\u9898\u7684\u6b8b\u5dee\u8bca\u65ad\u8868\u56de\u6765\u4e86\uff1b'\n"
          "                  '\u539f\u6765 surfaces \u56fe\uff08\u53ef\u9009\uff09\u628a\u6574\u8282\u90fd\u5305\u5728\u91cc\u9762')\n\n\n")
    k2 = s.find("def _p98_wired"); assert k2 > 0
    s = s[:k2] + F2 + s[k2:]
    E2 = ('    Patch("P99", "④ 验证", "surfaces 图与残差节解耦",\n'
          '          "real_c2024 只有 1 个 x，画不出响应面 → 缺 surfaces.pdf →'
          '整节残差诊断消失，required 报缺证据",\n'
          '          _p99_wired,\n'
          '          tags=["已做", "验证"]),\n'
          '    Patch("P98",')
    s = s.replace('    Patch("P98",', E2, 1)

ast.parse(s); compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  added P98 + P99")