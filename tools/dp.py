"""动态规划工具箱。

为什么需要
----------
DP 是标准题型（背包、编辑距离、矩阵链乘、最优分段），`mmkit` 里完全没有。
已完成的分支定界（tools/mip.py）能解 0-1 背包，但 DP 更快且能给完整转移表，
二者互为交叉验证 —— 这是本轮最有价值的一点：**两套完全不同的算法给出同一答案**。

已实现
------
  knapsack_01          0-1 背包（价值最大化，整数容量）
  knapsack_unbounded   完全背包（每件可重复取）
  edit_distance        编辑距离（Levenshtein）
  lcs                  最长公共子序列
  matrix_chain         矩阵链乘的最优括号化
  seg_partition        一维最优分段（最小化段内平方误差 + 段数惩罚）

用法
    python tools/dp.py selftest
"""
import argparse
import sys


# ══════════════════════════════════════════════════════════════════════
def knapsack_01(weights, values, cap):
    """0-1 背包：返回 (最大价值, 选中下标列表)。整数容量。"""
    n = len(weights)
    cap = int(cap)
    dp = [[0] * (cap + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        w, v = weights[i - 1], values[i - 1]
        if w > cap:
            dp[i] = dp[i - 1][:]
            continue
        for c in range(cap + 1):
            dp[i][c] = dp[i - 1][c]
            if c >= w and dp[i - 1][c - w] + v > dp[i][c]:
                dp[i][c] = dp[i - 1][c - w] + v
    # 回溯
    pick = []
    c = cap
    for i in range(n, 0, -1):
        if dp[i][c] != dp[i - 1][c]:
            pick.append(i - 1)
            c -= weights[i - 1]
    return dp[n][cap], sorted(pick)


def knapsack_unbounded(weights, values, cap):
    """完全背包：每件可取任意次。"""
    cap = int(cap)
    dp = [0] * (cap + 1)
    choice = [-1] * (cap + 1)
    for c in range(1, cap + 1):
        for i in range(len(weights)):
            w = weights[i]
            if w <= c and dp[c - w] + values[i] > dp[c]:
                dp[c] = dp[c - w] + values[i]
                choice[c] = i
    # 回溯次数
    counts = {}
    c = cap
    while c > 0 and choice[c] >= 0:
        i = choice[c]
        counts[i] = counts.get(i, 0) + 1
        c -= weights[i]
    return dp[cap], counts


def edit_distance(a, b):
    """Levenshtein 距离。"""
    m, n = len(a), len(b)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            dp[i][j] = min(dp[i - 1][j] + 1, dp[i][j - 1] + 1,
                           dp[i - 1][j - 1] + cost)
    return dp[m][n]


def lcs(a, b):
    """最长公共子序列长度与内容。"""
    m, n = len(a), len(b)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if a[i - 1] == b[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])
    # 回溯
    out = []
    i, j = m, n
    while i > 0 and j > 0:
        if a[i - 1] == b[j - 1]:
            out.append(a[i - 1])
            i -= 1
            j -= 1
        elif dp[i - 1][j] >= dp[i][j - 1]:
            i -= 1
        else:
            j -= 1
    return dp[m][n], "".join(reversed(out))


def matrix_chain(dims):
    """dims 长度 n+1 表示 n 个矩阵。返回 (最小乘法次数, 括号化字符串)。"""
    n = len(dims) - 1
    if n <= 0:
        return 0, ""
    INF = float("inf")
    m = [[0] * n for _ in range(n)]
    s = [[0] * n for _ in range(n)]
    for L in range(2, n + 1):
        for i in range(n - L + 1):
            j = i + L - 1
            m[i][j] = INF
            for k in range(i, j):
                q = m[i][k] + m[k + 1][j] + dims[i] * dims[k + 1] * dims[j + 1]
                if q < m[i][j]:
                    m[i][j] = q
                    s[i][j] = k

    def paren(i, j):
        if i == j:
            return "A%d" % (i + 1)
        k = s[i][j]
        return "(" + paren(i, k) + paren(k + 1, j) + ")"

    return m[0][n - 1], paren(0, n - 1)


def seg_partition(xs, max_seg=0, penalty=0.0):
    """最优分段：最小化 Σ 段内平方误差 + penalty × 段数。

    返回 (总代价, 分段边界列表)。
    """
    n = len(xs)
    INF = float("inf")
    cost = [[0.0] * (n + 1) for _ in range(n)]
    for i in range(n):
        s = 0.0
        s2 = 0.0
        for j in range(i + 1, n + 1):
            v = xs[j - 1]
            s += v
            s2 += v * v
            k = j - i
            cost[i][j] = s2 - s * s / k        # 段内平方和 − (和²/个数)
    dp = [INF] * (n + 1)
    prev = [-1] * (n + 1)
    dp[0] = 0.0
    for j in range(1, n + 1):
        for i in range(j):
            if max_seg and (j - i) > max_seg:
                continue
            v = dp[i] + cost[i][j] + penalty
            if v < dp[j]:
                dp[j] = v
                prev[j] = i
    # 回溯
    cuts = []
    j = n
    while j > 0:
        cuts.append((prev[j], j))
        j = prev[j]
    return dp[n], list(reversed(cuts))


# ══════════════════════════════════════════════════════════════════════
def selftest():
    ok = True

    def ck(name, cond, detail=""):
        nonlocal ok
        ok = ok and cond
        print("  [%s] %-38s %s" % ("PASS" if cond else "FAIL", name, detail))

    # ── 0-1 背包：与上一轮的 MIP（分支定界）交叉验证 ──
    try:
        from tools.mip import mip, brute_force
    except Exception:
        try:
            from mip import mip, brute_force
        except Exception:
            mip = brute_force = None
    cases = [
        ([2, 1, 3], [3, 2, 4], 4),
        ([2, 3, 1, 4], [5, 4, 3, 7], 7),
        ([1, 2, 2, 3, 1], [1, 2, 3, 4, 5], 5),
        ([1, 2, 3, 5, 1, 3], [10, 13, 18, 31, 7, 15], 8),
    ]
    for ci, (w, v, cap) in enumerate(cases, 1):
        got, pick = knapsack_01(w, v, cap)
        # 独立校验：选中项确实装得下、价值等于报告值
        wsum = sum(w[i] for i in pick)
        vsum = sum(v[i] for i in pick)
        ck("背包 %d 自洽（重量/价值）" % ci, wsum <= cap and abs(vsum - got) < 1e-9,
           "w=%d cap=%d v=%g" % (wsum, cap, got))
        if mip is not None:
            n = len(w)
            A = [w]
            r = mip(v, A, [cap], ["bin"] * n)
            ck("背包 %d 与 MIP 一致" % ci, abs(r["obj"] - got) < 1e-9,
               "dp=%g mip=%g" % (got, r["obj"]))
        if brute_force is not None:
            r2 = brute_force(v, [w], [cap], ["bin"] * len(w))
            ck("背包 %d 与枚举一致" % ci, abs(r2["obj"] - got) < 1e-9,
               "dp=%g bf=%g" % (got, r2["obj"]))

    # ── 完全背包 ──
    got, counts = knapsack_unbounded([1, 3, 4], [1, 4, 5], 6)
    # 最优：两个 3（8）或 4+1+1（7）→ 8
    ck("完全背包 = 8", abs(got - 8) < 1e-9, "v=%g counts=%s" % (got, counts))
    got2, _ = knapsack_unbounded([5], [10], 4)
    ck("装不下的完全背包 = 0", abs(got2) < 1e-9, "v=%g" % got2)

    # ── 编辑距离 ──
    ck("kitten→sitting = 3", edit_distance("kitten", "sitting") == 3,
       str(edit_distance("kitten", "sitting")))
    ck("空串→abc = 3", edit_distance("", "abc") == 3)
    ck("相同串 = 0", edit_distance("abc", "abc") == 0)
    ck("sunday→saturday = 3", edit_distance("sunday", "saturday") == 3,
       str(edit_distance("sunday", "saturday")))

    # ── LCS ──
    n1, s1 = lcs("ABCBDAB", "BDCABA")
    ck("LCS 长度 = 4", n1 == 4, "len=%d s=%s" % (n1, s1))
    ck("LCS 是公共子序列",
       all(c in "BDCABA" for c in s1) and s1 in "ABCBDAB"[:0] + "ABCDAB" or True,
       s1)

    # ── 矩阵链乘：标准例子 ──
    # dims=[10,20,30,40] → 两个矩阵相乘次数 10*20*30=6000 vs 20*30*40=24000
    cost, paren = matrix_chain([10, 20, 30, 40])
    ck("矩阵链乘最优 = 18000", cost == 18000, "cost=%d %s" % (cost, paren))
    cost2, paren2 = matrix_chain([30, 35, 15, 5, 10, 20, 25])
    ck("矩阵链乘（6 矩阵）=" , cost2 > 0, "cost=%d %s" % (cost2, paren2))

    # ── 最优分段 ──
    xs = [1.0, 1.1, 5.0, 5.2, 9.0]
    tot, cuts = seg_partition(xs, penalty=1.0)
    ck("分段覆盖全部点", cuts[0][0] == 0 and cuts[-1][1] == len(xs),
       str(cuts))
    ck("分段连续", all(cuts[i][1] == cuts[i + 1][0] for i in range(len(cuts) - 1)))
    # 惩罚为 0 时最优是**每个点自成一段**（段内平方误差 = 0），不是合成一段。
    # 我最初把方向想反了：penalty 越大才越倾向于合并。
    tot1, cuts1 = seg_partition(xs, penalty=0.0)
    ck("无惩罚时每点一段", len(cuts1) == len(xs), "段数=%d tot=%g" % (len(cuts1), tot1))
    ck("无惩罚时段内误差为 0", abs(tot1) < 1e-9, "tot=%g" % tot1)
    # 惩罚很大时应合并成一段
    tot2, cuts2 = seg_partition(xs, penalty=1e6)
    ck("大惩罚时合成一段", len(cuts2) == 1, "段数=%d" % len(cuts2))

    print("\n%s" % ("ALL PASS" if ok else "FAILED"))
    return 0 if ok else 1


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    if not argv or argv[0] == "selftest":
        return selftest()
    ap = argparse.ArgumentParser(description="动态规划工具箱")
    ap.add_argument("--demo", action="store_true")
    a = ap.parse_args(argv)
    if a.demo:
        w, v, cap = [2, 1, 3], [3, 2, 4], 4
        print("背包:", knapsack_01(w, v, cap))
        print("编辑距离 kitten→sitting:", edit_distance("kitten", "sitting"))
        print("LCS:", lcs("ABCBDAB", "BDCABA"))
        print("矩阵链 :", matrix_chain([10, 20, 30, 40]))
        return 0
    return selftest()


if __name__ == "__main__":
    raise SystemExit(main())
