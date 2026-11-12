| 命令 | 干什么 | 关键参数 |
|---|---|---|
| `advise` | 定题：判断题型（关系与解释/预测/优化/评价）+ 逐条可复核依据 | --data(数据) --sheet(工作表) --x(解释变量) --y(目标列) |
| `ahp` | 层次分析：判断矩阵 --ahp 求权重，带一致性检验 | --ahp(判断矩阵) |
| `clean` | 清洗：列名英文化（--names-out）、导出 CSV | --data(数据) --sheet(工作表) |
| `cluster` | 聚类：--x 选变量、--k 定簇数，出划分与簇质量 | --data(数据) --k(簇数) --sheet(工作表) --x(解释变量) |
| `dim` | 量纲分析：--var '名字=量纲'（等号！）求 Buckingham Pi 群 | --var(变量) |
| `forecast` | 时间序列预测：--t 时间轴、--y 目标，外推 --horizon 步 | --data(数据) --horizon(预测步数) --sheet(工作表) --t(时间轴) |
| `graph` | --op 四选一：dijkstra 最短路 / mst 最小生成树 / flow 最大流 / tsp 旅 | --edges(边) --matrix(邻接矩阵) --nodes(点) --op(算法) |
| `grey` | 灰色预测 GM(1,1)：小样本序列外推，与 forecast 互为对照 | --data(数据) --horizon(预测步数) --series(序列) --sheet(工作表) |
| `greyrel` | 灰色关联 + 模糊综合评价：--directions 定指标方向、--weights/--ahp 定权重 | --ahp(判断矩阵) --directions(方向) --grades(等级) --matrix(邻接矩阵) |
| `hints` | 给出可复制的命令提示（含 --claim/--compile 的常用组合） | --claim(主张) --compile(编译) --data(数据) --lang(语言) |
| `merge` | 多表合并：按共同列合并多个 sheet 或文件 | --data(数据) --sheet(工作表) |
| `ode` | 常微分方程：--rhs 给右端表达式，--method rk45|rk4 | --method(方法) --rhs(右端式) --t0(起点) --t1(终点) |
| `plot` | --kind 十六种图：scatter/forecast/bar/pareto/corr/pred/se | --data(数据) --horizon(预测步数) --k(簇数) --kind(图型) |
| `profile` | 数据剖面：每列的分布、缺失、异常摘要 | --data(数据) --sheet(工作表) |
| `race` | 模型赛马：多个模型结构 x 多 seed 的交叉验证对比，出 RMSE/R2 表 | --data(数据) --sheet(工作表) --x(解释变量) --y(目标列) |
| `run` | 一条龙：读数据到出 PDF 全自动 | --claim(主张) --compile(编译) --data(数据) --lang(语言) |
| `selftest` | 自检：所有内置用例 | — |
| `solve` | 约束优化：单目标最大化/最小化，或 --constraint 带约束；含 Pareto 前沿与膝点 | --constraint(约束) --data(数据) --maximize(最大化) --obj(目标列) |
| `video` | GIF/MP4：把多张图串成逐帧动画 | --data(数据) --out-gif(GIF) --sheet(工作表) --x(解释变量) |
