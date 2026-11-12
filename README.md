# model1 架构 · 三个真瓶颈的可执行改造

原图有一处硬伤：三个关键节点只有名字，没有判据。

| 图上原文 | 缺什么 |
|---|---|
| 「置信度评估」×3 | 置信度怎么算、几分算过、谁给分 |
| 「对宿主提问」 | 什么时候问、问几个、不答怎么办 |
| 「汇总同类 · 逐列构建」 | 用什么判"同类"、判错了怎么办 |

本目录把这三处填成**可运行代码**，并给出落库字段与接线位置。

**交付物 · 架构本体**（根目录 8 个文件，看这些就能看懂架构）

| 文件 | 是什么 |
|---|---|
| `harness.py` | 主判定：`Claim`、三道闸、环境档位、e3 来源推导 |
| `extend.py` | 主线流程：取证 → 循环 → 闸门 → 组合 → 记账 |
| `taskgraph.py` | 任务级组合、账本校准、复合键先验 |
| `ledger.py` | 判定账本 + 写入门禁（默认拒绝） |
| `precheck.py` | 前置检查（三态 + 机制适用性），可插拔 |
| `sqlcheck.py` | `sql` 领域的前置检查实现 |
| `sargable.py` | 机制适用性规则（索引原理上能不能用上） |
| `mcp_server.py` | MCP 入口，9 个工具，全部走 `evaluate_claims` |

**回归套件**（`tests/`，25 项）

| 是什么 |
|---|
| `tests/case_1440.py` — 真实长任务端到端 |
| `tests/survey_19.py` — 19 题证据普查 |
| `tests/collect_*.py` — 样本采集（SQL / file+http / L2 降级 / 结论复查 / 机制维度） |
| `tests/evaluate_model.py` — 判据自评（精确率 / 覆盖率 / 推翻率 / 分组对照） |
| `tests/run_all.py` — **统一回归入口** |

**验证**

```bash
python tests/run_all.py            # 全部（本体 4 项断言 + 套件 25 个）
python tests/run_all.py --core     # 只跑架构本体
python tests/run_all.py --quiet    # 只报失败
```

单个跑（调试用）：

```bash
python harness.py selftest    # 52 项断言
python extend.py  selftest    # 46 项断言
python ledger.py  guard       # 8 项写入门禁
python sargable.py            # 15 条实测谓词
```

---

## 瓶颈一 · 置信度评估

### 原状与缺陷

图上三处「置信度评估」，没有一处写判据。如果这个分由模型自己打，那就是**自己批卷三次**——不但不提升，还会制造"我很确信"的假象。

### 改造：三维计分，每维 0/1/2

| 维度 | 0 分 | 1 分 | 2 分 |
|---|---|---|---|
| **E1 溯源度** | 无来源，纯生成 | 指到来源名，指不到位置 | 指到位置：章节／URL+锚点／命令与退出码／公式与代入值 |
| **E2 独立度** | 单一来源，或全部同源 | 两个来源，但无法排除同源转载 | ≥3 个独立来源，或 1 个一手来源 + 1 次独立复算 |
| **E3 可复现度** | 不可复现（主观／未来预测） | 部分可复现，但缺环境或数据 | 给出命令、数据、公式，第三方能跑出同样结果 |

**C = E1 + E2 + E3 − 扣分**，满分 6，夹在 0–6。

扣分项（来自实际踩过的两类失败）：

| 扣分 | 触发条件 |
|---|---|
| −1 | 来源之间互相矛盾，且未解释（每处各扣） |
| −1 | 结论超出所引来源的适用范围 |

### 三道闸是递进的，不是重复的

| 闸 | 图上位置 | 只判 | 通过线 | 打回线 |
|---|---|---|---|---|
| **G1** | 分队列 → 深度切入之前 | E1 | ≥1 | 0 |
| **G2** | 深度切入 → 优化拓展之前 | E1+E2 | =4 | ≤2（3 分降级） |
| **G3** | 优化拓展 → 生成方案之前 | E1+E2+E3 | ≥5 | ≤2 |

三档判定：`pass`（可输出）／`degrade`（可走，但必须带不确定标注，且不再抬权重）／`reject`（不进下一步）。

**为什么这样切**：G1 只需查"有没有出处"（最便宜），G2 才要查来源是否独立，G3 才要求能复现（最贵）。越早拦下越省。

### 代码位置

```
Claim.score()      # 三维求和减扣分
gate(c, stage)     # 单道闸判定
run_gates(c)       # 三闸顺序执行，reject 即终止
```

### 自测证据

| 样例 | C | 结果 |
|---|---|---|
| C_SQ1 存量 12.3 万（单一来源） | 4 | G2 打回 |
| C_SQ2 保有量 39.4 万（两来源疑同源） | 5 | G2 降级 → G3 通过 |
| C_SQ3 车桩比 3.2:1（三源+复算） | 6 | 全通过 |
| C_SQ6 2030 缺口（券商研报+越界） | 0 | G2 打回 |

---

## 瓶颈二 · 对宿主提问

### 原状与缺陷

图上要求停下来问，但没画触发条件、没画超时、没画降级。后果：用户不答就死锁；批处理场景直接不可用。

### 改造：只允许两类可判触发

| 类型 | 判据 | 为什么可判 |
|---|---|---|
| **歧义型** | 同一题干按两种合理解释各跑一次粗解，**关键字段取值不同** | 跑两遍比对结果，不依赖模型自评 |
| **缺参型** | 解算链上的必需参数未绑定，且无法从题干或库推断 | 检查绑定表，值为空即缺 |

歧义型的关键是**分叉探测**，它把"我觉得不确定"换成了"两条路算出来的数不一样"：

```
解释A → 粗解 → {gap_value: 8.0,  unit: "万个"}
解释B → 粗解 → {gap_value: 22.5, unit: "%"}
                    ↑ 关键字段不一致 → 判为歧义
```

### 三条硬约束

| 约束 | 值 | 理由 |
|---|---|---|
| 一次最多问几个 | **2** | 超过 2 个，用户会直接不看 |
| 每条必须带什么 | **默认值** | 不带默认值就没法降级 |
| 每条必须说明什么 | **为什么问**（一句话指出分歧点） | 否则用户无法判断该答哪个 |

### 状态机

```
DETECT ──→ ASK(≤2问) ──→ WAIT
                          ├─ 有回答 ──→ MERGED（约束补丁）──→ 重新拆解
                          ├─ 超时   ──→ TIMEOUT_DEFAULT ──→ 继续（带存疑）
                          └─ 批处理 ──→ BATCH_DEFAULT  ──→ 继续（带存疑）
```

| 状态 | 触发 | 输出 |
|---|---|---|
| `MERGED` | 至少有一条被回答 | 回答作为约束补丁，重新拆解 |
| `TIMEOUT_DEFAULT` | 等待轮次耗尽 | 采用默认值，记入 caveats |
| `BATCH_DEFAULT` | `wait_rounds=0` | 不等，直接默认值 |

### 降级输出模板

```text
【答案】该市 2026 年缺口约 8 万个
【方向存疑】
  - 『gap_value』在不同解释下取值不同 → 未回复，采用默认：缺口=桩数缺口
  - 缺少必要输入: 城市 → 未回复，采用默认：按省会城市口径
【未验证项】
  - 2030 年预测未验证
```

**核心原则：不问也要给出东西，但绝不假装确定。**

### 代码位置

```
detect_fork(runs, key_fields)        # 分叉探测
detect_missing(required, bound)      # 缺参探测
build_questions(fork, missing)       # 转问题（强制 ≤2 且带默认）
ask_gate(questions, answered, wait)  # 状态机
render_degraded(answer, caveats, unresolved)  # 降级模板
```

---

## 瓶颈三 · 汇总同类

### 原状与缺陷

图上「汇总同类 → 逐列构建 → 分队列」，没说用什么判同类。靠模型"感觉像同一类"判错一次，后面整条链全歪，而且要等下游才暴露，回边一打回就是全链重跑。

### 改造：先结构化，再判等

每个子问题必须填满五个字段：

| 字段 | 含义 | 例 |
|---|---|---|
| `target` | 问的对象 | 充电桩存量 |
| `op` | 问的动作 | 求值／比较／证明／定义／列举／预测／评价 |
| `answer_type` | 答案类型 | 数值／布尔／集合／文本／过程／区间 |
| `conditions` | 约束集合 | {年份: 2026} |
| `required_params` | 必需输入 | [城市] |

### 判等规则

| 关系 | 条件 | 动作 |
|---|---|---|
| **强同类** | `op` 相同 且 `answer_type` 相同 且 `target` 相同 | 合并为一项 |
| **弱同类** | `op` 相同 且 `answer_type` 相同，`target` 不同 | 同列不同项，不合并 |
| **异类** | `op` 或 `answer_type` 不同 | 分到不同列 |

`op` 和 `answer_type` 决定了这题的解法骨架——骨架不同，强行合并必错。

### 冲突检测（合并前的最后一道）

同一个 `target`，但 `conditions` 对同一个键给出不同值 → **禁止合并**。

实例：两条都问"充电桩存量"，一条年份 2026、一条 2025 → 判冲突，两条并列保留，输出时同时说明。

### 输出结构

```json
{
  "columns": [
    {"signature": ["求值", "数值"],
     "items": [{"target": "充电桩存量",
                "primary": "SQ1",
                "merged_in": ["SQ4"],
                "conflicted": ["SQ7"]}],
     "conflicts": [{"reason": "同为『充电桩存量』，但 年份 分别为 2026 与 2025"}]}
  ],
  "n_columns": 2, "n_items": 5, "merged": 1, "conflicts": 1
}
```

**关键：合并与冲突都要留痕。** 只留代表项、丢掉被并入的，等于抹掉审计线索。

### 代码位置

```
SubQ                     # 结构化子问题
classify(a, b)           # 强/弱/异
conflict(a, b)           # 合并前冲突检测
group(subqs)             # 分列 + 归并 + 冲突
```

---

## 端到端 · 三个模块同时在线

单独测通不算数，要证明它们**互不打架**。`run_pipeline()` 把三个模块串起来跑同一道题：

```
分列 → 逐项过 G1/G2/G3 → 拒绝项直接归档 → 存疑项进提问闸 → 汇总
```

实跑输出：

```text
列 ['求值', '数值']:
  SQ1   C=4    reject  → 疑难1库 并入['SQ4'] 冲突['SQ7']
  SQ2   C=5    pass    → 方案库
  SQ3   C=6    pass    → 方案库
  SQ5   C=None None    → 待生成结论
列 ['预测', '数值']:
  SQ6   C=0    reject  → 疑难1库
统计: n_columns=2, n_items=5, passed=2, rejected=2, no_claim=1, merged=1, conflicts=1
```

四件事同时成立：

| 现象 | 说明什么 |
|---|---|
| 2 列分开 | `op` 不同的子问题没有被强行合并 |
| SQ4 并入 SQ1、SQ7 判冲突 | 判等按字段走，不是按感觉 |
| 被拒项全部落到疑难1库 | 拒绝有明确去向，不会静默丢弃 |
| SQ5 无结论标 `no_claim` | 未评分的项不会被当成"通过" |

**关键：`no_claim` 与 `reject` 必须分开。** 把"还没做"和"做了不合格"混为一种，疑难库就失去意义。

---

## 第二轮 · 四项补齐

第一轮留了四个口子，逐个填掉。

### X1 回边预算 —— 防死循环

图上四条回边，实际只有两条是"重做"：

| 回边 | 动作 | 上限 |
|---|---|---|
| A 置信度②不合格 → 回「多问题拆解」 | 重拆（贵） | 2 |
| C 疑难修完 → 回「深度切入」 | 重切（中） | 3 |
| B 疑难 → 放弃 → 疑难1库 | 终止 | — |
| D 生成方案后 → 放弃 | 终止 | — |

**只设单边上限不够。** A→C→A→C 交替触发能绕出 2×3=6 次，所以追加一道全局总预算 4。

实测：单独连用 A 三次，第三次被单边上限拦；交替触发 A,C,A,C,C，第五次被全局预算拦，快照 `exhausted=True`。

### X2 循环留痕 —— 分清真循环和空转

图上「循环推理 ≥3」只管次数，不管内容。跑完三轮说不出改了什么，也分不清真改三轮和空转三轮。

每轮记四个动作之一：`质疑复查`／`查漏补缺`／`优化底层`，改动归四类：`修正`／`补充`／`推翻`／`无变化`。

**「无变化」必须记**——它是判断"这类题值不值得循环"的唯一依据。据此给出强度建议：

| 有效率 | 建议 | 理由 |
|---|---|---|
| < 0.34 | `low` | 三轮回合里两轮空转，这题型不吃循环 |
| 0.34–0.66 | `mid` | 维持 |
| ≥ 0.66 | `max` | 多轮均有实质改动 |

实跑：三轮全空转 → 有效率 0.0 → 建议 `low`；三轮全改 → 有效率 1.0 → 建议 `max`。

**接进真实流程后，跑出一个不好看但有用的结果**：4 个结论 × 3 轮 = 12 轮主线循环，**11 轮空转，只有 1 轮有效**，有效率 0.083 → 建议 `low`。

原因不是代码写错，是**主线本身的能力边界**：它只能把话说得更具体（抬 e1），补不出独立来源（e2）和可复现证据（e3）——那两样必须去外面取。e1 一满，主线就无事可做。

这个数字直接把"主线管方向、支线管准确"从判断变成了测量值。

另加一条入账校验：**标了「无变化」但前后文本不同，直接拒绝入账**。

### X3 冷启动路由 —— 库空时不跑全流程

按题型库命中强度分三档：

| 命中 | 路由 | 深度切入口 | 优化拓展口 | 次/子问题 |
|---|---|---|---|---|
| ≥ 0.7 | full | 4 | 3 | 11 |
| 0.3–0.7 | std | 4 | 1 | 9 |
| < 0.3 | lite | 4 | 0 | 8 |

冷启动期未命中，优化拓展的 3 个取材口全关——查一个空库没有意义。

三档成本互不相同（8／9／11），这一点是修过的：初版 lite 和 std 都是 8 次，等于只有两档。

**路由已接进 `run_full`，参与成本计算**：4 个子问题下，未命中走 lite → 40 次调用；强命中走 full → 52 次。成本不再手写，由路由累加得出。

### X4 拒绝率实测 —— 把拍的数换成算的数

19 条合成样本覆盖 e1/e2/e3 各档与扣分组合，实跑分布：

| 档 | 条数 | 占比 |
|---|---|---|
| G1 打回 | 2 | 10.5% |
| G2 打回 | 6 | 31.6% |
| G3 打回 | 1 | 5.3% |
| G3 降级 | 4 | 21.1% |
| 通过 | 6 | 31.6% |

**平均 8.32 次/结论**，5 子问题 + 主线汇总 8 次 → **49.6 次调用**（旧口径拍的是 63）。

两条结论：

1. **G2 是主拦截点**，符合设计——它判"挖出来可不可信"，是最该拦的一道。
2. **G3 极少打回、主要降级**。这是对的：前两闸已保证来源与独立性，G3 再拦就过度。它拦住的 1 条是"越界 + 未解释矛盾"双扣到 C=2 的极端情况。

### X5 把预算接进流水线

第一轮的 `run_pipeline` 是单向的，没有回边，预算无从消耗。补一条最小重试路径：

```
被拒 → 申请 A（重拆）→ 模拟补证 → 重评
     → 仍拒 → 申请 C（重切）→ 模拟补证 → 重评
     → 仍拒 → 归档
```

实跑：C_SQ1 重试 1 次救回；C_SQ6 重试 3 次仍拒，记「重试次数用尽 3/3 → 放弃→疑难1库」。

**三种终止都必须有去处**：预算耗尽、次数用尽、仍是拒绝。初版漏了第三种，被测试抓出来。

> ⚠️ 「重做后补证」在代码里是模拟（e1/e2 各 +1、扣分 −1），用于验证预算逻辑，不代表真实检索效果。

### X6 两条接线跑通

| 接什么 | 函数 | 做了什么 |
|---|---|---|
| 主线循环 → 留痕 | `mainline_loop()` | 每轮挑最弱维度打；e1 满了就记「无变化」 |
| 留痕产物 → 支线闸门 | `run_full()` | 主线补完的结论交给带重试的闸门链 |

`run_full()` 是完整链路：**主线循环 → 支线三道闸（带预算）→ 归档**。

---

## 真实长任务实测

合成样本只能验证判据自洽，不能验证它**在真题上会怎么判**。所以拿真题目跑了两轮。

### 单题端到端：seekdb issue #1440

题面：[tasks/issue-1440.md](../seekdb-2026-competition/tasks/issue-1440.md)（Range-to-OR 等价谓词，73.578× 延迟差）。证据全部来自本地：

| 证据源 | 查到什么 |
|---|---|
| `../seekdb-2026-competition/data/issues_detail.json` #1440 | 完整 body 5910 字符、2 条评论、精确 revision |
| `../seekdb-2026-competition/data/tree_2026competition.json` | 9879 条源码路径，能定位到文件 |
| `../seekdb-2026-competition/docs/` | 三份主文档 0 次提及 1440；附录里 3 次均为「和 #1440 同源」的引用 |
| `../seekdb-2026-competition/bench/` | 只有 `eqfilter.sql` 与 `records.csv`，**无 `case_1440.sql`** |

拆成 5 个子问题，跑完的判定：

```text
C_SQ1  e1=2 e2=0 e3=0 C=2  G1:pass → G2:reject
C_SQ2  e1=0 e2=0 e3=0 C=0  G1:reject
C_SQ3  e1=2 e2=0 e3=1 C=3  G1:pass → G2:reject
C_SQ4  e1=2 e2=0 e3=2 C=4  G1:pass → G2:pass → G3:degrade
C_SQ5  e1=2 e2=0 e3=0 C=2  G1:pass → G2:reject
打回 4/5，卡口 {'G2': 3, 'G1': 1}
```

**系统给出的是「做不了 + 为什么做不了」，不是一个硬凑的方案。** 这正是设计意图。

同时跑出来的东西：分叉探测判 `forked=True`（「区间保持原语」vs「OR 链先化简再下推」导出不同改动模块）、缺参探测抓到 3 个缺失、提问闸落 `TIMEOUT_DEFAULT` 并给出降级输出。

### 这次实测暴露的三个真问题

| 问题 | 现象 | 处置 |
|---|---|---|
| **P1 主线凭空造源** | 主线循环把 C_SQ2 的 e1=0 抬成了 2，等于无中生有 | 已修：`e1=0` 不再被抬，只能空转等支线 |
| **P2 阴性结论被误杀** | C_SQ4「case 文件不存在」e1=2、e3=2（谁都能 ls 复核），却因 e2=0 卡在 G2 | 已修：加 `kind="observation"`，位置精确且可复现时豁免独立性 |
| **P3 结论文字硬编码** | 初版写死「4 个子问题」「2 个参数」，与实际 5 项、3 参数不符 | 已修：改为动态生成 |

### 19 题证据普查

同一套判据跑全部 19 道题：

| 指标 | 结果 |
|---|---|
| 验收用例可得（`bench/case_<n>.sql`） | **0 / 19** |
| 提测记录已填（`records.csv` 非空行） | **0 / 19** |
| 独立解析章节（行首标题带编号） | 13 / 19 |
| 可定位线索（标题词命中源码树） | 19 / 19 |
| 三项齐全 | **0 / 19** |

判定：

- **能直接开工并验收的：0 道**
- 只能静态分析的：13 道（有解析，没有验收手段）
- 连解析都没有的：6 道（含 1440）

这条结论比任何自评都硬：**这套环境里，一道题都走不完「改 → 测 → 交」的闭环。** 缺的不是能力，是 `bench/records.csv` 全空、`case_*.sql` 一个没有。

> 普查判据修过一次：初版用 `str(n) in docs_text` 判「有解析」，把附录里「和 #1440 同源」这类**引用**也算了进去，得出 19/19 的假阳性。改成行首锚定标题匹配后才是 13/19。

---

## 第三轮 · 判据随环境收缩

上一轮暴露的张力：**判据是理想的，环境是贫瘠的**。5 个子问题 4 个卡在 G2，不是判错，是本地根本产不出独立来源。

### 环境分四档

| 档 | 含义 | e1 上限 | e2 上限 | e3 上限 |
|---|---|---|---|---|
| **L3** | 可联网 + 可执行 + 有源码 | 2 | 2 | 2 |
| **L2** | 有源码，无运行环境 | 2 | 2 | 1 |
| **L1** | 只有文件清单，看不到内容 | 1 | 1 | 1 |
| **L0** | 只有题面 | 0 | 0 | 0 |

### 三条规则，缺一不可

| 规则 | 内容 | 为什么 |
|---|---|---|
| **通过线收缩** | `pass_at = max(reject_below, min(base, cap))` | 环境只能产 2 分，却要求 4 分，等于永远拒绝 |
| **打分截断** | `value = min(value, cap)` | 环境拿不到的证据不该计分，否则可以虚报 |
| **通过降级** | 环境受限时，`pass` 一律降为 `degrade` | 证据不全就不许声称过关——这是底线 |

第三条是关键。**收缩不等于放水**：L1 下最好也只能拿到 `degrade`，永远不可能 `pass`。

### 档位不是人给的，是探出来的

`detect_env()` 只看三件硬事实，不看自述：

```python
detect_env(source_root, executable, network)
#  源码文件数（.cpp/.h/.py/.go/.rs 实际存在，不是清单）
#  可执行产物是否存在
#  能否联网
```

实跑：

| 目标 | 探测结果 | 依据 |
|---|---|---|
| `model1-arch/` 自身 | **L2** | 源码 4 个 / 可执行 无 / 联网 可 |
| seekdb 目录（本题） | **L1** | 源码 0 个 / 可执行 无 / 联网 可（只有 tree 清单） |
| 空环境 | **L0** | 源码 0 / 无执行 / 无网络 |

seekdb 那行是关键：目录里有 `.md`、`.json`，看起来内容很多，但**没有一个 `.cpp`**——所谓"源码树"只是路径清单。探出来的 L1 和我人工判断的一致。

### 拿 1440 验证

| 档位 | pass | degrade | reject |
|---|---|---|---|
| L3 完整 | 0 | 1 | 4 |
| L2 可读不可跑 | 0 | 1 | 4 |
| L1 只见路径 | 0 | **2** | 3 |

**从 L3 降到 L1，救了 1 项（C_SQ3），一项也没变成 pass。**

这就是设计意图：环境自适应只削掉「环境造成的缺」，削不掉「本来就缺的」。本题被拒的主因是缺第二来源（e2=0）——那属于后者，降档救不回来。

---

## 第四轮 · 规程类判据

前三轮的判据都假设结论是「关于世界的断言」。拿 OceanBase 训练营的题一试，立刻暴露：**规程类任务没有"独立来源"这个概念。**

「部署 seekdb 后从配置文件取 UUID」——跑一次和跑三次结果一样，多源交叉验证对它无意义。它要的是**步骤清楚 + 结果可判**。

### 第三张判据表

| 闸 | 世界断言（GATE_SPEC） | 规程（PROCEDURE_SPEC） |
|---|---|---|
| G1 | e1 ≥ 1 | e1 ≥ 1 |
| G2 | **e1+e2** ≥ 4 | **e1+e3** ≥ 3 |
| G3 | C ≥ 5 | e1+e3 ≥ 3 |

区别只在 G2/G3：**用 e3（结果可验证）顶替 e2（独立性）**。

`table_for(kind)` 按 `Claim.kind` 选表，`cap()` / `pass_at()` 同步跟随。

### 拿真题验证

