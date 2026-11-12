import ast, os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "mmkit.py")
s = open(P, encoding="utf-8").read()

# 加 --from-tex 参数
if "--from-tex" not in s:
    OLD = '    ap.add_argument("--overrides", default="",'
    assert OLD in s
    NEW = ('    ap.add_argument("--from-tex", default="",\n'
           '                    help="skeleton 从这个已生成的 tex 提取段落（key 必然对得上）")\n'
           '    ap.add_argument("--overrides", default="",')
    s = s.replace(OLD, NEW, 1)

# skeleton 里支持从 tex 提取
OLD2 = '    if a.cmd == "skeleton":\n        import paper as _pp\n        _pp.set_overrides(None)'
assert OLD2 in s
NEW2 = ('    if a.cmd == "skeleton":\n'
        '        import paper as _pp\n'
        '        # 从已生成的 tex 提取：key 一定和 run 的产物对得上。\n'
        '        # 用 paper.build 的简化 ctx 会因措辞不同而错位（实测过）。\n'
        '        if a.from_tex:\n'
        '            _t = open(a.from_tex, encoding="utf-8").read()\n'
        '            _paras = [p.strip() for p in _t.split("\\n\\n")\n'
        '                      if p.strip() and not p.strip().startswith("\\\\")\n'
        '                      and len(p.strip()) > 120]\n'
        '            _sk = [(_pp.para_key(p), " ".join(p.split()))\n'
        '                   for p in _paras]\n'
        '        else:\n'
        '            _pp.set_overrides(None)')
s = s.replace(OLD2, NEW2, 1)

# 后面的 build 部分要缩进到 else 里
OLD3 = ('        _ctx = dict(ds=None, n=0, y=a.y,\n'
        '                    xs=[x.strip() for x in (a.x or "").split(",") if x.strip()],\n'
        '                    min_cols=a.min, problem=a.problem, lang=a.lang)\n'
        '        try:\n'
        '            _pp.build(_ctx)\n'
        '        except Exception as e:                  # noqa: BLE001\n'
        '            _say(f"  build 失败：{type(e).__name__}: {e}")\n'
        '        _sk = [(k, t) for k, t in _pp.dump_skeleton()\n'
        '               if k and not k.startswith("__")]')
assert OLD3 in s, "no build block"
NEW3 = ('            _ctx = dict(ds=None, n=0, y=a.y,\n'
        '                        xs=[x.strip() for x in (a.x or "").split(",") if x.strip()],\n'
        '                        min_cols=a.min, problem=a.problem, lang=a.lang)\n'
        '            try:\n'
        '                _pp.build(_ctx)\n'
        '            except Exception as e:              # noqa: BLE001\n'
        '                _say(f"  build 失败：{type(e).__name__}: {e}")\n'
        '            _sk = [(k, t) for k, t in _pp.dump_skeleton()\n'
        '                   if k and not k.startswith("__")]')
s = s.replace(OLD3, NEW3, 1)

ast.parse(s); compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  skeleton 支持 --from-tex")