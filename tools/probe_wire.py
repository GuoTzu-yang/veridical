import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
m = open(os.path.join(HERE, "mmkit.py"), encoding="utf-8").read()
g = open(os.path.join(HERE, "gate.py"), encoding="utf-8").read()
print("  === 关键模块在 mmkit.py / gate.py 里的出现次数 ===")
for mod in ("schema", "contract", "verify", "falsify", "lanes",
            "orchestrate", "review", "rules", "aitaste"):
    print("    %-12s mmkit:%-3d gate:%d"
          % (mod, m.count(mod), g.count(mod)))
print()
print("  === 这些模块自己能跑吗（有没有 __main__）===")
for mod in ("schema", "contract", "verify", "falsify", "lanes",
            "orchestrate"):
    p = os.path.join(HERE, mod + ".py")
    if not os.path.exists(p):
        continue
    t = open(p, encoding="utf-8").read()
    has = "__main__" in t
    print("    %-12s 可独立运行: %s" % (mod, has))