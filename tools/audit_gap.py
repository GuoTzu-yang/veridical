import ast
import json
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
print("  === 1. 全文中文的缺口 ===")
tree = ast.parse(open(os.path.join(HERE, "paper.py"), encoding="utf-8").read())
func = None
for n in ast.walk(tree):
    if isinstance(n, ast.FunctionDef) and n.name == "build":
        func = n
        break
lits = [v.value for v in ast.walk(func)
        if isinstance(v, ast.Constant) and isinstance(v.value, str)
        and len(v.value) >= 25 and v.value.isascii()
        and not v.value.startswith("\\")]
print("    build() 里固定英文长句: %d 条" % len(lits))
i18 = open(os.path.join(HERE, "i18n.py"), encoding="utf-8").read()
print("    i18n.py 有 body 词条表:", "BODY" in i18 or '"body"' in i18)

print()
print("  === 2. 文档同步状态 ===")
root = os.path.dirname(HERE)
for f in ("checkpoint.json", "checkpoints.json"):
    p = os.path.join(root, f)
    if os.path.exists(p):
        try:
            d = json.load(open(p, encoding="utf-8"))
            print("    %s: %d 条" % (f, len(d) if isinstance(d, list) else len(d.keys())))
        except Exception as e:
            print("    %s: 解析失败 %s" % (f, e))
    else:
        print("    %s: 不存在" % f)
docs = [x for x in os.listdir(root) if x.endswith(".md")]
print("    根目录 md: %d 个" % len(docs))

print()
print("  === 3. 文档里提到的「当前状态」是否还准 ===")
for f in docs:
    p = os.path.join(root, f)
    try:
        s = open(p, encoding="utf-8").read()
    except Exception:
        continue
    if "第 4" in s or "轮" in s:
        hits = [l.strip() for l in s.splitlines()
                if l.strip().startswith("**第") or "已完成" in l][:1]
        if hits:
            print("    %-34s %s" % (f, hits[0][:60]))