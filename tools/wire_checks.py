import ast, os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "paper.py")
s = open(P, encoding="utf-8").read()
FUNC = """

def _methods_missing(ctx) -> list:
    \"\"\"按题型查「该做但本次没做」的方法检查。

    数据来自 kb/methods/checks.json：每条给一组 probes，
    tex 里一个都搜不到就算没做。只收真正通用的项 --
    列不适用项等于制造噪音。
    \"\"\"
    import json as _j
    import os as _o
    p = _o.path.join(_o.path.dirname(_o.path.abspath(__file__)),
                     "kb", "methods", "checks.json")
    if not _o.path.exists(p):
        return []
    try:
        table = _j.load(open(p, encoding="utf-8")).get("kinds") or {}
    except Exception:
        return []
    kinds = (ctx.get("problem_kind") or {}).get("kinds") or []
    tex = str(ctx.get("_tex_lower") or "").lower()
    if not tex:
        return []
    out = []
    seen = set()
    for k in kinds:
        for item in (table.get(k) or []):
            nm = item.get("name") or ""
            if not nm or nm in seen:
                continue
            probes = [str(x).lower() for x in (item.get("probes") or [])]
            if any(pr in tex for pr in probes):
                continue
            seen.add(nm)
            out.append((nm, item.get("note") or ""))
    return out


"""
if "_methods_missing" not in s:
    k = s.find("def _claim_ledger")
    assert k > 0, "no _claim_ledger"
    s = s[:k] + FUNC + s[k:]
    A = "    if not rows:\n        return L\n\n    L += [r\"\\subsection{What each claim rests on}\", \"\"]"
    assert A in s, "no rows anchor"
    NEW = ("    # 方法完整性：该题型通常要做、但 tex 里搜不到依据的检查项\n"
           "    for _nm, _why in _methods_missing(ctx):\n"
           "        rows.append((_nm, \"\", _why or \"no trace of it in the report\"))\n\n")
    s = s.replace(A, NEW + A, 1)
    A2 = "    L += _claim_ledger(ctx)"
    assert A2 in s, "no call site"
    s = s.replace(A2, "    ctx[\"_tex_lower\"] = \"\\n\".join(L).lower()\n" + A2, 1)
    ast.parse(s)
    compile(s, P, "exec")
    open(P, "w", encoding="utf-8", newline="\n").write(s)
    print("  ok: wired checks.json")
else:
    print("  already wired")