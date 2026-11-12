import os
import sys
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import i18n

print("  LANGS 有:", sorted(i18n.LANGS))
for k in sorted(i18n.LANGS):
    d = i18n.LANGS[k]
    print("    %-4s engine=%-9s needs=%-28s babel=%s"
          % (k, d.get("engine"), d.get("needs"), d.get("babel")))
print()
print("  get('zh') 是不是英文包:", i18n.get("zh") is i18n.LANGS["en"])
print("  get('zh') sections[:3]:", i18n.get("zh")["sections"][:3])
print()
# 宏包可用性检查
try:
    import subprocess
    for k in sorted(i18n.LANGS):
        d = i18n.LANGS[k]
        if not d.get("needs"):
            continue
        for pk in d["needs"]:
            print("    %s 需要 %s" % (k, pk))
except Exception as e:
    print(e)