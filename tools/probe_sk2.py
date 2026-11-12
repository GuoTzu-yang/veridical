import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
s = open(os.path.join(HERE, "mmkit.py"), encoding="utf-8").read()
i = s.find('if a.cmd == "skeleton":')
print("  === skeleton 分支后 40 行 ===")
for ln in s[i:i + 1400].splitlines()[:36]:
    print("  " + ln[:96])