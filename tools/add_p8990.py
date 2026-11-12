import ast
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "patches.py")
s = open(P, encoding="utf-8").read()

if "P89" not in s:
    F = "def _p89_wired():\n"
    F += "    import os as _o\n"
    F += ("    m = open(_o.path.join(HERE, 'mmkit.py'), encoding='utf-8').read()\n")
    F += "    bad = []\n"
    F += "    if '_auto_figs' not in m:\n"
    F += "        bad.append('no _auto_figs')\n"
    F += "    if 'ys = str(ycol)' not in m:\n"
    F += "        bad.append('still translating names for plot')\n"
    F += "    if bad:\n"
    F += "        return False, '; '.join(bad)\n"
    F += ("    return True, ('run --compile \u4e00\u6761\u547d\u4ee4\u51fa\u5b8c\u6574\u7a3f\uff0812 \u5f20\u56fe\uff09\uff1b'\n"
          "                  '\u4e2d\u95f4\u8e29\u4e86 describe \u7ffb\u8bd1\u5bfc\u81f4\u53ea\u51fa 3 \u5f20')\n\n\n")
    k = s.find("def _p88_wired"); assert k > 0
    s = s[:k] + F + s[k:]
    E = ('    Patch("P89", "④ 验证", "run 自动出 12 张图",\n'
         '          "冷启动出稿但没有图、还要手动跑 12 条命令；自动出图后第一次只出 3 张，'
         '因为传了翻译后的列名",\n'
         '          _p89_wired,\n'
         '          tags=["已做", "验证"]),\n'
         '    Patch("P88",')
    s = s.replace('    Patch("P88",', E, 1)

if "P90" not in s:
    F2 = "def _p90_wired():\n"
    F2 += "    import os as _o\n"
    F2 += ("    p = open(_o.path.join(HERE, 'paper.py'), encoding='utf-8').read()\n")
    F2 += "    bad = []\n"
    F2 += "    for kind in ('surfaces', 'tornado', 'cand'):\n"
    F2 += "        if ('out\", \"fig\", \"' + kind) in p:\n"
    F2 += "            bad.append('still hardcoded ' + kind)\n"
    F2 += "    if 'tab:diag' not in p:\n"
    F2 += "        bad.append('no tab:diag')\n"
    F2 += "    if bad:\n"
    F2 += "        return False, '; '.join(bad)\n"
    F2 += ("    return True, ('paper.py \u91cc 3 \u5904\u786c\u7f16\u7801 <repo>/out/fig/*.pdf '\n"
           "                  '\u6539\u6210\u7528 ctx[figures]\uff1b\u6b8b\u5dee\u8bca\u65ad\u8868\u5c31\u57cb\u5728\u90a3\u4e2a\u5206\u652f\u91cc')\n\n\n")
    k2 = s.find("def _p89_wired"); assert k2 > 0
    s = s[:k2] + F2 + s[k2:]
    E2 = ('    Patch("P90", "④ 验证", "三处硬编码图路径",\n'
          '          "surfaces/tornado/cand 写死 <repo>/out/fig/，换目录跑整节静默消失；'
          '冷启动因此缺 1 条 required 证据",\n'
          '          _p90_wired,\n'
          '          tags=["已做", "验证"]),\n'
          '    Patch("P89",')
    s = s.replace('    Patch("P89",', E2, 1)

ast.parse(s)
compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  added P89 + P90")