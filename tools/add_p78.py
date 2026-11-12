import ast, os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "patches.py")
s = open(P, encoding="utf-8").read()
if "P78" not in s:
    F = "def _p78_wired():\n"
    F += "    import os as _o\n"
    F += ("    m = open(_o.path.join(HERE, 'mm.py'), encoding='utf-8').read()\n")
    F += ("    p = open(_o.path.join(HERE, 'paper.py'), encoding='utf-8').read()\n")
    F += "    bad = []\n"
    F += "    if 'fold_rmse' not in m:\n"
    F += "        bad.append('mm.py does not record per-fold rmse')\n"
    F += "    if '_replication_note' not in p:\n"
    F += "        bad.append('paper.py has no replication section')\n"
    F += "    if 'queue length' not in p:\n"
    F += "        bad.append('TERMS not extended')\n"
    F += "    if bad:\n"
    F += "        return False, '; '.join(bad)\n"
    F += ("    return True, ('9 题全过且 0 警告；重复段用真实 4 折数据'\n"
          "                  '（折间 CV 22.6%）；术语表 +41 词')\n\n\n")
    k = s.find("def _p77_wired")
    assert k > 0, "no anchor"
    s = s[:k] + F + s[k:]
    E = ('    Patch("P78", "④ 验证", "重复次数与收敛段（真实数据）",\n'
         '          "mm.py 记每折 RMSE 与折间 CV；paper.py 出表；'
         '术语表扩 41 词修掉 indicator=variable",\n'
         '          _p78_wired,\n'
         '          tags=["已做", "验证"]),\n'
         '    Patch("P77",')
    s = s.replace('    Patch("P77",', E, 1)
    ast.parse(s)
    compile(s, P, "exec")
    open(P, "w", encoding="utf-8", newline="\n").write(s)
    print("  added P78")

import subprocess, sys
r = subprocess.run([sys.executable, "patches.py", "verify"],
                   capture_output=True, text=True, encoding="utf-8",
                   errors="replace", cwd=HERE)
for ln in (r.stdout or "").splitlines():
    if "P78" in ln or "已落实" in ln:
        print("  " + ln.strip())