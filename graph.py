#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
graph.py —— 图论算法（第 82 轮补）

为什么单独一个文件
------------------
数模里路径规划、物流调度、管网设计、任务分配都归到图上，
而之前整个插件**一个图算法都没有**（查过 mm.py / engine.py，确实没有）。
放在这里而不是塞进 mm.py：mm.py 已经有 855 行，而且跟图论没有共享代码。

提供四个：
    dijkstra  单源最短路（非负权）
    kruskal   最小生成树
    max_flow  最大流（Edmonds-Karp）
    tsp       旅行商：最近邻构造 + 2-opt 改进

约定
----
节点用整数下标 0..n-1；边用 (u, v, w) 三元组，无向图由调用方补两条。
所有算法都返回 dict，里面既有结果也有**这次结果能信到什么程度**的说明——
图论算法本身是精确的，可信度问题出在"模型对不对"上（见各函数的边界说明）。
"""

from __future__ import annotations

import heapq


def dijkstra(n: int, edges: list[tuple[int, int, float]], src: int,
             dst: int | None = None) -> dict:
    """单源最短路。边是 (u, v, w)，w 必须非负。

    返回 dist / path / unreachable。
    """
    if n <= 0:
        raise ValueError("节点数必须为正")
    if not (0 <= src < n):
        raise ValueError(f"起点 {src} 越界（0..{n - 1}）")
    neg = [e for e in edges if e[2] < 0]
    if neg:
        raise ValueError(f"有 {len(neg)} 条负权边，Dijkstra 不适用"
                         f"（负权要用 Bellman-Ford）")

    adj: list[list[tuple[int, float]]] = [[] for _ in range(n)]
    for u, v, w in edges:
        if not (0 <= u < n and 0 <= v < n):
            raise ValueError(f"边 ({u},{v}) 的端点越界")
        adj[u].append((v, w))

    INF = float("inf")
    dist = [INF] * n
    prev = [-1] * n
    dist[src] = 0.0
    pq = [(0.0, src)]
    done = [False] * n
    while pq:
        d, u = heapq.heappop(pq)
        if done[u]:
            continue
        done[u] = True
        for v, w in adj[u]:
            nd = d + w
            if nd < dist[v] - 1e-12:
                dist[v] = nd
                prev[v] = u
                heapq.heappush(pq, (nd, v))

    def _path(t):
        if dist[t] == INF:
            return []
        out = []
        cur = t
        while cur != -1:
            out.append(cur)
            cur = prev[cur]
        return out[::-1]

    if dst is not None:
        if not (0 <= dst < n):
            raise ValueError(f"终点 {dst} 越界")
        p = _path(dst)
        return dict(ok=True, dist=dist[dst], path=p,
                    unreachable=(dist[dst] == INF),
                    paths={dst: p})
    return dict(ok=True, dist=dist, paths={i: _path(i) for i in range(n)},
                unreachable=[i for i in range(n) if dist[i] == INF])


def kruskal(n: int, edges: list[tuple[int, int, float]]) -> dict:
    """最小生成树（Kruskal + 并查集）。边按无向处理，重复边无害。"""
    if n <= 0:
        raise ValueError("节点数必须为正")
    parent = list(range(n))
    rank = [0] * n

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra == rb:
            return False
        if rank[ra] < rank[rb]:
            ra, rb = rb, ra
        parent[rb] = ra
        if rank[ra] == rank[rb]:
            rank[ra] += 1
        return True

    chosen = []
    total = 0.0
    for u, v, w in sorted(edges, key=lambda e: e[2]):
        if union(u, v):
            chosen.append((u, v, w))
            total += w
            if len(chosen) == n - 1:
                break

    comps = len({find(i) for i in range(n)})
    return dict(ok=True, mst=chosen, weight=total, components=comps,
                connected=(comps == 1),
                warn=[] if comps == 1 else
                [f"图不连通（{comps} 个连通分量），下面是**最小生成森林**，"
                 f"不是生成树"])


def max_flow(n: int, edges: list[tuple[int, int, float]], s: int,
             t: int) -> dict:
    """最大流（Edmonds-Karp，BFS 找增广路）。边是 (u, v, capacity)。"""
    if not (0 <= s < n and 0 <= t < n):
        raise ValueError("源点或汇点越界")
    if s == t:
        raise ValueError("源点和汇点不能相同")
    cap = [[0.0] * n for _ in range(n)]
    for u, v, c in edges:
        if c < 0:
            raise ValueError(f"边 ({u},{v}) 容量为负")
        cap[u][v] += c

    flow = 0.0
    rounds = 0
    while True:
        # BFS 找增广路
        prev = [-1] * n
        prev[s] = s
        q = [s]
        while q and prev[t] == -1:
            u = q.pop(0)
            for v in range(n):
                if prev[v] == -1 and cap[u][v] > 1e-12:
                    prev[v] = u
                    q.append(v)
        if prev[t] == -1:
            break
        # 找瓶颈
        bottleneck = float("inf")
        v = t
        while v != s:
            u = prev[v]
            bottleneck = min(bottleneck, cap[u][v])
            v = u
        v = t
        while v != s:
            u = prev[v]
            cap[u][v] -= bottleneck
            cap[v][u] += bottleneck
            v = u
        flow += bottleneck
        rounds += 1

    return dict(ok=True, max_flow=flow, augmentations=rounds)


def tsp(n: int, dist: list[list[float]], start: int = 0,
        improve: bool = True) -> dict:
    """旅行商：最近邻构造 + 2-opt 改进。

    **不保证最优**。精确解要 Held-Karp（O(n²2ⁿ)），20 个点就跑不动了。
    这里给的是近似解，并且会如实说明"比下界高多少"，让读者自己判断够不够。
    """
    if n < 2:
        raise ValueError("至少要 2 个点")
    if len(dist) != n or any(len(r) != n for r in dist):
        raise ValueError("距离矩阵必须是 n×n")

    # 最近邻构造
    unvisited = set(range(n)) - {start}
    tour = [start]
    cur = start
    while unvisited:
        nxt = min(unvisited, key=lambda j: dist[cur][j])
        tour.append(nxt)
        unvisited.remove(nxt)
        cur = nxt

    def tour_len(t):
        return sum(dist[t[i]][t[(i + 1) % len(t)]] for i in range(len(t)))

    if improve:
        # 2-opt：反复找能缩短的边交换，直到没有改进
        improved = True
        passes = 0
        while improved and passes < 200:
            improved = False
            passes += 1
            for i in range(1, n - 2):
                for j in range(i + 1, n):
                    if j - i == 1:
                        continue
                    a, b = tour[i - 1], tour[i]
                    c = tour[j]
                    d = tour[(j + 1) % n]
                    if a == c or b == d:
                        continue
                    delta = (dist[a][c] + dist[b][d]) - (dist[a][b] + dist[c][d])
                    if delta < -1e-10:
                        tour[i:j + 1] = tour[i:j + 1][::-1]
                        improved = True

    length = tour_len(tour)
    # 下界：每个点连出去的最短两条边加起来除以 2
    lb = 0.0
    for i in range(n):
        two = sorted(dist[i][j] for j in range(n) if j != i)[:2]
        lb += sum(two)
    lb /= 2.0
    gap = (length - lb) / lb if lb > 0 else 0.0

    return dict(ok=True, tour=tour, length=length, lower_bound=lb,
                gap=gap, improved=bool(improve),
                warn=([] if gap < 0.05 else
                      [f"近似解比下界高 {gap:.1%}，不保证最优；"
                       f"要精确解得用 Held-Karp（n≤15 左右还能跑）"]))


# ══════════════════════════════════════════════════════════════════════
#  自检：每个算法都拿有已知答案的例子对
# ══════════════════════════════════════════════════════════════════════
def selftest() -> int:
    ok = 0
    bad = 0

    def ck(name, cond, detail=""):
        nonlocal ok, bad
        if cond:
            ok += 1
            print(f"  [PASS] {name}" + (f"  — {detail}" if detail else ""))
        else:
            bad += 1
            print(f"  [FAIL] {name}" + (f"  — {detail}" if detail else ""))

    print("=" * 72)
    print("graph.py 自检")
    print("=" * 72)

    print("\n一、Dijkstra")
    # 0-1:4, 0-2:1, 2-1:2, 1-3:1, 2-3:5
    # 0→3 最短 = 0-2-1-3 = 1+2+1 = 4（不是 0-1-3=5）
    E = [(0, 1, 4), (0, 2, 1), (2, 1, 2), (1, 3, 1), (2, 3, 5)]
    r = dijkstra(4, E, 0, 3)
    ck("0→3 最短距离 = 4", abs(r["dist"] - 4) < 1e-12, f"{r['dist']}")
    ck("路径是 0-2-1-3", r["path"] == [0, 2, 1, 3], str(r["path"]))
    r2 = dijkstra(4, E, 0)
    ck("全源距离正确", r2["dist"] == [0, 3, 1, 4], str(r2["dist"]))
    # 不可达
    r3 = dijkstra(3, [(0, 1, 1)], 0, 2)
    ck("不可达时 dist=inf", r3["dist"] == float("inf"), str(r3["dist"]))
    ck("不可达时 path 为空", r3["path"] == [], str(r3["path"]))
    # 负权拒绝
    try:
        dijkstra(2, [(0, 1, -1)], 0, 1)
        ck("负权边被拒绝", False, "没抛异常")
    except ValueError as e:
        ck("负权边被拒绝", True, str(e)[:40])
    # 越界
    try:
        dijkstra(2, [(0, 5, 1)], 0, 1)
        ck("端点越界被拒绝", False, "没抛异常")
    except ValueError:
        ck("端点越界被拒绝", True, "ValueError")

    print("\n二、Kruskal 最小生成树")
    # 三角形：1+2=3
    r = kruskal(3, [(0, 1, 1), (1, 2, 2), (0, 2, 3)])
    ck("三角形 MST 权重 = 3", abs(r["weight"] - 3) < 1e-12, f"{r['weight']}")
    ck("MST 边数 = n-1", len(r["mst"]) == 2, str(len(r["mst"])))
    ck("连通图无警告", r["connected"] is True and not r["warn"], "")
    # 不连通
    r = kruskal(4, [(0, 1, 1), (2, 3, 1)])
    ck("不连通图报 2 个分量", r["components"] == 2, str(r["components"]))
    ck("不连通时给警告", len(r["warn"]) > 0, r["warn"][0][:40])
    # 经典 4 点例子
    E = [(0, 1, 1), (1, 2, 3), (0, 2, 2), (2, 3, 4), (0, 3, 5)]
    r = kruskal(4, E)
    ck("4 点 MST 权重 = 7 (1+2+4)", abs(r["weight"] - 7) < 1e-12,
       f"{r['weight']}")

    print("\n三、最大流（CLRS 经典例子，答案 23）")
    E = [(0, 1, 16), (0, 2, 13), (1, 2, 10), (2, 1, 4), (1, 3, 12),
         (3, 2, 9), (2, 4, 14), (4, 3, 7), (3, 5, 20), (4, 5, 4)]
    r = max_flow(6, E, 0, 5)
    ck("最大流 = 23", abs(r["max_flow"] - 23) < 1e-9, f"{r['max_flow']}")
    ck("有增广轮次", r["augmentations"] > 0, str(r["augmentations"]))
    # 简单情形：单边
    r = max_flow(2, [(0, 1, 7)], 0, 1)
    ck("单边最大流 = 容量", abs(r["max_flow"] - 7) < 1e-12, f"{r['max_flow']}")
    # 平行边要累加
    r = max_flow(2, [(0, 1, 3), (0, 1, 4)], 0, 1)
    ck("平行边容量累加 = 7", abs(r["max_flow"] - 7) < 1e-12, f"{r['max_flow']}")
    try:
        max_flow(2, [(0, 1, 1)], 0, 0)
        ck("源汇相同被拒绝", False, "没抛异常")
    except ValueError:
        ck("源汇相同被拒绝", True, "ValueError")

    print("\n四、TSP（4 点正方形，最优 4）")
    # 正方形边长 1，周长 4
    D = [[0, 1, 2 ** 0.5, 1],
         [1, 0, 1, 2 ** 0.5],
         [2 ** 0.5, 1, 0, 1],
         [1, 2 ** 0.5, 1, 0]]
    r = tsp(4, D)
    ck("正方形 TSP 长度 = 4", abs(r["length"] - 4) < 1e-9, f"{r['length']}")
    ck("回访所有点各一次", sorted(r["tour"]) == [0, 1, 2, 3], str(r["tour"]))
    ck("2-opt 后不劣于下界",
       r["length"] >= r["lower_bound"] - 1e-9,
       f"{r['length']:.4f} >= {r['lower_bound']:.4f}")
    ck("正方形解已最优（gap≈0）", r["gap"] < 0.02, f"gap={r['gap']:.4f}")
    # 5 点一线（退化：有重复距离）
    D5 = [[abs(i - j) for j in range(5)] for i in range(5)]
    r5 = tsp(5, D5)
    ck("一维等距 5 点 TSP 长度 = 8",
       abs(r5["length"] - 8) < 1e-9, f"{r5['length']}")
    try:
        tsp(2, [[0, 1]])
        ck("距离矩阵尺寸不符被拒", False, "没抛异常")
    except ValueError:
        ck("距离矩阵尺寸不符被拒", True, "ValueError")

    print()
    print("=" * 72)
    print(f"{'ALL PASS' if bad == 0 else 'FAILED'}  {ok} 通过 / {bad} 失败")
    print("=" * 72)
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    raise SystemExit(selftest())
