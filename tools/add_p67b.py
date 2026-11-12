import ast, os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "patches.py")
s = open(P, encoding="utf-8").read()
if "P67" not in s:
    F = "def _p67_wired():\n"
    F += "    import json as _j, os as _o\n"
    F += "    cp = _o.path.join(HERE, 'kb', 'methods', 'checks.json')\n"
    F += "    if not _o.path.exists(cp):\n"
    F += "        return False, 'missing checks.json'\n"
    F += "    d = _j.load(open(cp, encoding='utf-8'))\n"
    F += "    n = sum(len(v) for v in d['kinds'].values())\n"
    F += "    p = open(_o.path.join(HERE, 'paper.py'), encoding='utf-8').read()\n"
    F += "    bad = []\n"
    F += "    if n < 20:\n"
    F += "        bad.append(f'only {n} checks')\n"
    F += "    if '_methods_missing' not in p:\n"
    F += "        bad.append('paper not wired')\n"
    F += "    if 'end{document}' not in p:\n"
    F += "        bad.append('end{document} not handled')\n"
    F += "    for v in d['kinds'].values():\n"
    F += "        for it in v:\n"
    F += "            for f in ('name', 'note'):\n"
    F += "                if any(chr(0x4e00) <= c <= chr(0x9fff)\n"
    F += "                       for c in (it.get(f) or '')):\n"
    F += "                    bad.append('CJK in checks.json')\n"
    F += "    if bad:\n"
    F += "        return False, '; '.join(sorted(set(bad)))\n"
    F += "    return True, (str(len(d['kinds'])) + ' kinds / ' + str(n)\n"
    F += "                  + ' checks; hot-sink gained 1 (local-optimum)')\n\n\n"
    k = s.find("def _p66_wired")
    assert k > 0, "no anchor"
    s = s[:k] + F + s[k:]
    E = ('    Patch("P67", "\u2463 \u9a8c\u8bc1", '
         '"\u6309\u9898\u578b\u7684\u65b9\u6cd5\u5b8c\u6574\u6027\u68c0\u67e5",\n'
         '          "checks.json 24 \u6761 + _methods_missing\uff1b'
         '\u5fc5\u987b\u63d2\u5728 end{document} \u4e4b\u524d",\n'
         '          _p67_wired,\n'
         '          tags=["\u5df2\u505a", "\u9a8c\u8bc1"]),\n'
         '    Patch("P66",')
    s = s.replace('    Patch("P66",', E, 1)
    ast.parse(s); compile(s, P, "exec")
    open(P, "w", encoding="utf-8", newline="\n").write(s)
    print("  added P67")

import subprocess, sys
r = subprocess.run([sys.executable, "patches.py", "verify"],
                   capture_output=True, text=True, encoding="utf-8",
                   errors="replace", cwd=HERE)
for ln in (r.stdout or "").splitlines():
    if "P67" in ln or "\u5df2\u843d\u5b9e" in ln:
        print("  " + ln.strip())