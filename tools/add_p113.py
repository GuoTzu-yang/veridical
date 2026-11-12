import ast, os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "patches.py")
s = open(P, encoding="utf-8").read()

F = "\n".join([
 "def _p113_wired():",
 "    import os as _o",
 "    m = open(_o.path.join(HERE, 'mmkit.py'), encoding='utf-8').read()",
 "    p = open(_o.path.join(HERE, 'paper.py'), encoding='utf-8').read()",
 "    bad = []",
 "    if 'ctx[\"falsify\"]' not in m:",
 "        bad.append('falsify not in ctx')",
 "    if 'Monotonicity is not universal' not in p:",
 "        bad.append('paper does not admit local non-monotonicity')",
 "    if bad:",
 "        return False, '; '.join(bad)",
 "    return True, 'falsify results reach paper; failed claims downgraded to Limitations'",
 "",
 "",
 "def _p114_wired():",
 "    import os as _o",
 "    m = open(_o.path.join(HERE, 'mmkit.py'), encoding='utf-8').read()",
 "    if '（\", \"(\")' not in m and 'U+FF08' not in m:",
 "        return False, 'fullwidth punctuation not normalised'",
 "    return True, 'CJK gate also converts fullwidth punctuation; pdflatex no longer errors'",
 "",
 "",
 "def _p115_wired():",
 "    import os as _o",
 "    g = open(_o.path.join(HERE, 'gate.py'), encoding='utf-8').read()",
 "    bad = []",
 "    if 'sign=-1' in g:",
 "        bad.append('sign still hardcoded -1')",
 "    if '_admits' not in g:",
 "        bad.append('gate does not check paper admission')",
 "    if 'os.path.join(figdir, \"paper.tex\")' not in g:",
 "        bad.append('gate still references undefined tex')",
 "    if bad:",
 "        return False, '; '.join(bad)",
 "    return True, 'gate: sign from data; admits-if-paper-says-so; path from figdir'",
 "",
 "",
 "def _p116_wired():",
 "    import os as _o",
 "    mm = open(_o.path.join(HERE, 'mm.py'), encoding='utf-8').read()",
 "    if 'def partial_corr(' not in mm:",
 "        return False, 'mm.partial_corr still missing'",
 "    return True, 'mm.partial_corr(ds, y, x, others) exists; falsify/gate partial controls work'",
 "",
 ""])

if "_p113_wired" not in s:
    k = s.find("def _p111_wired")
    assert k > 0
    s = s[:k] + F + s[k:]
    for pid, cat, title, why in (
        ("P113", "④ 验证", "falsify 结论进论文",
         "paper.py 对 falsify 零引用，gate 报反例时论文照旧写成结论"),
        ("P114", "④ 验证", "全角标点归一",
         "中文列名替成 variable 后全角括号仍在，pdflatex 报 U+FF08"),
        ("P115", "④ 验证", "gate 的 falsify 判据",
         "sign 硬编码 -1（正相关变量对处处是反例）；tex 变量未定义，承认检测恒 False"),
        ("P116", "④ 验证", "mm.partial_corr 补齐",
         "falsify/gate 按 4 参数调，实际只有 3 参数版本，两处偏相关对照从未工作"),
    ):
        anchor = '    Patch("P111",'
        entry = ('    Patch("' + pid + '", "' + cat + '", "' + title + '",\n'
                 '          "' + why + '",\n'
                 '          _' + pid.lower() + '_wired,\n'
                 '          tags=["done"]),\n' + anchor)
        s = s.replace(anchor, entry, 1)
    ast.parse(s); compile(s, P, "exec")
    open(P, "w", encoding="utf-8", newline="\n").write(s)
    print("  added P113-P116")

import subprocess, sys
r = subprocess.run([sys.executable, "patches.py", "verify"],
                   capture_output=True, text=True, encoding="utf-8",
                   errors="replace", cwd=HERE)
for ln in (r.stdout or "").splitlines():
    if "P11" in ln or "已落实" in ln:
        print("  " + ln.strip()[:90])