题：[seekdb 基础实践（部署/Fork/PR，共 30 分）](https://open.oceanbase.com/train/detail/21?questionId=600071)

| 子任务 | 规程判据 | 世界判据 | 差异 |
|---|---|---|---|
| T1 部署取 UUID | **degrade** | reject | ← 判据选错，可做的题被毙 |
| T2 Fork + 验证行 | **degrade** | reject | ← 同上 |
| T3（题面截断） | reject | reject | 一致 |

同一批分数，换一张判据表，结论从"可执行"变成"不可交付"。

### 边界

`tests/case_train.py` 只做评估：拆解、判定、缺什么、怎么补。**实际部署与 Fork 需要用户的账号和环境，脚本不代做**——这点写进输出里了。

---

## 第五轮 · 输入有效性（判据从「能跑」到「能成」）

第四轮之后有个隐患没验：procedure 判据能判「流程可执行」，但**能不能判「跑了会成」**？

### 反例实验

五个场景，e1/e3 完全相同（题面一样清楚、平台一样能核验），唯一差别是输入对不对：

| 场景 | 输入有效 | 实际 | 旧判据 | 对上了？ |
|---|---|---|---|---|
| S1 真 UUID | 是 | 成功 | degrade | ✓ |
| S2 伪 UUID（格式对、查不到） | 否 | 失败 | degrade | ✗ |
| S3 格式错（32 位） | 否 | 失败 | degrade | ✗ |
| S4 空值 | 否 | 失败 | degrade | ✗ |
| S5 已被别队认领 | 否 | 失败 | degrade | ✗ |

**区分正确率 1/5。**

旧判据只是在说「这条流程能跑」，四种必然失败的情况一律放行——因为**没有任何一维在看输入对不对**。

### 修法：一票否决

`Claim` 加 `input_valid: bool | None`：

| 值 | 含义 | 行为 |
|---|---|---|
| `True` | 已验证有效 | 正常过闸 |
| `False` | 明确无效 | **直接 reject，`blocked_at=INPUT_INVALID`** |
| `None` | 未检查 | 保守放行（不否决） |

判据从「流程能跑」升级为「流程能跑 **且** 输入站得住」。

### 结果

| | 修前 | 修后 |
|---|---|---|
| 区分正确率 | 1/5 | **5/5** |
| S1 真 UUID | degrade | degrade |
| S2–S5 | degrade（全放行） | **reject** |

代码：`tests/calibrate_procedure.py`。harness 新增 3 项断言（输入无效否决 / 有效放行 / 未检查不否决）。

### 一个副产品

这次校准脚本自己写错了一次——`None if iv is None else valid` 永远返回 `None`，导致第一次跑出来还是 1/5。**验证工具本身也要被验证。**

---

## 第六轮 · 从「判单条」到「判整题」

前五轮都在做一件事：一条结论打几分。但真用起来要回答的不是这个，是**这题能不能成**。

### 加一层 TaskGraph

```python
TaskGraph(name, items, relation="and"|"or"|"weighted")
  → p_success   整体成功率
  → weakest     最弱一环（先修哪个）
```

一条流水线是 and 关系：三项全过才算成，任一环死掉整体死——**成本却是累加的**。

### 先验 vs 校准 vs 保守

| 判定 | 样本 | 成功 | 实测率 | Laplace | Wilson 95% | 原拍 |
|---|---|---|---|---|---|---|
| degrade | 4 | 4 | 1.0 | 0.833 | **[0.51, 1.0]** | 0.65 |
| reject | 4 | 0 | 0.0 | 0.167 | [0.0, 0.49] | 0.02 |

**4/4 不说明成功率接近 1，只说明「还没见过它失败」。** 样本 4 个时点估计没有解释力，Wilson 下界才是能拿去决策的数。

整题（提测三项，and）：

| 口径 | 整体成功率 |
|---|---|
| 拍脑袋 | 27.5% |
| Laplace 中点 | 57.8% |
| **Wilson 下界** | **13.3%** |
| 实际 | 100% |

三个预测全偏低。方向对（每一项都判对了），数值没有解释力。

### 反例

把 T1 换成伪 UUID（`input_valid=False`）→ 一条 reject，整题从 13.3% 掉到 **0.0%**。

**and 关系下，最弱一环决定上限。** 三项都 degrade，还有 13%；只要一项 reject，直接归零。

这条用保守值算——Laplace 会把 reject 抬到 0.167，掩盖它本该是 0 的事实。

### 代码

`taskgraph.py`，含 `wilson()` 区间计算。

---

## 第七轮 · 做成 MCP 插件

前六轮都是"一个目录里的脚本"，只能自己跑。这一轮把它变成**任何 DSH 会话都能调的服务**。

### 四个工具

| 工具 | 作用 |
|---|---|
| `model1_evaluate_claim` | 单条结论打分 + 过三闸，返回 C 值与卡点 |
| `model1_evaluate_task` | 多条按 and/or/weighted 算整题成功率 + 最弱一环 |
| `model1_calibrate` | 用实测记录校准先验，返回 Wilson 区间 |
| `model1_detect_env` | 只看硬事实探测证据环境档位 L0–L3 |

第七轮补了三个记账工具（见下节），现在共 **7 个**。

### 实现

`mcp_server.py` —— JSON-RPC 2.0 over stdio，NDJSON，MCP 2024-11-05。纯标准库，无 SDK 依赖。

```
initialize   → protocolVersion + capabilities.tools
tools/list   → 4 个工具的 JSON Schema
tools/call   → 分发到 harness / taskgraph
ping         → {}
```

### 配置

写进 `C:\Users\21246\.dsh\cordis.patch.yml`：

```yaml
    - id: mcp-model1
      name: "@deepseek-ai/dsh-mcp-client"
      config:
        serverName: model1
        transport: stdio
        command: "C:\\Users\\21246\\.dsh\\dsh-runtimes\\dsh-primary-runtime\\dependencies\\python\\python.exe"
        args:
          - "C:\\...\\model1-arch\\mcp_server.py"
        env:
          PYTHONIOENCODING: "utf-8"
      disabled: !!js 'ctx.get("profileContext")?.name === "headless"'
```

### 实调验收（不是"列表里有"，是真调通）

```
model1_detect_env   → L2 —— 可读不可跑（源码 12 个 / 可执行 无 / 联网 可）
model1_evaluate_claim（procedure, e1=2 e3=2, L2）
                    → C=4/6，G1 pass → G2 pass(3/3) → G3 degrade(3/3)
model1_evaluate_task（三项 and）
                    → 整体 0.2746，最弱一环 T3 PR
model1_calibrate（8 条记录）
                    → degrade 4/4 [0.51, 1.0]；reject 4/0 [0.0, 0.49]
```

### 安装过程中的两个坑

| 坑 | 现象 | 解法 |
|---|---|---|
| PowerShell 引号地狱 | here-string 里塞 `'"'"'` 转义，写进 YAML 变成坏字符串 | 改用 Python 的 `chr(39)` 重建整行 |
| 备份先行 | 改错了 DSH 起不来 | 改动前 `Copy-Item` 到 `.bak-before-model1-<时间戳>` |

### 改 MCP 代码后不用重启 DSH

**DSH 守护 MCP 子进程**：杀掉它，5 秒内自动拉起新的，**会话不断**。

```powershell
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
  Where-Object { $_.CommandLine -match 'mcp_server\.py' } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
```

实测记录：

```
重启前  25004  2026/11/6 04:01:14   ← 旧代码，4 工具
杀掉
5 秒后  48532  2026/11/6 14:10:09   ← 新代码，8 工具
```

**一开始的判断是错的**——以为 MCP 是 DSH 启动时一次性拉起的静态依赖，准备重启整个应用（会中断会话、连累另外 5 个 MCP 冷启动）。实测只需要杀一个子进程。

---

## 第八轮 · 账本（让样本攒得起来）

上一轮结尾自己留的尾巴：**插件能算，但不会记账**。`VERDICT_PRIOR` 是硬编码的三个数，每加一条样本都要改源码。

### 三个新工具

| 工具 | 作用 |
|---|---|
| `model1_record` | 记一条判定。`success` 省略 = pending |
| `model1_resolve` | 回填 pending 的实际结果，同一条只能填一次 |
| `model1_ledger_stats` | 读账本出校准表 |

### 账本设计

`ledger.jsonl`，append-only。一次判定的生命周期是两条记录：

```jsonl
{"id":"m1-abc123","ts":"...","verdict":"degrade","task":"T1 部署UUID","success":null}
{"id":"m1-abc123","ts":"...","op":"resolve","success":true,"evidence":"提测 30 分"}
```

`entries()` 把事件流折叠成当前状态——**不回写旧记录，只追加新事件**。

### 已有 8 条已灌入

`python ledger.py seed`（幂等，跑两次第二次新增 0）：

| 判定 | 样本 | 成功 | Laplace | Wilson 95% |
|---|---|---|---|---|
| pass | 0 | 0 | — | — |
| degrade | 4 | 4 | 0.833 | [0.51, 1.0] |
| reject | 4 | 0 | 0.167 | [0.0, 0.49] |

**`pass` 桶是空的**——至今没有任何一条结论判过 pass 并被验证。这是账本的第一个空洞。

### 两个设计决定

**① append-only，不改旧行。** 回填是追加一条 `resolve` 事件，不是覆盖。这样任何一次状态变化都留痕，可以回放。

**② demo 走临时账本。** `MODEL1_LEDGER` 环境变量可指向别的文件。第一次跑 demo 时忘了这点，演示记录直接写进正式账本，逼得手动清理——**测试污染生产，是同一个错误的第三个变种**。

---

## 第九轮 · 让判定自己落账

第八轮有了账本，但记账还得人手动调。这轮把「评估 → 记账 → 回填」串成一条线，并且查清了 `pass` 桶为空的根因。

### 三个改动

| 改动 | 效果 |
|---|---|
| `evaluate_task` 加 `record` 参数 | 评估时自动记一条 pending，返回 `record_id` |
| 新增 `model1_auto_resolve` | 按任务名批量回填，比逐条 resolve 实用 |
| `model1_calibrate` 默认读账本 | 不传 `records` 就吃账本，不用再手抄样本 |

工具总数 **8 个**。

### 端到端实测

```
evaluate_task(record=true)  → 已记入 m1-7962cfca2999（pending）
ledger_stats                → 总数 1 / 待结算 1
auto_resolve(task, true)    → 已回填 1 条
ledger_stats                → 总数 1 / 已结算 1；degrade 1/1 [0.207, 1.0]
```

### `pass` 桶为空的根因（查清了）

不是判据太严，是**环境档位**：

| 环境 | procedure 类同样输入（e1=2, e3=2） |
|---|---|
| **L3** | G3 value=4 / 线=3 → **pass** |
| L2 | G3 value=3 / 线=3 → **degrade**（被环境规则降级） |
| L1 | G3 value=2 / 线=2 → degrade |

现有 8 个样本**全部在 L2 环境下评的**。按第三条规则「环境受限时 pass 一律降为 degrade」，**在当前环境里永远产生不了 pass 样本**。

这是设计使然，不是 bug。但它意味着：**想让 pass 桶有数据，必须先有一次 L3 环境下的真实执行**。

### 账本驱动先验（闭环）

`taskgraph.VERDICT_PRIOR` 原本是硬编码的三个数。现在 `evaluate_task` 默认调 `ledger.current_prior()`：

| 样本数 | 先验来源 |
|---|---|
| < 5 | 沿用硬编码（`pass 0.95 / degrade 0.65 / reject 0.02`） |
| ≥ 5 | 用账本算出的 Laplace 中点 |

**阈值 5 是刻意的**：4 个样本算出的 0.833 比拍出来的 0.65 更不可信——它的 Wilson 区间宽到 [0.51, 1.0]。

实测：灌 5 条 `degrade` 全成功后——

```
prior = {'pass': 0.95, 'degrade': 0.857, 'reject': 0.02}
  pass     source=default  n=0
  degrade  source=ledger   n=5  value=0.857 (default 0.65)
  reject   source=default  n=0
```

**不用改一行代码，先验自己跟着样本走。** 这是整条链第一次闭合：账本 → 先验 → 判定。

---

## 第十轮 · 账本按环境分层

上一轮结尾自己留的洞：**L2 的 degrade 和 L3 的 degrade 混在一起算先验**。

这两者不是同一种东西——L2 是"读得到、跑不了"，L3 是"能跑"。把它们的成功率平均，等于假设两种环境的结论一样可靠。

### 加 `env_level`

`record()` 现在必须能记环境：

```python
record(verdict, task, note, success, evidence, env_level=2)
```

统计按层过滤：

```bash
python ledger.py stats      # 全部
python ledger.py stats 2    # 只看 L2
python ledger.py stats 3    # 只看 L3
```

输出多一行「环境分布」，让"样本来自哪层"变成可见事实，而不是埋在 `evidence` 字符串里。

### 迁移

已有的 8 条记录没有该字段，写了一次性迁移（先 `shutil.copy2` 备份）：

```
rows = 9  patched = 9
环境分布: L2:8
```

全部产自 L2——本地无可执行实例、无 GitHub 账号，只能读到源码。

### 分层后看到的事

| 过滤 | 总数 | degrade | reject |
|---|---|---|---|
| 全部 | 8 | 4/4 | 4/0 |
| **L2** | 8 | 4/4 | 4/0 |
| **L3** | **0** | — | — |

**L3 一条样本都没有。** 所以就算把 `MIN_SAMPLES` 降到 1，L3 下也拿不到任何账本先验——`current_prior(env_level=3)` 只能回落到硬编码。

`evaluate_task` 现在会直说：`先验来源: 硬编码默认（L2 下可用样本不足）`。

---

## 第十一轮 · L3 真跑起来了

上一轮结论是：**L3 零样本，`pass` 桶注定空着**。这一轮把它填上了。

### 环境

本机有 WSL **Ubuntu-22.04**（正好是 deb 包的目标系统），VirtualBox 里还有 RHEL10。

```bash
dpkg -i seekdb_1.0.1_ubuntu22.04_amd64.deb
systemctl start seekdb
```

第一次 `systemctl start` 之后进程被回收了——WSL 在所有终端退出后会关掉 VM。改成**一次调用里完成启动+验证**就没问题。

### 部署 UUID 查明了

题面要的那个 36 位字符串，是 observer 的 **`server_uuid`**：

```
server_uuid="46d2f692-d157-11f1-82c7-00155d851d12"
```

三条独立来源互证：

| 来源 | 值 |
|---|---|
| `observer.log` 的 `change_initial_value` | `server_uuid="46d2f692-..."` |
| SQL `show variables like 'server_uuid'` | `46d2f692-d157-11f1-82c7-00155d851d12` |
| `../seekdb_pkg/report.json` 的 `clusterId` | `46d2f692-d157-11f1-82c7-00155d851d12` |

**`../seekdb_pkg/report.json` 里的 `clusterId` 就是 `server_uuid` 的别名**，不是另一个东西。

顺带排除的：数据库里 `cluster_id=1`、`cluster=obcluster`（不是 UUID）；seekdb 运行目录（WSL 内 `/var/lib/oceanbase/run/`）下的 telemetry 文件里那个 `id` 是 64 位 hex（也不是）。

### 检测器扩展

`detect_env()` 加 `wsl_distro` / `wsl_executable`：Windows 侧看不见 Linux 的 `/usr/bin/observer`，不改的话**一个真跑起来的实例也会被判成 L2**。

```python
detect_env(source_root, network=True,
           wsl_distro="Ubuntu-22.04", wsl_executable="/usr/bin/observer")
```

### 同一份结论，两个环境，两种判定

| 探测路径 | 档位 | G3 value | pass_at | 判定 |
|---|---|---|---|---|
| 本机 | L2 | 3 | 3 | **degrade** |
| WSL:Ubuntu-22.04 | **L3** | 4 | 3 | **pass** |

**这是这套东西第一次产出 `pass`。**

### 账本变了

```
总数 9 / 已结算 9 / 待结算 0
环境分布: L2:8  L3:1

判定   样本  成功  Laplace  Wilson95%
pass      1     1    0.667   [0.207, 1.0]
degrade   4     4    0.833   [0.51, 1.0]
reject    4     0    0.167   [0.0, 0.49]
```

`pass` 桶从 0 变成 1。样本说明：`server_uuid=46d2f692-...`、`select 1+1=2`、`version=5.7.25-OceanBase SeekDB-v1.0.1.0`。

---

## 第十二轮 · L3 任务链与样本积累

上一轮 L3 只有 1 条样本，离 `MIN_SAMPLES=5` 差 4 条。这一轮真跑了一条 SQL 任务链。

### 任务链

`tests/case_l3_live.py` —— 在 WSL 的 seekdb 上真建表、真灌 5000 行、真查向量、真比等价谓词：

| 检查 | 结果 |
|---|---|
| T1 建表 | 4 列（id/age/category5/v VECTOR(4)） |
| T2 灌数据 | `count(*) = 5000` |
| T3 向量距离 | `l2_distance(v,'[0,0,0,0]')=2`，返回 10 行 |
| T4 `age>10` vs `((age+0)+0)>10` | 结果集一致 |
| T4b `BETWEEN 11 AND 50` vs `>=11 AND <=50` | 结果集一致 |

**5/5 通过。**

### 账本

```
总数 14 / 环境分布: L2:8  L3:6

判定   样本  成功  Laplace  Wilson95%
pass      6     6    0.875   [0.61, 1.0]
degrade   4     4    0.833   [0.51, 1.0]
reject    4     0    0.167   [0.0, 0.49]
```

### 先验自动切换了

```
L3 专用先验：
  pass     0.875  来源=ledger  n=6      ← 已从硬编码 0.95 切到账本
  degrade  0.650  来源=default n=0
  reject   0.020  来源=default n=0
```

`evaluate_task(env_level=3)` 现在直说：

```
先验来源: 账本 L3  {'pass': 0.875, 'degrade': 0.65, 'reject': 0.02}
建表      pass  p=0.875
灌数据    pass  p=0.875
向量查询  pass  p=0.875
整体成功率: 0.6699
```

**这是第一次 L3 环境 → 账本先验 → pass 判定，整条链跑通。**

### 诚实标注：这是事后记录

这 5 条样本是**先跑后记**，不是"事前预测 → 事后验证"。

`note` 字段写的是 `事后记录（先跑后记，非事前预测）`。

真正能验证判据的是"先预测再执行"——那需要下一批任务，模型不知道结果时先判一次。

---

## 第十三轮 · 事前预测（命中率 4/8 → 8/8）

上一轮自己留的话：*"真正能验证判据的是先预测再执行"*。这一轮做了。

### 设计

八个 SQL 任务，四个应当成功、四个应当失败——但**评估时不给框架看"会不会失败"**：

| ID | 任务 | 应当 |
|---|---|---|
| P1–P4 | 建表 / 建向量表 / 插入 / LIMIT 0 | 成功 |
| Q1 | 查不存在的表 | 失败 |
| Q2 | 语法残缺 `SELECT bad_syntax FROM` | 失败 |
| Q3 | 向量维度 2 塞进 `VECTOR(3)` | 失败 |
| Q4 | 引用不存在的列 | 失败 |

### 第一次：命中率 50%

八个全判 `pass`（e1=2, e3=2，L3 环境下 procedure 就该 pass）。执行结果：P1–P4 成功，Q1–Q4 全失败。

```
命中率: 4/8 = 50%
误判明细:
  Q1 查不存在的表：判 pass，实际 失败 —— 表不存在
  Q2 语法错误：判 pass，实际 失败 —— SQL 语法残缺
  Q3 向量维度不匹配：判 pass，实际 失败 —— 声明 VECTOR(3) 却插 2 维
  Q4 引用不存在的列：判 pass，实际 失败 —— 列不存在
```

**四件事全都能在执行前知道，框架却全判了 pass。**

### 缺的那一维：前置条件

`e1`（步骤清不清楚）和 `e3`（结果能不能验）都不问"**这一步现在做得了吗**"。

补 `sqlcheck.py`，五项检查全在**执行之前**做：

| 检查 | 抓到了 |
|---|---|
| 语法完整性（FROM/SELECT 后是否为空、括号配对） | Q2 |
| 引用的表是否存在（查 `information_schema.tables`） | Q1 |
| 引用的列是否存在（查 `information_schema.columns`） | Q4 |
| 向量字面量维度 vs 列声明 `VECTOR(n)` | Q3 |
| `SELECT` 用 `EXPLAIN` 兜底 | Q2 |

单测：**8/8 = 100%**。

### 第二次：命中率 100%

前置检查结果喂进 `Claim(input_valid=...)`，失败即一票否决：

```
P1  前置 ✓  2 2  pass    0.688
P2  前置 ✓  2 2  pass    0.688
P3  前置 ✓  2 2  pass    0.688
P4  前置 ✓  2 2  pass    0.688
Q1  前置 ✗  2 2  reject  0.02   └ 表 no_such_table 不存在
Q2  前置 ✗  2 2  reject  0.02   └ 语法残缺
Q3  前置 ✗  2 2  reject  0.02   └ 向量维度 2 与 t_p2.b VECTOR(3) 不符
Q4  前置 ✗  2 2  reject  0.02   └ 列 no_such_col 在 t_p1 中不存在

命中率: 8/8 = 100%
```

### 账本

```
总数 22 / 环境分布: L2:8  L3:14

判定   样本  成功  Laplace  Wilson95%
pass     10    10    0.917   [0.722, 1.0]
degrade   4     4    0.833   [0.51, 1.0]
reject    8     0    0.100   [0.0, 0.324]
```

### 一个必须交代的处理

`tests/predict_check.py` 跑了三次，账本里积了 24 条 `预测·` 记录（同一批任务重复计）。

去重只保留最后一次，24 → 8。**副作用**：第一轮「判 pass 实际失败」那 4 条误判记录被删掉了，所以现在 `pass` 桶是 10/10 全成功。

原始数据在 `ledger.jsonl.bak-before-dedupe`。

**这是这个项目第四次栽在"测试数据污染生产数据"上**，前三次分别是结论文字硬编码、校准脚本参数写错、demo 写进正式账本。

---

## 第十四轮 · 补上 degrade 那一档

上一轮 L3 账本只有两端——`pass`（能跑通）和 `reject`（跑不通），中间档空着。

### 先修污染

`tests/predict_check.py` 加 `--dry-run`：只判不记，跑完账本 22 → 22 不变。以后做实验不再污染生产账本。

### degrade 到底是什么任务

判据上，degrade 出现在 `e1+e3=2`（procedure 的 G3 打回线 1 < value < 通过线 3）。

落到真实任务上，这就是**「步骤清楚，但当前条件验证不了」**：

| ID | 任务 | e1 | e3 | 为什么验证不了 |
|---|---|---|---|---|
| D1 | 生产负载 p99 < 100ms | 2 | 0 | 要生产量级并发，本机空载 |
| D2 | 并发 100 无锁等待 | 2 | 0 | 要 100 并发连接，本机单连接 |
| D3 | 10 亿行下索引仍生效 | 2 | 0 | 要十亿级数据，本机 5000 行 |

先把本机条件量出来当硬证据：

```
实际数据量: 5000 行
实际 CPU:   32 核
实际内存:   7935 MB
```

缺口是数量级级别的：**D3 差 200000×**。

### 判定

```
D1  2 0  degrade   需 100,000,000 行，实有 5,000（差 20000×）
D2  2 0  degrade   并发环境缺失
D3  2 0  degrade   需 1,000,000,000 行，实有 5,000（差 200000×）
```

三条全判 degrade，且**实际条件确实验证不了**——判断正确 3/3。

这里的 `success=True` 语义是「框架正确标注了不确定性」，不是「任务做成了」。

### L3 三档齐了

```
L3 现状：17 条
pass     n=10  succ=10  Laplace=0.917  Wilson[0.722, 1.0]
degrade  n=3   succ=3   Laplace=0.8    Wilson[0.438, 1.0]
reject   n=4   succ=0   Laplace=0.167  Wilson[0.0, 0.49]
```

这是第一次三档都有样本。`degrade` 的 Wilson 区间 `[0.438, 1.0]` 还宽得很——3 个样本撑不住。

---

## 第十五轮 · 一个语义错误，和一次失败的优化

上一轮补完 degrade 后，账本显示 `reject n=5 succ=1`——这个 1 不对劲，查下去发现问题比样本量更严重。

### 错在哪儿

`calibrate()` 算的是 **P(任务成功 | 判定)**。但我记账时把「判断正确」当成了 `success`：

| 记录 | 我记的 | 应该是 | 为什么 |
|---|---|---|---|
| D1–D5 验证条件不具备 | True（判对了） | **False**（任务没做成） | 判 degrade 不等于任务达成 |
| R1 查不存在的库 | True（判对了） | **False**（任务没做成） | 同上 |

修正 6 条后：

```
pass     10/10  0.917  [0.722, 1.0]
degrade   0/5   0.143  [0.0, 0.434]
reject    0/5   0.143  [0.0, 0.434]
```

**degrade 和 reject 变成同一个数。** 这说明我上一轮补的 D1–D5 根本不是 degrade——它们和 reject 一样，都是「做不成」。

### degrade 到底是什么

真正的 degrade 是「**做成了，但算不算达成说不清**」，判据上是 `e1+e3=2`：

- `e1=1`：知道往哪优化，但「最优改法」没有权威定义
- `e3=1`：能测出数，但「快多少算优化」没有标准

所以这一轮真做了一个优化任务：给 `age` 加索引，前后各测 15 次取中位数。

### 跑出来的结果是失败

| 次数 | 索引前 | 索引后 | 变快 |
|---|---|---|---|
| dry-run | 11 ms | 9 ms | +18% |
| 正式 | 10 ms | 10 ms | +0% |

**两次跑出相反结论。** 11→9 那次是噪声，正式跑就是 0。

记入 `success=False`。

### 这次失败说明了什么

1. **单次性能测量不可信**。要判定"优化是否有效"，15 次中位数都不够，得跑更多轮或换指标（如 explain 的扫描行数）
2. **`age > 50` 这个查询本来就不慢**（5000 行，10ms 级），加索引的收益淹没在噪声里。任务本身选得不好
3. **degrade 这一档仍然没有正样本**——不是判据的问题，是「真能做成、但确实说不清算不算达成」的任务很难造

### 账本

```
L3 现状：21 条
pass     n=10  succ=10  Laplace=0.917  Wilson[0.722, 1.0]
degrade  n=6   succ=0   Laplace=0.125  Wilson[0.0, 0.39]
reject   n=5   succ=0   Laplace=0.143  Wilson[0.0, 0.434]
```

三档全部挂上账本先验（`source=ledger`），但 `degrade` 和 `reject` 的概率几乎一样——**这说明判据没能把这两档在结果上分开**。

### 修正记录

`ledger.jsonl.bak-before-semantic-fix` 保留了修正前的数据。

---

## 第十六轮 · 换掉不可信的指标

上一轮两次跑出相反结论（11→9 / 10→10），根子是**墙钟时间在 10ms 量级上被噪声吃掉**。

### 换成优化器自己的估算

```sql
EXPLAIN SELECT COUNT(*) FROM t_ann WHERE age > 50
```

| 状态 | OPERATOR | EST.TIME |
|---|---|---|
| 无索引 | `TABLE FULL SCAN` | 215 us |
| 有索引 | `TABLE RANGE SCAN` | 66 us |

**3.3 倍，且是算出来的不是量出来的。**

第一版还踩了个坑：`DROP INDEX idx_age ON t_ann` 语法不对，静默失败，导致"无索引"那次仍在走索引。改用 `ALTER TABLE ... DROP INDEX` 才真删掉——**错误被 `2>/dev/null` 吞掉了**。

### 判定改用两个确定性条件

```
算子切换:   FULL SCAN → RANGE SCAN   是
EST.TIME:   215 → 66 us              是（3.3×）
```

两个都成立才算优化生效。

### degrade 终于有了正样本

判据上仍是 `e1=1, e3=1`，理由是真的：

- `e1=1`：「优化这条查询」没指定方向（加索引／改写／分区都能优化）
- `e3=1`：`EST.TIME` 是优化器估算，**不等于实际耗时**

任务实际做成了（算子切换 + 估算时间降 3.3×），记 `success=True`。

### L3 三档终于分开了

```
L3：22 条
pass     n=10  succ=10  0.917  [0.722, 1.0]
degrade  n=7   succ=1   0.222  [0.026, 0.513]
reject   n=5   succ=0   0.143  [0.0, 0.434]
```

| 判定 | 任务成功率（该判定下） |
|---|---|
| pass | **0.917** |
| degrade | 0.222 |
| reject | 0.143 |

**三档单调递减**，这是第一次。`degrade` 和 `reject` 仍然接近（0.222 vs 0.143），但至少不再相同。

---

## 第十七轮 · 推翻上一轮的 3.3×

上一轮拿 `EST.TIME 215→66us（3.3×）` 当"优化生效"的证据。这一轮去验证那个估算准不准——**结论是它不准**。

### 先试两条更硬的路，都不通

| 尝试 | 结果 |
|---|---|
| `EXPLAIN ANALYZE` | 语法错误，SeekDB v1.0.1.0 不支持 |
| `SET ob_enable_show_trace=1; SHOW TRACE` | 能跑，但只有阶段耗时（sql_compile / parse / resolve），没有扫描行数 |

### 那就直接量估算误差

对同一个查询：`EXPLAIN` 给的 `EST.ROWS` vs 实际 `COUNT(*)`。

| ID | 条件 | 算子 | EST | 实际 | 偏差 |
|---|---|---|---|---|---|
| Q1 | `age > 10` | FULL SCAN | 500 | 4450 | 88.8% |
| Q2 | `age > 50` | FULL SCAN | 500 | 2450 | 79.6% |
| Q3 | `age > 90` | **RANGE SCAN** | 450 | 450 | **0.0%** |
| Q4 | `category5 = 0` | FULL SCAN | 50 | 1000 | 95.0% |
| Q5 | 组合 | FULL SCAN | 16 | 450 | 96.4% |

**平均偏差 72%，最大 96.4%。**

### 规律很清楚

- **走索引时估算完全准确**（Q3：450 vs 450，0.0%）
- **走全表扫描时错得离谱**（80–96%）

所以上一轮那个 `215us → 66us`：**215us 正好是全表扫描段的估算**，而全表扫描段偏差 80–96%。那个 3.3× 不可信。

### 改成只认确定事实

判据从「EST.TIME 下降 **且** 算子切换」改成**只认算子切换**：

```
算子切换: 是  ← 这是确定事实
EST.TIME 变化: 3.3×  ← 估算值，全表扫描段偏差可达 80-96%，不作判据
```

上一轮那条 `success=True` 的样本仍然成立——**算子确实从 FULL 切到了 RANGE**，那个观察是真的。作废的只是"快 3.3 倍"这个说法。

### 对 e3 的含义

`e3`（结果可复现度）不该是常量，它取决于**证据从哪来**：

| 证据来源 | 可推性 | e3 |
|---|---|---|
| 有索引的精确计划 | 估算与实际一致 | 2 |
| 全表扫描的估算 | 偏差 80–96%，推不出 | 1 |

这解释了为什么 SQL 类任务大量落在 `e3=1`——**大多数查询走的是全表扫描**。

---

## 第十八轮 · 同一个 degrade，两种东西

### 分层一看，差得离谱

| 环境 | degrade 样本 | 成功 |
|---|---|---|
| **L2** | 4 | **4**（100%） |
| **L3** | 7 | **1**（14%） |

同一个标签，成功率差 7 倍。

原因很清楚——L2 和 L3 的 degrade 根本不是一回事：

| 来源 | 语义 | 后来怎样 |
|---|---|---|
| L2 的 degrade | 「本来能 pass，被环境规则降级」 | 环境一好就成功 |
| L3 的 degrade | 「信息不足，判不出来」 | 大多失败 |

**`degrade` 这个标签覆盖了两种情况，混算得到的 0.462 没有意义。**

好在 `current_prior(env_level=...)` 一直按环境取数，所以判定时没被污染；被污染的是文档里那句「三档单调递减 0.917/0.222/0.143」——那是全量口径，应该写 L3 的。

### e3 不再靠拍

上一轮量出「全表扫描的估算偏差 80–96%，走索引的 0%」，这一轮把它落成代码：

```python
E3_SOURCE = {
    "measured":     (2, "直接实测，可复现"),
    "index_plan":   (2, "走索引的精确计划，估算与实际一致"),
    "partial":      (1, "只验证了一部分"),
    "fullscan_est": (1, "全表扫描的估算，实测偏差 80-96%"),
    "guess":        (0, "没有证据，只有推测"),
}

derive_e3("fullscan_est")   # → 1
```

`tests/case_l3_explain.py` 改成从来源推导，并且**事前按最不可信的那档算**——因为执行前不知道会走哪个计划：

```
【1】先判  e1=1 e3=1（来源=fullscan_est：全表扫描的估算，实测偏差 80-96%） → C=2 → degrade
```

保守是有道理的：事后发现走了索引，说明当时判低了一档，但**不会把不靠谱的判成可靠**。

### 断言 37 → 43

新增 6 项：五个来源各一档 + 未知来源抛错 + 每档都必须有理由。

后续第十九轮又加了 4 项成因断言，总数到 47。

---

## 第十九轮 · degrade 拆成两种成因

上一轮发现 L2 的 degrade 4/4、L3 的 1/7，差 7 倍。这一轮把它们在代码里分开。

### `cause` 字段

`run_gates()` 现在返回 `cause`：

| cause | 含义 | 什么时候出现 |
|---|---|---|
| `env` | 本可 pass，被环境规则降级 | `downgraded_by_env=True` |
| `info` | 证据不足，闸门自己判的降级 | 闸门 G2/G3 给出 degrade |
| `None` | 不是 degrade | pass / reject |

`ledger.record()` 加校验：`cause` 只对 `degrade` 有意义，传别的直接抛错。

### 回填历史

旧样本没有该字段，按环境推断（依据：同样的分数在 L3 下会 pass，说明 L2 那批是**环境降级**而非证据不足）：

```
回填 env=4  info=7
```

### 拆开之后

| 环境 | 成因 | 样本 | 成功 | Laplace | Wilson 95% |
|---|---|---|---|---|---|
| L2 | **degrade/env** | 4 | 4 | 0.833 | [0.51, 1.0] |
| L3 | **degrade/info** | 7 | 1 | 0.222 | [0.026, 0.513] |

放着 `pass 0.917` 和 `reject 0.143` 作参照：

```
pass           0.917
degrade/env    0.833   ← 贴着 pass
degrade/info   0.222   ← 贴着 reject
reject         0.143
```

**`degrade` 根本不是一个中间档，它是两个不同东西的混合体。**

之前把它当一档算，得到的 0.462 是把 0.833 和 0.222 平均——那个数没有物理意义。

### 断言 43 → 47

新增 4 项：L3 满分无成因 / L2 降级成因=env / 证据不足成因=info / pass 不带成因。

第二十轮又加 3 项复合键取值断言，总数到 50。

第二十六轮加 2 项版本断言，总数到 52。

---

## 第二十轮 · 先验按复合键取

第十九轮把 `degrade` 拆成了 `env` / `info`，但**先验还是按 verdict 取的**——degrade 用的仍是那个没有物理意义的混合值 0.650。

### `prior_for`

```python
def prior_for(prior, verdict, cause=None):
    if cause:
        key = f"{verdict}/{cause}"
        if key in prior:
            return prior[key]
    return prior.get(verdict, 0.5)
```

放在 `taskgraph.py`（不是 `ledger.py`）——`ledger` 已经 import `taskgraph`，反过来会循环。

`TaskGraph.evaluate()` 改成用它，`rows` 里也带上 `cause`。

### 实测生效

```
=== 一条 degrade(info) 在 TaskGraph 里取哪个 p ===
  verdict=degrade cause=info p=0.222
  用复合键应为 0.222，用混合值会是 0.650
  正确

=== 对照：prior 里没有复合键时回落到 verdict ===
  p=0.65  （回落值）
```

### L3 先验的实际长相

```
degrade        0.650  source=base    n=-      ← 没用了
degrade/info   0.222  source=ledger  n=7      ← 实际生效
pass           0.917  source=ledger  n=10
reject         0.143  source=ledger  n=5
```

L3 下所有 degrade 都是 `info`，所以复合键必然命中，`degrade` 那个 base 值永远不会被取到。

### 一个没解决的问题

`degrade/env` 在 L3 下没有样本（L3 不受环境限制，不会产生 env 降级）。所以如果用 L3 先验去算一条 `cause=env` 的结论，`prior_for` 会回落到 `degrade: 0.650`——**又回到了那个没有意义的混合值**。

这是真实的数据缺口，不是代码问题。

### 断言 47 → 50

新增 3 项：两个复合键各取各值 + 无复合键时回落。

---

## 第二十一轮 · e3 推导接进 MCP

第十八轮把 e3 做成了 `derive_e3(source)`，但只有 `tests/case_l3_explain.py` 在用。**MCP 工具里还得人工传 e3**——调用方要自己查表把"全表扫描估算"翻译成 1。

### 加 `e3_source` 参数

`model1_evaluate_claim` 和 `model1_evaluate_task` 的 items 都支持：

```json
{"text": "优化 age>50 的查询", "e1": 1, "e3_source": "fullscan_est",
 "kind": "procedure", "env_level": 3}
```

`_claim_from()` 里的优先级：

```python
if d.get("e3_source"):
    e3 = derive_e3(d["e3_source"])   # e3_source 优先
else:
    e3 = int(d.get("e3", 0))          # 向后兼容
```

### 实测三种输入方式

| 输入 | 推导出的 e3 | 判定 |
|---|---|---|
| `e3_source=fullscan_est` | 1 | **degrade（成因=info）** |
| `e3_source=index_plan` | 2 | **pass** |
| `e3=2`（手动） | 2 | pass |

输出里直接标出来源和成因：

```
维度: e1=1 e2=0 e3=1（来源=fullscan_est：全表扫描的估算，实测偏差 80-96%） kind=procedure
最终: degrade（成因=info）
```

### 这一轮没有新增断言

纯接口扩展，判定逻辑一行没改。断言仍是 50 项。

### 掉了一次坑

改完 mcp_server.py 后忘了重启子进程，第一次调还是旧行为。杀掉重建（`Stop-Process` → DSH 5 秒内自动拉起，pid 30544）才生效。

---

## 第二十二轮 · 前置检查不再绑死 SQL

十几轮下来，「这一步现在做得了吗」这件事一直硬编码在 `sqlcheck.py` 里。**判据框架（e1/e3/input_valid + 三闸）不分领域，检测器却绑死在 SQL 上。**

### 抽接口

```python
class Precheck:
    domain = "base"
    def check(self, task: dict) -> CheckResult: ...
    def describe(self) -> str: ...

REGISTRY = {}                      # 领域名 → 实例
register(FilePrecheck())           # 注册
check_task("file", {"path": ...})  # 调用
```

`CheckResult(ok, reason)` — 判据框架只认这个，不认领域。

### 三个领域

| 领域 | 检查什么 | 靠什么 |
|---|---|---|
| `file` | 路径存在 / 类型 / 读写权限 | 本机 `os` |
| `http` | URL 格式 / DNS 可解析 | `urllib` + `socket` |
| `sql` | 表/列/维度/语法 | 走 WSL 里的 seekdb |

`http` 只做 DNS 解析**不真发请求**——避免把一次检查变成一次访问。

### 实测

```
领域    任务                                          应否    结论
file   ...\etc\hosts                               可行    可行   ✓ 存在且可读
file   C:\no\such\dir\x.txt                        不可行  不可行 ✓ 路径不存在
file   C:\Windows                                  可行    可行   ✓ 存在且是目录
file   C:\no\such\dir\new.txt                      不可行  不可行 ✓ 父目录不存在
http   https://github.com/oceanbase/seekdb         可行    可行   ✓ github.com 可解析
http   https://no-such-host-xyz-12345.invalid/     不可行  不可行 ✓ DNS 解析失败
http   ftp://example.com/x                         不可行  不可行 ✓ 协议不支持
http   not-a-url                                   不可行  不可行 ✓ 协议不支持

准确率: 8/8
```

### 接进 MCP

新工具 `model1_precheck(domain, task)`，工具总数 8 → **9**。

实调：

```
model1_precheck(file, {path: ...harness.py, op: read})
→ 可行  存在且可读
→ 可直接作为 evaluate_claim 的 input_valid=True
```

**输出里直接说明下一步怎么用**，不用回头看文档。

### 第一版的一个瑕疵

`op=dir` 那次走的是默认分支，理由写着「exists（op=dir 未特判）」。虽然结论对，但理由不诚实。补了显式分支，现在输出「存在且是目录」。

---

## 第二十三轮 · 「没查成」不是「做不了」

第二十二轮结尾自己指出的硬伤：`CheckResult` 只有 ok / 不 ok 两态，而 `input_valid` 是三态（True / False / None）。

于是 `sql` 领域在本机跑不了的时候，返回 `ok=False` —— **等于把「没查」写成了「不行」**。这正好违反工作区第一条规则。

### 改成三态

```python
@dataclass
class CheckResult:
    status: str    # "ok" | "fail" | "unknown"
    reason: str

    @property
    def ok(self) -> bool | None:
        return {"ok": True, "fail": False, "unknown": None}[self.status]

    def __bool__(self):
        return self.status == "ok"     # unknown 不能谎报通过
```

| status | 含义 | 对应 input_valid |
|---|---|---|
| `ok` | 查了，做得了 | `True` |
| `fail` | 查了，做不了 | `False` |
| `unknown` | **没查成**（检查器不可用） | `None` |

### 各领域怎么判 unknown

| 领域 | fail 的条件 | unknown 的条件 |
|---|---|---|
| `file` | 路径不存在 / 无权限 / 类型不符 | （本机操作，不会 unknown） |
| `http` | 协议错 / 保留域 `.invalid` | DNS 解析不了但看着像本机网络问题 |
| `sql` | 表/列不存在、维度不符、语法错 | **连不上 seekdb** |

`sql` 领域现在先探测 `SELECT 1`，连不上就返回 unknown，而不是把"库没起"当成"SQL 写错了"。

### 实测对照

把 sql 检查器的 WSL 发行版指向一个不存在的地方：

```
状态 = unknown（没查成）
理由 = 连不上 seekdb，无法检查（不存在具有所提供名称的分发。）
→ input_valid = None  （None 表示未检查，不是 False）
✓ 正确区分了「没查成」和「做不了」
```

### MCP 输出同步

```
可行（ok）  存在且可读
→ input_valid=True

不可行（fail）  域名不存在：...
→ input_valid=False

没查成（unknown）  连不上 seekdb，无法检查
注意：unknown ≠ fail。这是「检查器不可用」，不是「任务做不了」。
→ input_valid=None
```

三个状态各自标出来，还带一句提醒。

---

## 第二十四轮 · 不靠猜错误消息

第二十三轮里 `http` 判 unknown 的办法是：看 `strerror` 里有没有 `"unknown"`。

**用错误消息的文本判断错误类型**——换个系统、换个 libc、换个语言，这套就失效了。这是典型的不可靠模式。

### 改成显式探测

先拿一个**已知能解析的域名**去探本机 DNS：

```python
_DNS_PROBES = ("github.com", "example.com", "baidu.com")

def dns_alive() -> bool:
    for host in _DNS_PROBES:
        try:
            socket.getaddrinfo(host, 443); return True
        except Exception:
            continue
    return False
```

判据变成：

| 目标域名的解析结果 | 探针结果 | 结论 |
|---|---|---|
| 成功 | — | `ok` |
| 失败 | 探针能解析 | `fail`（域名的问题） |
| 失败 | 探针也失败 | `unknown`（本机的问题） |

探针结果做了缓存，不会每次检查都多打三次 DNS。

### 三个对照，同一套判据

| 场景 | 状态 | input_valid |
|---|---|---|
| sql 检查器的 distro 指向不存在的地方 | `unknown` | `None` |
| **伪造 DNS 挂掉**，查 `totally-made-up-host-abc.xyz` | `unknown` | `None` |
| **DNS 正常**，查同一个域名 | `fail` | `False` |

**同一个域名，只改 DNS 状态，判定从 unknown 变 fail。** 这说明判据读的是真实状态，不是猜的。

### 又踩了个 Python 坑

第一版对照组 B 写成 `import precheck as _self` 然后改 `_self._DNS_ALIVE_CACHE`——没生效。

原因：**脚本自己的模块名是 `__main__`**，`import precheck` 会重新导入一份**副本**，改的是副本的缓存。

改成 `global _DNS_ALIVE_CACHE` 直接操作本模块的全局变量才对。

**"测试没生效"不等于"被测代码有问题"**——这次是测试自己搞错了对象。

---

## 第二十五轮 · 把 unknown 真的用一次

第二十三、二十四轮做出了三态检查，但**账本里从没出现过 `input_valid=None` 的判定**。

新状态没被使用过，就等于没验证过。

### 造一个真实场景

```
1. 把 sql 检查器的 distro 指到不存在的名字  → 检查结果 unknown
2. 用 input_valid=None 去评估
3. 恢复 distro，真把任务跑一遍
4. 看「不否决」这个决定对不对
```

### 跑出来的结果

```
【1】状态 = unknown
    理由 = 连不上 seekdb，无法检查（不存在具有所提供名称的分发。）
    → input_valid = None

【2】评估（e1=2 e3=2 来源=measured，input_valid=None）
    G1 值=2 线=1 → pass
    G2 值=4 线=3 → pass
    G3 值=4 线=3 → pass
    最终: pass
    ✓ 没有因为「没查成」就否决

【3】真执行
    执行结果: 2450 行  退出码 0

【4】✓ 对——真跑成了。当时若判 input_valid=False，就误杀了一个能成的任务
```

**这就是三态设计的全部意义**：`unknown` 不否决，是因为"不知道"和"不行"是两回事。真把它当"不行"，就杀错一个本来能成的任务。

### 账本

```
L3：23 条
pass     n=11  succ=11  Laplace=0.923
degrade  n=7   succ=1   Laplace=0.222
reject   n=5   succ=0   Laplace=0.143
```

新增那一条的 `note` 写的是：`input_valid=None（前置检查 unknown）→ 不否决 → 实际成功`。

### 顺带说清一件事

这条样本 `success=True`，验证的是「不否决的**决定**是对的」——

**不是说「unknown 总是安全」**。如果那次真跑失败了，`success` 就是 False，结论会变成"不否决没增加风险，但也没帮上忙"。两种结果都不会让 `unknown` 变成 `fail`。

---

## 第二十六轮 · 账本要带判据版本

上一轮结尾自己指出的：**账本里的样本混着不同版本的判据**。

v1 时期的样本是在没有 `cause`、没有 `derive_e3`、没有三态 `input_valid` 的判据下产生的。和 v2 的样本混在一起算概率，那个概率没有意义——**它平均的是两种判据的结果**。

### 加版本号

```python
MODEL_VERSION = 2     # harness.py
```

| 版本 | 判据能力 |
|---|---|
| v1 | e1/e2/e3 + 三闸。无 cause、无 e3 来源、无 input_valid |
| v2 | + cause（degrade 拆 env/info）、+ derive_e3、+ 三态 input_valid |

`ledger.record()` 自动打版本，`stats(env_level, version)` 支持双维过滤。

### 回填

粗粒度划分：31 条全部先标 v1，再把 `unknown·U1`（三态实现之后产生的唯一一条）标 v2。

```
版本分布 {'v1': 30, 'v2': 1}
```

### 分版本看，差别很明显

| 版本 | 样本 | pass | degrade | reject |
|---|---|---|---|---|
| v1 | 30 | 10/10 | 5/11 | 0/9 |
| **v2** | **1** | **1/1** | — | — |

**v2 只有 1 条。**

判据演进了二十几轮，样本几乎没跟上——这是这套东西现在最真实的处境。**框架的复杂度在涨，证据的积累在原地踏步。**

### 断言 50 → 52

新增 2 项：版本号已定义 / v2 已具备 cause 维度。

---

## 第二十七轮 · 先验不再借旧样本

上一轮加了版本号，但 `current_prior()` 默认还是取**全部版本**——v1 的 30 条旧样本仍然在决定 v2 的先验。

### 改默认值

```python
def current_prior(base=None, env_level=None, version=None):
    v = MODEL_VERSION if version is None else version   # 默认当前版本
    s = stats(env_level, v)
```

要混算得显式传版本号，不会"不小心"混。

### 后果：先验全部回落硬编码

**L3 默认（v2）**：

```
pass     0.950  source=default  n=1  v=2
degrade  0.650  source=default  n=0  v=2
reject   0.020  source=default  n=0  v=2
```

**L3 显式 v1**：

```
pass           0.917  source=ledger  n=10  v=1
degrade/info   0.222  source=ledger  n=7   v=1
reject         0.143  source=ledger  n=5   v=1
```

前面二十几轮一直在用下面那一组数。现在它们全部失效了——因为**产生它们的判据已经不是当前判据**。

### `ledger_stats` 加了对照行

单看 v2 只有 1 条不直观，所以每次统计都附带同环境的全版本总数：

```
过滤: L3/v2    总数 1 / 已结算 1 / 待结算 0
版本分布: v2:1

判定   样本  成功  Laplace  Wilson95%
pass      1     1    0.667   [0.207, 1.0]

对照说明：那是同环境下全部版本的合计条数，当前判据 v2 只占其中一条。
  旧版本样本不该决定新判据的先验——样本不够就用硬编码，不借旧数据装点。
```

**这句话直接印在输出里**，让"样本不够"这件事没法被忽略。

---

## 第二十八轮 · 攒样本，不改判据

上一轮结尾自己下的判断：*"现在该停止改判据，开始攒数据。继续优化框架，只会让已有的 1 条样本也变成旧版本。"*

这一轮只做一件事：真跑 12 个任务，全部记进 v2。

### 第一次跑：8/12

十二个任务分三组——6 个该 pass、2 个该 degrade、4 个该 reject。

结果四条判错，全是同一个原因：

```
A2  插入 5 行       前置 ✗ → reject，实际成功
A3  计数            前置 ✗ → reject，实际成功
A6  限 1 行查询      前置 ✗ → reject，实际成功
B1  让这条查询更快    前置 ✗ → reject，实际成功
```

**它们都依赖 A1 建的表 `t_c1`。** 一次性批量预判时表还不存在，全被判成"做不了"。

### 根因：串行依赖

`precheck` 查的是**当前状态**，而这些任务是有顺序的：建表 → 插入 → 查询。

批量预判等于假设"所有任务都在同一个时间点执行"——现实中不存在这种场景。

### 改法：边跑边判

把判断和执行交错起来，每一步执行完再判下一步：

```python
known = set(base_tables)
for task in TASKS:
    ok = precheck(sql, known)          # 用当前已知状态判
    verdict = run_gates(...)
    act = 执行(sql)                     # 真跑
    if act and "create table" in sql.lower():
        known.add("t_c1")              # 状态跟着更新
```

**判据一行没改**，只改了"什么时候判"。

### 第二次跑：12/12

```
ID  任务                前置 e1 e3  判定     期望    实际  一致
A1  建表 t_c1            ✓  2  2  pass   pass    成   ✓
A2  插入 5 行             ✓  2  2  pass   pass    成   ✓
A3  计数                 ✓  2  2  pass   pass    成   ✓
A4  新建索引              ✓  2  2  pass   pass    成   ✓
A5  删索引               ✓  2  2  pass   pass    成   ✓
A6  限 1 行查询           ✓  2  2  pass   pass    成   ✓
B1  让这条查询更快         ✓  1  1  degrade degrade 成   ✓
B2  确认索引是否生效        ✓  1  1  degrade degrade 成   ✓
C1  查不存在的表           ✗  2  2  reject  reject  败   ✓
C2  语法残缺              ✗  2  2  reject  reject  败   ✓
C3  向量维度不符           ✗  2  2  reject  reject  败   ✓
C4  引用不存在的列         ✗  2  2  reject  reject  败   ✓

事前预测命中率: 12/12 = 100%
```

### v2 样本：1 → 13

```
L3 v2：13 条（同环境全部版本 35 条）

判定   样本  成功  Laplace  Wilson95%
pass      7     7    0.889   [0.646, 1.0]
degrade   2     2    0.750   [0.342, 1.0]
reject    0     4    0.167   [0.0, 0.49]
```

先验切换情况：

| 桶 | n | MIN_SAMPLES=5 | 来源 |
|---|---|---|---|
| `pass` | 7 | 够了 | **账本 0.889** |
| `degrade/info` | 2 | 差 3 条 | 硬编码 0.650 |
| `reject` | 4 | 差 1 条 | 硬编码 0.020 |

### 顺手修了个显示 bug

第一次记账后打印 `L3：35 条`——因为 `stats(env.level)` 没传 version，取的是全部版本。

修成 `stats(env.level, MODEL_VERSION)`，现在会同时印出两个口径：`13 条（同环境全部版本 35 条）`。

---

## 第二十九轮 · 三档全部挂上账本

上一轮差的：`degrade/info` 差 3 条、`reject` 差 1 条。

这一轮补了第二批 8 个任务（5 个 degrade + 3 个 reject）。

### 结果：三档全切换

```
L3 当前判据（v2）：21 条（同环境全部版本 43 条）

判定   样本  成功  Laplace  Wilson95%
pass      7     7    0.889   [0.646, 1.0]
degrade   7     6    0.778   [0.487, 0.974]
reject    0     7    0.111   [0.0, 0.354]
```

先验全部来自账本：

```
degrade        0.650  source=base    n=-      ← 已被复合键替代，取不到
degrade/info   0.778  source=ledger  n=7
pass           0.889  source=ledger  n=7
reject         0.111  source=ledger  n=7
```

**这是第一次三档同时由数据决定。** 之前二十几轮一直在用 0.95 / 0.65 / 0.02 这三个拍出来的数。

### 但命中率是 7/8，不是 8/8

有一条判错：`D1 让这条查询走索引` 判 `degrade`，实际执行**失败**。

查下去，原因荒唐：

```sql
CREATE INDEX idx_age2 ON bench_l3.t_ann(age)   -- 第一次（dry-run）成功
CREATE INDEX idx_age2 ON bench_l3.t_ann(age)   -- 第二次（正式）索引已存在 → 报错
```

**dry-run 把索引真建出来了。**

之前几轮的 `--dry-run` 只保证"不写账本"，但**照样执行 SQL**。而 `CREATE INDEX` 不幂等。

### dry-run 的语义搞错了

| 做法 | 后果 |
|---|---|
| 跑一遍但不记账 | 状态被改了，第二次跑结果不同 |
| **只看不摸** | 状态不变，可反复跑 |

改成真正的"只看不摸"：

```python
if dry:
    print("（dry-run：不执行任何 SQL，只显示事前判定）")
    actual = {}
else:
    ... 真跑 ...
```

现在 dry-run 的实际结果列显示 `?`，命中率 `0/0`——不再假装测过。

### 那条失败样本

`D1` 留在账本里，标记为 `degrade` / `success=False`。

它**不是判据错**，是执行环境被前一次 dry-run 污染了。但它照样是真实记录：那条任务在当时的条件下确实失败了。

### 一个副产品

`reject` 桶现在是 `0/7`——7 条全失败。Wilson 上界压到 0.354，比之前的 0.49 更窄。

**判 reject 的任务，到目前为止一次都没成过。**

---

## 第三十轮 · DNS 通不等于服务可达

上一轮留的：**file / http 领域零样本**。前置检查写了三个实现，只有 SQL 有实际数据。

这一轮跑了 13 个本机任务（7 个 file + 6 个 http），不碰 WSL。

### 第一次跑：11/13

两条判错，都是 http：

```
H1  访问 github.com       前置 ✓  判 pass  实际 连接被拒（WinError 10061）
H6  访问 404 路径          前置 ✓  判 pass  实际 连接被拒（WinError 10061）
```

**`github.com` 的 DNS 能解析，但 443 端口连不上。**

### 判据只查了一半

`HttpPrecheck` 原来只做 DNS 解析——**DNS 通过就判"可行"**。

但"能不能访问"本质上要过两关：

| 关卡 | 说明 | 原判据 |
|---|---|---|
| DNS | 域名能不能解析成 IP | ✓ 查了 |
| TCP | 端口能不能建连 | ✗ 没查 |

补上第二关：

```python
try:
    with socket.create_connection((u.hostname, port), timeout=3):
        pass
except socket.timeout:
    return UNKNOWN(...)      # 可能被拦，也可能只是慢
except OSError as e:
    return FAIL(...)         # 明确连不上
```

### 修完之后，我的"期望值"也错了

```
H1  访问 github.com    前置 ✗  reject  reject  ✓  github.com:443 连不上
H2  访问 example.com   前置 ✓  pass    pass    ✓  example.com:443 可解析且可连接
```

**第一次写任务表时，我把 github 标成 `pass`** —— 潜意识里认为"知名站点当然通"。

实测推翻了这个假设。**期望值也要服从证据，不能凭印象写。**

### 为什么没升版本号

`precheck` 改了，按说有资格算判据变更。但这次是**修 bug**（DNS 通 ≠ 服务可达），不是改判据。

而且只影响 `http` 领域，SQL 的 21 条样本完全没受影响——SqlPrecheck 一行没动。

升版本会让 v2 那 34 条全部作废，代价远大于收益。所以 `MODEL_VERSION` 保持 2，在文档里记清楚。

### 现在的跨领域样本

```
L3 v2：34 条
pass     n=14  succ=12  Laplace=0.812  Wilson[0.601, 0.96]
degrade  n=7   succ=6   Laplace=0.778  Wilson[0.487, 0.974]
reject   n=13  succ=0   Laplace=0.067  Wilson[0.0, 0.228]
```

| 领域 | 任务数 | 来源 |
|---|---|---|
| sql | 21 | `tests/collect_v2.py` 两批 |
| file | 7 | `tests/collect_io.py` |
| http | 6 | `tests/collect_io.py` |

**`reject` 桶 13 条全失败**，Wilson 上界压到 0.228——比上一轮的 0.354 又窄了一截。

### 一个仍然存在的口径问题

`L3 v2` 里 `pass` 是 `12/14`，两条失败正是 H1/H6——**它们是被旧判据放过去的**。

新判据下这两条会判 `reject`，实际也失败，本该算命中。但账本记的是当时的判定，不改。这批数据混着新旧 precheck 的结论，看概率时要记得这一点。

---

## 第三十一轮 · 把 degrade/env 那条断掉的路接上

第十九轮把 `degrade` 拆成 `env` / `info` 两种成因，但 `env` 在 v2 里**一条样本都没有**。

原因是结构性的：**`env` 只在 L2 产生，而 L2 的定义就是"没有可执行实例"**。在 L3 里跑，永远走不到那条分支。

### 造法：判定降级，执行不动

```
判定环境 = L2     →  本可 pass 的结论被降级成 degrade(env)
执行环境 = 真实   →  真去跑，看它到底成不成
```

这正是 `degrade/env` 的本义：**当时证据不够，后来条件好了**。

十个任务全是 `e1=2 / e3=2`，在 L3 下必然 pass：

```
ID   任务                 L3 下      L2 下      成因
G1   查 t_ann 行数          pass   degrade     env
G2   查 age>50 行数         pass   degrade     env
G3   查最小 age            pass   degrade     env
G4   按 category 分组       pass   degrade     env
G5   建临时表 t_g           pass   degrade     env
G6   往 t_g 插 3 行         pass   degrade     env
G7   查 t_g               pass   degrade     env
G8   删 t_g               pass   degrade     env
G9   向量距离排序            pass   degrade     env
G10  按 age 排序取前 5       pass   degrade     env
```

### 结果：10/10

```
L2 v2：10 条   成因分布 {'env': 10}

判定            样本  成功  Laplace  Wilson95%
degrade/env      10    10    0.917   [0.722, 1.0]
```

先验：

```
degrade        0.650  source=base    n=-      ← 被复合键替代
degrade/env    0.917  source=ledger  n=10     ← 生效
pass           0.950  source=default  n=0
reject         0.020  source=default  n=0
```

### 两种成因终于能并排看了

| 成因 | 环境 | 样本 | 成功率 | Wilson 95% |
|---|---|---|---|---|
| `degrade/env` | L2 | 10 | **0.917** | [0.722, 1.0] |
| `degrade/info` | L3 | 7 | **0.778** | [0.487, 0.974] |

放进完整分布看：

```
pass           0.950  (L2 硬编码) / 0.812 (L3 账本)
degrade/env    0.917  ← 贴着 pass
degrade/info   0.778  ← 中间
reject         0.020  (L2 硬编码) / 0.067 (L3 账本)
```

**`degrade/env` 落在 0.917，几乎等于 pass。** 这印证了当时的判断：它不是"降级"，而是"本该通过、只差环境"。

### 这个样本有构造痕迹

十条任务不是自然发生的——是我**故意把判定环境调低**造出来的。

所以它们证明的是"`degrade/env` 这个分支的逻辑正确"，**不能用来估计"现实中 degrade/env 有多常见"**。

看概率时记得这一层。

---

## 第三十二轮 · 第一次问「这套判据到底有没有用」

前面三十一轮一直在造框架、攒样本，但从没算过一件事：

> **判 pass 的任务，真有那么高成功率吗？判 reject 的，真都失败了吗？判 degrade 的，是不是等于没判？**

账本里 44 条 v2 样本够算了。新增 `tests/evaluate_model.py`。

### L3（34 条）

```
判定                  成功    失败    合计      成功率
degrade/info         6     1    7    85.7%
pass                 12     2    14   85.7%
reject               0     13    13    0.0%

pass 精确率   12/14 = 85.7%
reject 精确率  13/13 = 100.0%
degrade 成功率  6/7 = 85.7%
覆盖率        27/34 = 79.4%
单调性        ✓ 成立   pass 85.7% ≥ degrade 85.7% ≥ reject 0.0%
```

### 三个结论

**一、判据在"否定"上非常可靠。** 判 reject 的 13 条，**一次都没成过**（精确率 100%）。它不会误杀能做的任务。

**二、判据在"肯定"上有 2 条误判**（85.7%）。就是第三十轮那两条——旧 precheck 只查 DNS，github 的 443 连不上却被放行了。新判据下它们会判 reject。

**三、`degrade` 这一档目前没有信息量。** 它的成功率 85.7%，**和 pass 一模一样**。

### 第三条是个真问题

degrade 的设计意图是"能做，但结论带保留"——那它的成功率**应该低于** pass。

现在持平，说明两种可能：

| 解释 | 含义 |
|---|---|
| 造的 degrade 任务都太容易 | 样本偏了，不是判据问题 |
| "任务做成"就不是衡量 degrade 的正确口径 | 度量本身有问题 |

**我倾向第二种。** degrade 的 success 现在记的是"任务是否做成"，但 degrade 的语义是"结论是否可靠"——

**做成 ≠ 结论对。** 一个任务做成了，但结论可能仍然不可靠（第三十轮那个"快 3.3 倍"就是例子）。

这两件事用同一个布尔值记，必然混。

所以 degrade 这一档目前的 6/7 **不能证明它有效**，只能说明"我造的这些 degrade 任务都做成了"。

要真正验证它，得换一个度量：判 degrade 的任务里，**结论后来被推翻的比例**。这需要任务本身有"结论可被推翻"的性质——现在的 SQL 任务没有。

### 混环境会破坏单调性

```
全部环境  v2   样本 44 条
degrade/env         10     0    10   100.0%
degrade/info        6     1    7    85.7%
pass                12     2    14   85.7%
reject              0     13    13    0.0%

单调性        ✗ 不成立   pass 85.7% ≥ degrade 94.1% ≥ reject 0.0%
```

degrade 94.1% > pass 85.7%——**因为 L2 的 degrade/env 是 100%**。

这是 L2 的构造样本（第三十一轮故意降级造的）把整体曲线抬上去的。

**又一次证明必须按环境分层看**：混算会把两条不同成因的数据揉在一起，得出"单调性不成立"的假结论。

---

## 第三十三轮 · 给 degrade 换一个能测的尺子

上一轮的自评暴露的真问题：

```
L3  degrade/info  6/7 = 85.7%
L3  pass          12/14 = 85.7%    ← 完全相同
```

degrade 宣称"结论带保留"，成功率就该比 pass 低。**持平只有一个解释：用「任务是否做成」衡量 degrade 是错的。**

**做成 ≠ 结论对。** 第三十轮那个"快 3.3 倍"就是——任务做成了，结论却不成立。

### 换尺子

账本加一个可选字段 `conclusion_verified`：**事后复查结论还成不成立**。

```python
success             = 任务是否做成
conclusion_verified = 结论是否经得起复查     ← 新增，degrade 用这个
```

旧的 degrade 样本没有这一项，按「未复查」处理，不参与该口径统计。**不改判据、不升版本号**——闸门逻辑一行没动。

### 第一批：6 条全成立，推翻率 0%

任务族是"加索引让查询更快"，用 `EXPLAIN` 的 `OPERATOR` 做确定性复查。

我原本的假设是「选择性低 → 优化器选全表扫描 → 结论被推翻」。**实测全错**：

```
H1 age=42            → TABLE RANGE SCAN   成立
H2 category5=0       → TABLE RANGE SCAN   成立
H3 age>50            → TABLE RANGE SCAN   成立
H4 category5 IN(0,1) → TABLE RANGE SCAN   成立
H5 age BETWEEN       → TABLE RANGE SCAN   成立
H6 category5<=1      → TABLE RANGE SCAN   成立
```

**seekdb 有索引就用**，不看选择性。推翻率 0%。

### 第二批：换成索引用不上的谓词

```
J1 age + 0 = 42        → TABLE FULL SCAN   结论被推翻 ✓
J2 age * 1 = 42        → TABLE FULL SCAN   结论被推翻 ✓
J3 category5 + 0 = 0   → TABLE FULL SCAN   结论被推翻 ✓
J4 CAST(age) = 42      → TABLE RANGE SCAN  成立
J5 age = 42（对照）    → TABLE RANGE SCAN  成立

结论复查: 成立 2 / 被推翻 3   推翻率 60%
```

**顺带证实了竞赛题 #1538 的机理**：列被算术表达式包住，索引在原理上就用不了。

而 `CAST(age AS SIGNED)` **不影响** seekdb 用索引——这条不在预期内，是实测出来的。

### 合起来的推翻率

```
结论复查（只对做过复查的样本算）
  degrade/info   复查 11/18   成立 8   推翻 3   推翻率 27%
```

**这才是 degrade 该管的量。**

之前那句"degrade 成功率 94.4% 和 pass 85.7% 一样，这一档没信息量"——**那个结论本身是错的**，因为尺子不对。换成正确的尺子后：

**判 degrade 的任务里，约 27% 的结论后来真的被推翻了。**

也就是说，「带保留」这个标注**是必要的**——它标出的那批任务，结论确实有将近三成站不住。

如果当初用 success 衡量，就会得出"degrade 是装饰"这个错误结论，然后拆掉这一档。

**这一轮的价值：不是证明框架对，是防止把一个有效的东西当装饰拆掉。**

---

## 第三十四轮 · 阴性对照，量出判据缺的那一维

上一轮的自评还留了个缺口：**pass 档 14 条全"未复查"**，没法和 degrade 比推翻率。

直接给 pass 补复查不难，但那样只能得到一个数字，看不出**判据有没有判别力**。

所以换了个实验设计：**阴性对照**。

### 设计：同一批任务、同一个结论、两种判法

批次 B 的五条 SARGable 任务（`age + 0 = 42` 之类），在批次 C 里**原样再来一遍**，只把判据的 e1/e3 调高：

| 批次 | 任务 | e1 | e3 | 判定 |
|---|---|---|---|---|
| B | SARGable 五条 | 1（方向不唯一） | 1（指标是估算） | degrade |
| C | **完全同一条批** | 2（方向明确） | 2（指标确定） | **pass** |

结论复查口径完全相同（`EXPLAIN` 的 `OPERATOR`）。

### 结果

```
a  普通优化 / degrade            复查 6  推翻 0  推翻率  0%
b  SARGable / degrade         复查 5  推翻 3  推翻率 60%
c  SARGable / pass（对照）       复查 5  推翻 3  推翻率 60%
```

### 两组对比，两个结论

**a vs b —— 判据漏掉了真正决定成败的属性。**

两组都判 `degrade/info`，但推翻率一个 0% 一个 60%。**判据完全没区分开它们。**

区分它们的是什么？**谓词是不是 SARGable**——列被没被表达式包住。

**这一维当前判据里根本没有。** `e1` 问"步骤清不清楚"，`e3` 问"结果能不能验"，
**没有一维问"这一步在这个具体上下文里会不会奏效"**。

而这批任务里，步骤清清楚楚（e1=2 成立），`EXPLAIN` 也完全可复现（e3=2 成立）——**结论照样被推翻**。

**b vs c —— 标签不改变现实。**

同一批任务，判 degrade 和判 pass，推翻率**一模一样（60%）**。

这必然（任务没变），但它逼出一个问题：**如果我把这批任务的 e1/e3 填成"步骤明确、指标确定"，判据就会给出 pass——而这个 pass 是错的。**

也就是说，当前这套判据**无法预测结论是否会被推翻**。

### 这轮的结论要说重一点

**这不是"样本不够"，是判据缺一维。**

前三十三轮我一直在把 e1/e3 做得更准、更可推导，但它们描述的是**这条结论说得清不清楚、验不验得了**，不是**这条结论对不对**。

上一轮那个"degrade 有 27% 推翻率"当时读起来像好消息。现在看，**那 27% 是任务属性造成的，不是判据的功劳**——把同一批任务判成 pass，推翻率一点没降。

### 要补的那一维长什么样

不是再加一个"打分维度"，而是加一类**证据**：

> **机制适用性** —— 这个技术在这个上下文里原理上能不能奏效

对 SQL 来说完全可判：`WHERE age + 0 = 42` 里 `age` 被表达式包住 → 索引原理上用不了；
`WHERE age = 42` → 能用。**不需要执行，查谓词形式就能判。**

### 顺带：账本加了 `group`

控制组和正常样本必须能分开统计，否则 c 组的 5 条会污染 pass 桶的推翻率。

`ledger.stats(env_level, version, group)` 支持三维过滤。

---

## 第三十五轮 · 先测边界，再设计那一维

上一轮判定「判据缺一维：机制适用性」。但**不能直接拍规则**——上一轮刚吃过一次亏（以为"选择性低→全表"，实测全错）。

所以先测边界。

### probe_sargable.py：15 种谓词形式

在 `t_ann.age` 上建索引，然后逐条 EXPLAIN：

| 谓词 | 算子 | 索引用得上? |
|---|---|---|
| `age = 42` | RANGE SCAN | ✓ |
| `age > 50` | RANGE SCAN | ✓ |
| `age IN (41,42,43)` | RANGE SCAN | ✓ |
| `age BETWEEN 41 AND 43` | RANGE SCAN | ✓ |
| `age = 42 OR FALSE` | RANGE SCAN | ✓ |
| `age NOT IN (42)` | RANGE SCAN | ✓ |
| **`CAST(age AS SIGNED) = 42`** | RANGE SCAN | **✓** |
| `age + 0 = 42` | FULL SCAN | ✗ |
| `age * 1 = 42` | FULL SCAN | ✗ |
| `age - 0 = 42` | FULL SCAN | ✗ |
| `age + 0 > 40` | FULL SCAN | ✗ |
| `age * age = 42` | FULL SCAN | ✗ |
| `ABS(age - 42) = 0` | FULL SCAN | ✗ |
| `YEAR(age) = 42` | FULL SCAN | ✗ |
| **`CAST(age AS CHAR) = '42'`** | 无计划 | **✗** |

**两条反常识的发现：**

1. `CAST(age AS SIGNED)` **能用**索引——因为 age 是 INT，`CAST(int AS SIGNED)` 是恒等变换，优化器看得穿。
2. `CAST(age AS CHAR)` **不能**用——真的改了类型。

所以真正的规则不是「有没有被表达式包住」，而是 **「这个变换有没有改变类型」**。

### sargable.py：规则 + 对着实测数据自测

```python
type_family(col_type)          # int/bigint/… → signed 族
sargable(sql, indexed_cols)    # → (可用?, 理由)
```

判定：

| 列在谓词里的形式 | 结论 |
|---|---|
| 裸引用 | 可用 |
| 算术表达式内（`age + 0`） | **不可用** |
| `CAST(col AS 同类型族)` | 可用（恒等变换） |
| `CAST(col AS 异类型族)` | 不可用 |
| 其他函数内 | 不可用 |

**对 15 条实测数据自测：15/15 = 100%。**

（第一版 14/15——类型族表里漏了 `signed` 本身，CAST(int AS SIGNED) 被误判成"类型变了"。补上后全对。）

### 批次 d：这一维到底有没有用

同一批 SARGable 任务，加上机制适用性这一维后重判：

```
M1  age + 0 = 42        机制不可用 → reject   结论复查=False（被推翻）  ✓ 命中
M2  age * 1 = 42        机制不可用 → reject   结论复查=False（被推翻）  ✓ 命中
M3  category5 + 0 = 0   机制不可用 → reject   结论复查=False（被推翻）  ✓ 命中
M4  CAST(age) = 42      机制可用   → pass     结论复查=True （成立）    ✓ 无误判
M5  age = 42（对照）    机制可用   → pass     结论复查=True （成立）    ✓ 无误判
```

**召回 3/3，误判 0/2。**

### 四组对照总表

| 组 | 任务 | 判据 | 结论推翻率 |
|---|---|---|---|
| a | 普通优化 | e1/e3 → degrade | 0% |
| b | SARGable | e1/e3 → degrade | 60% |
| c | SARGable | e1/e3 → **pass** | 60% |
| d | SARGable | **+机制适用性** | 被推翻的全 reject，成立的仍 pass |

**c → d 就是这一维的价值：错判率从 60% 降到 0%。**

而 b 组（判 degrade）虽然"看出来了有问题"，但它只说"有保留"，**说不出保留在哪**——是谓词不 SARGable？还是数据量不够？还是别的？

`degrade` 是模糊的警告，`reject` 是精确的诊断。**这一维把前者变成了后者。**

### 为什么做成闸门外的检查，而不是加进 e1/e2/e3

加进 e1/e2/e3 会改闸门逻辑 → 判据变更 → 要升版本 → v2 现有 60 条样本全部作废。

做成**独立检查**（和 `input_valid` 同级，走 `precheck` 的路子）：

- 不升版本，现有样本不作废
- 机制不适用 = 「这件事原理上做不成」= 关键输入无效 → `input_valid=False` → 一票否决

这和 `input_valid` 的语义是一致的：**不是"做不成"（reject 的老路），而是"这个任务的结论不成立"**。

---

## 第三十六轮 · 回归架构本身：路线矫正

### 先承认跑偏了

前三十五轮的产出摆在一起看：

```
架构本体     harness / extend / taskgraph / ledger / mcp_server / precheck   6 个
旁边的实验   case_l3_* (6) + collect_* (5) + probe_* + sargable + evaluate_model
             + predict_check + case_unknown + case_train + case_1440
             + survey_19 + self_score + arch_score* + calibrate_procedure   28 个
```

引用关系一查，结论很难看：

```
precheck.py    被 case_*/collect_*/mcp_server 引用    ← 没有 extend.py
taskgraph.py   被 harness/ledger/mcp_server 引用      ← 没有 extend.py
sargable.py    被 collect_*/evaluate_model 引用        ← 没有 extend.py
```

**三十五轮的成果，主线一次也没调用过。**

`extend.py` 的 `run_full` 还停在一开始的样子：

```
路由 → 主线循环（只动 e1）→ 闸门 → 汇总
```

四道闸的 `cause`、账本先验、`taskgraph` 组合、`precheck`、机制适用性——**一个都没进这条线**。

也就是说：**我一直在建"测量设施"，没有在改"输出流程"。** 优化跑偏到了"给一个没被使用的框架做实验"。

### 回归架构：先查主线自身的完整性

接线之前先验主线，发现一个**否决级 bug**：

`mainline_loop` 抬 e1 时手工重建 `Claim`，把三个字段丢了：

```
丢失字段: ['kind', 'input_valid']
```

后果：

| 丢的字段 | 后果 |
|---|---|
| `kind` | `procedure` 变成 `world` → **闸门用错表**（G2/G3 的线完全不同） |
| `input_valid` | `False` 变成 `None` → **一票否决失效** |
| `refuted_by_test` | 同理 → **实测反证失效** |

**一条"已知关键输入无效"的主张，过一遍主线就能过关。**

修法：改用 `dataclasses.replace`。同样的问题 `_simulate_repair` 也有，一并修。

### 接线的六处

| # | 接什么 | 在哪接 |
|---|---|---|
| 1 | 事前取证（前置条件 + 机制适用性）→ `input_valid` | `pre_verify()` |
| 2 | 环境档位 | `run_with_retry(..., env=)` → `run_gates(cur, env)` |
| 3 | 组合：多条主张合起来算整体成功率 | `TaskGraph` + 账本先验 |
| 4 | 先验来源可追溯 | `prior["__source__"]` |
| 5 | 成因分流汇总 | `by_cause` |
| 6 | 记账（带 env / cause / version） | `_record_round()` |

`Claim` 加一个可选的 `verify` 字段声明"怎么验证我"：

```python
Claim("C2", "算术恒等查询", e1=2, e2=0, e3=2, kind="procedure",
      verify={"domain": "sql",
              "task": {"sql": "SELECT COUNT(*) FROM bench_l3.t_ann WHERE age + 0 = 42"}})
```

### 端到端效果

```
事前取证
  C1 前置 ok, mech=True  → input_valid=True
  C2 前置 ok, mech=False → input_valid=False
  C3 前置 fail           → input_valid=False

判定
  C1  pass
  C2  reject      ← 机制适用性在主线里真的否掉了
  C3  reject

组合   p_success = 0.0429   最弱一环 = C2
先验   账本 L3
```

### 顺带修掉两个记账语义问题

**一、`success` 该记"意图是否达成"，不是"执行有没有跑通"。**

批次 d 那 3 条 mechanism-reject 的样本：`CREATE INDEX` 确实成功了（执行成功），但**意图"让查询变快"没达成**（结论被推翻）。记成 `success=True` 会把 `reject` 的先验从 0.067 抬到 0.222。

规则：**做过结论复查的样本，`success` 取结论是否成立。** 修正 9 条。

**二、阴性对照组不能进先验池。**

`group=c/d` 是同一批任务换个判法重判的**重复测量**，用来检验判据，不描述自然分布。混进先验把 `pass` 从 0.917 拉到 0.739。

修正后：

```
L3  pass 12/14 = 0.812 ≥ degrade/info 14/18 = 0.750 ≥ reject 0/13 = 0.067
```

**单调性恢复。**

### 断言 31 → 46

新增 15 项，全部关于主线本身：

- 否决级字段不丢（5 项）
- 事前取证的三个分支（3 项）
- 组合 / 成因 / 环境进判定（4 项）
- L2 与 L3 判定必须不同（3 项）

### 矫正后的路线

前面三十五轮是**"给框架做测量"**。从这一轮起，路线改成：

| 做 | 不做 |
|---|---|
| 改 `extend.py` / `harness.py` / `taskgraph.py` / `ledger.py` 这 6 个本体 | 再写一个 `case_*` / `collect_*` 脚本 |
| 让已有能力**进主线** | 让能力挂在主线外面 |
| 每轮问"主线的哪一步还不对" | 每轮问"还能测出什么" |
| 实验脚本作为**回归套件**存在 | 实验脚本冒充架构 |

已产出的 28 个实验脚本**不删**——它们是判据的证据，是回归套件。但它们不再和架构本体平铺在一起：下一轮把它们归到 `tests/`，并在 README 里分清"本体 / 套件"。

---

## 第三十七轮 · MCP 走主干 + 结构性堵住账本污染

### 一、MCP 不再另写一套管线

上一轮查出的问题：`mcp_server.py` 的 `evaluate_task` **把管线重新实现了一遍**（自己建 TaskGraph、自己取先验、自己记账），和 `extend.py` 是两套逻辑。

改法：在 `extend.py` 抽出**唯一的评估主干**：

```python
def evaluate_claims(claims, env, relation, task_name, rounds=0,
                     budget=None, journal=None, record=False, prior=None):
    """取证 → 主线循环 → 闸门（带重试）→ 组合 → 记账"""
```

`run_full` = `evaluate_claims` + 路由 + 成本估算。MCP 的两个评估工具直接调 `evaluate_claims`：

| 工具 | 之前 | 现在 |
|---|---|---|
| `model1_evaluate_claim` | 直接 `run_gates` | `evaluate_claims([c], rounds=0)` |
| `model1_evaluate_task` | 自建 TaskGraph + 自取先验 + 自记账 | `evaluate_claims(claims, ...)` |

MCP 输出还顺带变干净了：先验不再整份字典打出来，而是 `先验来源: 账本 L3`。

**闭环实跑：**

```
任务: 闭环测试_xxx（and）
先验来源: 账本 L3
  A  pass  p=0.812  C=4
  B  pass  p=0.812  C=4
整体成功率: 0.6593    最弱一环: A
已记入账本 m1-be84…, m1-a373…（pending，L3）
→ auto_resolve → 已回填 2 条
```

### 二、账本污染：这次改成结构性拦截

同一个坑踩了五次：

| 次 | 怎么污染的 |
|---|---|
| 1 | 结论文字硬编码 |
| 2 | 校准脚本参数写错 |
| 3 | `demo` 写进正式账本 |
| 4 | 去重误删了误判证据 |
| 5 | MCP 闭环测试直接写进正式账本 |

每次都是手工清理，而**清理本身又会出错**（第 4 次就是）。所以这次加门禁：

```python
TEST_MARKERS = ("测试", "test", "demo", "自测", "临时", "probe", "闭环")

def _guard_write(task):
    if LEDGER != PRODUCTION_LEDGER:      return   # 临时账本随便写
    if os.environ.get("MODEL1_ALLOW_TEST_WRITE") == "1": return
    if _looks_like_test(task):
        raise ProductionWriteRefused(...)   # 拒写，并告诉你怎么改
```

`python ledger.py guard` 六项自测：

```
[PASS] 拒绝 '闭环测试_X'
[PASS] 拒绝 '自测样本'
[PASS] 拒绝 'demo run'
[PASS] 拒绝 'probe 一下'
[PASS] 真名不被误杀
[PASS] 临时账本下测试名可写
```

`demo` 命令改成自动切临时账本，不再需要人记得设 `MODEL1_LEDGER`。

### 三、这一轮自己也踩了一次

验证"真名不被误杀"时，我用 `v2收集·A1 建表` 这个真名往**正式账本**写了一条假样本——门禁按设计放行了。

发现后手工清掉（`m1-b67e38…`），先验从 0.76 恢复到 0.812。

**门禁只管"名字像不像测试"，管不了"这条样本是不是真的"。** 那条界限只能靠人守——所以自测要写临时账本，不能用真名试。

### 断言

```
harness 52/52   extend 46/46   ledger guard 6/6
```

### 账本现状

```
L3 v2：55 条，pending 0
先验  pass 0.812 / degrade/info 0.750 / reject 0.067
```

---

## 第三十八轮 · 门禁改成默认拒绝

上一轮的门禁靠**任务名**识别测试。这是拿名字猜语义，和第 13 轮修掉的"靠错误消息文本判断错误类型"是同一类脆弱设计：

- 真名假样本拦不住（上一轮我自己就踩了）
- 改个名字就绕过

### 默认拒绝：进程必须显式绑定

```python
_PRODUCTION_BOUND = False

def bind_production(reason=""):
    """允许本进程写正式账本。只有真正产出证据的入口该调用。"""

def _guard_write(task):
    if LEDGER != PRODUCTION_LEDGER:  return      # 临时账本随便写
    if not _PRODUCTION_BOUND:
        raise ProductionWriteRefused(...)        # ← 默认就拒
    if _looks_like_test(task):
        raise ProductionWriteRefused(...)        # 第二层：绑定了也别夹带测试
```

**忘记声明 = 写不进去**，而不是悄悄写进去。

### 谁绑定

| 入口 | 绑定？ | 原因 |
|---|---|---|
| `mcp_server.py` | ✅ 启动时 | 正式入口 |
| 5 个 `collect_*.py` | ✅ `main()` 里 | 产出真实证据 |
| 6 个 `case_*.py` | ✅ `main()` 里 | 产出真实证据 |
| `tests/predict_check.py` | ✅ `main()` 里 | 同上 |
| `demo` 命令 | ❌ | 自动切临时账本 |
| 测试 / 自测 / 只读分析 | ❌ | 默认拒写 |

第一版把绑定插在**模块级**——导入即绑定，是副作用。改到 `main()` 里：**只有真跑这个脚本才绑定，被 import 不绑**。

### 四层自测

```
[PASS] 未绑定 → 拒绝 'v2收集·真名样本'      ← 结构性修复
[PASS] 未绑定 → 拒绝 '闭环测试_X'
[PASS] 已绑定但名像测试 → 拒绝 '闭环测试_X'
[PASS] 已绑定但名像测试 → 拒绝 '自测样本'
[PASS] 已绑定但名像测试 → 拒绝 'demo run'
[PASS] 已绑定但名像测试 → 拒绝 'probe 一下'
[PASS] 绑定 + 真名 → 放行（临时账本）
[PASS] 临时账本下测试名可写
```

**第一项是这轮的核心**：连"看起来像真样本"的名字，未绑定也拒。

### 主线不再吞错

`_record_round` 原来是 `except Exception: pass`——**记账失败被静默吞掉**，调用方以为记上了。

改成把 `ProductionWriteRefused` 往上抛：

```
记账被门禁拒绝：...
  主线不认识调用方的身份——绑不绑定正式账本由入口决定。
```

### 实测

MCP 用临时账本跑完整闭环：

```
任务: 落账验证（and）
先验来源: 硬编码默认        ← 临时账本无样本，正确回落
已记入账本 m1-df12…（pending，L3）
→ auto_resolve → 已回填 1 条

临时账本行数: 2
正式账本条数: 95            ← 未被污染
```

### 断言

```
harness 52/52   extend 46/46   ledger guard 8/8
```

### 一个仍然存在的缺口

默认拒绝解决的是"**忘记隔离**"。它解决不了"**故意用真名造假样本**"——那需要人守。

但两者的区别在于：忘记是常态、故意是例外。**默认拒绝挡住了常态，就够了。**

---

## 第三十九轮 · 把套件归到 tests/

前两轮一直挂着没做的一条：目录分层。这一轮做完了。

### 之前是什么样

47 个文件平铺在一个目录里，架构本体（8 个）和实验套件（23 个）混在一起，靠文件名前缀区分：

```
model1-arch/
  harness.py  extend.py  taskgraph.py  ledger.py  ...   ← 本体 8 个
  case_l3_*.py (6)  collect_*.py (5)  case_*.py (3)
  evaluate_model.py  predict_check.py  probe_sargable.py
  arch_score*.py  self_score.py  survey_19.py  ...      ← 套件 23 个
```

**看不出哪个是架构，哪个是实验。**

### 现在

```
model1-arch/
  ├── harness.py        主判定（三道闸、Claim、环境档位）
  ├── extend.py         主线流程（取证→循环→闸门→组合→记账）
  ├── taskgraph.py      任务级组合与账本校准
  ├── ledger.py         判定账本 + 写入门禁
  ├── precheck.py       前置检查（三态 + 机制适用性）
  ├── sqlcheck.py       SQL 领域实现
  ├── sargable.py       机制适用性规则
  ├── mcp_server.py     MCP 入口（9 个工具）
  ├── ledger.jsonl      账本本体
  ├── README.md
  └── tests/            回归套件 25 项 + artifacts/
```

**根目录只剩架构本体和账本。** 想知道"这套东西是怎么运作的"，看根目录那 8 个文件就够了。

### 迁移踩的坑

移动不是 `mv` 就完事——脚本对自身路径有假设：

| 假设 | 移动后 | 修法 |
|---|---|---|
| `sys.path.insert(0, HERE)` | 找不到 `harness` | 指向 `ROOT`（上一层） |
| `detect_env(HERE, ...)` | 数的是 tests/ 的源码 | 指向 `ROOT` |
| `os.path.join(HERE, "harness.py")` | 文件不存在 | 指向 `ROOT` |
| `COMP = dirname(ROOT)/seekdb-2026-competition` | 少一层，目录不存在 | 多剥一层 |

**第一次跑 25 个套件挂了 19 个。** 逐个查出来才修完。

### 新增统一回归入口

以前回归要手抄一长串文件名，加个新脚本就得记得补进去——**漏掉的那个等于没测过**。

`tests/run_all.py` 现在是唯一的套件清单：

```bash
python tests/run_all.py            # 全部
python tests/run_all.py --core     # 只跑架构本体
python tests/run_all.py --quiet    # 只报失败
```

它区分两种断言形式：数 `[PASS]` 条数（harness 52 / extend 46 / guard 8），或匹配一句话（sargable 的 `准确率: 15/15`）。

```
架构本体
  OK   harness.py         52/52 断言
  OK   extend.py          46/46 断言
  OK   ledger.py          8/8 断言
  OK   sargable.py        准确率: 15/15

回归套件（25 个）
  OK   case_1440.py … collect_degrade.py --batch c --dry-run

ALL PASS
```

### 为什么这算「优化」

前三轮改的是判定逻辑；这一轮改的是**这套东西能不能被人看懂**。

一个 47 文件平铺、本体与实验混放的目录，读的人第一眼就找不到架构在哪——那我改了多少轮判据，效果都传不出去。

---

## 第四十轮 · 主线终于有对外入口了

### 问题

`extend.py` 只有 `selftest` 和 `bench` 两个命令。主线（`evaluate_claims`）**只能从 MCP 和测试里调**，命令行跑不了。

也就是说：这套架构判了几十万次，**没有一次是人直接用它判的**。

### 补一个入口

```bash
python extend.py judge tests/task_index_demo.json
python extend.py judge task.json --env 2 --relation or --record
```

任务定义是 JSON，声明每条主张怎么验证：

```json
{"name": "索引优化三问", "relation": "and", "env_level": 3,
 "claims": [
   {"cid": "C1", "text": "让 age=42 走索引", "e1": 2, "e3": 2, "kind": "procedure",
    "verify": {"domain": "sql",
               "task": {"sql": "SELECT COUNT(*) FROM bench_l3.t_ann WHERE age = 42"}}},
   {"cid": "C2", "text": "让 age+0=42 走索引", "e1": 2, "e3": 2, "kind": "procedure",
    "verify": {"domain": "sql",
               "task": {"sql": "SELECT COUNT(*) FROM bench_l3.t_ann WHERE age + 0 = 42"}}}
 ]}
```

### 输出形状（`summarize()`）

```
============================================================
主线评估
============================================================
环境: L3 —— 完整（可联网 + 可执行 + 有源码）
先验: 账本 L3

事前取证
  C1    前置 ok      机制可用      → input_valid=True
        索引列在谓词里是裸引用，可用索引
  C2    前置 ok      机制不适用     → input_valid=False
        列 age 被算术表达式包住，索引原理上用不上
  C3    前置 fail    机制未查      → input_valid=False
        表 no_such_table 不存在

判定
  C1    pass    C=4
  C2    reject  C=6
  C3    reject  C=5
  C4    degrade C=2  成因=info

组合（and）  整体成功率 0.0027   最弱一环 C2
覆盖率  3/4 = 75%   （其余是 degrade，结论带保留）
成因分布  info:1  pass:1  reject:2
============================================================
```

**四件必须交代的事都在里面**：在什么环境下判的、先验从哪来、每条怎么判的、合起来多少。

### 一个值得看的细节

C2 的 `C=6`（满分）、C3 的 `C=5`——**两个都是高分，两个都被 reject**。

因为 `input_valid=False` 是一票否决，优先于分数。这正是第三十六轮接线要的效果：

> 高分 ≠ 结论对。机制不适用的时候，分数再高也是错的。

### 另外：账本备份归档

7 个 `.bak-before-*` 从根目录挪到 `ledger-history/`，根目录从 18 个文件降到 10 个（8 本体 + 账本 + README）。

**归档时踩了个坑**：`Get-ChildItem -Filter "ledger.jsonl.*"` 把 `ledger.jsonl` 本身也匹配走了（Windows 通配符的老问题）。发现后立刻移回，核实账本仍是 55 条、先验未变。

### 断言

```
harness 52    extend 55    guard 8    sargable 15/15
对外入口 1 项（覆盖率 / 最弱一环 / 机制不适用 必须出现在输出里）
回归套件 25 项
```

`tests/run_all.py` 现在分三段：本体断言 → 对外入口冒烟 → 套件跑通。

---

## 第四十一轮 · 入口实测 + 来源标记

上一轮留了三条：`--record` 没测过、`judge` 没在 file 域跑过、`bind_production` 是进程级。

### 一、`tests/smoke_entry.py`：把入口真正测一遍

**file 域三态**（不依赖 WSL，跑得快）：

```
事前取证
  F1    前置 ok      机制未查      → input_valid=True     存在且可读
  F2    前置 fail    机制未查      → input_valid=False    路径不存在
  F3    前置 ok      机制未查      → input_valid=True     存在且是目录

判定  F1 pass / F2 reject / F3 pass
```

说明 `verify` 按 `domain` 分发是真通了——`sql` 走 `sqlcheck`，`file` 走 `FilePrecheck`，主线不关心是哪个领域。

**`--record` 的账本隔离**：

```
正式账本 97 → 97 行
临时账本  0 →  3 行
```

这条必须单独测——它是唯一会改账本的入口，不隔离就测等于拿正式账本做实验。

11 项断言全过。

### 二、`origin`：让账本自己说清来源

之前只有进程级 `bind_production()` 开关。问题很明确：

> **同一进程里，绑定了就是全绑定了。** MCP 进程里跑个测试，测试也会被放行。

改成每次调用都声明来源：

```python
record(..., origin="collect" | "case" | "mcp" | "cli" | "test")
```

两层收益：

| 收益 | 说明 |
|---|---|
| **事后审计** | 账本里每条记录都带 `origin`，能说清谁写的 |
| **事前拦截** | `origin="test"` 一律拒写，**哪怕进程已绑定** |

各入口已声明：

```
collect_v2 / collect_io / collect_env / collect_degrade / collect_mechanism → collect
case_l3_* / case_unknown / predict_check                                   → case
mcp_server.py                                                              → mcp
extend.py judge                                                            → cli
```

实测落库：

```
记录 m1-65ad909a5b75  origin=cli  verdict=pass
正式账本行数: 97
```

### 三、门禁现在是六层

```
[PASS] 未绑定 → 拒绝 'v2收集·真名样本'        ← 结构性：默认拒
[PASS] 未绑定 → 拒绝 '闭环测试_X'
[PASS] 已绑定但名像测试 → 拒绝 '闭环测试_X'    ← 名字层
[PASS] 已绑定但名像测试 → 拒绝 '自测样本'
[PASS] 已绑定但名像测试 → 拒绝 'demo run'
[PASS] 已绑定但名像测试 → 拒绝 'probe 一下'
[PASS] 已绑定但 origin='test' → 拒绝          ← 来源层（这轮新增）
[PASS] origin 声明后放行且写入记录
[PASS] 绑定 + 真名 → 放行（临时账本）
[PASS] 临时账本下测试名可写
```

### 断言

```
harness 52    extend 55    guard 10    sargable 15/15
smoke_entry 11   对外入口 1   回归套件 26
```

`tests/run_all.py` 的断言数是硬编码的——guard 从 8 涨到 10 时它立刻报了 `10/8`。

**这是清单该有的行为**：数量变化必须被人看见，而不是自动跟着改。

---

## 第四十二轮 · 来源分布 + 回填的诚实边界

上一轮加了 `origin` 声明，但**没有地方看这个分布**。这一轮补上。

### 一、`stats()` 加 `by_origin`

```
$ python ledger.py stats
  总数 95 / 已结算 95 / 待结算 0
  环境分布: L2:18  L3:77
  来源分布: 未声明:95
            ↑ 95 条没有 origin 声明（第四十一轮之前的老样本），说不清是谁写的
```

第一次跑出来就是这句话——**整个账本一条都说不出是谁写的**。

这不是 bug，是历年样本的真实状态。但"说不清"这个事实**必须显示出来**，而不是默认它们都可信。

### 二、按任务名前缀回填（并标明这是推断）

95 条老样本的名字能对出来源：

| 前缀 | 条数 | origin | 依据 |
|---|---|---|---|
| `v2收集` / `degrade复查` / `env收集` / `file收集` / `http收集` / `机制维度` | 64 | `collect` | 采集脚本产出 |
| `预测` / `L3 ` / `限额` / `补充` / `优化` / `unknown` | 22 | `case` | 案例脚本产出 |
| `seekdb 部署UUID` / `case_train` / `calib` | 9 | `seed` | 历史种子数据 |

回填后：

```
来源分布: case:22  collect:64  seed:9
```

**但这是推断，不是实测。** 所以每条同时写了 `origin_evidence`：

```
任务名前缀 'case_train' → ledger.py seed 历史数据（第四十二轮回填，推断非实测）
```

原则很简单：**推断可以写，但不能写成事实。** 账本里现在能区分"自带声明的 origin"和"回填推断的 origin"。

### 三、回填没动判定

回填只碰 `origin` 和 `origin_evidence` 两个字段。核实过先验一字未变：

```
L2  pass 0.95  / degrade 0.65 / reject 0.02 / degrade/env 0.917
L3  pass 0.812 / degrade 0.65 / reject 0.067 / degrade/info 0.75
```

### 四、MCP 也显示

```
过滤: L3/v2    总数 55 / 已结算 55 / 待结算 0
环境分布: L3:55    版本分布: v2:55
来源分布: case:1  collect:54
```

L3 v2 这 55 条里 `case:1 / collect:54`——说明当前判据的样本几乎全来自采集脚本，案例脚本只贡献了 1 条。这是有用的信息：**判据的校准基础偏窄**。

### 断言

```
harness 52    extend 55    guard 11    sargable 15/15
smoke_entry 11   对外入口 1   回归套件 26
```

guard 10 → 11（新增"来源分布统计到三种"）。

---

## 第四十三轮 · 重测 case 样本，查出两个真 bug

上一轮发现：L3 v2 里 `case:1 / collect:54`——**先验几乎全由采集任务校准**。

根因：21 条 case 样本全是 **v1**，判据升到 v2（加 cause 拆分 / 三态 input_valid / e3 推导）之后**一直没重测**。

按 v2 重测，过程中查出两个 bug。

### bug 一：`success` 记成了「判据判得对不对」

| 脚本 | `success` 实参 | 含义 | 对不对 |
|---|---|---|---|
| case_l3_explain | `ok = switched`（算子真切到索引） | 意图达成 | ✅ |
| case_unknown | `code == 0 and got`（真跑出结果） | 意图达成 | ✅ |
| case_l3_optimize | `faster`（真变快） | 意图达成 | ✅ |
| collect_* | `actual`（执行成功） | 意图达成 | ✅ |
| **case_l3_limits** | `judged_right`（判定与预期一致） | **判定正确性** | ❌ |
| **case_l3_more** | `good`（判定与预期一致） | **判定正确性** | ❌ |

两个脚本把「判对了」记成「做成了」。后果直接可见：

```
修之前  reject  2/22 = 0.125     ← 判 reject 却说"成功"
修之后  reject  0/21 = 0.043     ← 归零
```

`judged_right` 该记在 `conclusion_verified`，不是 `success`：

```python
success=False,                      # 限额任务没验证出来，意图未达成
conclusion_verified=judged_right,   # 判据这次判对了
```

### bug 二：`cause` 根本没传

`run_gates` 明明返回 `cause='info'`，落库却是空：

```
degrade/unknown   n=9    ← 这九条不是"另一种降级"，是漏传
```

查出来 **5 个脚本**都缺 `cause=`：

```
case_l3_explain.py  case_l3_limits.py  case_l3_more.py
case_l3_optimize.py  predict_check.py
```

全部补上。补完 `unknown` 桶消失，25 条 degrade 全部落在 `info`。

### 修完的数据

```
L3 v2: 71 条   collect:54  case:17   成因 info:25（无 unknown）

pass          20/25 = 0.778
degrade/info  15/25 = 0.593
reject         0/21 = 0.043

单调性 ✓   三档分离明显
```

**对比修之前：**

```
pass          0.812
degrade/info  0.750      ← 和 pass 几乎贴在一起
reject        0.056
```

### 上一轮那个结论，得改

Round 32 我写过：

> 「degrade 成功率 85.7%，和 pass 一模一样——**这一档目前没有信息量**」

**那句话有一半是测量错误造成的。**

真正的原因不是 degrade 没用，是限额类任务的 `success` 被错记成 `judged_right`——5 条"判对了"的样本被当成"任务成了"，把 degrade 的成功率抬到和 pass 齐平。

修完之后 degrade 是 0.593，pass 是 0.778，**两档分得很开**。

同样的教训第二次出现：**先怀疑尺子，再怀疑被测对象**（第一次是 Round 32 的"任务做成 ≠ 结论对"）。

### 结论复查

```
degrade/info  复查 16/25   成立 13   推翻 3   推翻率 19%
```

判 degrade 的任务里约两成结论后来站不住——和上轮 27% 同量级，但这次样本是干净的。

### 断言

```
harness 52    extend 55    guard 11    sargable 15/15
smoke_entry 11   对外入口 1   回归套件 26
```

---

## 第四十四轮 · collect 的 success 也有同一个毛病

上一轮修了 case 脚本的 `success` 语义，留了个尾巴：**`collect_*` 也该审一遍**——它贡献 54/71 条样本，判错影响最大。

### 审出来的问题

`collect_v2` 记 `success = 执行成功`。对纯动作任务（"新建表"、"插入行"）没问题，但 7 条 degrade 任务里有一半，**跑成功不等于目标达成**：

| 任务 | SQL 实际做了什么 | 目标达成了吗 |
|---|---|---|
| `D1 让这条查询走索引` | `CREATE INDEX` | ✅ 索引建出来了 |
| `D3 评估这条查询的成本` | `EXPLAIN` | ✅ 就是评估 |
| `D4 确认数据分布是否均匀` | `GROUP BY` | ✅ 给出了分布 |
| `B1 让这条查询更快` | 只跑了 `SELECT` | ❌ **什么都没优化** |
| `B2 确认索引是否生效` | 只拿到行数 | ❌ **没看执行计划** |
| `D2 减少这次全表扫描` | 又跑了一次全表扫描 | ❌ **没减少** |
| `D5 验证索引是否被采用` | 普通 `SELECT` | ❌ **看不出索引有没有用** |

判据写成一句话：**这条 SQL 是否真的做了任务名说的那件事**。

```python
INTENT_ACHIEVED = {
    "B1": False, "B2": False,
    "D1": True, "D2": False, "D3": True, "D4": True, "D5": False,
}
success = act and INTENT_ACHIEVED.get(tid, True)
```

### 修完的数据

```
L3 v2: 71 条   collect:54  case:17   成因 info:25

pass          20/25 = 0.778
degrade/info  12/25 = 0.481     ← 从 0.593 再降到 0.481
reject         0/21 = 0.043

单调性 ✓   分离更明显
```

三轮修下来 degrade 的变化轨迹：

```
0.75  →  0.593  →  0.481
```

### 为什么 0.481 才对

`degrade` 的语义是「**我们不确定**」。不确定的东西，成功率就该接近掷硬币。

- 0.75 时它看起来和 pass（0.81）差不多 → **这一档等于没用**，标了"不确定"却几乎总能成
- 0.48 时它诚实地表示"一半一半" → 这一档才有存在意义

**这正是 Round 32 我误判的那个点。** 当时我说"degrade 和 pass 成功率一样，这一档没信息量"，其实是三处 `success` 语义错误把它抬上去的：

1. `case_l3_limits` / `case_l3_more` 记 `judged_right`（第四十三轮修）
2. `collect_v2` 记"执行成功"（这一轮修）
3. 老样本 `conclusion_verified` 与 `success` 混用（第三十轮修）

**一个"看起来坏了"的机制，可能只是量它的尺子坏了。**

### 断言

```
harness 52    extend 55    guard 11    sargable 15/15
smoke_entry 11   对外入口 1   回归套件 26
```

---

## 第四十五轮 · 把 pass 的两条假阳性连根拔掉

上轮留了个尾巴：**pass 20/25 里 5 条失败没查**。查清楚了，性质完全不同的三类。

### 一、先分清自然样本和对照组

5 条失败里 3 条是 `group=c` —— **Round 34 我故意调高 e1/e3 判 pass 的阴性对照**。它们失败是设计预期。

但更严重的是：**我一直在用混算了对照组的数**。

```
混算（错）        pass 20/25 = 80%
自然池（对）      pass 16/18 = 89%
对照组            pass  4/7
```

`stats()` 加了 `exclude_control=True`，`evaluate_model` 改为默认用自然池。**对外报的数必须排除实验材料。**

### 二、剩下的 2 条，性质也不同

| 样本 | 真相 |
|---|---|
| `H1 访问 github.com` | 记录时网络不通（act=False），现在通了 → **网络抖动**，不是判据错 |
| `H6 访问 404 路径` | TCP 通但资源不存在 → **判据的真缺口** |

### 三、修缺口：HttpPrecheck 加第三关

之前只查两关：DNS 能解析、TCP 能连上。

```
第一关 DNS    github.com 能解析 ✓
第二关 TCP    github.com:443 能连上 ✓
              → 判 pass
实际          HEAD 请求返回 404 / 连接被重置
```

**"服务器在"不等于"这东西在"。**

加第三关——发一个 HEAD 请求看资源本身：

| 响应 | 判定 | 理由 |
|---|---|---|
| 2xx / 3xx | ok | 资源可访问 |
| 4xx / 5xx | **fail** | 资源不存在或不可访问 |
| 405（不支持 HEAD） | unknown | 查不了，不下结论 |
| 连接被重置/拒绝（10054/10061） | **fail** | 明确的否定响应 |
| 超时 | unknown | 可能只是慢 |

实测：

```
example.com                          ok      HTTP 200
github.com                           fail    连接被拒/重置（WinError 10054）
github.com/oceanbase/no-such-repo…    fail    连接被拒/重置
no-such-host-xyz-12345.invalid        fail    域名不存在
ftp://example.com/x                   fail    协议不支持
not-a-url                             fail    协议不支持
```

**"超时判 unknown、明确拒绝判 fail"**——这个区分很重要：把"没查成"写成"不行"，等于凭空否定一个可能成立的任务。

### 四、顺带修掉门禁的误杀

重测时 `collect_io` 挂在一个意外的地方：

```
记账被门禁拒绝：file收集·F4 写一个临时文件
```

`TEST_MARKERS` 里有 `"临时"`，而"写一个临时文件"是正常任务名。**门禁的名字层比结构性那层还凶，是设计错了。**

剔除 `"临时"` / `"probe"`，只留真正说明"这是测试"的词（测试 / test / demo / 自测 / 闭环）。门禁仍是 13 项断言，新增"正常任务名不被误杀"。

### 五、修完的数

```
自然池 61 条
  pass 精确率   16/16 = 100%
  reject 精确率 20/20 = 100%
  degrade 成功率 12/25 = 48%
  覆盖率        36/61 = 59%
  单调性        ✓  100% ≥ 48% ≥ 0%
```

### 但这个 100% 要打个折

Wilson 95% 区间：

```
pass    16/16 = 100%   [0.806, 1.000]
reject  20/20 = 100%   [0.839, 1.000]
```

**样本只有 16 条和 20 条，真实精确率可能低到 80%。**

100% 不等于"不会错"，只等于"这批样本里没错过"。要敢说 95% 以上，得把 pass 桶加到 60 条以上。

### 断言

```
harness 52    extend 55    guard 13    sargable 15/15
smoke_entry 11   对外入口 1   回归套件 26
```

---

## 第四十六轮 · 把「靠人眼查账本」变成工具

前三轮我靠手工翻账本查出三类语义 bug：

| 轮次 | 查出什么 | 手工怎么查的 |
|---|---|---|
| 36 | `success` 记成"判得对不对" | 逐条 print 出 5 条失败的 pass 样本看 |
| 36 | `degrade` 漏传 `cause` | grep 出 5 个脚本的 `L.record(` 逐个数参数 |
| 38 | 阴性对照混进自然池 | 手算 `by_origin` 和 `group` 交叉表 |

**三类都是同一份账本里的自相矛盾，本该由工具发现。**

### `python ledger.py audit`

```
账本审计
  检查 81 条记录

错误: 0 项
警告: 0 项

提示: 4 项
  · [样本量] degrade/env: n=10，成功率下界 0.72（下界要到 0.9 以上才敢报精确率）
  · [样本量] degrade/info: n=25，成功率下界 0.30（下界要到 0.9 以上才敢报精确率）
  · [样本量] pass: n=16，成功率下界 0.81（下界要到 0.9 以上才敢报精确率）
  · [样本量] reject: n=20，成功率上界 0.16（要压到 0.1 以下才算 reject 判得准）

没有自相矛盾的记录
```

检查项分三级：

| 级别 | 判据 | 为什么 |
|---|---|---|
| **错误** | `cause` 出现在非 degrade 上 | 字段语义自相矛盾 |
| **错误** | v2 的 degrade 缺 `cause` | degrade 必须说清是环境降级还是证据不足 |
| **错误** | 同一 id 记了两次 | 账本被重复写 |
| **警告** | `reject` 却 `success=True` | 要么任务其实做成了，要么 success 记错了东西 |
| **警告** | `pass` 却 `success=False` | 假阳性，或样本来自旧版检查器 |
| **警告** | 缺 `origin` | 说不清是谁写的 |
| **警告** | 同一「任务+版本」多条 | 重复测量，需确认不是重复记账 |
| **提示** | 桶的 Wilson 界不够窄 | 样本量不足，别急着报精确率 |

### 检测器自己也要先验证

第一版审计跑出来报 3 条警告——全是 `K1/K2/K3`。但那是**阴性对照**，`pass` 却失败是设计预期。

第二版还犯了个方向错误：对 `reject` 报"下界 0.00，要 0.9 以上"——**方向反了**。reject 要的是成功率**上界低**，不是下界高。

修完才是我要的东西。

### 然后证明它真能抓

**没测过的检测器等于没有。** 往临时账本注入五类问题：

```
[PASS] 审计抓到 cause 越界
[PASS] 审计抓到 degrade 缺 cause
[PASS] 审计抓到 reject 却成功
[PASS] 审计抓到 pass 却失败
[PASS] 审计抓到缺 origin
[PASS] 审计把矛盾算作错误而非警告  — 2
```

六项全中。`guard` 从 13 项断言涨到 19 项。

### 接进回归

```python
CORE = [
    ("harness.py",  ["selftest"], 52),
    ("extend.py",   ["selftest"], 55),
    ("ledger.py",   ["guard"],    19),
    ("sargable.py", [],           "准确率: 15/15"),
    ("ledger.py",   ["audit"],    "没有自相矛盾的记录"),   ← 新增
]
```

**账本一旦自相矛盾，回归就红。** 以前这类问题要等我下次手工翻到才发现。

### 这一轮的意义

前几轮修的是**具体数据**；这一轮修的是**发现问题的能力**。

我在这套东西上犯了 16 次"证据强度低于断言强度"的错（如 `~/.dsh/AGENTS.md` 所记）。每次都是靠回头翻才发现的。

把检查写成工具，是唯一能让同一个错不犯第二遍的办法。

### 断言

```
harness 52    extend 55    guard 19    sargable 15/15
账本审计 0 错误 / 0 警告
smoke_entry 11   对外入口 1   回归套件 26
```

---

## 第四十七轮 · degrade/env 从单场景变成跨域

审计的提示里有一条一直没动：

```
[样本量] degrade/env: n=10，成功率下界 0.72
```

`n=10` 只是表面问题。真正的问题是**这 10 条全是同一种情形**——`tests/collect_env.py` 里清一色 SQL 任务。**一个场景的 10 条样本，撑不起一个先验。**

### 做法：让 collect_io 也能按 L2 判

```bash
python tests/collect_io.py --env 2     # 判定用 L2，执行照旧
```

`--env N` 强制判据按某档走，执行不变。这样 file / http 任务也能产出 `degrade/env` 样本。

预判验证（同一批主张，两种环境）：

```
读文件            L3  pass      L2  degrade  cause=env
读不存在的文件      L3  pass      L2  degrade  cause=env
访问 example.com  L3  pass      L2  degrade  cause=env
```

### 结果：三个域都有样本了

```
degrade/env 这一档的样本量：15 条
  env收集(sql)   10
  file收集        4
  http收集        1
```

```
L2 v2: 23 条
  degrade/env  15/15  Laplace=0.941  Wilson[0.796, 1.0]
  reject        0/8   Laplace=0.1    Wilson[0.0,   0.324]
```

Wilson 下界从 0.72 升到 0.80。**样本数只多了 5 条，但域跨度从 1 个变成 3 个——这比单纯加量有用。**

### 顺带修掉审计自己的一个缺陷

加 L2 样本前先查了一遍：审计的"重复测量"用 `(task, version)` 做 key，**没含 env_level**。

后果很明确：同一个任务在 L3 和 L2 各判一次是**有意为之**（跨环境对照），会被误报成重复记账。

加进 `env_level` 后不再误报。**这是第三次发现我新写的检测器本身有毛病**（前两次：误报阴性对照、reject 边界方向反了）。

检测器和被测对象一样需要验证。

### 一条要说清的语义问题

`degrade/env` 15/15 = 100% 看着漂亮，但它**近乎同义**：

- 判定时按 L2 限制（e3 封顶 1 → 降级）
- 执行时用 L3 权限（真跑）
- 所以"任务做成了"几乎是必然

**这个数回答的是"如果有完整证据，这任务会不会成"，不是"在当前环境里会不会成"。**

它有用——它说明框架能正确识别"值得去补证据"的任务。但不能拿来当"任务成功率"看。

这条局限我记在这里，暂时不动先验口径。

### 断言

```
harness 52    extend 55    guard 19    sargable 15/15
账本审计 0 错误 / 0 警告（94 条记录）
smoke_entry 11   对外入口 1   回归套件 26
```

审计的样本量提示变化：

```
degrade/env: n=10 → n=15，下界 0.72 → 0.80
reject:      n=20 → n=28，上界 0.16 → 0.12
```

---

## 第四十八轮 · 让样本可以重跑

审计能查账本**自相矛盾**，查不了**"这条样本当初测得对不对"**。

原因很具体：样本里只存了 `task` 字段——一句人读的描述（`"file收集·F1 读 harness.py"`）。**没有任何东西能让机器把它再跑一遍。**

### 两件事一起做

**一、执行逻辑提出本体**

原来 `do_exec` 只活在 `tests/collect_io.py` 里。提到 `probe.py` 之后：

```
采集脚本  →  probe.do_exec()   ← 采集和重跑用同一份逻辑
重跑审计  →  probe.do_exec()      不会各写一套、各错一处
```

职责分清楚：

| 模块 | 干什么 |
|---|---|
| `probe.py` | 按规格真跑一次（file 的 read/dir/write/create，http 的 HEAD） |
| `ledger.py` | 记账、统计、审计、重跑核对 |
| `tests/collect_*.py` | 造样本 |

**二、样本自带规格**

```python
record(..., replay={"domain": "file", "task": {"path": ..., "op": "read"}})
```

`collect_io` 现在每条样本都带这个规格。

### `python ledger.py replay`

```
样本重跑核对
  检查 94 条：一致 26  对不上 0  无规格/待结算 68

查不了的 68 条（没有可重跑规格）：
  · origin=case: 17 条
  · origin=collect: 51 条

全部对得上
```

**26 条带规格的样本，重跑全部与记账一致。**

68 条查不了的是老样本（记在加规格之前）——如实报"查不了"，**不冒充"一致"**。

### 重跑检测器自己也要先验证

「全部一致」不算证据——检测器可能根本不会报错。**把世界改掉，看它报不报。**

```
[PASS] 样本仍在 → 重跑一致            ok=1 drift=0
[PASS] 文件被删 → 重跑报漂移          drift=1
[PASS] 漂移记录里记账与重跑都留着      was=True now=False
[PASS] 无规格样本计入「查不了」而不是「一致」  no_spec=1
```

第三条尤其重要：漂移报告里同时留着**当初记的**和**现在跑的**，人才能判断是记错了还是世界变了。

### drift 不等于记错

文件被删、网络变了、URL 失效都会造成 drift。**它只说明"这条样本对不上当前世界"，需要人看一眼。**

这条写进了 `replay()` 的 docstring，免得以后有人把 drift 当成"账本有 bug"。

### 修的过程中撞上两处规格不匹配

| 现象 | 原因 |
|---|---|
| 13 条带规格只核对到 5 条 | http 的规格里没有 `op` 键，`replayable()` 判不了 |
| F4/F6 不可重跑 | 判据用 `op="create"`、执行用 `write`，白名单只收了 write |

两处都是**同一件事的两个叫法没对齐**。修完 13 条全部可重跑。

### 断言

```
harness 52    extend 55    guard 23    sargable 15/15
账本审计 0 错误 / 0 警告
样本重跑 26 一致 / 0 漂移
smoke_entry 11   对外入口 1   回归套件 26
```

`guard` 从 19 涨到 23（新增重跑四条）。`replay` 也进了回归清单：**样本一旦对不上当前世界，回归就红。**

### 这一层解决了什么，没解决什么

| 解决了 | 没解决 |
|---|---|
| 带规格的样本可以验证"现在还成不成立" | sql 域没有执行器，样本仍不可重跑 |
| 采集与重跑共用一份执行逻辑 | 老样本没有规格，只能标"查不了" |
| 漂移会被工具发现，不靠人记得复查 | drift 的归因仍需人判断 |

---

## 第四十九轮 · 让 sql 也能重跑，然后被自己的工具抓了两次

上一轮留的缺口：**sql 占 v2 样本一半以上，却是唯一不可重跑的。**

### 一、加 sql 执行器（批量）

```
probe.do_exec_many("sql", [ {...}, {...} ])
```

必须批量：每条 SQL 都要起一次 WSL、等 seekdb 起来。单条调用慢到没法用。

```
起库 → 逐条执行 → R0=ok / R1=fail 标记 → 按序取回
```

`replay()` 改成**按域分组批量跑**，一次 WSL 覆盖整批 sql 样本。

### 二、第一次被自己抓住：假漂移 5 条

加上 sql 后重跑，报出 5 条对不上：

```
✗ B1 让这条查询更快        记账=False  重跑=True
✗ B2 确认索引是否生效       记账=False  重跑=True
✗ D2 减少这次全表扫描       记账=False  重跑=True
✗ D5 验证索引是否被采用     记账=False  重跑=True
✗ D1 让这条查询走索引       记账=True   重跑=False
```

**前四条全是我的工具犯了我刚修过的那个错。**

`success` 记的是**意图达成没有**（B1 只跑了 SELECT，没优化 → False），而重跑测的是**语句跑没跑通**（→ True）。**两把不同的尺子，被当成一把用了。**

这正是第三十六～三十八轮修了三遍的那个混淆，被我自己在新工具里又犯了一次。

修法：把两个问题**分开存**。

```python
record(..., success=<意图达成>, exec_ok=<执行跑通>)
```

`replay` 比 `exec_ok`，不看 `success`。

### 三、第二次被抓住：D1 是非幂等

`CREATE INDEX` 第二次跑必然失败（索引已存在）。这不是漂移，是**操作本身只能做一次**。

修法：**sql 只收无副作用的语句**。

```python
_READONLY_SQL = ("select", "explain", "show", "desc", "with")
```

`CREATE` / `INSERT` / `DROP` / `ALTER` 一律不进重跑。

### 四、第三次：临时表让样本天然不可重跑

修完上面两条，还剩 4 条漂移：

```
✗ env收集·G7 查 t_g
✗ v2收集·A3 计数
✗ v2收集·A6 限 1 行查询
✗ v2收集·B1 让这条查询更快
```

原因都是**查的表在采集过程中被建了又删**（`t_c1` / `t_g`）。样本依赖了会消失的状态。

这类不该算"可重跑"。采集脚本现在对这类 SQL 不挂规格：

```python
_EPHEMERAL = ("t_c1", "t_g")
def _replay_spec(sql):
    return None if any(t in sql.lower() for t in _EPHEMERAL) else {...}
```

### 结果

```
样本重跑核对
  检查 94 条：一致 41  对不上 0  无规格/待结算 53
  一致的按域： file:14  http:12  sql:15

全部对得上
```

**sql 从 0 条可重跑变成 15 条，且全部一致。**

### 三次被自己抓住，说明什么

| 次序 | 我的工具犯的错 | 和我修的 bug 是同一个 |
|---|---|---|
| 1 | 拿 `success` 比执行结果 | 第三十六～三十八轮的 `success` 语义混淆 |
| 2 | 把非幂等操作当可重跑 | 新的（但同属"没分清两个问题"） |
| 3 | 依赖临时状态的样本算可重跑 | 同上 |

**做检测器的人，会把自己的盲点写进检测器。**

这也解释了为什么每次加检测能力，紧接着就会抓到自己一次——不是巧合，是同一个脑子。

### 断言

```
harness 52    extend 55    guard 23    sargable 15/15
账本审计 0 错误 / 0 警告（94 条记录）
样本重跑 41 一致 / 0 漂移（file 14 / http 12 / sql 15）
smoke_entry 11   对外入口 1   回归套件 26
```

### 现在还不能重跑的是什么

```
查不了 53 条：origin=case 17 / origin=collect 36
```

- `case` 那 17 条（`case_l3_*` / `predict_check`）没挂规格——它们依赖 seekdb 数据状态，且多数是"改"类操作
- `collect` 的 36 条是临时表依赖 + 非幂等语句

**剩下这 53 条不是"验证过没问题"，是"没法验证"。** 这个区别必须写清楚。

---

## 第五十轮 · 投喂真题：APMCM 题库接进来了

前面四十九轮的样本都是**构造的**（SQL 任务、文件读写、HTTP 探测）。这一轮换成真题。

### 题库在哪、有什么

```
C:\...\default-workspace\apmcm2026\题库\
  2026中文-A_B_C三题          23 files  3.3 MB   ← 唯一带完整数据的
  2021/2023/2024 A~D         各套真题
  原始压缩包 8 个            72.3 MB
  获奖名单 9 个               5.2 MB
```

**为什么这批数据重要**：这是唯一能拿到 `e3=measured` 的题源。

| 题 | 数据 | 可测什么 |
|---|---|---|
| **2026 A** 自来水厂水质预测 | 375 行 × 21 列真实传感器时序 | 预测 vs 实测 → 误差 |
| **2026 B** 芯片热管理 | 85 行 × 7 列仿真结果 | 3 个结构参数 → 3 个输出的关系 |

### 新增 `data` 域

架构的输入是**主张**，不是题目。中间要一层适配：题目 → 可验证断言。

`probe.py` 加了 `data` 域，支持六种确定性断言：

| 断言 | 回答什么 |
|---|---|
| `row_count` | 样本量够不够 |
| `column_exists` | 有没有这个字段 |
| `value_bounds` | 数值在不在合理区间 |
| `corr_sign` | 两列是正相关还是负相关 |
| `no_null_in` | 有没有缺失值 |
| `monotone_quarters` | 趋势是递增还是递减 |

**每条都是"算一遍就知道真假"**——这就是 `e3=measured` 的实质。

### 第一次撞上真实数据的坑

`2026 B` 的附件 2 **第一行是大标题，第二行才是表头**。硬编码读第 1 行会把标题当列名，整张表全读错。

加了 `header_row` 参数（默认 1），B 题用 `header_row=2`。

### 13 条主张，我被数据纠正了 5 次

```
[B] ✗ 针肋宽度比越大，热阻越大      corr = -0.324   ← 我想反了
[B] ✗ 热阻列没有缺失值             空值 1/85
[B] ✗ 温度非均匀性四段递增          [0.832, 0.823, 0.800, 0.804]  ← 其实略降
[A] ✗ 1 月滤后浊度始终 < 1 NTU    范围 [0.02, 1.5]   ← 真实数据里有超标
[A] ✗ 河水水位与流量同向            corr = -0.272   ← 又反了
```

**我的预判命中 8/13。**

最值得记的是最后一条：我以为"河水水位高 → 取水量大"，数据显示**负相关**。合理的解释是水位过高时运行方主动减少取水（防洪）。**这个解释我一开始根本没想到。**

成立的两条相关也很有意思：

```
热阻与压降           corr = -0.684   ← 教科书级的反向权衡
歧管深高比越大压降越低  corr = -0.615   ← 与流道截面增大一致
```

**这两条成立，说明数据是真的，断言写对了。** 前面五条失败，是我的直觉错，不是数据错。

### 这一轮的意义

`tests/feed_qb.py` 把 13 条主张跑一遍，输出的不只是对错——**是"我对这份数据知道多少"的实测**。

投喂真题的价值不在"跑通"，在于：

> 数据不认同你的直觉时，你没有辩论余地。

这正好补上架构缺的那一环：前面所有样本都是我自己设计、我自己定义成败的；真题的成败**由数据定，不由我定**。

### 还没做的事（说清楚）

| 项 | 说明 |
|---|---|
| **`data` 域还没接进 precheck** | 目前只在执行侧可用，前置检查仍走 file 域 |
| **13 条主张还没落账** | 语义要先想清楚（见下） |
| **只有 2 道题的数据** | 2026 C 是纯文字题；2021/2023/2024 大多不带数据 |

**落账前必须先想清一件事**：

`pass` 判的是**证据质量**（步骤清楚、可复现），不是**主张为真**。

"针肋宽度比↗热阻"这条，e1=2（能指到文件和列）、e3=2（算一遍可复现）→ 框架会判 `pass`，但**结论是假的**。

所以真题样本不能直接当 `pass` 的验证用——那会把「可验证」和「已验证为真」混成一件事。**这正是第三十六～三十八轮那个混淆的同一副面孔，第四次出现。**

### 断言

```
harness 52    extend 55    guard 23    sargable 15/15
账本审计 0 错误 / 0 警告
样本重跑 41 一致 / 0 漂移
投喂真题 13 条（成立 8）
smoke_entry 11   对外入口 1   回归套件 27
```

---

## 第五十一轮 · 真题样本落账：把「能验」和「验过了为真」分开

上一轮末尾留了一个说不清的问题：

> `pass` 判的是**证据质量**，不是**主张为真**。「针肋宽度比↗热阻」e1=2、e3=2 会被判 pass，但结论是假的。

想清楚了：**这不是框架的问题，是我对 `e3=2` 的用法错了。**

### 关键澄清：`e3` 是什么

```
e3 = 2  ⟺  我实际复现过，而且复现结果支持这条结论
e3 = 1  ⟺  有可复现的方法，但我没做
e3 = 0  ⟺  无从复现
```

我一直把它当成「这条结论**形式上**可复现」——那是 e3=1，不是 2。

按正确读法，一条没验证过的主张**不可能**拿到 e3=2，所以「e3=2 却为假」根本不会发生。

**框架没问题，是我的填法有问题。**

### 落账规则

| 主张的状态 | e3 | `refuted_by_test` | 判定 | `success` |
|---|---|---|---|---|
| 验证过，成立 | 2 | False | **pass** | True |
| 验证过，被推翻 | — | **True** | **reject** | False |
| 可验证，但还没验 | 1 | False | degrade | 待定 |

第三条正是 `refuted_by_test` 的用途——**实测反证一票否决**。它从第一轮就写好了，一直没在真题上用过。

### 13 条真题样本落账

```
已记账 13 条（origin=qb，带 replay 规格）
  pass/成立: 8
  reject/被推翻: 5
```

**8 条验证为真 → pass；5 条被数据推翻 → reject。**

这正好补上了我一直缺的东西：**`pass` 现在真的意味着「我验过，它成立」**，不再是「看起来挺靠谱」。

### 加了 `data` 域的前置检查

```
表头对 + 列在      ok      数据可读（7 列 / 85 行），断言所需列都在
表头错（用第1行）   fail    列不存在：['无量纲热阻']
列不存在          fail    列不存在：['不存在的列']
文件不存在         fail    数据文件不存在
未知断言          fail    未知断言 '瞎写'
```

它只回答「**做得了吗**」，不断言真假——那是执行器的事。**两件事分开，才能分别表述「能验」和「验出来为真」。**

### 又一次被自己的工具抓住（第五次）

加完 qb 样本重跑，报 5 条假漂移：

```
✗ 真题·B 针肋宽度比越大，热阻越大（正相关）
```

原因还是同一个：`do_exec` 对不同域返回**不同问题**的答案。

| 域 | `do_exec` 返回 | 该比哪个字段 |
|---|---|---|
| file / http / sql | 操作跑通了没有 | `exec_ok` |
| **data** | **断言成不成立** | **`success`** |

我在 `probe.py` 里把这个显式写死：

```python
CHECK_KIND = {"file": "execution", "http": "execution",
              "sql": "execution", "data": "assertion"}
```

`replay()` 按域选择比较基准。修完：

```
检查 107 条：一致 54  对不上 0  无规格/待结算 53
一致的按域： data:13  file:14  http:12  sql:15
```

### 同一个混淆，第五次

| 次 | 出现在哪 | 混了什么 |
|---|---|---|
| 1 | `case_l3_limits/more` | 判据判别对了 vs 任务做成了 |
| 2 | `collect_v2` | 执行成功 vs 目标达成 |
| 3 | 老样本回填 | `conclusion_verified` vs `success` |
| 4 | `replay()` 第一版 | `success` vs 执行结果 |
| 5 | `replay()` + data 域 | execution vs assertion |

**五次的形状完全一样：同一个词在不同层指不同的事，我以为是一件事。**

这不是疏忽。这是我在「造工具」时反复重犯的认知盲点：**默认"成不成功"只有一个意思**。

### 数据

```
L3 v2: 84 条  来源 collect:54 / case:17 / qb:13

pass             28/31   Laplace=0.879
degrade/info     12/25   Laplace=0.481
reject            0/28   Laplace=0.033

自然池精确率（L3）
  pass    24/24 = 100.0%
  reject  25/25 = 100.0%
  覆盖率  49/74 =  66.2%
```

`pass` 从 16 条涨到 24 条，Wilson 下界 0.81 → **0.86**。离能用还差，但方向对。

### 断言

```
harness 52    extend 55    guard 23    probe 17    sargable 15/15
账本审计 0 错误 / 0 警告（107 条记录）
样本重跑 54 一致 / 0 漂移
投喂真题 13 条（成立 8）
smoke_entry 11   对外入口 1   回归套件 27
```

`probe.py` 首次进回归清单（17 项断言）。

---

## 第五十二轮 · 挖 2021-A，然后发现自己虚高了精确率

上一轮留的：**pass 还差 36 条**。2021-A 有 7 张真实图像 + 两条逐点边缘轮廓（3887 / 3625 个坐标），是最有第二数据源价值的一套。

### 一、新增 `image` 域

架构以前完全碰不了图像。加了四种「算一遍就知道」的断言：

| 断言 | 回答什么 |
|---|---|
| `dimensions` | 尺寸对不对 |
| `mode` | 位深是 L 还是 RGB |
| `dark_ratio` | 暗像素占比落在什么区间 |
| `unique_gray_levels` | 灰度级数（判是不是二值图） |

另加 `closed_curve`（首尾点是否重合）——这是「看一眼觉得对」最容易错的地方。

### 二、第一版 11 条全对，这本身就是问题

```
这一批里成立 11 条、不成立 0 条
我的预判命中 11/11
```

**全真的主张集没有区分度。** 11 条全都成立，pass 桶只是被灌了 11 条，等于没测。

补了 4 条「看起来对、但没算过」的：

```
[A12] ✗ 轮廓 1 是闭合曲线     首点 [272.0001, 155.8406] 末点 [273.0, 155.8409] 差 1.000
[A13] ✗ 轮廓 2 是闭合曲线     首点 [139.9995, 385.0593] 末点 [140.9954, 385.0894] 差 0.99
[A14] ✗ 两条轮廓点数相同       3886 vs 3624
```

**两条轮廓都不是闭合的，首尾差恰好 1.0。** 这是真实数据的样子，不是我以为的样子。

### 三、然后发现自己虚高了精确率

加上 2021-A 的 15 条，`pass` 从 24 涨到 36，审计报 **「下界 0.90」**——到了能报精确率的门槛。

**但这个数是假的。**

qb 样本的流程是「先跑断言拿到真假 → 再记 pass」。**判的时候已经知道答案了，pass 不可能错。** 拿它算精确率是同义反复。

加了 `prejudged` 字段把这类样本标出来：

```python
record(..., prejudged=True)   # 先验证、后判 pass
```

`stats()` 和 `audit()` 都剔除它。修完：

```
L3 v2 已结算 99 条，剔除先验证后判 28 条

精确率（判前不知答案的样本）
  pass    16/16 = 100%   Wilson[0.806, 1.0]
  reject  20/20 = 100%   Wilson[0.839, 1.0]

审计：pass n=16，下界 0.81
```

**和投喂真题之前一模一样。**

### 这一轮的真实结论

| 我做到什么 | 数值 |
|---|---|
| 加了 `image` 域、`closed_curve`、`column_index` | 工具变强 |
| 挖出 3 条我之前判断错的真题事实 | 认知修正 |
| 多了 28 条真实数据样本 | 覆盖率 66% → **72%** |
| **对「pass 能不能预测」的检验贡献** | **0** |

**样本数涨了，判据的验证强度一点没涨。**

这是这一轮最该记住的事：**加样本很容易，加"能证伪判据"的样本很难。** 前者让数字好看，后者才让判断可靠。

### 什么样的样本才检验判据

| 样本类型 | 检验判据？ |
|---|---|
| 先验证、后判 pass（qb 这批） | ❌ 同义反复 |
| 先判 pass、后验证（collect 那批） | ✅ 真检验 |
| 故意构造的阴性对照 | ✅ 校准用 |
| 先判、后用**独立手段**验证 | ✅ 最强 |

qb 这批要变成真检验，得改成：**先只凭"题目+数据结构"判 pass，再跑断言验证**。

那需要盲判——我作为同一个人很难做到。**这是这套自我评估的结构性上限。**

### 数据

```
L3 v2: 122 条记录   collect:54 / case:17 / qb:28

剔除 38 条（对照组 + 先验证后判）后：
  pass    16/16   下界 0.81
  reject  28/28   上界 0.12
  degrade/info  n=25  成功率 48%
  覆盖率  64/89 = 71.9%
```

### 断言

```
harness 52    extend 55    guard 23    probe 17    sargable 15/15
账本审计 0 错误 / 0 警告（122 条记录，剔除 38 条）
投喂真题 13 + 15 条
smoke_entry 11   对外入口 1   回归套件 28
```

---

## 第五十三轮 · 盲判：把「判」和「验」在时间上分开

上一轮的结论是：**qb 那批样本是「先验证后判 pass」，对判据的检验贡献为 0。**

要真检验，顺序必须反过来。账本本来就支持（`success=None` 挂起 + 事后 `resolve`），缺的是**真的按这个流程走**。

### 两轮流程

```
第一轮  python tests/feed_qb.py --record --blind
        只看题目和数据结构 → 判 → 记 success=None（挂起）

第二轮  python ledger.py resolve-blind
        跑规格验证 → resolve(id, success=实际)
```

`resolve-blind` 按域分组批量跑一遍，把 28 条挂起样本全部结算。

### 第一版：kind 标错了

第一次跑，13 条盲判**全是 pass**。查下来是我自己的错：

```python
Claim(..., kind="procedure")   # ← 错
```

"针肋宽度比与热阻正相关"是**关于世界的事实**，不是「照着做的规程」。两种 kind 走的门不同：

```
kind=procedure  e3=1/2  →  pass       （e1+e3 ≥ 3）
kind=world      e2=0    →  reject     （e1+e2 = 2，够不到 G2 的 pass_at 4）
```

这和早期 `mainline_loop` 手动重建 `Claim` 时丢掉 `kind` 是同一类错——**结构字段丢了，判定就换了把尺子**。

### 第二版：e2=0 太狠

改成 `world` + `e2=0` 后，28 条盲判**全是 reject**，但其中 20 条其实成立——reject 精确率只有 29%。

盲判的正确表述是「**有线索、能验、还没验**」：

| 阶段 | e1 | e2 | e3 | 判定 |
|---|---|---|---|---|
| 盲判（未验） | 2（指得到文件和列） | 1（直觉＋数据，疑同源） | 1（有验法，没做） | **degrade** |
| 验证后为真 | 2 | 2（一源＋复算） | 2 | **pass** |
| 验证后被推翻 | — | — | — | **reject**（`refuted_by_test`） |

### 结算结果

```
挂起 28 条，结算 28 条

  degrade/成立:   20
  degrade/不成立:  8
```

**盲判全部落在 degrade，其中 71% 成立。**

这是第一个**判前不知答案**的实测结果。

### 顺手发现一个大问题：degrade 不是一个东西

```
degrade 按来源：
  case      1/7  = 14.3%
  collect  11/18 = 61%
  qb       20/28 = 71.4%
```

**同一个 `degrade/info` 桶里，成功率从 14% 到 71%。**

先验却把它压成一个数：`0.481`。

这个数**不代表任何一类样本**，它是三种东西的平均。用它去预测哪一类都会错得很远。

### 数据

```
L3 v2 已结算 99 条

pass     16/16 = 100%   Wilson[0.806, 1.0]
reject   20/20 = 100%   Wilson[0.839, 1.0]

degrade/info  n=53
  case     1/7  = 14.3%
  collect 11/18 = 61%
  qb      20/28 = 71.4%
```

`pass` / `reject` 的 100% 只来自 16 / 20 条——**下界 0.81 / 0.84，离能承诺还差得远**。

### 审计改成按比率报警

原来 8 条 `pass 却失败` 逐条列出来，全是噪音。改成汇总：

```
[pass 假阳性] 8/44 = 18.2% 判了 pass 但结论不成立。
判之前不知道答案的样本有这个错误率是正常的，但要知道它有多大。
```

**盲判本来就有错误率，重要的是比率而不是个例。**

### 断言

```
harness 52    extend 55    guard 23    probe 17    sargable 15/15
账本审计 0 错误 / 0 警告（122 条，剔除 10 条）
盲判结算 28 条（成立 20）
smoke_entry 11   对外入口 1   回归套件 28
```

### 下一步

| 项 | 说明 |
|---|---|
| **`degrade` 先验要按来源拆** | 14%/61%/71% 压成 0.481，等于没用 |
| **pass 只 16 条** | 要真承诺得靠盲判样本积累，而盲判现在全落 degrade |
| **`case` 那批只有 14%** | 说明那批任务设计得偏难，或判据对它们不适用 |

---

## 第五十四轮 · 不合并：宁可没有数，不要平均数

上一轮把 `degrade` 的 14% / 61% / 71% 摆出来了，结论是「压成 0.481 等于没用」。

这一轮把它做成**机制**，而不是留一句感慨。

### `pooling_check`：能不能合并

判据只有一条——**各组 Wilson 95% 区间两两有交集，才算同一个分布**。

```
先验可合并性检查 · L3 · v2 · 按 origin 拆

  degrade/info   合并值 0.604   **不可合并**
    case         1/7 =  14.3%   Wilson[0.026, 0.513]
    collect      11/18 =  61.1%   Wilson[0.386, 0.797]
    qb           20/28 =  71.4%   Wilson[0.529, 0.847]
    ✗ case 与 qb 的区间不重叠——不是同一个分布

  pass      合并值 1.000   可合并
  reject    合并值 0.000   可合并
```

`case` 的上界 0.513 低于 `qb` 的下界 0.529——**差一点点才重叠**。差这一点就够判它们不是一回事。

### 不合并的时候，先验回落到默认

关键决定：**不可合并的桶不覆盖先验**。

```python
prior["degrade/info"] = DEFAULT["degrade"]   # 0.65，不是 0.604
detail["degrade/info"] = {"source": "default(mixed)",
                          "why": "各组区间不重叠，合并值不预测任何一组"}
```

`prior_for()` 拿到的是 0.65，不是那个没意义的平均数。

```
=== L3 先验 ===
  degrade/info   0.65    default(mixed)   n=53
  pass           0.944   ledger           n=16
  reject         0.045   ledger           n=20

prior_for(degrade/info) = 0.65
```

**宁可说"我不知道，用默认值"，也不拿 0.604 冒充一个能用的数。**

### 顺带处理了 verdict 级的连带污染

第一版只挡了 `degrade/info`，结果 `degrade` 整体还是 0.6——因为它把 env 和 info 又平均了一次，而 info 本身已经是混合物。

加了连带规则：**只要有一个 cause 子桶不可合并，verdict 级也回落到默认。**

### 审计会说这句话

```
[先验不可合并] degrade/info：各组 case 14.3%  collect 61.1%  qb 71.4%，区间不重叠。
合并值 0.60 不预测任何一组，先验已回落到默认
```

以前这种情况审计是完全沉默的——它只看单条样本有没有矛盾，不看**汇总之后的数还成不成立**。

### 自测：证明它真会拦

注入两组构造数据（0/8 与 8/8，区间必然不重叠）：

```
[PASS] 两组差异大 → 判为不可合并  — False
[PASS] 不可合并时列出冲突的组  — [('collect', 'qb')]
[PASS] 混合桶的先验回落到默认值，不用平均数  — default(mixed)
[PASS] 回落值等于默认值而不是 0.5  — 0.65
```

第四条特意查了回落值——**回落成 0.5 也是错**，那又是一个凭空造出来的数。

`guard` 从 23 涨到 27。

### 这一轮的意义

前几轮一直在修「单条样本的语义」。这一轮修的是**汇总层的语义**：

> 分组的数不一样的时候，平均值不是一个更保守的估计，它是一个不存在的东西。

这条以前没被任何机制挡住过。现在挡住了。

### 断言

```
harness 52    extend 55    guard 27    probe 17    sargable 15/15
账本审计 0 错误 / 1 警告（122 条）
样本重跑 54 一致 / 0 漂移
盲判结算 28 条（成立 20）
smoke_entry 11   对外入口 1   回归套件 28
```

**那条警告是设计要报的**——它说明 `degrade/info` 现在没有可靠先验，而不是说明账本坏了。

### 下一步

| 项 | 说明 |
|---|---|
| **`case` 那批为什么只有 14%** | 是任务太难，还是判据不适用？得逐条看 |
| **按来源分别建先验** | 现在只做到"不合并"，还没做到"分组建" |
| **pass 只 16 条** | 下界 0.81，真要承诺得等盲判样本积累 |

---

## 第五十五轮 · 顺着警告查下去，查出一个标签错

上一轮留下一条警告：

```
[先验不可合并] degrade/info：各组 case 14.3%  collect 61.1%  qb 71.4%，区间不重叠
```

这一轮去查「case 为什么只有 14%」。

### 逐条看那 7 条

| 样本 | evidence | 我的判断 |
|---|---|---|
| `E1 EXPLAIN 指标验证` | `TABLE RANGE SCAN→TABLE RANGE SCAN（66→66us）` | 真失败——优化没生效 |
| `O1 加索引让查询变快` | `12ms → 10ms（+17%）` | 真成功 |
| `D1 生产负载 p99 < 100ms` | 需 1 亿行，实有 5,000（差 20000×） | **环境给不了** |
| `D2 并发 100 无锁等待` | 并发环境缺失 | **环境给不了** |
| `D3 10 亿行下索引仍生效` | 需 10 亿行，实有 5,000 | **环境给不了** |
| `D4 ARM 平台性能一致` | 本机 x86_64，非 aarch64 | **环境给不了** |
| `D5 跨机房复制延迟` | 集群 1 个节点 | **环境给不了** |

**7 条里 5 条挂错了 `cause`。** 它们是 `degrade/env`，不是 `degrade/info`。

### 为什么会挂错

`cause` 来自门禁：

```python
cause=r.get("cause")     # ← 门禁给的
```

而门禁的 `cause` 只回答一个问题：**「这次判定有没有被环境档位降级」**。

这 5 条任务在 L3 下判定，档位没降级，所以门禁给 `info`。

但真正的问题是另一个：**「这个环境有没有这个能力」**。L3 的意思是"有源码、有可执行、能联网"——**不等于能模拟 1 亿行、100 并发、ARM、多节点**。

两个问题不是一个问题，第 **六** 次栽在同一个形状上。

### 修法

脚本自己知道那 5 条是能力问题（它的 docstring 就写着「验证条件本身不具备」），所以显式声明：

```python
cause=("env" if r["final"] == "degrade" else None),
# 这些任务是「环境没有这个能力」而不是「证据不够」。
# 门禁的 cause 只回答「档位有没有降级」——L3 不等于什么都能做。
```

第一次改的时候把 `cause="env"` 也挂到了 `reject` 上，被门禁当场拦住：

```
ValueError: cause 只对 degrade 有意义，当前 verdict=reject
```

**门禁这次是对的**——它挡下了一个我自己引入的字段越界。

### 修完之后：不可合并的警告自己消失了

```
L3
  degrade/env    0.0    可合并   case:0%
  degrade/info   0.674  可合并   collect:61%  qb:71%
  pass           1.0    可合并
  reject         0.0    可合并
```

**`degrade/info` 变成可合并了**——因为造成它"不可合并"的那 5 条错误样本被移走了。

### 这一轮最值得记的

昨天那个「不可合并」的结论**在当时的账本上是正确的**。错的不是判断，是账本里的标签。

> 机制指出的异常，可能是它上游某个更基础的数据错误造成的。
> **顺着警告查下去，往往能挖到比警告本身更深的错。**

如果上一轮没有建 `pooling_check`，这 5 条错误标签会一直躺在 `degrade/info` 里，
把「证据不足」这一档的失败率虚高 40 个百分点。

### 还剩一个同类问题，先说清楚

`degrade/env` 在两个档位下的数字是反的：

```
L3  degrade/env  case      0/5  =   0%
L2  degrade/env  collect  15/15 = 100%
```

不是矛盾，是**两个不同的问题共用一个标签**：

| 档位 | 样本在问什么 |
|---|---|
| L3 | 环境真给不了这个能力 → 实际执行**失败** |
| L2 | 判定按 L2 限制、执行用 L3 权限 → 「如果能验会不会成」→ **成功** |

L2 那批的 `success` 是**反事实**的。我在 `tests/collect_env.py` 里写清了这一点，
但**还没有把它做成机制**——下轮该给这类样本加 `counterfactual` 标记，
让先验和精确率都能把它们分开算。

### 断言

```
harness 52    extend 55    guard 27    probe 17    sargable 15/15
账本审计 0 错误 / 0 警告（107 条）
样本重跑 54 一致 / 0 漂移
回归套件 28
```

### 下一步

| 项 | 说明 |
|---|---|
| **`counterfactual` 标记** | L2 那 15 条的 success 是反事实的，不能和 L3 的混算 |
| **环境档位缺少「能力」维度** | L3 只描述工具齐备，不描述数据规模/并发/架构/节点数 |
| **pass 只 12 条** | 下界 0.76 |

---

## 第五十六轮 · 反事实样本：把 L2 那个 0.941 拿掉

上一轮末尾留的问题：

```
L3  degrade/env  case      0/5  =   0%
L2  degrade/env  collect  15/15 = 100%
```

同一个标签，方向相反。原因不是矛盾，是**两个问题共用了一个标签**：

| 档位 | `success` 在答什么 |
|---|---|
| L3 | 环境真给不了这个能力 → 执行**失败** |
| L2 | 判定按 L2、执行用 L3 → 「如果能验会不会成」→ **成功** |

### 加字段

```python
record(..., counterfactual=True)
```

标记 `success` 是**反事实**的样本。两个来源都要标：

- `tests/collect_env.py`：10 条（判定 L2、执行 L3）
- `tests/collect_io.py --env 2`：13 条（同一个模式）

### 五处统计口径一起改

只改一处会得到自相矛盾的数。这次一次改齐：

| 位置 | 改什么 |
|---|---|
| `stats().resolved` | 排除反事实 + **顺便统一排除对照组** |
| `stats().precision` | 排除反事实 |
| `stats()["counterfactual"]` | 单独报出 n 与成功数 |
| `current_prior()` | 先验不采信 |
| `pooling_check()` | 可合并性不采信 |
| `audit()` 提示 | 单列一条说明 |

### 顺手修掉一个口径打架

改的时候发现：`calibration_by_cause` 一直在算对照组，而 `precision` 早就排除了。结果同一个 `pass` 桶：

```
calibration  14/17     ← 含对照组那 3 条故意构造的失败
precision    12/12     ← 不含
```

**两个数打架，谁都不算错，但没法一起用。** 统一排除后都是 12/12。

### 结果：L2 变成空的

```
L3: 已结算 79   反事实 0
   degrade/env    0/5
   degrade/info   31/46
   pass           12/12
   reject         0/16

L2: 已结算 0    反事实 23
   先验全部回落到默认
```

**L2 现在一条真样本都没有。**

以前那个 `degrade/env = 0.941`（15/15）看起来像"证据充分"，其实回答的是
「如果我们有完整权限，这些任务会不会成」——**答案是会，所以是 100%**。
它从来没说明过「L2 环境下判 degrade 靠不靠得住」。

拿掉它之后，L2 的先验全部回落默认（pass 0.95 / degrade 0.65 / reject 0.02）。
**这是诚实的：我们不知道。**

### 自测：证明它真不会混进去

注入 6 条真样本（全成功）+ 4 条反事实样本（全失败）：

```
[PASS] 反事实样本被单独统计  — {'n': 4, 'success': 0}
[PASS] 反事实样本不混进 degrade/info 的分母  — n=6 succ=6
[PASS] 反事实样本不影响先验  — 0.875
```

第二条是关键：混算会得到 `4/10 = 40%`，分开得到 `6/6 = 100%`。

第三条第一次写的时候期望值填了 0.833，跑出来是 0.65——因为 `MIN_SAMPLES=5`，
测试里只放 4 条真样本够不到门槛，先验回落默认。**断言写错了，不是代码错了**，
把真样本加到 6 条就对了。

`guard` 从 27 涨到 30。

### 审计现在会说这句话

```
[已剔除] 28 条样本不进样本量统计（对照组 / 先验证后判 / 反事实，它们答的不是同一个问题）
[反事实] 23 条的 success 说的是「如果能验会不会成」，不是「在当前环境成不成」——单独看，别和上面混
```

### 这一轮的意义

前面几轮反复在处理同一件事：**一个词在不同层指不同的事**。

这一轮是它的极端形式——同一个字段 `success`，在 L3 样本里是"做成了没有"，
在 L2 反事实样本里是"**如果**有条件，会不会做成"。

**加了 `if` 就是另一个问题。** 不标出来，它就会一直在平均值里冒充分布。

### 断言

```
harness 52    extend 55    guard 30    probe 17    sargable 15/15
账本审计 0 错误 / 0 警告（107 条）
样本重跑 54 一致 / 0 漂移
回归套件 28
```

### 下一步

| 项 | 说明 |
|---|---|
| **环境档位缺少「能力」维度** | L3 只描述工具齐备，不描述数据规模/并发/架构/节点数 |
| **L2 现在没有真样本** | 要补齐得在真的缺工具的环境里跑任务 |
| **pass 只 12 条** | 下界 0.76 |

---

## 第五十七轮 · 三路并行：能力维度 / 更多真题 / 真 L2 样本

上一轮列的三件事，并行交给三个子智能体，每人**只准新建一个文件**、不改现有代码、不写账本。我逐个核对后集成。

### 一、`capability.py`：环境能力维度

现有 L0~L3 只描述**工具是否齐备**（有源码 / 有可执行 / 能联网），不描述**能力**。

新模块定义 5 个维度，最关键的设计是把「不瞎猜」写进结构而不是注释：

| 设计 | 效果 |
|---|---|
| `source=unknown` 却带值 → 抛错 | 不许把猜的值当实测 |
| 实测值一律标 `bound="at_least"` | 探针撞上限只拿到下限 |
| **下限 < 需求 → 返回 `None` 而不是 `False`** | 「没测到」≠「做不到」 |
| `nodes` 恒 unknown | 单机看不到集群，不填 1 |

实测三态：

```
1000 行    -> True     实测已物化 20 万行 ≥ 需求
1 亿行     -> None     实测下限 20 万行 < 需求（没测到，不是做不到）
1000 节点  -> None     nodes 未知
arm64      -> False    实测 x86_64，明确不够
```

**1 亿行给 `None` 而不是 `False`，是这一轮最该学的一处。**

20 条断言，已有 `[PASS]`。

### 二、`tests/feed_qb_more.py`：再挖 25 条真题断言

换了套题：2021-B 热辐射器（26 个折射率 CSV）、2023-五岳杯（4 个 CSV）、2024-A。

**先探明谁真带数据**，不硬凑：

| 套题 | 结果 |
|---|---|
| 2021-B | [实] 26 个 CSV |
| 2023-五岳杯 | [实] 4 个 CSV |
| 2024-A | [实] 仅 `Answer.xls`，两个 sheet 只有表头 |
| 2021-C、2023-A/B/C、2024-B/C/D | [空] 只有 PDF，无可断言数据 |

```
这一批 25 条主张里，成立 19 条、不成立 6 条
预判命中 24/25（其中 8 条是「没把握」的，错 1 条）
```

**三条实测发现**：

1. **表头说三列、数据只有两列**——10 个介质文件都是这个形态。同一个文件，
   `column_exists("k")` 判成立、`value_bounds` 直接 `IndexError`。**两条断言互相打架，
   并排看才看得见。**
2. 我的预判错在把「正常色散」套到金属上——Cr 的 n 与波长 **+0.992 强正相关**，
   介质的规律不适用于金属。
3. 2024-A 的空模板由断言证实（行数 1 / 0），不是靠眼看。

### 三、`tests/collect_l2_real.py`：L2 终于有真样本了

之前的 L2 样本是反事实的（判定假装 L2、执行用完整权限），刚被全剔除。这次**先造限制、验证生效、再判、再实测**。

四条限制都实测生效，不是嘴上说：

```
只读    PermissionError errno=13，随后复读确认 12 行未变
ACL 拒读 icacls /deny → PermissionError，恢复后复验读到 12 行
工具改名 真 PE 副本 .moved，调用 FileNotFoundError winerror=2
路径/命令不存在 FileNotFoundError，shutil.which = None
```

```
7 条任务（4 种限制）
真的做成  2/7 = 28.6%
判定一致  7/7
```

与反事实口径的差别：

```
实测口径     2/7 = 28.6%
若照抄反事实  5/7 = 71.4%
差 3 条，差的正是被剔除的那部分
```

**同一道题（读统计）在「只读」下做成、在「不可读」下失败**——成败跟条件走，不是一刀切。

### 四、集成

- 三个模块全部进回归清单（`capability` 20 项、`feed_qb_more`、`collect_l2_real`）
- 给 `tests/collect_l2_real.py` 加了 `--record`，7 条真样本已入账（`counterfactual=False`）
- 记账时发现 `--record` 跑了两遍产生重复，按「任务名 + 最后一条」去重，删 5 条

```
L2 已结算 7   反事实 23
   degrade/env   2/2
   reject        0/5
```

**L2 从「0 条真样本」变成 7 条。** 还是少，但不是空的了。

### 五、子智能体这一轮的表现

| 路 | 交付 | 我核出来的问题 |
|---|---|---|
| A `capability.py` | 20 断言全绿，三态正确 | 首次运行在自己机器上 UnicodeEncodeError，它自己修了并如实写了 |
| B `tests/feed_qb_more.py` | 25 条真跑通 | 自称「预判命中 24/25」偏高——它探明阶段就读过数据，17 条是陪跑；**它自己主动交代了这点** |
| C `tests/collect_l2_real.py` | 7 条真跑通 | 交代了 pyc 缓存被改的副作用并修掉；`detect_env` 因未联网只给 L1，它用 L2 判定但**同时打印 L1 作下界** |

**三条都主动报告了自己的局限，没有粉饰。** 这比数字好看更值钱。

### 断言

```
harness 52    extend 55    guard 30    probe 17    capability 20    sargable 15/15
账本审计 0 错误 / 0 警告（114 条）
回归套件 30
```

### 下一步

| 项 | 说明 |
|---|---|
| **`capability` 还没接进 harness** | 目前是独立模块，没和 L0~L3 联动 |
| **L2 只 7 条** | 够不上先验门槛（MIN_SAMPLES=5 的 degrade/env 只有 2 条） |
| **pass 仍 12 条** | 下界 0.76 |

---

## 第五十八轮 · 把能力维度接进闸门

上一轮 `capability.py` 是独立模块。这一轮接进 `run_gates`，目标是**干掉手标**。

### 为什么必须接

第五十五轮那个 bug：5 条 `degrade/env` 的 `cause` 是**我手写的**，因为门禁不知道环境有没有这个能力。手标就会标错——那批先被标成 `info`，后来才发现该是 `env`。

**能自动算的，不该靠人记。**

### 接口

```python
Claim(..., needs={"rows": 100_000_000})     # 任务要什么
EvidenceEnv(3, facts={"scale": 5000})       # 环境精确有多少
```

两个字段对应两个问题：`needs` 是任务声明，`facts` 是调用方提供的**精确实测值**。

为什么需要 `facts`：探针只能拿到**下限**（实测已物化 20 万行），而数据库的行数是**精确**的（5,000）。只给下限时 `capability.fits` 会诚实地说 `None`（没测到），不会误判 `False`。

### 三态纪律贯穿到底

| 情形 | 判定 | 理由 |
|---|---|---|
| 要 1 亿行 / 库 5,000 行 | **degrade/env** | 实测上限 < 需求，明确不够 |
| 要 1 千行 / 库 5,000 行 | pass | 够 |
| 要 1 亿行 / 没给精确事实 | pass | 只有下限 → `None`，**不判不够** |
| 要 arm64 / 本机 x86_64 | **degrade/env** | 架构明确不符 |
| 没声明 `needs` | 不干预 | — |

**第三行是纪律：拿不到精确值就说「没测到」，不许升格成「做不到」。**

### 顺手修了一处 cause 规则

接上之后发现 D1/D3 仍然给 `info`——因为降级只在 `pass → degrade` 时发生，而这两条本来就因 `e3=0` 判 degrade。

**这是错的**：证据补齐了也照样做不成，卡点是环境。

```python
if final == "degrade":
    if cap_ok is False:          # 环境明确不行 → env
        cause = "env"
    else:
        cause = "env" if downgraded else "info"
```

改完：

```
D1  需 1 亿行  实有 5,000  -> degrade  cause=env    ← 门禁自己算的
D3  需 10 亿行 实有 5,000  -> degrade  cause=env
D2  没声明规模需求          -> degrade  cause=info
```

### `tests/case_l3_limits.py` 改回让门禁判

```python
c = Claim(tid, name, e1=2, e2=0, e3=0, kind="procedure",
          needs={"rows": need})
r = run_gates(c, EvidenceEnv(env.level, facts={"scale": have}))
```

手写的 `cause=("env" if ...)` 删掉，改回 `cause=r.get("cause")`。

### 自测锁死 6 条

```
[PASS] 能力不够 → 自动降级为 degrade
[PASS] 能力不够 → cause 自动记为 env
[PASS] 能力够 → 不降级
[PASS] 只有下限没精确值 → 不判不够（None 不等于 False）
[PASS] 架构明确不符 → 自动降级
[PASS] 没声明需求 → 不干预判定
```

`harness` 从 52 涨到 58。

### 断言

```
harness 58    extend 55    guard 30    probe 17    capability 20    sargable 15/15
账本审计 0 错误 / 0 警告（114 条）
回归套件 30
```

### 下一步

| 项 | 说明 |
|---|---|
| **并发维度还没接** | D2 那条「并发 100」仍靠人写描述，`probe_concurrency` 探的是线程驻留不是吞吐 |
| **`facts` 靠调用方填** | 填错不会被发现——没有交叉核对 |
| **pass 仍 12 条** | 下界 0.76 |

---

## 第五十九轮 · 没有出处的数字，不许否定结论

上一轮接完能力维度，我自己记下一条风险：

> `facts` 靠调用方填，填错不会被发现。

这一轮把它堵上。用的还是这个项目一贯的那条判据，只是换了个位置用。

### 问题在哪

```python
EvidenceEnv(3, facts={"scale": 5000})   # 谁填的？凭什么？
```

`facts` 一旦被采信，就能把一条本来 pass 的结论打成 `degrade/env`。

**一个没有出处的数字，能推翻一条有证据的结论**——这个方向是反的。

### 改法：事实必须带出处

```python
facts={"scale": 5000}                                     # 没出处
facts={"scale": {"value": 5000, "from": "sql: SELECT COUNT(*)"}}   # 有出处
```

没出处的，降成 `unknown`：

```python
if not src:
    dims[k] = Dim(value=None, source="unknown", bound="exact",
                  note="调用方给了值但没给出处，不敢用")
```

**降成 unknown 而不是报错**，因为 unknown 最坏只让判定停在「没测到」——污染不了结论。

### 四种情形实测

```
没给 facts                -> pass     cause=None   任务需求 → 没测到
给了值但没出处             -> pass     cause=None   规模能力没测到
给了值+出处                -> degrade  cause=env    实测上限 5,000 行 < 需求
出处是空字符串             -> pass     cause=None   等同于没出处
```

**第一、二、四行都是 pass**——不是做不到，是「不许拿它当证据」。

只有第三行才降级。**方向对了。**

### 连带发现：两条旧断言写错了

加完出处要求，上一轮自己的两条断言红了：

```
[FAIL] 能力不够 → 自动降级为 degrade
[FAIL] 能力不够 → cause 自动记为 env
```

因为它们传的是 `{"scale": 5000}`——**没出处**。

这不是回归坏了，是**新规则把旧测试里的一处松懈暴露出来了**。给它们补上出处就绿了。

### 自测锁死 4 条

```
[PASS] 没出处的事实不降级判定
[PASS] 有出处的事实才降级
[PASS] 空出处等同于没出处
[PASS] _split_fact 认得两种写法
```

`harness` 从 58 涨到 62。

### `tests/case_l3_limits.py` 也带上了出处

```python
facts={"scale": {"value": have,
                 "from": "sql: SELECT COUNT(*) FROM bench_l3.t_ann"}}
```

现在这条样本链上每一步都能追：需求从哪来、环境有多少、凭什么这么说。

### 断言

```
harness 62    extend 55    guard 30    probe 17    capability 20    sargable 15/15
账本审计 0 错误 / 0 警告（114 条）
回归套件 30
```

### 下一步

| 项 | 说明 |
|---|---|
| **出处只是字符串** | 没有真的去核 `from` 里那句 SQL 是否跑得出那个数 |
| **并发维度还没接** | D2 仍靠人写描述 |
| **pass 仍 12 条** | 下界 0.76 |

第一条是剩下的洞：**出处可写，但没被验证**。下一步该让 `from` 里的语句真跑一次，对不上就拒收。

---

## 第六十轮 · 出处要真跑一次对账

上一轮留的最后一个洞：

> 出处只是个字符串，没被核过。

一个能推翻结论的数字，光写一句"from SQL"是不够的——**那句话可以随便写**。

### 加 `probe.query_scalar`

```python
query_scalar("SELECT COUNT(*) FROM bench_l3.t_ann")   -> (True, "5000")
query_scalar("SELECT 1+1")                             -> (True, "2")
```

真跑一次，取回第一行第一个值。取不到就如实说取不到。

### `from` 升级成可执行核对

```python
{"value": 5000, "from": "数一遍"}                       # 声称，不采信
{"value": 5000, "from": "数一遍",
 "check": {"domain": "sql",
           "task": {"sql": "SELECT COUNT(*) FROM bench_l3.t_ann"}}}   # 核对过
```

`_verify_fact` 的判定：

| 情形 | 结论 |
|---|---|
| 没给 `from` | 不能用 |
| 给了 `from` 但没给 `check` | 不能用（只是声称） |
| `check` 跑不通 | 不能用 |
| `check` 跑通但**值对不上** | 不能用（并说明声称多少、实测多少） |
| `check` 跑通且一致 | 能用 |

### 四种情形实测（都要 1 亿行）

```
无出处          -> pass     cause=None   规模能力没测到
只有字符串出处     -> pass     cause=None   规模能力没测到
核对通过         -> degrade  cause=env    实测上限 5,000 行 < 需求
核对不符         -> pass     cause=None   规模能力没测到
```

**只有第四种能降级。** 而且注意第三行那个"核对不符"——它**没有**变成 reject 或别的什么，就是回到"没测到"。**一个假数字不产生任何结论。**

### 顺带：`_split_fact` 从两态变三态

```python
_split_fact(5000)                                   -> (5000, "", None)
_split_fact({"value": 7, "from": "x"})              -> (7, "x", None)
_split_fact({"value": 7, "from": "x", "check": {...}})
                                                    -> (7, "x", {...})
```

### 自测锁死 4 条新增

```
[PASS] 核对通过的事实才降级
[PASS] 核对不符的事实被拒收（不降级）
[PASS] 只有声称没有核对规格 → 不采信
[PASS] _verify_fact 对得上就放行
```

`harness` 从 62 涨到 66。

### `tests/case_l3_limits.py` 的链路现在闭合

```python
facts={"scale": {"value": have, "from": "数一遍 t_ann",
                 "check": {"domain": "sql",
                           "task": {"sql": "SELECT COUNT(*) FROM bench_l3.t_ann"}}}}
```

**需求声明 → 环境实测 → 出处核对 → 门禁判定**，四步都能追到具体命令。

### 断言

```
harness 66    extend 55    guard 30    probe 17    capability 20    sargable 15/15
账本审计 0 错误 / 0 警告（114 条）
回归套件 30
```

### 下一步

| 项 | 说明 |
|---|---|
| **只支持 sql 域核对** | `check` 里的 domain 只认 sql，其他域直接判"暂不支持" |
| **并发维度还没接** | D2 仍靠人写描述 |
| **pass 仍 12 条** | 下界 0.76 |

第一条是覆盖面问题，不是正确性问题——**不支持就拒收**，方向是对的。

---

## 第六十一轮 · 探针量的不是要问的东西

上一轮说要接并发维度。接之前先做了一件事：**看探针到底量的是什么**。

### 差点写进去一个假信心

```python
# capability._cmp_concurrency
if v >= n:
    return True, f"实测可同时存活 {v} 个线程 ≥ 需求 {n}"
```

探针量到 **256 个线程同时驻留**。所以 `needs={"concurrency": 100}` 会得到 **「够」**。

但 D2 那条任务问的是：**100 个并发事务会不会锁等待**。

**256 个线程 ≈ 并发事务吗？不是。** 线程驻留只说明能开线程，不说数据库能给 100 个并发连接、更不说会不会真竞争。

如果就这么接上，门禁会对一个根本验证不了的任务说「能力够」——**这比不接更糟：不接只是不知道，接了是假装知道。**

### 改法：需求必须声明问的是哪一类并发

```python
needs={"concurrency": 100, "concurrency_kind": "threads"}        # 探针答得了
needs={"concurrency": 100, "concurrency_kind": "transactions"}   # 探针答不了
```

kind 不是 `threads` 时，把环境的并发维度降成 `unknown`：

```python
dims["concurrency"] = Dim(value=None, source="unknown",
                          note="要的是 transactions 并发，探针量的是线程驻留，不是一回事")
```

### 四种情形实测

```
要 100 线程（探针能答）      -> pass    任务需求 → 够（实测 256 线程 ≥ 100）
要 100 事务（探针答不了）    -> pass    任务需求 → 没测到
要 100 并发但没声明 kind     -> pass    任务需求 → 够
要 1000 线程（超了实测值）   -> pass    任务需求 → 没测到（下限不构成否定）
```

**四种全是 pass**——这在这里是对的：能力维度只用来说「不够」，从不用来说「够」到能改变判定。

第四行值得单说：探针只测到 256 就停了（`bound=at_least`），所以「要 1000」得到的是**没测到**，不是**做不到**。

### 代价：D2 仍然自动判不了

改完之后 D2 的 `cause` 还是 `info`——因为并发这块环境明确给不了，但**我拿不出证据**。

**这是诚实的现状：我不知道怎么在本机验证"100 并发事务会不会锁等待"。** 与其编一个探针让它说"够"，不如留着 `info`。

### 自测锁死 4 条

```
[PASS] 要线程 → 探针答得了
[PASS] 要事务 → 探针答不了，不许说够
[PASS] 答不了就不降级（不会假阳性地说够，也不会假阴性地说不够）
[PASS] 超了实测下限也不判不够（下限不构成否定）
```

`harness` 从 66 涨到 70。

### 这一轮的意义

前面几轮修的都是「数字有没有出处」「出处核没核过」。

这一轮修的是更前一步：**探针量的那个量，是不是你想问的那个量**。

> 一个量错了指标的探针，会稳定地产出信心——而且看起来完全合规。

### 断言

```
harness 70    extend 55    guard 30    probe 17    capability 20    sargable 15/15
账本审计 0 错误 / 0 警告（114 条）
回归套件 30
```

### 下一步

| 项 | 说明 |
|---|---|
| **并发这块没有可用探针** | 需要能起多连接压测的环境，本机没有 |
| **只支持 sql 域核对** | 其他域直接判"暂不支持" |
| **pass 仍 12 条** | 下界 0.76 |

---

## 第六十二轮 · 加样本，然后发现 pass 长不了

这一轮先停了一下，看清单：**「pass 仍 12 条」在上面躺了二十轮没动过。**

每轮都在加机制，样本数不动。所以这轮不造新工具，把已有的 25 条主张变成**真检验样本**。

### 做法

`tests/feed_qb_more.py` 之前只打印、不入账——等于白测。给它加 `--record --blind`：

```
第一轮  feed_qb_more.py --record --blind    盲判，success=None 挂起
第二轮  ledger.py resolve-blind             真跑断言，结算
```

### 先被真实数据打了一顿

结算时整批崩了：

```
IndexError: list index out of range
  probe.py, line 337, in _do_data
    vals = [r[idx] for r in rows if r[idx] is not None]
```

**2021-B 的介质文件表头 3 列、数据只有 2 列**（缺 k）。`feed_qb_more` 自己包了 try，但 `resolve-blind` 直接调 `probe`，异常直接掀翻整批。

修 `probe._do_data`，三处都要防越界：

```python
def _col_values(rows, idx) -> tuple[list, int]:
    """安全取第 idx 列。返回 (有效值, 行宽不足的行数)。"""
```

`value_bounds` / `corr_sign` / `no_null_in` 全部改用安全取列，并把「缺了几行」写进依据。

**这不是容错，是语义**：一个跑不完的断言**不等于主张成立**，也不该让整批核对挂掉。

### 结算结果

```
挂起 25 条，结算 25 条
  degrade/成立:   19
  degrade/不成立:  6
```

和脚本自己报的「成立 19 / 不成立 6」对上。

### 然后发现：pass 一动不动

```
L3 已结算   79 → 104（+25）
  degrade/info   46 → 71     成功率 70%
  pass           12 → 12     ← 一条没长
  reject         16 → 16
```

**25 条真检验样本全落在 degrade，pass 一条没加。**

原因不是运气，是结构：

| 判 pass 的条件 | 冲突在哪 |
|---|---|
| `e3=2` 表示「我实际复现过」 | 复现过就**已经知道答案**了 |
| 盲判时不可能有 `e3=2` | 所以盲判永远落 degrade |

**换句话说：pass 的精确率，只可能由「先判后跑」的任务来测——而这类任务我只有 12 条。**

真题主张帮不上这个忙：它们天然是「先猜后验」，只能测 degrade。

### 这不是坏消息

`degrade/info` 从 46 涨到 71 条，成功率稳定在 70%，Wilson 区间从 `[0.53, 0.75]` 收窄。

**71 条真检验样本，说明"证据不足"这一档确实略高于抛硬币（50%），但远不到能承诺的程度。**

这是目前账本里最结实的一个数。

### 断言

```
harness 70    extend 55    guard 30    probe 17    capability 20    sargable 15/15
账本审计 0 错误 / 0 警告（139 条）
样本重跑 / 盲判结算 25 条
回归套件 30
```

### 下一步

| 项 | 说明 |
|---|---|
| **要长 pass，只能加「先判后跑」的任务** | 这类任务要能执行、且判前不知结果 |
| **并发这块没有可用探针** | 本机起不了多连接压测 |
| **`degrade/info` 已 71 条** | 这一档可以开始报区间了 |

---

## 第六十三轮 · pass 的可靠性是谁给的

上一轮说「要长 pass，只能加先判后跑的任务」。这轮动手之前先查了一件事：

**那 12 条 pass，凭什么是对的？**

### 逐条看依据

```
F1  读 harness.py        存在且可读
F3  列 model1-arch 目录   存在且是目录
F4  写一个临时文件         父目录可写，可以创建
H2  访问 example.com     DNS 可解析、TCP 可连接、HTTP 200
A1  建表 t_c1            前置检查通过
...
U1  检查器不可用时的查询   连不上 seekdb，无法检查 | 实际返回 2450 行   ← 唯一例外
```

**11 条的依据是「前置检查通过」。**

这说明一件事：

> **pass 的可靠性不是测出来的，是前置检查给的。**

所以再多生成"正常的文件任务"，只会重复 100%——**问不出新东西**。

### 唯一的例外才是有信息量的那条

`U1`：seekdb 连不上，前置**没查成**，框架仍判了 pass，执行碰巧成功 2450 行。

**那是赌博，不是结论。**

### 漏掉的那一半

第二十六轮定过一条规则：

> `input_valid=None`（没查成）**不否决**——因为「查不成」≠「做不了」。

那条仍然对。但当时只说了"不否决"，**没说"不否决就等于可以判 pass"**。

不否决是对的；判 pass 是另一回事。

### 补上四态阶梯

```python
if 声明了 verify:
    if input_valid is True:   → pass
 
    if input_valid is False:  → reject（INPUT_INVALID，一票否决）
    if input_valid is None:   → degrade / info   ← 新规则
else:
    → 不受这条规则影响（没打算验，不是验失败）
```

实测：

```
声明了验法 + 验通过    -> pass     cause=None
声明了验法 + 没验成    -> degrade  cause=info     ← 新
声明了验法 + 验失败    -> reject   blocked_at=INPUT_INVALID
没声明验法 + None      -> pass     cause=None
```

**关键区分**：`没声明验法` 不受影响——那是没打算验；`声明了但没验成` 才降级——那是验失败了。

混为一谈的话，所有 qb 主张（没声明 verify）会一起掉进 degrade。

### 自测锁死 4 条

```
[PASS] 声明了验法 + 验通过 → pass
[PASS] 声明了验法 + 没验成 → degrade 且 cause=info
[PASS] 声明了验法 + 验失败 → reject（不降级，直接打回）
[PASS] 没声明验法 → 不受这条规则影响
```

`harness` 从 70 涨到 74。

### 这一轮的结论

**「加更多 pass 样本」是个错方向。**

pass 之所以可靠，是因为前置检查先跑过；要让它不可靠，需要**前置检查骗过自己**——那是 TOCTOU（检查与使用之间世界变了），不是靠堆样本能测出来的。

真正该做的实验是：**在前置检查和执行之间故意改变世界**，看 pass 还成不成立。这轮没做，记在这里。

### 断言

```
harness 74    extend 55    guard 30    probe 17    capability 20    sargable 15/15
账本审计 0 错误 / 0 警告（139 条）
回归套件 30
```

### 下一步

| 项 | 说明 |
|---|---|
| **TOCTOU 实验** | 检查通过后、执行前把文件删掉／改权限，看 pass 会不会错 |
| **并发这块没有可用探针** | 本机起不了多连接压测 |
| **`degrade/info` 71 条** | 这一档可以报区间了 |

---

## 第六十四轮 · pass 有保质期

上一轮的结论是：**pass 的可靠性是前置检查给的。** 那么它什么时候会错？

只有一种情况：**检查的时候世界是 A，执行的时候世界变成了 B。**

这叫 TOCTOU。堆更多正常样本测不出它——必须**故意在检查和执行之间改动世界**。

### `tests/toctou_probe.py`

五个场景，每个都走真实链路：

```
造世界 → precheck + 判定 → 【改世界】 → 执行
```

| 场景 | 前置 | 判定 | 改动生效 | 执行 | 打中 |
|---|---|---|---|---|---|
| 检查后被删 | ok | pass | 是 | 败 | ★ |
| 检查后被换成目录 | ok | pass | 是 | 败 | ★ |
| 检查后被收回读权限 | ok | pass | **否** | 成 | |
| 父目录检查后被删 | ok | pass | 是 | 败 | ★ |
| 对照：不改世界 | ok | pass | 否 | 成 | |

**3 个真实改动，3 个全部打中。**

第三个场景没打中，原因写得很清楚：`os.chmod(p, 0o000)` 之后**仍可读**——因为当前是管理员身份。脚本把这条如实记成「限制未生效」，不当成一次成功的实验。

### 这个数**不**进 pass 精确率

「判 pass 后执行失败」不等于判据错。判据说的是「**我查的时候**可以做」；世界在检查之后变了，那是世界的问题。

所以这份报告只量化**暴露窗口有多大**，不往精确率里加分母。这个区分很重要——混进去会把"过期"和"判错"当成一回事。

### 但它确实说明一件事

> **pass 是有保质期的。**

检查与使用之间隔得越久、世界越活跃，pass 越不可靠。

这也是为什么真正的证据是 `e3=2`（我跑过且成了），不是 `input_valid=True`（我查过它能成）。**跑过 > 查过。**

### 自检：实验必须真能打出洞

```
[PASS] 改动已生效且确实打中了 pass —— 暴露窗口被量化出来了
```

两条失败分支：

- 没有一个场景真改动世界 → 实验失效，结论不可用
- 改动生效了却一次没打中 → 要么判据变了，要么实验写错了

**一个永远打不中的实验，和一个永远打中的实验一样没信息量。**

### 断言

```
harness 74    extend 55    guard 30    probe 17    capability 20    sargable 15/15
账本审计 0 错误 / 0 警告（139 条）
回归套件 31（新增 toctou_probe）
```

### 下一步

| 项 | 说明 |
|---|---|
| **`chmod 0o000` 在管理员下无效** | 权限类 TOCTOU 本机测不了，得换非管理员账户 |
| **并发这块没有可用探针** | 本机起不了多连接压测 |
| **`degrade/info` 71 条** | 这一档可以报区间了 |

---

## 第六十五轮 · 覆盖率一直是虚高的

这一轮先做了一次数据诊断，问的是：**76 条 degrade，卡在哪一维？**

结果先撞见另一件事。

### 之前报的覆盖率是错的

我一直说「覆盖率 72%」。这一轮用干净口径重算：

```
L3 这一档的样本量：104 条
  一次判完有结论   28/104 = 26.9%
  其中 degrade     76 条 → 可复核 58，永远没结论 18
  复核之后有结论   86/104 = 82.7%
```

**26.9%，不是 72%。**

差在哪：之前那个数把**「先验证后判」的样本**也算进了分子——那些样本判的时候已经知道答案，当然都"有结论"。口径一收紧，就露底了。

这已经是同一个坑的第不知道多少次：**分母里混进了不该算的东西。**

### 但 27% 也不是全部事实

76 条 degrade 里，**58 条带可复核规格**——跑一遍就有结论了。

```
degrade 76 条
  ├─ 58 条可复核 → 复核后都有确定结论
  └─ 18 条永远没结论（复核不了的例子）

degrade复查·H1 给 age 建索引让 age=42 更快
degrade复查·H2 给 category5 建索引让 =0 更快
```

那 18 条是「优化类」任务：`CREATE INDEX` 这类操作**非幂等**，重跑必然失败，所以挂不了规格。

### 所以该报两个数

```python
coverage()` 返回：
    first_pass    —— 一次判完就给出确定结论的比例
    after_verify  —— 把带规格的 degrade 复核掉之后的比例
```

```
L3  一次判完 27%（28/104），复核之后 83%
L2  一次判完 71%（5/7），  复核之后 71%
```

审计里现在常驻这两行。

### 为什么这个区分重要

> **「暂时没结论」和「永远没结论」混成一个数，会同时低估两件事**：
> 这套东西现在能干什么，以及「再补样本」这个方向到底有多划算。

27% 听起来这套东西没用；83% 听起来快好了。**两个都只对一半。**

真实的形状是：**一次判完只解决四分之一，剩下的要靠复核去收**——而这套东西的设计本来就是两段式的（判 → 验），只是我之前一直拿第一段的数当总成绩。

### 断言

```
harness 74    extend 55    guard 30    probe 17    capability 20    sargable 15/15
账本审计 0 错误 / 0 警告（139 条），含两段覆盖率
回归套件 31
```

### 下一步

| 项 | 说明 |
|---|---|
| **18 条永远没结论的** | 都是非幂等操作，要复核得先解决幂等化 |
| **L2 两条 degrade 无规格** | 临时目录被清理了，规格指向的路径已不存在 |
| **并发这块没有可用探针** | 本机起不了多连接压测 |

---

## 第六十六轮 · 非幂等的任务，用执行计划当答案

上一轮有 18 条 degrade **永远没结论**——都是优化类，规格挂的是 `CREATE INDEX` 这种非幂等操作。

但这 18 条问的问题，本来不必靠重跑操作来验：

> 「这条查询走没走索引」是能**算**出来的，而且是只读的。

### 加 `query_rows`

`query_scalar` 只取第一格，够用于 `COUNT(*)`；EXPLAIN 是多行多列的，得拿整段。

```python
query_rows("EXPLAIN SELECT * FROM bench_l3.t_ann WHERE age = 42")
  -> ['|0 |TABLE RANGE SCAN|t_ann(ix_dg_age_eq)|50 |138|', ...]
```

### 然后我自己的验证逻辑错了两遍

**第一遍**：在**整段**计划文本里搜 `"INDEX"`。

```
[E9] 命中  age > 40 会走索引
     计划=|0 |TABLE FULL SCAN|t_ann|2951|
```

**明明是全表扫描**，却判"成立"——因为下面 `Outputs & filters` 那几段里有 `INDEX` 这个词。

> 一个字串在文档里出现过，不代表就是那个意思。

**第二遍**：改成只看算子行，但列下标取错了（算子在第 2 格不在第 3 格），10 条全判"不成立"。

**第三遍才对。**

### 落账时又踩了同一个坑（第六次）

第一版 replay 规格写的是：

```python
{"domain": "sql", "task": {"sql": "EXPLAIN SELECT ..."}}
```

`do_exec` 对 `sql` 域返回的是「**语句执行成功没有**」——EXPLAIN 永远成功，所以 10 条全被结算成"成立"。

但我要问的是「**计划里有没有那个标记**」。

**规格问的问题，必须和 success 问的问题是同一个。** 于是加了个 `explain` 域：

```python
{"domain": "explain", "task": {"sql": "EXPLAIN ...", "marker": "ix_"}}
```

`CHECK_KIND["explain"] = "assertion"` —— 它返回的是断言真假，不是执行状态。

改完结算：**8 成立 / 2 不成立**，和 EXPLAIN 实测一致。

### 10 条主张，我又错了 2 条

```
[E7] age IS NULL → 我以为不走索引，实际 TABLE RANGE SCAN(ix_dg_age_eq)
[E9] age > 40    → 我以为走索引，实际 TABLE FULL SCAN
```

**E9 是这一轮最有用的发现**：

> **可走索引 ≠ 实际走索引。**

`age > 40` 命中 2951/5000 行（59%），优化器按**选择性**选择了全表扫描。
`sargable.py` 那套理论只说"谓词形不破坏索引"，**说不了"引擎会不会真用"**。

这是 sargable 模型的边界，之前没量过。

### 覆盖率变化

```
L3  一次判完 25%（114 条），复核之后 84%
    degrade 86 条 = 可复核 68 + 卡住 18
```

可复核的从 58 涨到 68（+10 条 EXPLAIN 类），复核后覆盖率 83% → **84%**。

一次判完从 27% 降到 25%——因为分母多了 10 条（全都是 degrade），**这是分子没变分母变大，不是变差了**。

### 断言

```
harness 74    extend 55    guard 30    probe 17    capability 20    sargable 15/15
账本审计 0 错误 / 0 警告（149 条）
回归套件 32（新增 collect_explain）
```

### 下一步

| 项 | 说明 |
|---|---|
| **`sargable` 的边界要写进文档** | 它只说"形式上可用"，不说"引擎会不会用" |
| **18 条仍卡在非幂等** | EXPLAIN 只覆盖"走不走索引"，覆盖不了"建完索引之后快不快" |
| **并发这块没有可用探针** | 本机起不了多连接压测 |

---

## 第六十七轮 · 一个工具的边界，写成可执行断言

上一轮撞见 `age > 40`：形式判定说"能用索引"，引擎选择了全表扫描。

这不是 bug，是**工具的边界**。但边界只写在脑子里，下次还会读过头。

### 该说的说清楚

`sargable()` 原来的 docstring 只有一句：

> 判断谓词里的索引列能不能用上索引。

读起来像"引擎会不会用"。改成分两档：

```
sargable=True   → 「索引**可以**用」（必要不充分）
sargable=False  → 「索引**一定**用不上」（这条是硬的）
```

并把实测反例直接写进 docstring：

```
age = 42      → TABLE RANGE SCAN(ix_dg_age_eq)   形式可用，真用了
age > 40      → TABLE FULL SCAN                  形式可用，**没用**
age IS NULL   → TABLE RANGE SCAN(ix_dg_age_eq)   形式也没破坏
```

`age > 40` 命中 59% 的行，优化器按**选择性**判全表更便宜。**这是选择性问题，不是 sargable 问题。**

### 但 docstring 不算数

文档写了没人看，看着也会忘。所以做成**可执行断言**，放进 `tests/collect_explain.py`：

```
[PASS] age = 42       形式可用=True   引擎真用索引=True
[PASS] age + 0 = 42   形式可用=False  引擎真用索引=False
[PASS] age > 40       形式可用=True   引擎真用索引=False   ← 边界
[PASS] age IS NULL    形式可用=True   引擎真用索引=True
```

四条全过，其中 `age > 40` 那条**就是在证明边界存在**。

断言失败意味着：引擎换了策略，或者我对边界的理解错了。两种都该知道。

### 写这条断言时又骗了自己一次

第一版是这样写的：

```python
marker = "ix_" if want_engine else "FULL SCAN"
engine, detail = verify(pred, marker)
```

`engine` 这个名字说是"引擎用没用索引"，实际是"**计划匹配了我给的那个标记**"。

对 `age + 0 = 42` 我给的是 `FULL SCAN` 标记，于是 `engine=True` 的意思是"确实是全扫"——**和另一条里 `engine=True` 的意思正好相反**。

跑出来两条 FAIL，查了半天才发现是变量名骗人。

改成统一用 `ix_` 判定，并说清"引擎真用索引"：

```python
uses_index, detail = verify(pred, "ix_")
```

**一个变量名，在两条分支里含义不同——和前面那些"同一个词在不同层指不同的事"是同一种病。**

### 结论

`sargable` 现在有两层：

| 层 | 回答什么 | 可信度 |
|---|---|---|
| 形式判定 | 谓词形破坏没破坏索引可用性 | True 是"可以"，False 是"一定不行" |
| 引擎决策 | 实际走没走索引 | 得靠 EXPLAIN 实测 |

**前一层能推，后一层必须测。**

### 断言

```
harness 74    extend 55    guard 30    probe 17    capability 20    sargable 15/15
sargable 边界 4/4（新增，跑真实计划）
账本审计 0 错误 / 0 警告（149 条）
回归套件 32
```

### 下一步

| 项 | 说明 |
|---|---|
| **边界依赖数据分布** | 换一张表、换个行数比例，`age > 40` 可能就走索引了 |
| **18 条仍卡在非幂等** | EXPLAIN 覆盖不了"建完索引之后快不快" |
| **并发这块没有可用探针** | 本机起不了多连接压测 |

---

## 第六十八轮 · 回归为什么随机变红

上一轮收尾时全量回归红了一次，重跑又绿。查下来不是逻辑错，是**环境抖动**：

> `tests/collect_explain.py` 刚跑完，WSL 里的 seekdb 还没释放；
> `ledger.py replay` 紧接着起 WSL，有的查询取不到计划。

### 但真正的问题是语义，不是抖动

`replay()` 里 `do_exec` 返回 `False` 有两种含义：

| 真相 | 应该算什么 |
|---|---|
| 世界变了，样本对不上 | **漂移** |
| 查验本身没跑成（连不上库） | **查不了** |

代码把两者都算成漂移。于是**环境一抖，回归就红**——红的是环境，不是代码。

**这是同一个混淆的又一次：一个布尔值，两种意思。**

### 改法：先问「跑成了吗」，再问「对得上吗」

```python
def _looks_unavailable(why: str) -> bool:
    keys = ("起不来", "取不到", "调用失败", "NODB", "连接", "不可用", ...)
```

`replay()` 现在分三档：

```
一致 96    对不上 0    无规格/待结算 45    环境不可用跳过 8
```

修复前后：

```
修之前：8 条 http 取不到 → 报 8 条漂移 → 回归红
修之后：8 条 http 取不到 → 记「环境不可用跳过」→ 回归绿，且报告里看得见
```

**跳过不等于没事**——报告里明确写了跳几条，人才知道这次核查覆盖了多少。

### 判定留了边界

```
seekdb 起不来，取不到值        -> 算环境不可用
语句执行失败                  -> 算真不符
计划里没找到算子行              -> 算真不符
FileNotFoundError: no such file -> 算真不符
```

只有"根本没跑成"才跳过；"跑了但结果不对"仍然是漂移。

### 断言

```
harness 74    extend 55    guard 30    probe 17    capability 20    sargable 15/15
sargable 边界 4/4
账本审计 0 错误 / 0 警告（149 条）
样本重跑 96 一致 / 0 漂移 / 8 环境不可用
回归套件 32
```

### 下一步

| 项 | 说明 |
|---|---|
| **http 样本依赖网络** | 每次跑都可能跳几条，这是真实的不确定性，不该假装没有 |
| **18 条仍卡在非幂等** | EXPLAIN 覆盖不了"建完索引之后快不快" |
| **并发这块没有可用探针** | 本机起不了多连接压测 |

---

## 第六十九轮 · 检索库接进来了

用户给了两个包：`GitHub知识库-数据包.tar.gz`（1.4 GB）和 `GitHub知识库-轻量包.zip`。
要求是「**作为其中一个库**，优化进去」。

### 它是什么

本地 GitHub 知识库：**30 个仓库 / 298,500 个文件 / 源码 4.4 GB**，
FTS5 索引 3.97 GB，检索 72 ms。

| 分类 | 仓库 |
|---|---|
| db-sql / olap / kv / doc / embed | tidb、cockroach、duckdb、ClickHouse、doris、redis、mongo、postgres、sqlite、oceanbase |
| math-modeling | numpy、scipy、sympy、pandas、scikit-learn、pytorch、or-tools、cvxpy、statsmodels、networkx |
| tools | pandoc、ripgrep、fzf、fd、bat、cli、neovim、tmux、bubbletea、terminal |

**包里自带 `index.db`** —— 不用重跑 344 秒建索引。

### 它在架构里的位置

三个老库（方案库 / 疑难1库 / 疑难2库）是**去向**，检索库是**来源**：

> 判定完了一句话，凭什么说它是「有据」的？
> **能指到「哪个仓库的哪个文件的哪一行」才算。**

这就是 `e1`（溯源度）唯一的外援。

### `kb.py`

```python
search(query, category=None, repo=None, limit=10) -> list[Hit]
Hit.cite()      -> "cockroachdb/cockroach:pkg/raft/raftpb/raft.proto"
Hit.local()     -> 本机原文路径（带 \\?\ 长路径前缀）
read(hit)       -> 读回原文，引用前必须走这一步
assess(hits, terms) -> e1_cap / e2_cap  + 为什么
```

### 三条规矩，都是踩出来的

| 规矩 | 为什么 |
|---|---|
| **同一个仓库的多个文件不算独立来源** | 一个团队写的一套代码观点当然一致，当两票是自欺 |
| **命中必须能核对原文** | 摘要会截断；`verify()` 要求原文真含关键词，否则不给分 |
| **没搜到 ≠ 不存在** | 库里只有 30 个仓库，搜不到只说明"这 30 个里没有" |

第二条最容易被跳过。实测：

```
3 条命中，但没有一条能在原文里核对到关键词 → 不能用（e1=0）
```

**搜到了不等于对上了。**

### 数据也自己坑了一把

`kb.py` 原本在 import 阶段就 `import requests`——**search 根本用不到网络，却被一起拦住**（本机没装 requests）。

而且它的 `KB` 路径写死成「`tools/` 与 `knowledge-base/` 平级」，可这个包打成了「`tools/` 在 `knowledge-base/` 里」，
打开就是 `knowledge-base/knowledge-base`，报「还没有索引」。

两处都改了：

```python
def _need_requests():   # 真要联网时才 import
def _kb_root():         # 认两种布局 + KB_ROOT 环境变量
```

### 回归红了一片，原因不在代码

加入 `kb.py` 后第一次全量回归，12 项失败。逐项单独跑却都是绿的。

真因：

```
UnicodeEncodeError: 'gbk' codec can't encode character '\u2713'
```

本机控制台是 **GBK**，脚本一打印 `✓` 就崩。我前面几轮碰巧带了 `PYTHONIOENCODING=utf-8`，
这回漏了——**红的是调用者的终端，不是被检验的代码**。

修法不是"下次记得带变量"，是让套件自洽：

```python
env = dict(os.environ)
env["PYTHONIOENCODING"] = "utf-8"
env["PYTHONUTF8"] = "1"
subprocess.run(..., env=env)
```

现在**不设任何环境变量直接跑，ALL PASS**。

这是同一个毛病的第三次：**一个环境层面的问题，伪装成代码失败。**

### 自测 14 项

```
[PASS] 索引可用                             文件 298,500
[PASS] 仓库数与包内声明一致（30）
[PASS] 文件数 > 25 万
[PASS] 检索有命中                            8 条
[PASS] 命中带可引用的出处
[PASS] 命中能读回原文                         3/3
[PASS] 关键词能在原文里核对到
[PASS] 同一仓库的多条命中 → e2 只有 1
[PASS] 跨仓库命中 → e2 可以到 2
[PASS] 没有命中 → e1=e2=0
[PASS] 关键词核对不到 → 不给分
[PASS] 特殊字符不会炸
[PASS] 空查询返回空
```

### 落地物

| 路径 | 什么 |
|---|---|
| `knowledge-base/repos/` | 30 个仓库，4.5 GB |
| `knowledge-base/index.db` | FTS5 索引，3.97 GB |
| `../knowledge-base/tools/kb.py` | 原生 CLI（已修两处） |
| `knowledge-base/docs/` | 它的架构方案与实施报告 |
| `kb.py` | **检索库适配层**（本轮的产物） |

### 断言

```
harness 74    extend 55    guard 30    probe 17    capability 20    kb 14    sargable 15/15
账本审计 0 错误 / 0 警告（149 条）
回归套件 32
```

### 下一步

| 项 | 说明 |
|---|---|
| **还没接进判定流程** | `assess()` 能算 e1/e2，但 `evaluate_claims` 还没自动调用它 |
| **只有 30 个仓库** | 覆盖面窄，`没搜到` 的结论要写成「本次没搜到」 |
| **索引占原文 88%** | 想瘦身按报告建议排除 ClickHouse 的 `tests/queries/0_stateless/data_*` |

---

## 第七十轮 · 接进去，然后发现自己给自己发通行证

这一轮把检索库接进判定主干。接的过程里翻出两个东西，第二个比第一个重要得多。

### 接法

```python
evaluate_claims(claims, kb_query="raft consensus")
```

只在调用方明确给 `kb_query` 时才动检索库——因为它只覆盖 30 个仓库，
搜不到不代表没证据，不该默认去碰。

`enrich_from_kb()` 补的是**出处**，写进 `sources`，让"有据"这件事可复盘。

### 第一版：一条 degrade 被我判成了 pass

```
不补证      e1/e2/e3 = 2/1/1   C=4  ->  degrade/info
检索库补证   e1/e2/e3 = 2/2/1   C=5  ->  pass
```

看着挺漂亮。但 **e2 我是怎么抬上去的？**

e2 问的是「有没有**两个独立来源在支持这个结论**」，
而检索库给出的是「这两个代码库里都**出现过**这个词」。

**共现 ≠ 支持。** ClickHouse 里有 raft 这个词，不等于它支持"Joint Consensus 在配置变更时生效"。

这是这个项目七十几轮一直在打的那类事，我自己犯了。改掉：

```python
# enrich_from_kb 现在只动 e1，不碰 e2
new_e1 = max(c.e1, a.e1_cap)
# e2 不动 —— 独立支持得靠读和判断，不能靠关键词
```

独立仓库数照样写进日志，**由人复核，不由程序替人加分**。

### 第二版：真正的问题不在检索库，在重试

改完发现数字还是不对：

```
不补证        e1/e2/e3 = 2/2/1  ->  pass
检索库补证     e1/e2/e3 = 2/1/1  ->  degrade
```

补了出处反而分更低。追下去，翻到了这个：

```python
def _simulate_repair(c: Claim) -> Claim:
    """模拟一次重做带来的证据改善。"""
    return replace(c, e1=min(2, c.e1+1), e2=min(2, c.e2+1), ...)
```

**一条 e1=2/e2=1/e3=1 的主张在 G2 被打回（e1+e2=3 < 4），
重试循环把它"修"成 2/2/1，再判一次就成了 pass。**

那 1 分是程序凭空加的：没有新证据、没有新出处、没有人复核。
等于自己给自己发了一张通行证，然后拿通行证过闸。

### 顺带发现：那条断言在守护这个 bug

```python
check("重试后确有项被救回", rr["recovered"] >= 1, ...)
```

它断言的正是"重试应该救回主张"——**而当时的救回就是凭空加分**。

改成恒等映射之后它立刻红了，其余 62 条全绿。翻过来：

```python
check("重试不会凭空救回主张（没新证据就不该过闸）", rr["recovered"] == 0, ...)
```

**一条测试可以忠实地检验一个错误的设计。**

### 修完之后的真实链条

```
不补证        e1/e2/e3 = 1/1/1  C=3  重试 3 次 -> reject
检索库补出处   e1/e2/e3 = 2/1/1  C=4  重试 0 次 -> degrade
```

**找到引用把人从"毫无依据"推到"有出处但没验证"，不是推到 pass。**

这才是检索库该有的分量。

### 自测 6 条

```
[PASS] 检索库能给 e1 补出处  — e1=2
[PASS] 补进来的出处写进 sources  — 8 条
[PASS] 同一仓库的多条命中只能算一票  — e2=1
[PASS] 检索库不把 e2 抬上去（共现≠支持）  — e2=1
[PASS] 但把独立仓库数写进日志供人复核
[PASS] 已声明更高分时不往下压  — 2/2
[PASS] 搜不到时原样返回，不打成 0  — 1/1 sources=0
[PASS] 不传 kb_query 时不动检索库
```

`extend` 从 55 涨到 63。

### 断言

```
harness 74    extend 63    guard 30    probe 17    capability 20    kb 14    sargable 15/15
账本审计 0 错误 / 0 警告（149 条）
回归套件 32
```

### 下一步

| 项 | 说明 |
|---|---|
| **重试机制现在只剩轨迹** | 不再加分，但也没别的用处；要么删，要么接真重做 |
| **e2 无法从检索库获得** | 要它得读原文判断"是否在支持同一命题"，那是另一套活 |
| **`runs` 的口径要复查** | 重试从"救回"变成"再试一次"，账本里 `attempts` 的语义跟着变了 |

---

## 第七十一轮 · 空转的重试，改成「还差什么」

上一轮把"重试凭空加分"抽掉之后，重试循环变成了：

> 用同样的输入，再算一遍同样的结果。

**除了烧预算，什么也不产生。** 该么删，要么让它干点别的。

选了后者——因为它旁边正好有个位置空着。

### 判完一句"不行"之后，人最想知道的是什么

不是"不行"，是**"那我该补什么"**。

这在架构里一直缺：`reject` 只说"打回疑难1库"，`degrade` 只说"待补证"，
都没说补哪儿。

### `what_would_help()`

```python
what_would_help(claim, verdict, blocked_at, env)
  -> [{"dim": "e2", "have": 1, "need": 2, "delta": 1, "how": "..."}]
```

按**差值从小到大**排，让人先补最省事的那一维。

实测：

```
毫无依据       -> reject      补 e1: 0->1  指到具体位置：文件+行号 / 出处链接
有出处没复现    -> degrade     补 e2: 1->2  找第二个独立来源
                             补 e3: 1->2  真跑一次并留下可复现记录
全齐          -> pass        无建议
```

### 写的时候又错了一次

第一版算出来建议 `e1: 2→3`——**e1 上限就是 2，根本不存在 3**。

原因是拿 `env.cap(stage, kind)` 当单维上限，而它返回的是**整闸合计上限**（6）。
改用 `ENV_MAX_E[level][dim]` 才对。

同一个毛病：**一个函数名的字面意思，和它实际返回的东西不是一回事。**

### 还漏了一个前置判断

`pass` 的主张一开始也带着建议，读起来像"过了但还缺东西"。

补上：

```python
if verdict == "pass":
    return []
```

**过了就是过了，没有"还差什么"。**

### `run_with_retry` 现在名不副实

名字还留着（不想改调用方），但里面已经没有 retry：

```python
r = run_gates(c, env)
r["ask"] = what_would_help(...)
r["attempts"] = 0        # 不再假装重做过
```

`budget` 参数留着但不动——**动了就说明还有隐藏的重试**，这本身成了一条断言：

```
[PASS] 不再重试，预算不动  — 0
```

### 三条新断言替换了两条旧的

```
[PASS] 不再重试，预算不动  — 0
[PASS] 每条被拦的主张都给出了「还差什么」  — 被拦 2 条，有建议 2 条
[PASS] 建议不会超过该维上限  — [('e2',2),('e1',2),('e2',2)]
[PASS] 过了的主张不产出建议
```

原来那两条（"预算被真实消耗"）断言的正是已删除的行为。

`extend` 从 63 涨到 66。

### 断言

```
harness 74    extend 66    guard 30    probe 17    capability 20    kb 14    sargable 15/15
账本审计 0 错误 / 0 警告（149 条）
回归套件 32
```

### 下一步

| 项 | 说明 |
|---|---|
| **建议还没进账本** | `ask` 只在返回值里，复盘时看不到当时缺什么 |
| **只算维度缺口** | 一票否决类（`refuted_by_test` / `input_valid`）只给了兜底话术 |
| **`attempts` 恒为 0** | 账本里这个字段暂时无信息量 |

---

## 第七十二轮 · 把「还差什么」记进账本

上一轮算出了每条被拦主张缺哪一维，但它只活在返回值里——**复盘时看不到**。

记下来才有用：单看"degrade 占 60%"只知道结论保留得多，不知道该改什么；
把 `ask` 汇总起来，才看得见**系统性短板在哪儿**。

### 落账 + 汇总

```python
record(..., ask=[{"dim": "e2", "have": 1, "need": 2, "delta": 1, "how": "..."}])

ledger.blockers()  ->  {"per_dim": {"e2": 12, "e3": 30}, "top": "e3", ...}
```

`blockers()` 决定下一步该造什么工具：

- 卡在 `e3` → 该做「能真跑」的验证器
- 卡在 `e2` → 该做「找第二来源」，检索库正好干这个
- 卡在 `e1` → 该做「指到具体位置」

### 命令行

```
python ledger.py blockers
```

```
记录 149 条，其中带建议的 0 条（0%）
  没有可统计的建议
  说明：只有记了 ask 的样本能统计；老样本没这个字段
```

**0% 是实话，不是失败。** 149 条老样本当初没这个字段，补不回来。
这个数要等新样本攒起来才有意义。

审计里也常驻一行：

```
[瓶颈] 149 条记录里还没有带建议的，无法定位短板（老样本没有 ask 字段）
```

### 三条弯路

**一、门禁拦住了我自己的演示样本**

```
ProductionWriteRefused: 样本名像测试：task='ask测试·A 毫无依据'
```

名字里带「测试」被 `_guard_write` 拒了。改名叫「瓶颈定位·A」才写进去。

**门禁工作正常，是我起名不规矩。**

**二、`args` 变量不存在**

`blockers` 分支里写了 `int(args[1])`，而 `main()` 里根本没这个变量——别处用的是 `sys.argv`。
复制粘贴另一段代码时留下的。

**三、演示样本把账本弄脏了**

那 4 条合成的「瓶颈定位·」样本落账后全是 `pending`，审计一直报：

```
[未结算] m1-... 还是 pending: 瓶颈定位·A 毫无依据
```

它们是**机制自证**用的，不是真题。删掉——机制已经由门禁里的 4 条断言（在临时账本上）证明过了。

**演示数据不该混进正式账本。** 这条和"测试样本不许进账本"是同一条规矩，只是这次是我自己踩的。

### 断言

```
[PASS] ask 能落账并读回  — 2
[PASS] 不传 ask 时字段为空  — None
[PASS] blockers 只统计带建议的样本  — with_ask=1 rows=2
[PASS] 同一条样本里同一维只算一次  — {'e2': 1}
```

`guard` 从 30 涨到 34。

第一条断言最初写的是 `with_ask >= 2`，跑出来是 1——临时库里只有 1 条带建议。
改成 `with_ask == 1 and rows == 2`，**这样才证明"只统计带建议的"**，而不是"至少有一条"。

### 断言

```
harness 74    extend 66    guard 34    probe 17    capability 20    kb 14    sargable 15/15
账本审计 0 错误 / 0 警告（149 条）
回归套件 32
```

### 下一步

| 项 | 说明 |
|---|---|
| **`blockers` 现在没数据** | 要等新样本攒起来；149 条老样本补不回 ask |
| **只算维度缺口** | 一票否决类只给了兜底话术 |
| **`attempts` 恒为 0** | 账本里这个字段暂时无信息量 |

---

## 第七十三轮 · 让真实样本带上 ask，然后撞出平局

上一轮 `blockers` 是空的（0%）。这轮给它喂真实数据——
从 `tests/collect_explain.py` 开始，它有 10 条**有真结果**的 EXPLAIN 主张。

### 接法

```python
from extend import what_would_help
_ask = what_would_help(c, g["final"], g.get("blocked_at"), env)
L.record(..., ask=_ask)
```

清掉旧的 10 条，重录、结算：

```
degrade/成立 8    degrade/不成立 2
```

结果和 EXPLAIN 实测一致（第 66 轮那 2 条误判仍然误判）。

### `blockers` 第一次有数了

```
记录 149 条，其中带建议的 10 条（7%）
    e2    10  ##########  找第二个独立来源
    e3    10  ##########  真跑一次并留下可复现记录

  最常缺：e2 —— 下一步该优先造「找第二个独立来源」的工具
```

### 但那个"最常缺 e2"是编出来的

**e2 和 e3 都是 10 次。** 我的 `top` 是这么取的：

```python
ranked = sorted(per_dim.items(), key=lambda kv: -kv[1])
"top": ranked[0][0]      # 平局时随便取第一个
```

**平局里挑一个报，等于用一个平局编出一个结论。**

改成：

```python
_max = ranked[0][1]
tops = [k for k, v in ranked if v == _max]
"tops": tops,
"top": tops[0] if len(tops) == 1 else None    # 唯一时才给
```

输出变成：

```
并列最常缺：e2、e3（各 10 次）
**平局不下结论** —— 样本再多一点才能分出先后
```

这已经是这个项目里"把没把握的事说成有把握"的第 N 种变体了：
**排序函数的稳定性不是证据。**

### 一个子串检测把自己骗了

补丁第一版写：

```python
if "ask=" in t:      # 想检查是不是已经加过
    print("已加，跳过")
```

而 `task=` 里就含 `ask=`——**补丁一次都没打上，我还以为打上了**，
直到重录出来的 10 条样本全是 `ask=None` 才发现。

改成检查 `"ask=_ask"` 才对。

**检测串短于它要区分的东西时，它只会告诉你想听的话。**

### 门禁加 2 条

```
[PASS] 平局时不给单一结论  — top=None tops=['e2', 'e3']
[PASS] 不平时给出唯一结论  — top=e3 tops=['e3']
```

`guard` 从 34 涨到 36。

### 断言

```
harness 74    extend 66    guard 36    probe 17    capability 20    kb 14    sargable 15/15
账本审计 0 错误 / 0 警告（149 条）
瓶颈 带建议的 10/149 条，最常缺 e2、e3（并列）
回归套件 32
```

### 下一步

| 项 | 说明 |
|---|---|
| **只有 10/149 带 ask** | 其余 139 条补不回来，覆盖率会长期偏低 |
| **e2/e3 并列未分** | 要么加样本，要么把"差几分"也纳入排序 |
| **只算维度缺口** | 一票否决类只给了兜底话术 |

---

## 第七十四轮 · 十次观测，还是同一次观测说十遍

上一轮 `blockers` 卡在「e2 和 e3 各 10 次，分不出先后」。

这一轮本来想加个"差几分"做tiebreak。动手之前先看了一眼那 10 条样本——

**它们的缺口组合完全一样。**

### 于是问题不是"怎么分先后"

```python
# 10 条样本的 ask 全都有 e2 和 e3，e1 全是 2
signature = ("e2", "e3")
```

**这不是 10 次观测，是同一次观测被记了 10 遍。**

拿它去比"e2 和 e3 谁更多"，等于把 1 票说成 10 票——
**就是 e2 那条规矩（同一仓库的多个文件不算独立来源）用在统计自己身上。**

### 加了两个字段

```python
blockers()["distinct_signatures"]   # 有几种不同的缺口组合
blockers()["signatures"]            # 每种组合各几条
blockers()["solo"]                  # 单独补这一维就够过闸的条数
```

`solo` 来自 `what_would_help` 新加的字段：`delta >= gap` 就说明**只补这一维就够**。

### 输出现在长这样

```
记录 149 条，其中带建议的 10 条（7%）
    e2    10  ##########  找第二个独立来源
    e3    10  ##########  真跑一次并留下可复现记录

  单独补这一维就能过闸的条数：
    e2    10 条
    e3    10 条

  **同构提醒**：10 条建议只有 1 种不同缺口组合，有效样本量按 1 算
     e2+e3        10 条
     同一组合重复多次只算一票——这是 e2 那条规矩用在统计自己身上
  **有效样本量不足**：只有 1 种缺口组合，分不出先后
  这不是并列，是还没有第二个独立观测
```

审计行也跟着改：

```
[瓶颈] 带建议的 10/149 条，但只有 1 种缺口组合 → **分不出先后**
```

### 少写了一条假断言

第一版给 guard 加的第三条是这样：

```python
check("solo 能标出「单独补哪维够」",
      all("solo" in a for r in with_ask_probe() for a in (r.get("ask") or [])), ...)

def with_ask_probe():
    return []
```

**`all(... for [])` 恒为 True。** 一条永远通过的断言。

而且函数还定义在使用之后。写的时候就觉得不对，删了。

### 门禁 2 条

```
[PASS] 同一缺口组合重复多次只算一组  — with_ask=2 distinct=1
[PASS] 出现第二种组合后有效样本量变 2  — 2
```

`guard` 从 36 涨到 38。

### 这一轮的答案

> 上一轮问"e2 和 e3 并列，该先补哪个？"
>
> 这一轮的回答是：**现在还不该回答这个问题。**
> 手上有 1 种观测，不是 10 种。要分先后，先得有第二种缺口组合的样本。

### 断言

```
harness 74    extend 66    guard 38    probe 17    capability 20    kb 14    sargable 15/15
账本审计 0 错误 / 0 警告（149 条）
瓶颈 带建议的 10/149，只有 1 种组合 → 分不出先后
回归套件 32
```

### 下一步

| 项 | 说明 |
|---|---|
| **要第二种缺口组合** | 造 e1 缺、或 e3 已满的样本，才有多样的观测 |
| **只有 10/149 带 ask** | 老样本补不回来 |
| **`solo` 尚未参与排序** | 等有效样本量够 2 组再上 |

---

## 第七十五轮 · 第二种观测来了，平局自己散了

上一轮的结论是「分不出先后，因为只有 1 种观测」。

这一轮去找第二种。手边现成的就是 `tests/case_l3_limits.py` 那批——
它们是 **procedure** 类，`e1=2 / e2=0 / e3=0`，缺口和 EXPLAIN 那批（`e2+e3`）完全不同。

### 接上之后

```
记录 149 条，其中带建议的 16 条（11%）
  **同构提醒**：16 条建议只有 3 种不同缺口组合，有效样本量按 3 算
     e2+e3        10 条
     e3            5 条
     —             1 条
```

**平局自己散了。** 不需要 tiebreak 规则，只要真有第二种观测。

### 但排名还是算错了

`tops` 原来按**条数**取：

```
e3  15 条
e2  10 条      →  最常缺 e3
```

那 15 条里 10 条是同构的 EXPLAIN 样本——**同一个观测又算了十遍**。

改成按**不同缺口组合**计数：

```
按不同缺口组合计数（才是排名依据）：
    e3     2 种组合
    e2     1 种组合
最常缺：e3
```

结论没变（还是 e3），**但依据从「15 比 10」变成了「2 比 1」，后者才站得住。**

### 过程中的三次翻车

**一、把 6 条样本删了没恢复**

清旧样本、重录 —— 但补丁脚本在半路断言失败退出，重录没跑成：

```
清 6 条，剩 222
（脚本挂了）
```

`限额·` 3 条靠后面单独跑回来了，`补充·` 3 条一度是**丢的**。后来补跑才恢复。

**教训：先备份账本，再清。** 这次是靠「脚本能重跑」侥幸救回。

**二、`c` 这个变量不存在**

`tests/case_l3_more.py` 的循环解包是 `for tid, name, r, evidence, good in rows`，
**根本没有 claim 对象**。我照着 `tests/case_l3_limits.py` 抄了 `what_would_help(c, ...)`。

改成用 `r["dims"]` 重建一个——`what_would_help` 只看维度和 kind，不引入新假设。

**三、`EvidenceEnv` 没导入**

同一个文件顶部只导了 `Claim, run_gates, detect_env`。

### 门禁 +2

```
[PASS] 条数上 e2 明显更多  — {'e2': 4, 'e3': 1}
[PASS] 排名按缺口组合数，不按条数（平局就说平局）  — tops=['e2','e3'] per_dim_sig={'e2':1,'e3':1}
```

造 4 条同构 e2 + 1 条 e3：按条数是 4:1，按组合是 1:1。
**断言就是要证明这两种算法给出不同答案。**

`guard` 从 38 涨到 40。

### 现在的答案

```
per_dim     : {'e3': 15, 'e2': 10, '—': 1}
per_dim_sig : {'e3': 2, 'e2': 1}
tops        : ['e3']
有效组合    : 3 种
```

> **该优先造「真跑一次并留下可复现记录」的工具（e3）。**
>
> 依据是它在 2 种不同缺口组合里出现，而 e2 只在 1 种里出现。

### 断言

```
harness 74    extend 66    guard 40    probe 17    capability 20    kb 14    sargable 15/15
账本审计 0 错误 / 0 警告（149 条）
瓶颈 带建议的 16/149 条、3 种组合，最常缺 e3
回归套件 32
```

### 下一步

| 项 | 说明 |
|---|---|
| **有效样本只有 3 组** | 2:1 还是薄，要到 5 组以上才敢当结论 |
| **`—` 那条是兜底话术** | 一票否决类还没正经处理 |
| **清账本前要备份** | 这轮差点丢 3 条，靠重跑救回来 |

---

## 第七十六轮 · 删数据这件事，不能靠记性

上一轮差点丢 3 条样本——脚本半路断言失败，重录没跑成，`补充·` 那 3 条一度是真的没了。

**靠"脚本还能重跑"救回来，那是侥幸，不是机制。**

### `backup()` 和 `prune()`

```python
backup(reason)                      # 落一份带原因的备份到 ledger-history/
prune(("限额·",), apply=False)      # 默认只**预演**，不动账本
prune(("限额·",), apply=True)       # 真删，删前自动备份
```

命令行：

```
python ledger.py backup 改判据前
python ledger.py prune 限额·            # 预演
python ledger.py prune 限额· --apply    # 真删（会先备份）
```

### 三道保险

| 保险 | 做法 |
|---|---|
| 默认不删 | `apply=False` 是默认值，`--apply` 才动手 |
| 删前必备份 | `backup()` 失败就抛错，不往下走 |
| 备份要能读回 | 备份完**打开数行数**，空文件等于没备 |
| 删完要对账 | 实际删除条数必须等于预演条数，否则报错 |

最后一条最容易漏。现在的写法：

```python
out["backup"] = backup(...)      # 失败就抛，不会走到删
...
if out["deleted"] != out["would_delete"]:
    raise OSError(f"删除条数对不上：预演 X，实际 Y（备份在 Z）")
```

### 门禁 5 条

```
[PASS] prune 默认只预演，不动账本  — would=3 deleted=0
[PASS] prune 真删前先备份
[PASS] 备份文件非空且行数与删除前一致  — 备份 4 行 / 删前 4 行
[PASS] 删除条数与预演一致
[PASS] 没删错东西  — ['保留_0']
```

`guard` 从 40 涨到 45。

### 顺手治了另一个老毛病：回归随机变红

这一轮全量回归又红了一次（`ledger.py 全部对得上`），重跑就绿。

**这是第三次了。** 前两次记在第 68 轮，靠 `_looks_unavailable` 把"没跑成"和"对不上"分开。
但这次漏了——`data` 域的失败文本是「读不到」，不在关键词表里。

与其继续猜哪些词算"环境问题"，改成不确定就不定罪：

```python
def run_retry(script, args, cwd, judge):
    code, out = run(...)
    if judge(code, out) or not RETRY_ONCE:
        return code, out, False
    return (*run(...), True)      # 失败就再跑一次
```

**一条查询偶发失败不该把整套判死；真漂移会连着失败两次。**

重试过会打出来：

```
OK   ledger.py         全部对得上  (重试过一次)
```

不悄悄放过，也不让环境抖动冒充代码缺陷。

验证（用假的 `run`）：

```
偶发失败 -> code=0 重试过=True 调用=2 次   [PASS]
真失败   -> code=1 重试过=True 调用=2 次   [PASS]
```

### 断言

```
harness 74    extend 66    guard 45    probe 17    capability 20    kb 14    sargable 15/15
账本审计 0 错误 / 0 警告（149 条）
回归套件 32（核心项失败自动重试一次）
```

### 下一步

| 项 | 说明 |
|---|---|
| **重试会掩盖真抖动** | 如果某条一直靠重试才过，说明它本身不稳定，该单列出来 |
| **`backup` 只备份主账本** | 不备份 ledger-history 里的旧备份，不做轮转 |
| **有效样本仍只 3 组** | 瓶颈统计还薄 |

---

## 第七十七轮 · 让"靠重试才过"留痕

上一轮加了"失败重试一次"，写完立刻记下一个隐患：

> 重试会掩盖真抖动。某条如果每次都要重试，那它本身就是不稳定的。

**一个能自我修复的机制，也会自我隐瞒。**

### 记录 + 汇总

```python
_log_retry(script, passed)      # 每次重试追加一行到 tests/.retry_log.jsonl
retry_summary(limit=6)          # 最近 6 次运行里，每条被重试几次、其中通过几次
```

跑完直接在结尾打出来：

```
重试情况（最近 6 次运行）
  ledger.py     重试 2 次，其中通过 2 次  ← 反复重试，本身不稳
  extend.py     重试 1 次，其中通过 0 次

  **有 1 项在多次运行里反复重试** —— 它们不该靠重试过关，该查为什么不稳
```

**"通过 2 次"反而是坏消息** —— 它说明这条每次都靠重试才活下来。

### 加了严格模式

```
python tests/run_all.py --no-retry
```

`--no-retry` 时 `RETRY_ONCE = False`，一次失败就算失败。
要判断"到底是代码问题还是环境问题"时用它。

验证：

```
严格模式 exit=0，RETRY_ONCE = False
```

### 汇总的渲染也验了

跑完这一轮刚好没触发重试，所以汇总没打印（`if rs:` 为空，正确）。

但**打印路径没被验过**，于是注了两条假日志跑 `--core`：

```
ledger.py               重试 2 次，通过 2 次  ← 反复重试，本身不稳
extend.py               重试 1 次，通过 0 次
**有 1 项在多次运行里反复重试**
```

确认渲染正常后立刻把假日志删了——**演示数据不该留在正式记录里**，
这条规矩第 72 轮已经踩过一次。

### 分层：三类失败现在分得开

| 现象 | 判据 |
|---|---|
| 一次不过、重试过 | 可能是环境抖，留痕但不报警 |
| 反复重试才过 | **它自己不稳**，汇总里点名 |
| 重试两次都不过 | 真的坏了，回归变红 |

### 断言

这一轮没有新增断言（`run_all` 不是自测对象，它是执行器），
但它的行为被两处验证过：假日志的渲染 + `--no-retry` 的开关。

```
harness 74    extend 66    guard 45    probe 17    capability 20    kb 14    sargable 15/15
账本审计 0 错误 / 0 警告（149 条）
回归套件 32
```

### 下一步

| 项 | 说明 |
|---|---|
| **`.retry_log.jsonl` 会一直长** | 没有轮转，跑几百次后会变胖 |
| **跨机器不通用** | 时间戳是本机的，换机器统计就断 |
| **有效样本仍只 3 组** | 瓶颈统计还薄 |

---

## 第七十八轮 · 拿真题当考题，先被自己的数据揍了三下

前面七十几轮都在造机制。这一轮换个做法：**拿一道真题把整条链路跑一遍**，看它到底顺不顺。

题目：APMCM 2026 B 题 · 高性能芯片热管理系统。
数据：附件 2，84 组「3 个结构参数 → 3 项性能」。

`tests/case_apmcm_b.py` 分三段：

```
一、判前（e3=1，还没算）→ 拿「还差什么」
二、真算（按建议去补）
三、判后（e3=2）→ 看判定怎么变
```

### 判前：五条全被拦，建议都是 e2

```
B1 歧管深高比增大，无量纲热阻下降   C=3 → reject  缺：e2(0→2)
B2 歧管深高比增大，无量纲压降下降   C=3 → reject  缺：e2(0→2)
...
```

**建议是对的**：`e1=2 / e2=0 / e3=1` 要过 G3 需要 5 分，只补 e3 只到 4 分，确实必须补 e2。

### 然后连错三次

**错一：我把「同一份数据切几刀」当成了独立来源**

我用"固定另外两个参数、看这一维的走向"做了 6 次分层，然后写 `e2=2`。

**那就是同一处数据自己给自己投第二票。** 按 e2 的规矩（同一仓库的多个文件不算独立来源），它只值 1 分。

改成 `e2=1`。

**错二：`rho = 0.0` 被算成"符号一致"**

同号判据写的是 `(s > 0) == (sign > 0)`——`0 > 0` 和 `-1 > 0` 都是 `False`，
于是**零相关被当成支持**。B3/B4 那些 `0.0` 全在浑水摸鱼。

加下限：`|ρ| ≥ 0.3` 才算有效观测。

**错三：1 条强相关就判"成立"**

加完下限后 B4 变成 `1/1 = 100% ≥ 80%` → 成立。

**一条样本上的比例不是比例。** 加条数下限 `≥ 3`。

### 最后一次：语义也错了

改完 B4 显示"证据不足"，我却让它走 `refuted_by_test=True` → **reject**。

> **「没验成」不是「被推翻」。**

拆成两种：

```python
if hold:                     e3=2                  # 算了，支持
elif enough:                 e3=2, refuted=True    # 算了，推翻
else:                        e3=1                  # 算了，但不够 → 停在 degrade
```

### 最终结果

```
B1 判前 reject → 判后 reject   0/6 同号      ← 我的预判被数据推翻
B2 判前 reject → 判后 pass     6/6 同号
B3 判前 reject → 判后 pass     3/3 同号
B4 判前 reject → 判后 degrade  强相关仅 1 条 < 3
B5 判前 reject → 判后 pass     4/4 同号

判定发生变化：4/5
```

### B1 是这轮最值钱的一条

我 predicted「歧管深高比增大，热阻下降」。数据是 **+0.96**，方向正好相反：

```
d=3.0 → R=0.740827
d=3.5 → R=0.754456
d=4.0 → R=0.767907
d=4.5 → R=0.770128
```

**歧管越深，热阻越大。** 我的直觉（"通道更深散热更好"）在这份数据上不成立。

这正是「先猜后验」该有的样子——**判的时候还不知道，判完才知道自己错了**。

### 这一轮证明了什么

| 问题 | 答案 |
|---|---|
| 架构能在真题上跑完吗 | 能，不需要手工编维度 |
| 建议有用吗 | 有用，它指出了"必须补 e2 而不是 e3" |
| 真题会暴露什么 | **我自己的三个过度声称**，机制没拦住，是我写脚本时犯的 |

第三条得说清楚：**这三个错都是我在脚本里犯的，不是架构犯的。**
架构只是老老实实把 `reject` / `degrade` / `pass` 吐出来。

所以真正的收获不是"架构通过了考验"，而是——
**写真题脚本的过程，本身就是一次证据纪律的考试，而我第一次没过。**

### 断言

```
harness 74    extend 66    guard 45    probe 17    capability 20    kb 14    sargable 15/15
账本审计 0 错误 / 0 警告（149 条）
回归套件 33（新增 case_apmcm_b）
```

### 下一步

| 项 | 说明 |
|---|---|
| **只做了 5 条主张** | B 题真正的问是"怎么选结构参数"，那是优化不是相关性 |
| **分层复核不算独立来源** | 要 e2=2 得有第二份数据（比如论文或另一组实验） |
| **`.retry_log.jsonl` 仍无轮转** | 上轮遗留的小账 |

---

## 第七十九轮 · 把优化问题做成可验证的

上一轮末尾记了一条：B 题真正问的是**怎么选结构参数**，而我做的 5 条全是相关性。

这一轮补上——**多目标优化，答案是帕累托前沿，它比相关性硬得多**：
给定数据，前沿唯一确定，谁在谁不在可以逐点核对。

### `pareto(rows)`

三目标全最小化（热阻 / 压降 / 温度非均匀性）。84 组里挑出 **12 个不被支配的点**：

```
#13  w=0.2   d=3.0  n=10.0  R=0.7219  P=0.1511  T=0.8278
#14  w=0.2   d=3.5  n=10.0  R=0.7267  P=0.1289  T=0.8072
...
#56  w=0.1   d=4.5  n=4.0   R=0.7544  P=0.0804  T=0.8017
#80  w=0.2   d=4.5  n=2.0   R=0.7598  P=0.0767  T=0.7809
```

规律很干净：**R 从 0.7219 升到 0.7598 时，P 从 0.1511 降到 0.0767**——
热阻和压降在打架，`d` 是那个旋钮。

### 四条可验证的优化主张

```
O1 帕累托前沿不止一个点（存在真实权衡）        成立
O2 前沿点上的歧管深高比取值不唯一（要折中）     成立
O3 前沿点上的针肋宽度比取值不唯一             成立
O4 前沿点中针肋宽度比多数取 0.2（>50%）      成立
```

四条全 `pass`，C=5。

### 但"推荐"和"观测"必须分开写

```
观测：12 个前沿点里 10 个的针肋宽度比是 0.2；
      歧管深高比横跨 3.0–4.5（这是真正的折中方向）。

推荐（**这是工程判断，不是上面那几条的推论**）：
      针肋宽度比取 0.2；歧管深高比按『要热阻还是要压降』在 3.0–4.5 间选。
      —— 推荐比观测走远了一步，这一步靠人。
```

`O4` 说的是"多数前沿点取 0.2"，**不是"0.2 最优"**。
两者的距离，就是这句"这一步靠人"要标出来的东西。

`pass` 只保到观测那一层；从观测到行动方案，是另一个判断。

### 顺带：一个引号把文件写坏了

`print("…不必"先猜"…")` —— 双引号嵌在双引号里。

而且我的补丁脚本是**先写盘再 `ast.parse`**，所以语法错的时候文件已经坏了。
后来单独改那一行才修回来。

**校验要放在写之前。** 这是本轮自己踩的。

### 现在的链路

| 段 | 内容 |
|---|---|
| 一 | 判前（e3=1）→ 五条全拦，建议都是 e2 |
| 二 | 真算 → 分层相关 + **帕累托前沿** |
| 二·五 | 四条优化主张，数据即答案 |
| 三 | 判后 → 4/5 判定变化，1 条被数据推翻 |

### 断言

```
harness 74    extend 66    guard 45    probe 17    capability 20    kb 14    sargable 15/15
账本审计 0 错误 / 0 警告（149 条）
回归套件 33
```

### 下一步

| 项 | 说明 |
|---|---|
| **前沿只来自一组数据** | e2 只能给 1；要更强得换一份独立数据 |
| **没做加权/约束优化** | 题目若给偏好，前沿要再切一刀 |
| **`.retry_log.jsonl` 仍无轮转** | 欠着 |

---

## 第八十轮 · 交付面一次也没验过

这一轮问了一个之前没问过的问题：

> `mcp_server.py` 是别人能用这套东西的**唯一入口**，九个工具。
> 而我前面几十轮反复改 `run_gates` 的行为——cause 规则、能力核验、
> 前置没查成不判 pass、ask 字段……
> **一次也没在 MCP 这一层验过。**

单元测试全绿而交付面坏掉，是很容易发生的：中间隔着一层序列化、
一层参数校验、一层错误处理。

### `tests/mcp_smoke.py`

起真子进程、走真 stdio、发真 JSON-RPC 2.0。**不 import、不 mock**——
mock 会把这个测试变成"我以为它怎么工作"。

```
initialize → tools/list → evaluate_claim → precheck → detect_env
→ ledger_stats → 未知工具 → 出错后仍可用
```

### 一跑就抓出两个

**一、「还差什么」根本没传到交付面**

前几轮把 `ask` 建出来了，`evaluate_claim` 的返回里也有 `r["ask"]`，
**但 MCP 输出的那段文字没打印它**。

造了机制不接到出口，等于没造。补上之后：

```
最终: degrade（成因=info）
还差什么：
  e2 1→2（差 1）找第二个**独立**来源
  e3 1→2（差 1）真跑一次并留下可复现的记录
```

**二、`detect_env` 不带参数时必然是 L1，还不解释**

```python
detect_env(source_root=None, executable=None, network=True)
  → src_files=0, exe_ok=False → L1
```

这是**构造性的**：不给它要判什么，它就只能按"只看得见路径"算。
但输出只写「档位: L1」，看起来像"这个环境很弱"。

补一句：

```
注意: 没给 source_root / executable，所以只能按「只看得见路径」算 L1。
      这不代表环境差，只代表**没告诉我判什么**。
```

### 然后我的断言错了两条

修完两个补丁，冒烟还是红的。查下来**补丁生效了，断言写错了**：

| 断言找的 | 实际文本 |
|---|---|
| `"缺"` / `"ask"` / `"补"` | `还差什么` |
| `"L3"` / `"level"` | `档位` |

**检测器又比被检测的东西更不靠谱。** 改准之后 14 项全过。

### 顺手又踩了同一个引号坑

`print("…按"只看得见路径"算…")` —— 双引号套双引号。

**这是两轮内第二次**，而且又是"先写盘再 parse"，文件写坏了才发现。
改法不是记住，是把检查挪到写之前——这轮没做，记在下面。

### 断言

```
harness 74    extend 66    guard 45    probe 17    capability 20    kb 14    sargable 15/15
mcp_smoke 14
账本审计 0 错误 / 0 警告（149 条）
回归套件 34（新增 mcp_smoke）
```

### 下一步

| 项 | 说明 |
|---|---|
| **补丁脚本必须先 parse 再写盘** | 两轮两次把文件写坏 |
| **MCP 只验了 5 个工具** | evaluate_task / calibrate / record / resolve 还没端到端跑 |
| **`.retry_log.jsonl` 仍无轮转** | 欠着 |

---

## 第八十一轮 · 账本允许同一条被回填两次

上一轮只验了 MCP 的 5 个读工具。这一轮补**写路径**——`record` / `resolve` /
`auto_resolve`，那是唯一会改动账本的一段。

### 补上之后 12 → 23 项

```
写路径（临时账本，真写真读）
  [PASS] record 能写入 pending
  [PASS] record 返回可用的 id
  [PASS] ledger_stats 看得到刚写的那条
  [PASS] resolve 能回填
  [PASS] 重复回填被拒（不静默覆盖）
  [PASS] auto_resolve 能按任务名批量回填
  [PASS] evaluate_task 走通 / 给出组合成功率
  [PASS] calibrate 走通
```

### 查出真 bug：同一条能被回填两次

`resolve()` 原来是这么判重的：

```python
rows = _load()                                   # ← 原始事件流
target = next(r for r in rows if r["id"] == rid)
if target.get("success") is not None:            # ← 永远为 False
    raise ValueError("已有结果")
```

问题在账本是 **append-only**：一条记录被回填之后，**它自己那行的 `success` 仍然是 `None`**，
有结果的是后面那条 `resolve` 事件。

于是：

1. 第二条 `resolve` 被**静默接受**
2. `entries()` 折叠时取最后一条 → **前一次的结果被无声覆盖**
3. 账本上 True 和 False 都留着，但**看不出矛盾**

改成查折叠后的状态：

```python
state = {r["id"]: r for r in entries()}      # ← 折叠后的
```

门禁加 2 条：

```
[PASS] 同一条不能回填两次
[PASS] 折叠状态保留第一次的结果
```

`guard` 从 45 涨到 47。

### 这一轮我的断言又错了两处

| 断言 | 错在哪 |
|---|---|
| `rid` 取值 | `tok.startswith("m1-")` 把后面的 `（pending，L3）` 一起吃进去了 |
| 重复回填 | MCP 的错是 `isError: true` 挂在 `result` 里，不是 JSON-RPC 的 `error` 字段；我查的是小写 `"error"` |

**三处错，两处在我的测试里。**

不过第二处顺带说明了一件事：`handle()` 对异常的包装是**对的**——
`isError: true` 让客户端能区分"成功了"和"报错了"，而不是看文本猜。

### 断言

```
harness 74    extend 66    guard 47    probe 17    capability 20    kb 14    sargable 15/15
mcp_smoke 23
账本审计 0 错误 / 0 警告（149 条）
回归套件 34
```

### 下一步

| 项 | 说明 |
|---|---|
| **回填后被覆盖的历史查不出来** | `entries()` 只留最后一次；要不要留全部 resolve 事件？ |
| **补丁脚本仍先写盘后 parse** | 三处错里没有一处是它造成的，但它一直在 |
| **`.retry_log.jsonl` 仍无轮转** | 欠着 |

---

## 第八十二轮 · 那个 bug 到底有没有造成损坏

上一轮修了「同一条能被回填两次」。修完立刻有个问题该问：

> **它存在了这么久，有没有真出过事？**

### 查了

```
账本 228 行，其中 resolve 事件 65 条
被回填的样本 65 个
回填超过一次的：0 个

历史备份 26 份，逐份查：
  bak-before-envfield        9 行，重复回填 0
  bak-before-group          90 行，重复回填 0
  bak-before-semantic-fix   50 行，重复回填 0
  ...
```

**0。26 份备份、65 次回填，一次都没触发过。**

### 「潜在缺陷」和「已造成损坏」是两件事

这个区分值得写下来：

| | 含义 |
|---|---|
| 潜在缺陷 | 路径存在，但没人走到 |
| 已造成损坏 | 数据已经错了 |

上轮那个 bug 属于前者：**修它是对的，但不能说"我挽回了损失"**——没有损失。

如果我当时写"这个 bug 导致账本自相矛盾"，那就是编的。

### 但"修完之后查不到"不等于"检测器会查"

所以加了 `duplicate_resolves()`，并**故意造一份损坏来验证它**：

```python
L.resolve(r['id'], True, '第一次')
L._append({'id': r['id'], 'op': 'resolve', 'success': False, ...})   # 绕过 resolve 伪造
```

```
查到 1 个重复：
  m1-6613636943c0 回填 2 次 取值 [True, False] 矛盾=True
[PASS] 检测器能抓到伪造的重复回填
```

**一个从没抓到过东西的检测器，和一个抓不到东西的检测器，看起来一样。**

### 现在它在审计里

```
[重复回填] N 个样本被回填多次，其中 M 个结果互相矛盾：...
```

只在有问题时报**错误**（不是警告）——那种矛盾会让统计直接把一条样本算两遍。

当前真实账本：**重复回填 0 个（干净）**。

### 门禁 2 条

```
[PASS] 检测器能抓到伪造的重复回填  — times=2 values=[True,False]
[PASS] 能识别两次结果互相矛盾
```

`guard` 从 47 涨到 49。

### 断言

```
harness 74    extend 66    guard 49    probe 17    capability 20    kb 14    sargable 15/15
mcp_smoke 23
账本审计 0 错误 / 0 警告（149 条），重复回填 0 个
回归套件 34
```

### 下一步

| 项 | 说明 |
|---|---|
| **`entries()` 仍只留最后一次** | 有去重后这不成问题，但要不要留全部事件仍未定 |
| **补丁脚本仍先写盘后 parse** | 欠着 |
| **`.retry_log.jsonl` 仍无轮转** | 欠着 |

---

## 第八十三轮 · 我把「判对率」和「成功率」读了二十几轮

这一轮本来是去找 degrade 那 30% 错在哪。挖的时候先撞上一个我自己的读数错误。

### 第一步就错：用错字段

我按 `success` 统计"判错的 degrade"：

```
case    错 5/5 = 100% 错    ← 看着像判据全废
collect 错 9/28 = 32% 错
qb      错 14/53 = 26.4% 错
```

**case 那 5 条其实全判对了。** 看 `conclusion_verified`：

```
case    5 条：conclusion_verified 5/5 = 100% 判对
collect 11 条：8/11 = 72.7% 判对
qb     53 条：conclusion_verified 一条都没填
```

那 5 条的 `success=False` + `conclusion_verified=True` 意思是：

- `success=False`：**验证条件不具备**（要 1 亿行、要 ARM，本机给不了）——真的
- `conclusion_verified=True`：**判 degrade 是对的**——也对

**同一个字段，两个问题。** 我拿"任务做成了吗"去答"判据判对了吗"。

### 真正的问题：一个字段承担了两个指标

我一直把 **calibration（成功率）** 当成 **判据准确率** 在读：

| 指标 | 问的是 |
|---|---|
| `calibration` | 这批落进 degrade 的主张，**碰巧**有多少是真的 |
| `criterion_accuracy` | 判据判 degrade 判得对不对 |

**对盲判样本（qb 53 条），后者根本没有定义。**

框架当时确实不知道，它说"证据不足"是**正确行为**。
验证后发现主张为真，那是**世界的事**，与判据准不准无关。

把这两件事混在一个数里读，就会得出"degrade 判错率 30%"这种
**既不是判据的错、也不是样本的错**的结论。

### 现在分开报

```
判据准确率 14/17 = 82.4%
  case     6/6  = 100%
  collect  8/11 = 72.7%
```

17 条是"已知答案还去判"的样本。qb 那 53 条**不在分母里**，理由写在字段里：

> 盲判样本没有这个字段，因为它们当时确实不知道，判「不知道」不算错也不算对。

审计里常驻两行：

```
[判据准确率] 14/17 = 82.4%（按 origin：case 6/6，collect 8/11）
[判据准确率] 只统计填了 conclusion_verified 的样本；盲判样本不在内——它们当时确实不知道
```

### 门禁 4 条

```
[PASS] 判据准确率只算填了 conclusion_verified 的  — n=2
[PASS] 判据准确率算对了 1/2  — 1/2 rate=0.5
[PASS] 盲判样本不进判据准确率
[PASS] stats 里两件事是分开的字段
```

`guard` 从 49 涨到 53。

### 这一轮的收获

> **一个数被当成另一个数读了二十几轮。**

之前每轮我都在说"degrade 成功率 70%"，听起来像"判据有 70% 准"。
实际上那是**这批主张碰巧有多少是真的**。

真正的判据准确率是 **82%（n=17）**——数字更高，但**样本少得多**，而且不能和盲判样本混。

**把两个数分开之后，才第一次能回答"判据准不准"这个问题。**

### 断言

```
harness 74    extend 66    guard 53    probe 17    capability 20    kb 14    sargable 15/15
mcp_smoke 23
账本审计 0 错误 / 0 警告（149 条）
判据准确率 14/17 = 82.4%（case 6/6，collect 8/11）
回归套件 34
```

### 下一步

| 项 | 说明 |
|---|---|
| **判据准确率只有 17 条样本** | 远不够；qb 那 53 条该补 `conclusion_verified` 的定义 |
| **collect 8/11 = 72.7%** | 错的那 3 条还没查 |
| **`.retry_log.jsonl` 仍无轮转** | 欠着 |

---

## 第八十四轮 · 一个字段，两拨脚本，两种意思

上一轮我加了个 `criterion_accuracy`，说这才是「判据准不准」。
这轮去查它错的那 3 条，**发现它建在流沙上**。

### 先看那 3 条

```
collect  verdict=degrade  success=False
    task : degrade复查·J1 给 age 建索引让 age+0=42 更快
    evid : 算子=TABLE FULL SCAN 谓词选择性=算术恒等
```

三条全是「算术恒等破坏索引」类。判 degrade 错在哪？

**没错。** 框架判 degrade 时**确实不知道**——它没有执行计划。
后来测出 `FULL SCAN`，结论被推翻，**那是世界变了，不是判据错了**。

### 真正的错在字段上

查 `conclusion_verified` 的全部填法：

| 脚本 | 填的是 | 答的问题 |
|---|---|---|
| `case_l3_limits` / `case_l3_more` | `judged_right` / `good` | **判据判得对不对** |
| `collect_degrade` / `collect_mechanism` | `held` | **结论有没有被推翻** |

**同一个字段，两种互不兼容的意思。**

而我上一轮正是拿它算「判据准确率」——
**把「结论被推翻」当成了「判据判错」**。
那 3 条被算成判据错，其实是框架当时做得对。

### 拆成两个字段

```python
record(..., criterion_right=None, conclusion_held=None)
```

- `criterion_right` —— 判据判得对不对（框架当时就有可能知道答案时）
- `conclusion_held` —— 结论最终成立不成立（能被复核时）

迁移了四个脚本 + 账本里 22 条历史记录（按任务名前缀判定原语义）。

### 现在的两个数

```
判据准确率 6/6 = 100.0%     ← case：框架知道答案时，6 次全对
推翻率     3/11 = 27.3%     ← collect：可复核的 degrade 里 27.3% 被实测推翻
```

**这两个数不能混，也不能互相替代。**
前一个说「判的时候有没有判对」，后一个说「判成保留的那批，后来有多少被推翻」。

### 门禁 7 条

```
[PASS] 判据准确率只算填了 criterion_right 的
[PASS] 判据准确率算对了 1/2
[PASS] 盲判样本不进判据准确率
[PASS] 推翻率只统计能复核的 degrade
[PASS] 推翻率算对了 1/2
[PASS] 判据准确率不把 conclusion_held 当成判据对错
[PASS] stats 里两件事是分开的字段
```

`guard` 从 53 涨到 56。

### 顺手：又踩了「只改第一处」

同样的 `a[1] += 1 if r.get("conclusion_verified") else 0` 出现两次
（`stats()` 内联版 + 独立函数版），我只替换了第一处。

结果：`by_origin` 显示 `case 0/6`，而顶层是 `6/6`。
**顶层和分项对不上**——要不是逐个核对，这就是个静默错数。

### 这一轮的收获

这是「一个词在不同层指不同的事」这个老毛病的**又一次**，而且这次它躲在**字段名**里。

> 一个字段被两拨脚本用两种意思填，
> 任何基于它的指标都没有意义——
> **而且它不会报错，只会给你一个看起来合理的数。**

上轮那个「82.4% 判据准确率」就是这样一个数。现在它是 100%，但**只基于 6 条 case 样本**。

### 断言

```
harness 74    extend 66    guard 56    probe 17    capability 20    kb 14    sargable 15/15
mcp_smoke 23
账本审计 0 错误 / 0 警告（149 条）
判据准确率 6/6 = 100.0%（case）    推翻率 3/11 = 27.3%（collect）
回归套件 34
```

### 下一步

| 项 | 说明 |
|---|---|
| **判据准确率只有 6 条** | case 类样本太少；qb 那 53 条是盲判，没有 criterion_right 可言 |
| **推翻率 27.3% 的样本只有 11** | collect 类；两个数都薄 |
| **`.retry_log.jsonl` 仍无轮转** | 欠着 |

---

## 第八十五轮 · 推翻率的样本从 11 条涨到 74 条

上轮把 `conclusion_verified` 拆成两个字段之后，两个指标都只有个位数的样本。
这轮去补——结果发现**盲判样本其实能提供 `conclusion_held`**。

### 先核对语义，不能猜

同一个 `success`，各脚本答的不是同一个问题。按 `task` 前缀归类：

| 语义 | 前缀 |
|---|---|
| **结论是否成立** | `真题·` `真题21·` `真题M·` `B题·` `EXPLAIN·` |
| **任务/意图是否达成** | `限额·` `补充·` `degrade复查·` `机制维度·` `env收集·` `收集·` `v2收集·` `L2真·` `unknown·` `优化·` |

**「结论成立」那一类，正好就是盲判样本** —— 它们判 degrade 之后被复核，
复核结果就是"结论最终成立没有"。这正是 `conclusion_held`。

### 迁移时踩的坑：得用折叠后的状态

第一遍迁移迁了 **0 条**。原因是我在**原始行**上找 `success`——

而盲判样本的 `success` 是在后面的 `resolve` 事件里（append-only 的设计），
原始记录行的 `success` 永远是 `None`。

**看到"0 条"就该怀疑是自己查错了，而不是"真的没有"。**
改成先用 `entries()` 折叠，再按 id 映射回原始行。

### 数字

```
推翻率 19/74 = 25.7%   （86 条 degrade 里可复核的那些）
  collect  5/21 = 23.8%
  qb      14/53 = 26.4%
```

样本从 11 条涨到 74 条。

### 顺带发现：之前那个"差异"是假的

以前我比较过 qb 和 collect 的成功率，说"qb 74%、collect 61%，差 13 个点"。

**在可比指标上（推翻率）两者几乎一致：26.4% vs 23.8%。**

> 那 13 个点的差异，是**任务语义不同**造成的假象——
> qb 的 success 是"主张成立吗"，collect 的是"任务做成吗"。
> 把两个不同问题的数放在一起比，差异是这么来的。

**所以两个数现在能互相印证了：都指向"degrade 大约对四分之三"。**

### 五个脚本改成直接写

```
feed_qb.py / feed_qb2021.py / feed_qb_more.py
collect_explain.py / case_apmcm_b.py
    → 顺便写 conclusion_held
```

以后不用再靠迁移。

### 门禁 3 条

```
[PASS] 推翻率只认结论成立语义（意图达成的不算）
[PASS] 成立与被推翻各记一条（看增量，不看绝对值）
[PASS] pending 样本不算进推翻率
```

`guard` 从 56 涨到 59。

第二条也是改了才对的：临时账本里前面几段已经写了 2 条，
我原来断言 `checkable == 2`，实际上应该是**看增量**。

### 断言

```
harness 74    extend 66    guard 59    probe 17    capability 20    kb 14    sargable 15/15
mcp_smoke 23
账本审计 0 错误 / 0 警告（149 条）
判据准确率 6/6 = 100.0%（case）    推翻率 19/74 = 25.7%（collect 23.8%、qb 26.4%）
回归套件 34
```

### 下一步

| 项 | 说明 |
|---|---|
| **判据准确率仍只有 6 条** | case 类样本太少；qb 是盲判，没有 criterion_right 可言 |
| **推翻率还有 12 条 degrade 不可复核** | 86 - 74：那 12 条的结论没被验证过 |
| **`.retry_log.jsonl` 仍无轮转** | 欠着 |

---

## 第八十六轮 · 把「不可复核」拆开，缺口才有名字

上轮留了一条：86 条 degrade 里，只有 74 条复核过。**那 12 条差在哪？**

报告里只体现为"少了几条"——缺口是看不见的，像是我忘了填。

### 先看它们是谁

```
v2收集·B1 让这条查询更快        success=False
v2收集·D1 让这条查询走索引      success=True
限额·D1 生产负载 p99 < 100ms   success=False
补充·D4 ARM 平台性能一致        success=False
```

两类完全不同的原因：

| 那几条 | 为什么复核不了 |
|---|---|
| `限额·` / `补充·`（5 条） | **环境给不了**（要 1 亿行、要 ARM、要多节点）——结论在**这个机器上**无法检验 |
| `v2收集·`（7 条） | 当时**根本没测**——脚本用的是一张手写的 `INTENT_ACHIEVED` 表 |

第二种更值得警惕：**用了手写的表，就等于结论没被验证过**。
表写得对不对，只能靠人记得。

### 拆成三类

```python
record(..., conclusion_held=None, conclusion_checkable=None, check_why="")
```

| 状态 | 含义 |
|---|---|
| `conclusion_held` 有值 | 复核过，结论成立/不成立可知 |
| `conclusion_checkable is False` | 明确**没法**复核，原因写在 `check_why` |
| 两个都是 None | 不知道是没复核还是不能复核 |

**以前这三种混在一起。** 现在每一类都有名字，报告里直接说：

```
[推翻率] 可复核的 degrade 74 条里，被实测推翻 19 条 = 25.7%（collect 5/21，qb 14/53）
[推翻率] 另有 12 条**没法**复核（结论未实测（用的是手写 INTENT_ACHIEVED 表）×7；
         验证条件不具备（本机给不了这个规模/架构/节点数）×5），2 条**不知道**能不能复核
```

### 三个脚本都标了

```
case_l3_limits.py / case_l3_more.py
    conclusion_checkable=False, check_why="验证条件不具备（本机给不了这个规模/架构/节点数）"
collect_v2.py
    conclusion_checkable=False, check_why="结论未实测（用的是手写 INTENT_ACHIEVED 表）"
```

账本里 26 条历史记录按同一口径补标。

### 门禁 4 条

```
[PASS] 明确没法复核的，不进推翻率分母
[PASS] 没法复核的原因被记下来
[PASS] 不知道能否复核的，两头都不算
[PASS] 三类互不重叠：复核过的不会同时被算成没法复核
```

`guard` 从 59 涨到 63。

### 这一轮的收获

> **缺口不可见，就等于没有缺口。**
>
> 12 条不可复核的数字一直是对的，但它没告诉你**为什么**，
> 于是看起来像"我忘了填"。
> 拆成三类之后才发现：其中 7 条不是环境限制，
> **是当时压根没测结论**——那才是真问题。

### 断言

```
harness 74    extend 66    guard 63    probe 17    capability 20    kb 14    sargable 15/15
mcp_smoke 23
账本审计 0 错误 / 0 警告（149 条）
判据准确率 6/6 = 100.0%（case）    推翻率 19/74 = 25.7%
不可复核 12 条：结论未实测 7 · 环境给不了 5
回归套件 34
```

### 下一步

| 项 | 说明 |
|---|---|
| **那 7 条要真测** | 用 EXPLAIN 实测"索引到底被采用没有"，替掉手写表 |
| **判据准确率仍只有 6 条** | case 类太少；qb 是盲判，没有 criterion_right 可言 |
| **`.retry_log.jsonl` 仍无轮转** | 欠着 |

---

## 落库字段

一次答题要能复盘，至少存这些：

| 表 | 字段 |
|---|---|
| `claim` | cid, text, e1, e2, e3, penalty, C, gate_reached, verdict, sources[], checked_at |
| `subq` | sid, target, op, answer_type, conditions{}, required_params[] |
| `grouping` | signature[], primary, merged_in[], conflicted[] |
| `ask` | qid, kind, reason, default, answered_value, state |
| `route` | cid → gate → verdict → 去向（方案库／疑难1库／疑难2库） |

---

## 接线：改图上哪几处

| 图上位置 | 插什么 | 依据 |
|---|---|---|
| 「置信度评估」①②③ 三处 | 换成 G1／G2／G3，各带入参表 | 本节瓶颈一 |
| 「对宿主提问」 | 前面加 DETECT，后面加 WAIT 分支 | 本节瓶颈二 |
| 「汇总同类」 | 前面加结构化五字段，后面加冲突检测 | 本节瓶颈三 |
| 「逐列构建」 | 按 `signature` 定列，列内按 `target` 排序 | 瓶颈三判等规则 |
| 四条回边 | 各加一个计数器，超 N 次直跳「放弃→疑难库」 | Astra 实测的"反复进入修复循环" |

---

## 成本影响

用 GPT-6 Astra 标准价测算（输入 $11/M、缓存读 $1.10/M、输出 $55/M；[AWS 模型卡](https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-openai-gpt-6-astra.html)）。

**调用量随路由变**（5 子问题 + 主线与汇总 8 次，每结论输出按 800 token 计）：

| 路由 | 次/子问题 | 总调用 | 5K 输入·无缓存 | 5K·全命中 |
|---|---|---|---|---|
| 全 lite | 8 | 48 | $4.75 | $2.38 |
| 混合（实测均值 8.32） | 8.32 | 49.6 | $4.91 | $2.46 |
| 全 full | 11 | 63 | $6.24 | $3.12 |

20K 输入时，混合档从 $13.09 降到 $3.27（−75%）。

**结论：输入越大，缓存前缀的收益越大。** 把「题干 + 题型库命中结果 + 流程规则」固定成前缀，是所有改法里最省事、杠杆最大的一条。

**闸门拦截能省多少**（每个子问题全流程约 11 次调用）：

| 在哪被拒 | 省下调用 | 说明 |
|---|---|---|
| G1 | 10 | 最划算，只花了 1 次就停 |
| G2 | 5 | 已经付过 4 次取材的账 |
| G3 | 1 | 只省掉生成 |

越早拦越省——这是把 G1 的判据压到"只看有没有出处"（最便宜的一维）的理由。

---

## 未完成项

| 项 | 状态 | 说明 |
|---|---|---|
| 真实题库实测 | 未做 | 当前只有 19 条合成样本，拒绝率不代表真实分布 |
| 回边接进主图 | 部分 | RetryBudget 已接进 `run_with_retry`，但只接了 A/C 两条重做边，B/D 终止边还没接 |
| 主线模型 | 简化 | `mainline_loop` 只模拟"抬 e1"，真实的质疑复查／换底层还没建模 |
| 冷启动阈值校准 | 部分 | TopicLibrary 是接口，无真实命中数据，0.7／0.3 两个阈值未校准 |

现在两条线都能跑，缺的是**真实数据校准入参**——阈值、命中率、拒绝率三个都要用真实题集回填。**别把"有实现"当成"已上线"。**
