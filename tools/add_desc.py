import ast
import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "schema.py")
s = open(P, encoding="utf-8").read()

DESC = '''

# ══════════════════════════════════════════════════════════════════════
#  每个子命令干什么
#
#  为什么非要有这张表
#  ------------------
#  mmkit 的 22 个参数全挂在顶层 argparse 上，`cmd` 只是个 choices。
#  于是 `mmkit race --help` 和 `mmkit run --help` 输出**完全一样** ——
#  58 个全局参数，看不出命令之间的区别。实测确认过。
#
#  结果是：LLM 只知道有个命令叫 race，不知道它和 run 差在哪，
#  于是每次都退回 run 一条龙，插件的能力全被绕过。
#
#  这张表是「能力可发现」的唯一入口。
# ══════════════════════════════════════════════════════════════════════

DESC = {
    "advise": "定题：判断题型（关系与解释/预测/优化/评价）+ 逐条可复核依据。"
              "**建模第一步**，先用它确认方向再选工具",
    "race": "模型赛马：多个模型结构 x 多 seed 的交叉验证对比，出 RMSE/R2 表。"
            "要回答「为什么用这个模型」就跑它",
    "solve": "约束优化：单目标最大化/最小化，或 --constraint 带约束；"
             "含 Pareto 前沿与膝点",
    "forecast": "时间序列预测：--t 时间轴、--y 目标，外推 --horizon 步",
    "grey": "灰色预测 GM(1,1)：小样本序列外推，与 forecast 互为对照",
    "greyrel": "灰色关联 + 模糊综合评价：--directions 定指标方向、"
               "--weights/--ahp 定权重、--membership/--grades 做模糊评。"
               "评价类题目的主力",
    "ahp": "层次分析：判断矩阵 --ahp 求权重，带一致性检验",
    "cluster": "聚类：--x 选变量、--k 定簇数，出划分与簇质量",
    "graph": "--op 四选一：dijkstra 最短路 / mst 最小生成树 / "
             "flow 最大流 / tsp 旅行商",
    "ode": "常微分方程：--rhs 给右端表达式，--method rk45|rk4",
    "dim": "量纲分析：--var '名字=量纲'（等号！）求 Buckingham Pi 群",
    "profile": "数据剖面：每列的分布、缺失、异常摘要",
    "clean": "清洗：列名英文化（--names-out）、导出 CSV",
    "merge": "多表合并：按共同列合并多个 sheet 或文件",
    "plot": "--kind 十六种图：scatter/forecast/bar/pareto/corr/pred/sens/"
            "flow/box/hist/resid/qq/tornado/cand/surface/surfaces",
    "video": "GIF/MP4：把多张图串成逐帧动画",
    "hints": "给出可复制的命令提示（含 --claim/--compile 的常用组合）",
    "cand": "候选模型对比表",
    "surface": "响应面：两因素对目标的三维曲面",
    "run": "一条龙：读数据到出 PDF 全自动。**自动模式**，"
           "会替你做掉所有建模决定 —— DSH 主导建模时不要用它",
    "selftest": "自检：所有内置用例",
}
'''

if "DESC = {" not in s:
    # 插到第一个 def 之前
    i = s.find("\ndef ")
    assert i > 0
    s = s[:i] + DESC + s[i:]

# 让 build() 把 desc 写进命令条目
OLD = '        "args": '
if '"desc":' not in s:
    # 在构造每个命令 dict 的地方加 desc
    for pat, rep in (
        ('{name: ({"args": ', '{name: ({"desc": DESC.get(name, ""),\n                   "args": '),
    ):
        if pat in s:
            s = s.replace(pat, rep, 1)
            print("  patched command dict")
            break

ast.parse(s)
compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  已加 DESC 表（%d 条）" % s.count('": "'))