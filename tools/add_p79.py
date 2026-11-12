import ast, os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "patches.py")
s = open(P, encoding="utf-8").read()
if "P79" not in s:
    F = "def _p79_wired():\n"
    F += "    import os as _o\n"
    F += ("    r = open(_o.path.join(HERE, 'tests', 'run_all.py'),\n"
          "             encoding='utf-8').read()\n")
    F += "    if '机制未查' not in r and '\"机制\"' not in r:\n"
    F += "        return False, 'ENTRY still checks the stale wording'\n"
    F += ("    return True, ('\u5165\u53e3\u68c0\u67e5\u5b57\u4e32\u4ece\u300c\u673a\u5236\u4e0d\u9002\u7528\u300d\u6539\u4e3a'\n"
          "                  '\u300c\u673a\u5236\u672a\u67e5\u300d\uff08\u4e09\u6001\u6587\u6848\u91cc\u8fd9\u6761\u7528\u4f8b\u843d\u5728 None \u6001\uff09')\n\n\n")
    k = s.find("def _p78_wired")
    assert k > 0, "no anchor"
    s = s[:k] + F + s[k:]
    E = ('    Patch("P79", "④ 验证", "入口检查文案跟上实现",\n'
         '          "extend.py 的 mech_s 是三态（可用/不适用/未查），'
         'run_all 还检查旧文案导致入口一直红",\n'
         '          _p79_wired,\n'
         '          tags=["已做", "验证"]),\n'
         '    Patch("P78",')
    s = s.replace('    Patch("P78",', E, 1)
    ast.parse(s)
    compile(s, P, "exec")
    open(P, "w", encoding="utf-8", newline="\n").write(s)
    print("  added P79")

import subprocess, sys
r = subprocess.run([sys.executable, "patches.py", "verify"],
                   capture_output=True, text=True, encoding="utf-8",
                   errors="replace", cwd=HERE)
for ln in (r.stdout or "").splitlines():
    if "P79" in ln or "已落实" in ln:
        print("  " + ln.strip())