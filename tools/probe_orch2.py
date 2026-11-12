import os
import re
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
t = open(os.path.join(HERE, "orchestrate.py"), encoding="utf-8").read()
print("  === 公开函数签名 ===")
for m in re.finditer(r"^def (\w+)\(([^)]*)\)", t, re.M):
    print("    def %s(%s)" % (m.group(1),
                             " ".join(m.group(2).split())[:64]))
print()
print("  === propose 回调的期望签名（从文档/校验看）===")
i = t.find("def run")
print(t[i:i + 900] if i > 0 else "no run()")