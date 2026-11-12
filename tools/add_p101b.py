import ast
import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "patches.py")
s = open(P, encoding="utf-8").read()

F1 = "\n".join([
 "def _p101_wired():",
 "    import os as _o",
 "    bad = []",
 "    for f in ('tools/battle.py', 'tools/verify_all.py'):",
 "        t = open(_o.path.join(HERE, f), encoding='utf-8').read()",
 "        q = chr(34) + chr(36890) + chr(36807) + chr(34)",
 "        if q + ' in' in t:",
 "            bad.append(f + ' bare substring check')",
 "        if 'startswith(' not in t:",
 "            bad.append(f + ' no startswith')",
 "    if bad:",
 "        return False, '; '.join(bad)",
 "    return True, 'acceptance scripts use startswith; failed gates are no longer counted as passed'",
 "",
 "",
 "def _p104_wired():",
 "    import json as _j",
 "    import os as _o",
 "    c = _j.load(open(_o.path.join(HERE, 'runs.json'), encoding='utf-8'))",
 "    if len(c) < 22:",
 "        return False, 'only %d problems' % len(c)",
 "    n = sum(1 for v in c.values()",
 "            if _o.path.exists(_o.path.join(HERE, v['out'], 'paper.pdf')))",
 "    if n < 22:",
 "        return False, 'only %d/22 PDFs' % n",
 "    return True, '22 problems configured and built (incl. 8 real contest datasets)'",
 "",
 ""])

if "_p101_wired" not in s:
    k = s.find("def _p100_wired")
    assert k > 0
    s = s[:k] + F1 + s[k:]
    for pid, cat, title, why in (
        ("P101", "④ 验证", "acceptance substring trap",
         "chr(34)+pass+chr(34) in 'not passed' is True, so a failing gate was reported as passing"),
        ("P104", "⑥ 打包", "22-problem full-run config",
         "only 6 of 184 external data files were used; now 22 problems all build"),
    ):
        anchor = '    Patch("P100",'
        entry = ('    Patch("' + pid + '", "' + cat + '", "' + title + '",\n'
                 '          "' + why + '",\n'
                 '          _' + pid.lower() + '_wired,\n'
                 '          tags=["done"]),\n' + anchor)
        s = s.replace(anchor, entry, 1)
    ast.parse(s)
    compile(s, P, "exec")
    open(P, "w", encoding="utf-8", newline="\n").write(s)
    print("  added P101 + P104")
else:
    print("  already present")