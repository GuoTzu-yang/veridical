import ast
import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "mmkit.py")
s = open(P, encoding="utf-8").read()

# 把 skeleton 分支换成「复用 run 的完整 ctx」：
# 直接设 _SKELETON_ONLY，然后让它走 run 的流程，出 tex 之前导出骨架就返回。
i = s.find('    # ── 骨架：导出可被 LLM 替换的正文段落 ──')
j = s.find('    if a.cmd == "experiment":')
assert i > 0 and j > i
NEW = ('    # ── 骨架：导出可被 LLM 替换的正文段落 ──\n'
       '    # 必须走 run 的完整 ctx，否则多数段落的条件不满足、导不全。\n'
       '    # 做法：置一个「只导骨架」的开关，run 跑到出 tex 前停下。\n'
       '    if a.cmd == "skeleton":\n'
       '        global _SKELETON_ONLY\n'
       '        _SKELETON_ONLY = True\n'
       '        a.cmd = "run"          # 走 run 的构造\n'
       '        a.no_gate = True\n'
       '        a.compile = False\n'
       '        a.json = False\n'
       '        # 落到下面的 run 分支；它在 build 之后会检查这个开关\n'
       '\n')
s = s[:i] + NEW + s[j:]

# run 分支里，build 之后检查开关
if "_SKELETON_ONLY" not in s.split("global _SKELETON_ONLY")[0]:
    # 定义全局默认
    s = s.replace("_JSON_MODE = [False]",
                  "_JSON_MODE = [False]\n_SKELETON_ONLY = False", 1)

OLD3 = '        _paper.set_overrides(None)\n'
if OLD3 in s:
    s = s.replace(OLD3,
                  '        _paper.set_overrides(None)\n'
                  '        if _SKELETON_ONLY:\n'
                  '            _sk = [(k, t) for k, t in _paper.dump_skeleton()\n'
                  '                   if k and not k.startswith("__")]\n'
                  '            if a.json:\n'
                  '                _emit([dict(key=k, text=t) for k, t in _sk])\n'
                  '            else:\n'
                  '                _say(f"  可替换的正文段落：{len(_sk)} 段")\n'
                  '                for k, t in _sk:\n'
                  '                    _say(f"\\n  [{k}]")\n'
                  '                    _say(f"    {t[:150]}")\n'
                  '            return 0\n', 1)

ast.parse(s); compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  skeleton 改为复用 run 的 ctx")