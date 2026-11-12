import ast
import os
import re

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "patches.py")
s = open(P, encoding="utf-8").read()
OLD = ("    if 'f\"$R^2 = ' in p:\n"
       "        bad.append('abstract still emits $R^2$')\n")
NEW = ("    # 只查摘要范围：正文（Goodness of fit / Limitations）里 $R^2$\n"
       "    # 是合法的，全局 grep 会把它也当成残留。\n"
       "    import re as _r\n"
       "    _m = _r.search(r'\\\\\\\\begin\\\\{abstract\\\\}(.*?)'\n"
       "                   r'\\\\\\\\end\\\\{abstract\\\\}', p, _r.S)\n"
       "    if _m and '$' in _m.group(1):\n"
       "        bad.append('abstract still emits math')\n")
assert OLD in s, "no old block"
s = s.replace(OLD, NEW, 1)
ast.parse(s)
compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  P83 judged on abstract only")

import subprocess, sys
r = subprocess.run([sys.executable, "patches.py", "verify"],
                   capture_output=True, text=True, encoding="utf-8",
                   errors="replace", cwd=HERE)
for ln in (r.stdout or "").splitlines():
    if "P83" in ln or "已落实" in ln:
        print("  " + ln.strip())