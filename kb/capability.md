==================================================================
插件能力报告
==================================================================

方法库共 56 条分支

能做（23 条，41%）：
  run        6 条  t检验 / ANOVA, χ²检验, 多元回归 / Logistic回归, 多元线性回归（最小二乘）
  graph      3 条  Mann-Whitney / Krusk, Dijkstra / A*, Kruskal / Prim
  profile    3 条  删除/填充/插值, IQR/Z-score/Isolatio, 相关性/重要性/RFE
  forecast   2 条  ARIMA / Prophet, ARIMA + 特征重要性分析
  solve      2 条  期望优化, 超售/定价优化
  grey       2 条  GM(1,1), GM(1,N)
  plot       1 条  熵权法 + TOPSIS（客观）
  ahp        1 条  AHP + 模糊评价（主客观结合）
  cluster    1 条  K-Means / DBSCAN / 层
  greyrel    1 条  灰色关联分析
  ode        1 条  ODE (scipy integrate

已知做不了（11 条，20%）：
  LSTM / XGBoost          需深度学习框架，环境只有 numpy
  XGBoost / RandomForest  需 xgboost 包，未安装
  XGBoost / LightGBM / S  需 xgboost 包，未安装
  GA / PSO / SA           启发式优化未实现
  加权法 / ε-约束 / NSGA-II    需遗传算法框架，未实现
  PDE (有限差分)              未实现
  蒙特卡洛                    可作为求解手段，但不是独立命令
  元胞自动机                   未实现
  马氏链                     未实现
  动态规划                    未实现
  变分法/Euler方程             未实现

未知缺口（22 条，39%）：
  广义差分法
  报童模型
  (s,S)策略
  灰色系统
  LP (PuLP/OR-Tools)
  MILP (OR-Tools CP-SAT)
  Dinic / EK
  TSP (GA/SA)
  VRP (蚁群/节约算法)
  差分方程
  Leslie矩阵
  蛛网模型
  最优控制/Hamilton
  量纲分析
  因果回路图 / 存量流量图
  Nash均衡 / Shapley值
