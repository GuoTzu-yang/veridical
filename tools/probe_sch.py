import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
s = open(os.path.join(HERE, "schema.py"), encoding="utf-8").read()
i = s.find("commands")
# 找构造 commands 的地方
for k, ln in enumerate(s.splitlines(), 1):
    if ('"commands"' in ln or "commands[" in ln or "cmds[" in ln
            or "per_cmd" in ln):
        print("  %4d %s" % (k, ln.strip()[:92]))