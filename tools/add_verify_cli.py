import ast
import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "verify.py")
s = open(P, encoding="utf-8").read()
OLD = ('if __name__ == "__main__":\n'
       '    raise SystemExit(selftest())')
assert OLD in s, "no main"
NEW = ('def main(argv=None) -> int:\n'
       '    """命令行：查一篇真实论文的数字溯源。\n'
       '\n'
       '        python verify.py <paper.tex> [--out-dir 产物目录] [--json]\n'
       '\n'
       '    原来 __main__ 只跑 selftest，新会话想查自己的论文没法用。\n'
       '    """\n'
       '    import argparse\n'
       '    ap = argparse.ArgumentParser(description="数字溯源")\n'
       '    ap.add_argument("tex", nargs="?", default="")\n'
       '    ap.add_argument("--out-dir", default="")\n'
       '    ap.add_argument("--json", action="store_true")\n'
       '    a = ap.parse_args(argv)\n'
       '    if not a.tex:\n'
       '        # 没有参数：跑自测（保持原行为）\n'
       '        return selftest()\n'
       '    import os as _o\n'
       '    d = a.out_dir or _o.path.dirname(_o.path.abspath(a.tex))\n'
       '    t = open(a.tex, encoding="utf-8").read()\n'
       '    outs = load_outputs(d)\n'
       '    r = trace(t, outs)\n'
       '    if a.json:\n'
       '        import json as _j\n'
       '        print(_j.dumps(r, ensure_ascii=False, indent=2, default=str))\n'
       '    else:\n'
       '        print(report(r))\n'
       '    return 0 if not (r.get("unmatched") or []) else 1\n'
       '\n'
       '\n'
       'if __name__ == "__main__":\n'
       '    raise SystemExit(main())')
s = s.replace(OLD, NEW, 1)
ast.parse(s); compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  verify.py 已加 CLI")