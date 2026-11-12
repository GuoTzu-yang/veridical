#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""额外领域库：评价 / 预测 / 图论 / 排队 / 增长。

原本这些放在 domain.py 的 DOMAINS 字典里，但字典很大，脚本插入容易
错缩进。单独成文件、由 domain.py 在末尾 update 进来，改动面最小。

原则：公式必须是**该领域通用的**，不含任何具体题目的专有名词。
宁少勿错 —— 两条站得住的通用式，好过五条半对的。
"""

EXTRA = {
    "evaluation": dict(
        cn="综合评价",
        en="multi-criteria evaluation",
        en_detail="scoring, weighting and ranking of alternatives",
        zh="指标 / 权重 / 排序",
        keywords=["评价", "评分", "排名", "排序", "权重", "综合", "指标",
                  "优劣", "选优", "evaluation", "scoring", "ranking",
                  "weight", "criteria"],
        numbers=[
            ("$r_{ij}$",
             r"(x_{ij}-\min_j x_{ij})/(\max_j x_{ij}-\min_j x_{ij})",
             "normalised indicator"),
            ("$S_i$", r"\sum_j w_j r_{ij}", "composite score"),
        ],
        assumptions=[
            "All indicators are converted to a common direction before "
            "weighting, so that a larger normalised value always means a "
            "better alternative.",
            "The comparison is scale-free: only the relative position of "
            "each alternative on each indicator enters, not its raw "
            "magnitude.",
            "Weights express priorities, not statistical importance; they "
            "are supplied by the decision context and are varied in a "
            "sensitivity check rather than estimated from the data.",
        ],
        equation=r"""
\begin{equation}
S_i = \sum_{j=1}^{m} w_j\, r_{ij}, \qquad
\sum_{j=1}^{m} w_j = 1, \quad w_j \ge 0,
\label{eq:composite}
\end{equation}
\noindent $r_{ij}$ is alternative $i$'s normalised value on indicator
$j$ and $w_j$ is that indicator's weight. Direction is fixed before
normalisation, so every $r_{ij}$ points the same way. The composite is a
weighted sum rather than a distance to an ideal point because it keeps the
contribution of each indicator auditable.
""",
        extra_eq=r"""
\begin{equation}
C_i = \frac{D_i^{-}}{D_i^{+} + D_i^{-}},
\qquad
D_i^{\pm} = \bigl\| r_i - r^{\pm} \bigr\|_2,
\label{eq:closeness}
\end{equation}
\noindent where $r^{+}$ and $r^{-}$ are the ideal and anti-ideal points
formed from the best and worst observed value on each indicator. $C_i$
near one means alternative $i$ is close to the ideal. Reporting both the
weighted sum and this closeness is a consistency check on the ranking,
not a second opinion.
""",
    ),
    "prediction": dict(
        cn="预测",
        en="time-series forecasting",
        en_detail="trend, seasonality and forecast error",
        zh="趋势 / 周期 / 误差",
        keywords=["预测", "趋势", "时间序列", "未来", "时序", "外推",
                  "forecast", "predict", "trend", "series", "horizon",
                  "月份", "年份", "日期", "month", "year", "date"],
        numbers=[
            ("$e_t$", r"y_t - \hat{y}_t", "one-step residual"),
            ("$h$", r"1,2,\dots", "forecast horizon"),
        ],
        assumptions=[
            "The generating process is stable over the forecast horizon: "
            "the relation estimated on the observed window still holds "
            "outside it.",
            "Residuals are treated as the irreducible error; structure that "
            "remains in them would mean the model is misspecified rather "
            "than that the data are noisy.",
            "Forecasts are conditional on the observed history and carry "
            "the uncertainty of the parameter estimates, which is why an "
            "interval is reported alongside every point forecast.",
        ],
        equation=r"""
\begin{equation}
\hat{y}_{t+h} = f\bigl(y_t, y_{t-1}, \dots, y_{t-p};
\hat{\boldsymbol{\theta}}\bigr),
\label{eq:forecast}
\end{equation}
\noindent where $p$ is the number of lags retained and
$\hat{\boldsymbol{\theta}}$ is estimated on the observed window. The lag
order is chosen by out-of-sample error, not by in-sample fit: an extra lag
always lowers the residual sum of squares and therefore cannot be selected
that way.
""",
        extra_eq=r"""
\begin{equation}
\mathrm{RMSE} = \sqrt{\frac{1}{n}\sum_{t=1}^{n} e_t^{2}},
\qquad
\mathrm{MAPE} = \frac{100}{n}\sum_{t=1}^{n}
\Bigl|\frac{e_t}{y_t}\Bigr|,
\label{eq:ferror}
\end{equation}
\noindent Both are reported because they answer different questions: RMSE
is in the units of the response and is dominated by large errors, while
MAPE is scale-free and is dominated by small actual values. A single error
statistic can be made to look good by choosing the one that favours the
model.
""",
    ),
    "network": dict(
        cn="图论与网络",
        en="graph and network optimisation",
        en_detail="routing, connectivity and flow conservation",
        zh="节点 / 边 / 路径",
        keywords=["网络", "路径", "节点", "连通", "最短", "最大流", "路线",
                  "network", "graph", "path", "node", "edge", "route",
                  "flow", "起点", "终点", "距离", "边", "弧"],
        numbers=[
            ("$c_{ij}$", r"w(i,j)", "edge weight"),
            ("$x_{ij}$", r"\{0,1\}", "edge selected"),
        ],
        assumptions=[
            "The graph is known before optimisation: nodes, edges and their "
            "weights are given rather than inferred, so the problem is one "
            "of selection and not of structure discovery.",
            "Edge weights are additive along a path and independent of the "
            "flow already carried, which rules out congestion effects.",
            "Flow is conserved at every internal node, so what enters leaves "
            "except at the designated source and sink.",
        ],
        equation=r"""
