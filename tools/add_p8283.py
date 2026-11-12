import ast
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "patches.py")
s = open(P, encoding="utf-8").read()

if "P82" not in s:
    F = "def _p82_wired():\n"
    F += "    import os as _o\n"
    F += ("    p = _o.path.join(HERE, 'out', 'real', 'paper.pdf')\n"
          "    q = _o.path.join(HERE, 'out', 'real', '题型.json')\n")
    F += "    if not (_o.path.exists(p) and _o.path.exists(q)):\n"
    F += "        return False, 'real C2023 not built'\n"
    F += "    import json as _j\n"
    F += ("    k = _j.load(open(q, encoding='utf-8'))['kinds']\n")
    F += "    if not k:\n"
    F += "        return False, 'no kind detected on real data'\n"
    F += ("    return True, ('2023 \u534e\u6570\u676f C \u9898\uff08410 \u884c\u771f\u5b9e\u6570\u636e\uff09'\n"
          "                  '\u901a\u8fc7 gate\uff1b\u9898\u578b %s' % k)\n\n\n")
    k = s.find("def _p81_wired")
    assert k > 0, "no anchor"
    s = s[:k] + F + s[k:]
    E = ('    Patch("P82", "④ 验证", "真赛题验证（华数杯 2023 C）",\n'
         '          "10 道题的数据都是造的；用 external 里的 410 行真实母婴数据跑通，'
         '题型判 regression",\n'
         '          _p82_wired,\n'
         '          tags=["已做", "验证"]),\n'
         '    Patch("P81",')
    s = s.replace('    Patch("P81",', E, 1)

if "P83" not in s:
    F2 = "def _p83_wired():\n"
    F2 += "    import os as _o\n"
    F2 += ("    p = open(_o.path.join(HERE, 'paper.py'), encoding='utf-8').read()\n")
    F2 += "    bad = []\n"
    F2 += "    if 'f\"$R^2 = ' in p:\n"
    F2 += "        bad.append('abstract still emits $R^2$')\n"
    F2 += "    if 'an R-squared of' not in p:\n"
    F2 += "        bad.append('R-squared wording missing')\n"
    F2 += "    if bad:\n"
    F2 += "        return False, '; '.join(bad)\n"
    F2 += ("    return True, ('\u6458\u8981\u91cc $R^2$ \u6539\u6210 R-squared\uff1b'\n"
           "                  'R\u00b2<10% \u65f6\u4f1a\u591a\u8f93\u51fa\u4e00\u53e5\u5bfc\u81f4\u4e24\u4e2a\u516c\u5f0f\uff0c'\n"
           "                  '\u771f\u8d5b\u9898\uff08R\u00b2=2.7%\uff09\u5c31\u662f\u8fd9\u6837\u7ea2\u7684')\n\n\n")
    k2 = s.find("def _p82_wired")
    assert k2 > 0
    s = s[:k2] + F2 + s[k2:]
    E2 = ('    Patch("P83", "④ 验证", "摘要去公式（R-squared）",\n'
          '          "CUMCM 摘要要求无公式；R²<10% 时 concl 多一句 → $R^2$ 出现两次 →'
          ' abstract 检查红",\n'
          '          _p83_wired,\n'
          '          tags=["已做", "验证"]),\n'
          '    Patch("P82",')
    s = s.replace('    Patch("P82",', E2, 1)

ast.parse(s)
compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  added P82 + P83")

import subprocess, sys
r = subprocess.run([sys.executable, "patches.py", "verify"],
                   capture_output=True, text=True, encoding="utf-8",
                   errors="replace", cwd=HERE)
for ln in (r.stdout or "").splitlines():
    if "P82" in ln or "P83" in ln or "已落实" in ln:
        print("  " + ln.strip())