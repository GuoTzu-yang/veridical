import ast, os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "mm.py")
s = open(P, encoding="utf-8").read()
if "def partial_corr(" in s:
    print("  已存在")
else:
    F = '''

def partial_corr(ds, ycol: str, xcol: str, others=None) -> dict:
    """控制 others 之后，y 与 x 的偏相关。

    为什么要有这个包装
    ------------------
    mmkit.py 里那个 partial_corr(X, y, j) 收的是「矩阵 + 列索引」，
    而 falsify.py 与 gate.py 一直按 (ds, 列名, 列名, [控制变量]) 调它 ——
    签名不匹配，两处的偏相关对照从来没工作过，只在 except 里静默打印
    「偏相关对照失败：AttributeError」。这是「造好了没接上」的典型。

    实现：把 y 和 x 各自对控制变量回归，取残差的相关。
    """
    import numpy as np
    cols = [xcol, ycol] + [c for c in (others or []) if c not in (xcol, ycol)]
    try:
        M = np.column_stack([np.asarray(ds.col(c), dtype=float) for c in cols])
    except Exception:                               # noqa: BLE001
        return {"r": None}
    M = M[~np.isnan(M).any(axis=1)]
    n = len(M)
    if n < 5:
        return {"r": None}
    k = M.shape[1]
    Z = np.column_stack([np.ones(n)] + [M[:, i] for i in range(2, k)])

    def _resid(v):
        beta, *_ = np.linalg.lstsq(Z, v, rcond=None)
        return v - Z @ beta

    rx, ry = _resid(M[:, 0]), _resid(M[:, 1])
    den = float(np.sqrt((rx ** 2).sum() * (ry ** 2).sum()))
    if den <= 0:
        return {"r": None, "n": n}
    return {"r": float((rx * ry).sum() / den), "n": n}
'''
    s = s.rstrip("\n") + F + "\n"
    ast.parse(s); compile(s, P, "exec")
    open(P, "w", encoding="utf-8", newline="\n").write(s)
    print("  mm.partial_corr 已补")