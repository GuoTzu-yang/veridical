"""复杂网络指标：中心性、聚类系数、连通分量、PageRank。

为什么需要
----------
网络/图论题在 APMCM 里常见（D 类运筹、C 类关系分析），而 mmkit 的 `graph`
只有最短路 / MST / 流 / TSP，没有任何「节点重要性」指标。

实现（全部纯 numpy/python，无 networkx）
----------------------------------------
  degree        度中心性（可按权重）
  closeness     接近中心性（用最短路距离，非连通图按可达子图归一）
  betweenness   介数中心性（Brandes 算法，O(VE)）
  eigenvector   特征向量中心性（幂迭代）
  pagerank      PageRank（带阻尼的幂迭代）
  clustering    局部聚类系数 + 全局平均
  components    连通分量

验证策略
--------
用三类结构已知的图做自检：星形图、路径图、完全图。它们的中心性排序是确定的，
任何实现错误都会立刻暴露（例如星形图的中心点介数必须是 (n-1)(n-2)/2）。
"""
import argparse
import sys

import numpy as np


def _adj(n, edges):
    A = np.zeros((n, n), dtype=float)
    for u, v, w in edges:
        A[u, v] += w
        A[v, u] += w
    return A


def degree(A, weighted=False):
    return A.sum(axis=1) if weighted else (A > 0).sum(axis=1).astype(float)


def shortest_paths(A):
    """Floyd–Warshall，返回距离矩阵（不可达为 inf）。"""
    n = A.shape[0]
    D = np.where(A > 0, A, np.inf)
    np.fill_diagonal(D, 0.0)
    for k in range(n):
        D = np.minimum(D, D[:, k][:, None] + D[k, :][None, :])
    return D


def closeness(A):
    n = A.shape[0]
    D = shortest_paths(A)
    out = np.zeros(n)
    for i in range(n):
        reach = D[i][np.isfinite(D[i])]
        reach = reach[reach > 0]
        if len(reach) == 0:
            out[i] = 0.0
        else:
            out[i] = len(reach) / reach.sum()     # 按可达节点数归一
    return out


def betweenness(A):
    """Brandes 算法（无权，按边数计）。"""
    n = A.shape[0]
    nb = np.zeros(n)
    neigh = [[j for j in range(n) if A[i, j] > 0] for i in range(n)]
    for s in range(n):
        S = []
        P = [[] for _ in range(n)]
        sigma = np.zeros(n)
        sigma[s] = 1.0
        d = np.full(n, -1)
        d[s] = 0
        Q = [s]
        while Q:
            v = Q.pop(0)
            S.append(v)
            for w in neigh[v]:
                if d[w] < 0:
                    d[w] = d[v] + 1
                    Q.append(w)
                if d[w] == d[v] + 1:
                    sigma[w] += sigma[v]
                    P[w].append(v)
        delta = np.zeros(n)
        while S:
            w = S.pop()
            for v in P[w]:
                if sigma[w] > 0:
                    delta[v] += sigma[v] / sigma[w] * (1 + delta[w])
            if w != s:
                nb[w] += delta[w]
    return nb / 2.0                       # 无向图每对被算两次


def eigenvector(A, iters=1000, tol=1e-12):
    n = A.shape[0]
    x = np.ones(n) / n
    for _ in range(iters):
        y = A @ x
        nrm = np.linalg.norm(y)
        if nrm == 0:
            return x
        y = y / nrm
        if np.abs(y - x).max() < tol:
            return y
        x = y
    return x


def pagerank(A, d=0.85, iters=1000, tol=1e-12):
    n = A.shape[0]
    W = (A > 0).astype(float)
    out = W.sum(axis=1)
    dangling = out == 0
    pr = np.full(n, 1.0 / n)
    for _ in range(iters):
        contrib = np.zeros(n)
        for i in range(n):
            if out[i] > 0:
                contrib += pr[i] * W[i] / out[i]
        new = (1 - d) / n + d * contrib
        if dangling.any():
            new += d * pr[dangling].sum() / n
        if np.abs(new - pr).sum() < tol:
            return new
        pr = new
    return pr


def clustering(A):
    """局部聚类系数与全局平均（无向）。"""
    n = A.shape[0]
    B = (A > 0).astype(float)
    local = np.zeros(n)
    for i in range(n):
        nb = np.where(B[i] > 0)[0]
        k = len(nb)
        if k < 2:
            local[i] = 0.0
            continue
        sub = B[np.ix_(nb, nb)]
        links = sub.sum() / 2.0
        local[i] = links / (k * (k - 1) / 2.0)
    return local, float(local.mean())


