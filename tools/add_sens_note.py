import ast
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "paper.py")
s = open(P, encoding="utf-8").read()

FUNC = '''

def _sens_note(ctx) -> list[str]:
    """单因子时的灵敏度说明。

    只有 1 个解释变量时做不了 one-at-a-time 灵敏度扫描 —— 扫的就是那一个
    系数本身。但「做不了」不等于「不用提」：一句话说清原因，
    比整节沉默好，也让 I004（三大检验）有据可查。
    """
    xs = ctx.get("xs") or []
    sens = ctx.get("sens") or {}
    if len(xs) != 1 or (sens.get("rows") or []):
        return []
    return [r"\\subsection{Sensitivity analysis}", "",
            ("This problem carries a single explanatory factor, so a "
             "one-at-a-time sensitivity sweep would compare that factor's "
             "coefficient with itself. What replaces it here is the "
             "cross-validated dispersion already reported: the fold-to-fold "
             "variation of the error and the width of the prediction "
             "interval both say how far the fitted relation can be trusted "
             "before extrapolation. A multi-factor sweep is stated as a "
             "limitation rather than silently omitted."),
            ""]


'''
if "_sens_note" not in s:
    k = s.find("def _replication_note")
    assert k > 0, "no anchor"
    s = s[:k] + FUNC + s[k:]
    A = '    tex = tex + "\\n" + "\\n".join(_replication_note(ctx))'
    assert A in s, "no call site"
    s = s.replace(A, '    tex = tex + "\\n" + "\\n".join(_sens_note(ctx))\n' + A, 1)
    ast.parse(s)
    compile(s, P, "exec")
    open(P, "w", encoding="utf-8", newline="\n").write(s)
    print("  added _sens_note")