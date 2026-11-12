import ast
import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "tools", "pack.py")
s = open(P, encoding="utf-8").read()

# ① 补打包 out/data —— 这是 runs.json 里 14 道题的数据源，
#    漏了它用户拿到包一道题都跑不了（实测冷启动 0/1 通过）。
OLD = ('# ── ③ 数据文件（在项目外的题库目录）──')
assert OLD in s, "no anchor"
NEW = ('# ── ②b 数据集（out/data）──\n'
       '# runs.json 里 14 道题都指向这里。上一版整段漏掉，实测冷启动\n'
       '# 报「数据缺失」、14 道题一道都跑不了。\n'
       '_dd = os.path.join(HERE, "out", "data")\n'
       'if os.path.isdir(_dd):\n'
       '    for _f in sorted(os.listdir(_dd)):\n'
       '        if _f.lower().endswith((".xlsx", ".xls", ".csv")):\n'
       '            copy(os.path.join(_dd, _f), os.path.join("out", "data", _f))\n'
       '    print("  数据集已带入: %d 个" % len([\n'
       '        x for x in os.listdir(_dd)\n'
       '        if x.lower().endswith((".xlsx", ".xls", ".csv"))]))\n'
       '\n'
       '# ── ③ 数据文件（在项目外的题库目录）──')
s = s.replace(OLD, NEW, 1)

# ② README 里过时的「两步」「genfigs」改成一键
OLD2 = ('## 跑出这篇论文（两步）\n'
        '\n'
        '**第一步：生成图**（`mmkit run` 只写 tex，不画图）\n'
        '```bash\n'
        'python tools/genfigs.py\n'
        '```')
assert OLD2 in s, "no readme anchor"
NEW2 = ('## 跑出论文（一条命令）\n'
        '\n'
        '```bash\n'
        '# 跑全部 14 道题（含出图、编译、过 gate）\n'
        'python tools/battle.py\n'
        '\n'
        '# 只跑某几道\n'
        'python tools/battle.py chemical real_c2023\n'
        '\n'
        '# 验收藏（逐题过 gate + 回归 + 补丁）\n'
        'python tools/verify_all.py\n'
        '```\n'
        '\n'
        '题目配置在 `runs.json`（数据 / y / x / min / 题面 / 产物目录）。\n'
        '`mmkit run --compile` 会**自动出图**（12 张），不需要单独跑 genfigs。')
s = s.replace(OLD2, NEW2, 1)

ast.parse(s)
compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  pack.py: 已加 out/data + 更新 README")