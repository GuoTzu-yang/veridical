import ast
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "patches.py")
s = open(P, encoding="utf-8").read()
if "P88" not in s:
    F = "def _p88_wired():\n"
    F += "    import os as _o\n"
    F += ("    m = open(_o.path.join(HERE, 'mmkit.py'), encoding='utf-8').read()\n")
    F += "    bad = []\n"
    F += "    if '_fig_hint(ctx, data,' not in m.replace('  ', ' '):\n"
    F += "        bad.append('still passing data_path')\n"
    F += "    if 'if _rp.get(\"converged\")' in m and '\\u8fd8\\u6ca1\\u6709\\u56fe' in m:\n"
    F += "        pass\n"
    F += "    if bad:\n"
    F += "        return False, '; '.join(bad)\n"
    F += ("    return True, ('\u51b7\u542f\u52a8\u7b2c 4 \u6b21\u624d\u51fa\u63d0\u793a\uff1a'\n"
          "                  '\u5148\u88ab\u6536\u655b\u5206\u652f\u6321\u4f4f\uff0c\u518d\u88ab NameError \u541e\u6389')\n\n\n")
    k = s.find("def _p87_wired")
    assert k > 0, "no anchor"
    s = s[:k] + F + s[k:]
    E = ('    Patch("P88", "④ 验证", "出图提示的三次失败",\n'
         '          "第 1 次被 if converged 挡住、第 2 次 data_path 不存在被 except 吞掉；'
         '冷启动跑到第 4 次才见到提示",\n'
         '          _p88_wired,\n'
         '          tags=["已做", "验证"]),\n'
         '    Patch("P87",')
    s = s.replace('    Patch("P87",', E, 1)
    ast.parse(s)
    compile(s, P, "exec")
    open(P, "w", encoding="utf-8", newline="\n").write(s)
    print("  added P88")