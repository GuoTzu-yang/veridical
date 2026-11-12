import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
s = open(os.path.join(HERE, "orchestrate.py"), encoding="utf-8").read()
i = s.find("def build_context")
j = s.find("\ndef ", i + 10)
print(s[i:j][:1800])