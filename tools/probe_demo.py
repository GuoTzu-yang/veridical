import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
s = open(os.path.join(HERE, "orchestrate.py"), encoding="utf-8").read()
i = s.find("def main")
j = s.find("\nif __name__", i)
print(s[i:j][:2200])