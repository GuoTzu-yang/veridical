import ast
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "patches.py")
s = open(P, encoding="utf-8").read()
if "P87" not in s:
    F = "def _p87_wired():\n"
    F += "    import os as _o\n"
    F += ("    m = open(_o.path.join(HERE, 'mmkit.py'), encoding='utf-8').read()\n")
    F += "    bad = []\n"
    F += "    if '_fig_hint' not in m:\n"
    F += "        bad.append('no _fig_hint')\n"
    F += "    if '_fh = _fig_hint(' not in m:\n"
    F += "        bad.append('hint not wired')\n"
    F += ("    if '\u8fd8\u6ca1\u6709\u56fe\uff0cPDF \u91cc\u53ea\u6709\u6b63\u6587' not in m:\n"
          "        bad.append('no hint text')\n")
    F += "    if bad:\n"
    F += "        return False, '; '.join(bad)\n"
    F += ("    return True, ('\u51b7\u542f\u52a8\u5b9e\u6d4b\uff1arun \u51fa 400KB PDF \u4f46\u4e00\u5f20\u56fe\u4e5f\u6ca1\u6709\uff0c'\n"
          "                  '\u8f93\u51fa\u91cc\u4e0d\u63d0\uff1b\u73b0\u5728\u7ed9\u53ef\u590d\u5236\u7684 plot \u547d\u4ee4')\n\n\n")
    k = s.find("def _p86_wired")
    assert k > 0, "no anchor"
    s = s[:k] + F + s[k:]
    E = ('    Patch("P87", "④ 验证", "冷启动 + 出图提示",\n'
         '          "解压到全新目录只按说明书跑：能出稿（400KB），但一张图都没有且不提示；'
         '现在给可复制命令",\n'
         '          _p87_wired,\n'
         '          tags=["已做", "验证"]),\n'
         '    Patch("P86",')
    s = s.replace('    Patch("P86",', E, 1)
    ast.parse(s)
    compile(s, P, "exec")
    open(P, "w", encoding="utf-8", newline="\n").write(s)
    print("  added P87")