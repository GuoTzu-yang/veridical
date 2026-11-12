import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
s = open(os.path.join(HERE, "mmkit.py"), encoding="utf-8").read()
i = s.find('if _lang_now.startswith("en"):')
print("  === CJK 总闸 ===")
print(s[max(0, i-300):i+700])