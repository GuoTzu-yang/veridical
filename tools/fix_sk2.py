import ast, os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "mmkit.py")
s = open(P, encoding="utf-8").read()
i = s.find('    # ── 骨架：导出可被 LLM 替换的正文段落 ──')
j = s.find('    if a.cmd == "experiment":')
assert i > 0 and j > i
NEW = '''    # ── 骨架：列出可被 LLM 替换的正文段落 ──
    # 不依赖 run() 的内部流程（那条路上有多个提前 return，实测卡住），
    # 直接调 paper.build 收集。代价是只能拿到不依赖完整 ctx 的段落，
    # 但那些正好是最该由 LLM 重写的：摘要与结论。
    if a.cmd == "skeleton":
        import paper as _pp
        _pp.set_overrides(None)
        _ctx = dict(ds=None, n=0, y=a.y,
                    xs=[x.strip() for x in (a.x or "").split(",") if x.strip()],
                    min_cols=a.min, problem=a.problem, lang=a.lang)
        try:
            _pp.build(_ctx)
        except Exception as e:                  # noqa: BLE001
            _say(f"  build 失败：{type(e).__name__}: {e}")
        _sk = [(k, t) for k, t in _pp.dump_skeleton()
               if k and not k.startswith("__")]
        if a.json:
            _emit([dict(key=k, text=t) for k, t in _sk])
        else:
            _say(f"  可替换的正文段落：{len(_sk)} 段")
            _say("  用法：写一个 {\\"原文前40字\\": \\"新文本\\"} 的 JSON，")
            _say("        然后 run --overrides 那个文件（或用 MMKIT_OVERRIDES）")
            for k, t in _sk:
                _say("")
                _say(f"  [{k}]")
                _say(f"    {t[:150]}")
        return 0

'''
s = s[:i] + NEW + s[j:]
ast.parse(s); compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  skeleton 改为直调 paper API")