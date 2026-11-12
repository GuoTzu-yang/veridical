import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
s = open(os.path.join(HERE, "gate.py"), encoding="utf-8").read()
i = s.find("边际反例且控制后符号仍矛盾")
print(s[max(0, i-1100):i+260])