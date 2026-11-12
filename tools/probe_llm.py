import os
import re
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
print("  === 有没有 LLM 接入 ===")
for f in sorted(os.listdir(HERE)):
    if not f.endswith(".py"):
        continue
    t = open(os.path.join(HERE, f), encoding="utf-8", errors="replace").read()
    for kw in ("openai", "deepseek", "anthropic", "api_key", "requests.post",
               "chat/completions", "llm", "prompt"):
        if kw.lower() in t.lower():
            n = t.lower().count(kw.lower())
            print("    %-16s %-16s x%d" % (f, kw, n))
print()
print("  === hints / advise 子命令 ===")
m = open(os.path.join(HERE, "mmkit.py"), encoding="utf-8").read()
for i, ln in enumerate(m.splitlines(), 1):
    if "def _hints" in ln or "def _advise" in ln:
        print("    mmkit.py:%-5d %s" % (i, ln.strip()[:80]))