import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
s = open(os.path.join(HERE, "aitaste.py"), encoding="utf-8").read()
i = s.find("def check_repetition")
j = s.find("\ndef ", i + 10)
print(s[i:j][:1600])