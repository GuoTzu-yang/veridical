import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
s = open(os.path.join(HERE, "mmkit.py"), encoding="utf-8").read()
lines = s.splitlines()
# def run( 签名
for i, ln in enumerate(lines, 1):
    if ln.startswith("def run("):
        print("  === def run( 签名 ===")
        for k in range(i - 1, min(i + 12, len(lines))):
            print("  %5d %s" % (k + 1, lines[k][:90]))
        break
# main 里怎么调 run
i = s.find("    return run(a.data, a.y,")
print("\n  === main 调用 ===")
print(s[i:i + 560])