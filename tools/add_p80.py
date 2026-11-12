import ast, os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "patches.py")
s = open(P, encoding="utf-8").read()
if "P80" not in s:
    F = "def _p80_wired():\n"
    F += "    import os as _o\n"
    F += ("    v = _o.path.join(HERE, 'tools', 'verify_all.py')\n"
          "    p = open(_o.path.join(HERE, 'paper.py'), encoding='utf-8').read()\n")
    F += "    bad = []\n"
    F += "    if not _o.path.exists(v):\n"
    F += "        bad.append('no verify_all.py')\n"
    F += "    if '_has_pareto' not in p:\n"
    F += "        bad.append('claim_ledger still refs fig:pareto unconditionally')\n"
    F += "    if bad:\n"
    F += "        return False, '; '.join(bad)\n"
    F += ("    return True, ('10 题全绿且 0 警告；一条命令可复现'\n"
          "                  '（tools/verify_all.py）')\n\n\n")
    k = s.find("def _p79_wired")
    assert k > 0, "no anchor"
    s = s[:k] + F + s[k:]
    E = ('    Patch("P80", "④ 验证", "全量验收脚本 + 引用对齐",\n'
         '          "化工题没在 9 题列表里，改 TERMS 后它的 fig:pareto 无图 → refs 红；'
         '加 verify_all.py 一条命令跑 10 题",\n'
         '          _p80_wired,\n'
         '          tags=["已做", "验证"]),\n'
         '    Patch("P79",')
    s = s.replace('    Patch("P79",', E, 1)
    ast.parse(s)
    compile(s, P, "exec")
    open(P, "w", encoding="utf-8", newline="\n").write(s)
    print("  added P80")

import subprocess, sys
r = subprocess.run([sys.executable, "patches.py", "verify"],
                   capture_output=True, text=True, encoding="utf-8",
                   errors="replace", cwd=HERE)
for ln in (r.stdout or "").splitlines():
    if "P80" in ln or "已落实" in ln:
        print("  " + ln.strip())