def components(A):
    n = A.shape[0]
    seen = [False] * n
    comps = []
    for s in range(n):
        if seen[s]:
            continue
        stack = [s]
        seen[s] = True
        cur = []
        while stack:
            v = stack.pop()
            cur.append(v)
            for w in range(n):
                if A[v, w] > 0 and not seen[w]:
                    seen[w] = True
                    stack.append(w)
        comps.append(sorted(cur))
    return comps


def selftest():
    ok = True

    def ck(name, cond, detail=""):
        nonlocal ok
        ok = ok and cond
        print("  [%s] %-34s %s" % ("PASS" if cond else "FAIL", name, detail))

    # 星形图：0 为中心，1..5 为叶子
    n = 6
    star = [(0, i, 1.0) for i in range(1, n)]
    A = _adj(n, star)
    deg = degree(A)
    ck("星形图：中心度最高", int(np.argmax(deg)) == 0, "deg=%s" % deg.tolist())
    ck("星形图：叶子度=1", all(deg[i] == 1 for i in range(1, n)))
    bt = betweenness(A)
    # 星形图中心点的介数 = (n-1)(n-2)/2 = 10
    ck("星形图：中心介数 = (n-1)(n-2)/2",
       abs(bt[0] - (n - 1) * (n - 2) / 2.0) < 1e-9, "%.4f" % bt[0])
    ck("星形图：叶子介数=0", all(abs(bt[i]) < 1e-12 for i in range(1, n)))

    # 路径图 0-1-2-3-4：中间点介数最高
    m = 5
    path = [(i, i + 1, 1.0) for i in range(m - 1)]
    Ap = _adj(m, path)
    bp = betweenness(Ap)
    ck("路径图：中点介数最高", int(np.argmax(bp)) == 2, "bt=%s" % np.round(bp, 3).tolist())
    cl = closeness(Ap)
    ck("路径图：中点接近中心性最高", int(np.argmax(cl)) == 2)

    # 完全图：所有中心性相等
    k = 5
    comp = [(i, j, 1.0) for i in range(k) for j in range(i + 1, k)]
    Ac = _adj(k, comp)
    ck("完全图：度相等", len(set(degree(Ac).tolist())) == 1)
    ck("完全图：介数全为 0", np.allclose(betweenness(Ac), 0))
    loc, avg = clustering(Ac)
    ck("完全图：聚类系数=1", abs(avg - 1.0) < 1e-12, "%.4f" % avg)

    # 路径图聚类系数为 0（没有三角形）
    _, avgp = clustering(Ap)
    ck("路径图：聚类系数=0", abs(avgp) < 1e-12)

    # 特征向量中心性：星形图中心最大
    ev = eigenvector(A)
    ck("星形图：特征向量中心最大", int(np.argmax(ev)) == 0)
    # PageRank：星形图中心最大
    pr = pagerank(A)
    ck("星形图：PageRank 最大", int(np.argmax(pr)) == 0)
    ck("PageRank 归一", abs(pr.sum() - 1.0) < 1e-9, "sum=%.6f" % pr.sum())

    # 连通分量：两个独立的三角形
    two = [(0, 1, 1.0), (1, 2, 1.0), (2, 0, 1.0),
           (3, 4, 1.0), (4, 5, 1.0), (5, 3, 1.0)]
    comps = components(_adj(6, two))
    ck("两个连通分量", len(comps) == 2 and comps[0] == [0, 1, 2],
       str(comps))

    print("\n%s" % ("ALL PASS" if ok else "FAILED"))
    return 0 if ok else 1


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    if not argv or argv[0] == "selftest":
        return selftest()
    ap = argparse.ArgumentParser(description="复杂网络指标")
    ap.add_argument("--edges", required=True,
                    help="边列表文件：u,v[,w] 每行一条；或 --demo 用内置图")
    ap.add_argument("--n", type=int, default=0, help="节点数（省略则按最大编号+1）")
    a = ap.parse_args(argv)
    rows = []
    for line in open(a.edges, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.replace("\t", ",").split(",")
        u, v = int(parts[0]), int(parts[1])
        w = float(parts[2]) if len(parts) > 2 else 1.0
        rows.append((u, v, w))
    n = a.n or (max(max(u, v) for u, v, _ in rows) + 1)
    A = _adj(n, rows)
    print("网络：%d 节点 %d 边" % (n, len(rows)))
    comps = components(A)
    print("  连通分量 %d 个，最大 %d 节点"
          % (len(comps), max(len(c) for c in comps)))
    loc, avg = clustering(A)
    print("  平均聚类系数 %.4f" % avg)
    print()
    bt = betweenness(A)
    pr = pagerank(A)
    print("  %-6s %-8s %-10s %-10s %-10s" % ("节点", "度", "介数", "接近", "PageRank"))
    for i in np.argsort(-bt)[:15]:
        print("  %-6d %-8.0f %-10.4f %-10.4f %-10.4f"
              % (i, degree(A)[i], bt[i], closeness(A)[i], pr[i]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
