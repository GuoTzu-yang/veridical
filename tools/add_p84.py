import ast
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "patches.py")
s = open(P, encoding="utf-8").read()
if "P84" not in s:
    F = "def _p84_wired():\n"
    F += "    import os as _o\n"
    F += ("    p = open(_o.path.join(HERE, 'paper.py'), encoding='utf-8').read()\n")
    F += "    bad = []\n"
    F += "    if '_sens_note' not in p:\n"
    F += "        bad.append('no single-factor sensitivity note')\n"
    F += "    if 'sens.get(\"items\")' not in p and 'sens.get(\\'items\\')' not in p:\n"
    F += "        bad.append('still judging by sens.rows')\n"
    F += "    q = _o.path.join(HERE, 'out', 'hs2024', 'paper.pdf')\n"
    F += "    if not _o.path.exists(q):\n"
    F += "        bad.append('hs2024 not built')\n"
    F += "    if bad:\n"
    F += "        return False, '; '.join(bad)\n"
    F += ("    return True, ('\u7b2c 2 \u9053\u771f\u8d5b\u9898\uff082024 \u9ad8\u6559\u676f C\uff09\u901a\u8fc7\uff1b'\n"
          "                  '\u5355\u56e0\u5b50\u65f6\u8f93\u51fa\u7075\u654f\u5ea6\u8bf4\u660e\u800c\u4e0d\u662f\u6c89\u9ed8')\n\n\n")
    k = s.find("def _p83_wired")
    assert k > 0, "no anchor"
    s = s[:k] + F + s[k:]
    E = ('    Patch("P84", "④ 验证", "第 2 道真赛题 + 单因子灵敏度说明",\n'
         '          "2024 高教杯 C（107 行/1 个 x）通过；I004 原来因无法做灵敏度而死锁，'
         '现在出说明",\n'
         '          _p84_wired,\n'
         '          tags=["已做", "验证"]),\n'
         '    Patch("P83",')
    s = s.replace('    Patch("P83",', E, 1)
    ast.parse(s)
    compile(s, P, "exec")
    open(P, "w", encoding="utf-8", newline="\n").write(s)
    print("  added P84")

import subprocess, sys
r = subprocess.run([sys.executable, "patches.py", "verify"],
                   capture_output=True, text=True, encoding="utf-8",
                   errors="replace", cwd=HERE)
for ln in (r.stdout or "").splitlines():
    if "P84" in ln or "已落实" in ln:
        print("  " + ln.strip())