import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
s = open(os.path.join(HERE, "tests", "i18n_gate.py"), encoding="utf-8").read()
print(s[:2600])