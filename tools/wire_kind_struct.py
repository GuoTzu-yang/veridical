import ast
import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "mmkit.py")
s = open(P, encoding="utf-8").read()

OLD = ('def _kind_ctx(problem, ds, xs, ycol):\n'
       '    """题型识别：题目描述 + 全部数值列 → 题型与所需模块。\n'
       '\n'
       '    识别结果决定 paper.py 走 full / brief / none 哪条机理分支。\n'
       '    """\n'
       '    try:\n'
       '        import kind as _kind\n'
       '        cols = [str(c) for c in (getattr(ds, "num_names", None) or [])]\n'
       '        return _kind.detect(problem or "", cols, ycol)\n'
       '    except Exception:                               # noqa: BLE001\n'
       '        return {}')
assert OLD in s, "no _kind_ctx"
NEW = ('def _kind_ctx(problem, ds, xs, ycol, n_obj=None):\n'
       '    """题型识别：题目描述 + 数值列 + **结构信号** → 题型与所需模块。\n'
       '\n'
       '    识别结果决定 paper.py 走 full / brief / none 哪条机理分支。\n'
       '    结构信号（目标个数、行数、有没有时间维度）比列名可靠：\n'
       '    列名是用户起的，pop2005 这种名字谁都无法据此判类型。\n'
       '    """\n'
       '    try:\n'
       '        import kind as _kind\n'
       '        cols = [str(c) for c in (getattr(ds, "num_names", None) or [])]\n'
       '        n_rows = int(getattr(ds, "n_rows", 0) or 0)\n'
       '        # 时间维度：列名里出现年份/月份这类词\n'
       '        _low = " ".join(cols).lower()\n'
       '        has_time = any(w in _low for w in (\n'
       '            "date", "time", "year", "month", "week", "quarter",\n'
       '            "period", "day"))\n'
       '        return _kind.detect(problem or "", cols, ycol,\n'
       '                            n_obj=n_obj, n_rows=n_rows,\n'
       '                            has_time=has_time)\n'
       '    except Exception:                               # noqa: BLE001\n'
       '        return {}')
s = s.replace(OLD, NEW, 1)

# 调用处传 n_obj
OLD2 = 'problem_kind=_kind_ctx(problem, ds, xs, ycol),'
assert OLD2 in s, "no call site"
NEW2 = 'problem_kind=_kind_ctx(problem, ds, xs, ycol,\n' \
       '                                            n_obj=len(min_cols or [])),'
s = s.replace(OLD2, NEW2, 1)

ast.parse(s)
compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  wired n_obj/n_rows/has_time")