\begin{equation}
\min \sum_{(i,j)\in E} c_{ij}\, x_{ij}
\quad\text{s.t.}\quad
\sum_{j} x_{ij} - \sum_{j} x_{ji} =
\begin{cases} 1 & i = s \\ -1 & i = t \\ 0 & \text{otherwise}\end{cases}
\label{eq:shortest}
\end{equation}
\noindent with $x_{ij}\in\{0,1\}$. The right-hand side is the flow
balance: one unit leaves the source, one unit enters the sink, and nothing
accumulates at an internal node. Relaxing $x_{ij}$ to $[0,1]$ leaves the
optimal value unchanged for this constraint matrix, which is why a linear
programme solves it exactly.
""",
        extra_eq=r"""
\begin{equation}
\max \sum_{j} f_{sj}
\quad\text{s.t.}\quad
0 \le f_{ij} \le u_{ij},\;
\sum_{j} f_{ij} = \sum_{j} f_{ji}\;\;(i \ne s,t),
\label{eq:maxflow}
\end{equation}
\noindent where $u_{ij}$ is the capacity of edge $(i,j)$. By the
max-flow min-cut theorem the optimal value equals the capacity of the
bottleneck cut, so the solution certifies itself: any cut of that capacity
is a proof of optimality that needs no comparison against a baseline.
""",
    ),
    "queueing": dict(
        cn="排队与随机服务",
        en="queueing and stochastic service",
        en_detail="arrival rate, service rate and waiting time",
        zh="到达 / 服务 / 等待",
        keywords=["排队", "等待", "服务", "到达率", "队列", "窗口", "客流",
                  "queue", "wait", "service", "arrival", "server"],
        numbers=[
            ("$\\rho$", r"\lambda/\mu", "utilisation"),
            ("$L$", r"\lambda W", "mean number in system"),
        ],
        assumptions=[
            "Arrivals are modelled as a Poisson process, so the time to the "
            "next arrival does not depend on how long the current wait has "
            "already been.",
            "Service times are independent of arrival times and of each "
            "other; a server that slows down under load would break the "
            "independence the formulas rely on.",
            "The system is in steady state: the observation window starts "
            "after the transient, and $\\rho < 1$ so a stationary "
            "distribution exists.",
        ],
        equation=r"""
\begin{equation}
\rho = \frac{\lambda}{\mu}, \qquad
L = \lambda W, \qquad
L_q = \lambda W_q,
\label{eq:little}
\end{equation}
\noindent $\lambda$ is the arrival rate and $\mu$ the service rate.
Little's law relates the mean number in the system to the mean time spent
there and holds for any stable system, whatever the arrival and service
distributions; it is therefore the safest of the queueing relations to
report, because it does not depend on the distributional assumptions.
""",
        extra_eq=r"""
\begin{equation}
W = \frac{1}{\mu - \lambda}, \qquad
W_q = \frac{\rho}{\mu - \lambda}
\qquad (\rho < 1),
\label{eq:mm1}
\end{equation}
\noindent for a single server with Poisson arrivals and exponential
service. The form is specific to that model; when the service distribution
is not exponential the same mean can be far off, which is why the
distributional assumption is stated rather than left implicit.
""",
    ),
    "population": dict(
        cn="增长与种群动力学",
        en="growth and population dynamics",
        en_detail="carrying capacity, spread and interaction",
        zh="增长 / 承载 / 传播",
        keywords=["增长", "种群", "传播", "感染", "人口", "扩散", "竞争",
                  "growth", "population", "spread", "infect", "epidemic"],
        numbers=[
            ("$r$", r"\tfrac{1}{N}\tfrac{dN}{dt}", "per-capita growth rate"),
            ("$K$", r"\lim_{t\to\infty} N(t)", "carrying capacity"),
        ],
        assumptions=[
            "The population is closed: no immigration or emigration, so "
            "change in size is attributable to births and deaths alone.",
            "The environment is constant, so the growth rate and the "
            "carrying capacity do not drift over the modelled horizon.",
            "Individuals are exchangeable within a compartment; the model "
            "tracks counts, not identities, which is what allows it to be "
            "written as a small system of ordinary differential equations.",
        ],
        equation=r"""
\begin{equation}
\frac{dN}{dt} = rN\Bigl(1 - \frac{N}{K}\Bigr),
\label{eq:logistic}
\end{equation}
\noindent with $r>0$ the intrinsic growth rate and $K>0$ the carrying
capacity. Growth is exponential while $N \ll K$ and vanishes as
$N \to K$; the two parameters are separately identifiable only if the
observations cover both regimes, which is a condition on the data rather
than on the model.
""",
        extra_eq=r"""
\begin{equation}
\frac{dS}{dt} = -\frac{\beta S I}{N}, \quad
\frac{dI}{dt} = \frac{\beta S I}{N} - \gamma I, \quad
\frac{dR}{dt} = \gamma I,
\label{eq:sir}
\end{equation}
\noindent with $\beta$ the transmission rate and $\gamma$ the removal
rate. The basic reproduction number is
$\mathcal{R}_0 = \beta/\gamma$: an outbreak grows only if
$\mathcal{R}_0 > 1$. Reporting $\mathcal{R}_0$ rather than the raw
coefficients is what makes the result comparable across settings.
""",
    ),
}
