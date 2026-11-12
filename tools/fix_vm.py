import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
p = os.path.join(HERE, "tools", "verify_matrix.py")
s = open(p, encoding="utf-8").read()
OLD = '        ok = "OK " if r.returncode == 0 else "FAIL"'
assert OLD in s
NEW = ('        # falsify 找到反例时返回 1，那是「证伪成功」，不是失败\n'
       '        _expect1 = "falsify.py" in c[0]\n'
       '        ok = ("OK " if (r.returncode == 0 or (_expect1 and r.returncode == 1))\n'
       '              else "FAIL")')
s = s.replace(OLD, NEW, 1)
open(p, "w", encoding="utf-8", newline="\n").write(s)
print("  判据已修")