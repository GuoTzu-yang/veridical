import ast
import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "mmkit.py")
s = open(P, encoding="utf-8").read()

# ① choices 加 skeleton
s = s.replace('"experiment", "contract", "formula"])',
              '"experiment", "contract", "formula", "skeleton"])', 1)

# ② 参数
if "--overrides" not in s:
    OLD = '    ap.add_argument("--proposal", default="",'
    assert OLD in s
    NEW = ('    ap.add_argument("--overrides", default="",\n'
           '                    help="LLM 写的正文段落（JSON: 原文前40字 -> 新文本）")\n'
           '    ap.add_argument("--proposal", default="",')
    s = s.replace(OLD, NEW, 1)

# ③ skeleton 分支
OLD2 = '    if a.cmd == "experiment":'
assert OLD2 in s
NEW2 = ('    # ── 骨架：导出可被 LLM 替换的正文段落 ──\n'
        '    if a.cmd == "skeleton":\n'
        '        data = a.data or mm.find_xlsx()\n'
        '        if not data or not os.path.exists(data):\n'
        '            _say(f"找不到数据：{data!r}")\n'
        '            return 2\n'
        '        ds = mm.DS(data)\n'
        '        _paper.set_overrides(None)\n'
        '        try:\n'
        '            _paper.build({"ds": ds, "n": ds.n_rows,\n'
        '                          "y": a.y,\n'
        '                          "xs": [x.strip() for x in (a.x or "").split(",") if x.strip()],\n'
        '                          "min_cols": a.min, "problem": a.problem,\n'
        '                          "lang": a.lang})\n'
        '        except Exception:                       # noqa: BLE001\n'
        '            pass\n'
        '        sk = _paper.dump_skeleton()\n'
        '        if a.json:\n'
        '            _emit([dict(key=k, text=t) for k, t in sk])\n'
        '        else:\n'
        '            _say(f"  可替换的正文段落：{len(sk)} 段")\n'
        '            for k, t in sk:\n'
        '                _say(f"\\n  [{k}]\\n    {t[:160]}")\n'
        '        return 0\n'
        '\n'
        '    if a.cmd == "experiment":')
s = s.replace(OLD2, NEW2, 1)

# ④ run 前装 overrides
if "--overrides" in s and "_paper.set_overrides(" not in s:
    m = s.find('tex = _paper.build(ctx)')
    if m < 0:
        m = s.find('_paper.build(ctx)')
    assert m > 0, "no build call"
    ind = s[:m].split("\n")[-1]
    ins = ('    if getattr(a, "overrides", ""):\n'
           '        _ov = json.load(open(a.overrides, encoding="utf-8"))\n'
           '        _paper.set_overrides(_ov)\n'
           '        _say(f"  正文覆盖 {len(_ov)} 段 <- {a.overrides}")\n'
           '    else:\n'
           '        _paper.set_overrides(None)\n')
    # 插到 build 调用所在行之前
    line_start = s.rfind("\n", 0, m) + 1
    s = s[:line_start] + ins + s[line_start:]

ast.parse(s); compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  skeleton + --overrides 已接")