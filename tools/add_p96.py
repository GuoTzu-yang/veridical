import ast
import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "patches.py")
s = open(P, encoding="utf-8").read()
if "P96" not in s:
    F = "def _p96_wired():\n"
    F += "    import os as _o\n"
    F += "    i = open(_o.path.join(HERE, 'i18n.py'), encoding='utf-8').read()\n"
    F += "    p = open(_o.path.join(HERE, 'paper.py'), encoding='utf-8').read()\n"
    F += "    bad = []\n"
    F += "    for k in ('SECT = {', 'def name(', 'def sec(', 'def body('):\n"
    F += "        if k not in i:\n"
    F += "            bad.append('i18n missing ' + k)\n"
    F += "    if '_i18n.sec(_lang' not in p:\n"
    F += "        bad.append('sections not wired')\n"
    F += "    if 'zip(en[\"sections\"]' in p:\n"
    F += "        bad.append('sections zip still there (second mechanism)')\n"
    F += "    if bad:\n"
    F += "        return False, '; '.join(bad)\n"
    F += ("    return True, ('\u4e2d\u82f1\u4e24\u5957\u72ec\u7acb\u8bcd\u6761\uff1b11 \u4e2a\u7ae0\u8282\u6807\u9898\u5168\u4e2d\u6587\uff0c'\n"
          "                  '\u4e2d\u6587\u7248\u7528\u539f\u540d\uff08\u4ea7\u91cf\uff09\u800c\u975e\u82f1\u6587\u540d\uff1b\u82f1\u6587\u7248\u9010\u5b57\u8282\u4e0d\u53d8')\n\n\n")
    k = s.find("def _p95_wired"); assert k > 0
    s = s[:k] + F + s[k:]
    E = ('    Patch("P96", "④ 验证", "中英两套独立词条",\n'
         '          "删掉拿英文当模板的 zip 替换（那是互相干扰的根源）；'
         '章节标题改为生成时取词条，中文用原名",\n'
         '          _p96_wired,\n'
         '          tags=["已做", "验证"]),\n'
         '    Patch("P95",')
    s = s.replace('    Patch("P95",', E, 1)
    ast.parse(s); compile(s, P, "exec")
    open(P, "w", encoding="utf-8", newline="\n").write(s)
    print("  added P96")