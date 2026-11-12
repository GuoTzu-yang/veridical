# LLM × 插件：拟合与规正方案

> 第 150 轮 | 解决两个问题：
> ① 如何让 LLM 用上插件已有的 55%（不推倒重来）
> ② 如何规正 LLM（不让它瞎想）

---

## 核心矛盾

| | 插件 | LLM |
|---|---|---|
| 强项 | 算得准、可复现、250 条断言 | 读题意、提路线、判断 |
| 弱项 | 只会 if-else 挑方法 | 会编数字、会瞎推 |
| 危险 | 选错方向还自信输出 | 把"看起来对"当成"对" |

**所以不能让任何一方单独决策。**

插件单独决策 = 55%（现在的状态）
LLM 单独决策 = 不可控（会编数据、会漏算）

**解法：LLM 提案，插件执行并验证，LLM 只按插件给的数字做判断。**

---

## 一、拟合：把插件装进 LLM 的循环

### 现在的调用关系

```
人 → mmkit.py run → 一条命令 → 论文
```
一次跑完，没有 LLM。

### 目标调用关系

```
        ┌─────────────────────────────────────┐
        │  LLM（提案者 + 判断者）              │
        │  只做三件事：提路线 / 看数字 / 写论证 │
        └──────────────┬──────────────────────┘
                       │ ① 提案（JSON）
                       ▼
        ┌─────────────────────────────────────┐
        │  contract.py（闸门）                 │
        │  提案能不能映射成插件命令？不能就退回 │
        └──────────────┬──────────────────────┘
                       │ ② 命令
                       ▼
        ┌─────────────────────────────────────┐
        │  插件（执行者）                       │
        │  run / forecast / plot / merge ...   │
        │  返回结构化数字，不是散文             │
        └──────────────┬──────────────────────┘
                       │ ③ 结果（JSON）
                       ▼
        ┌─────────────────────────────────────┐
        │  verify.py（判据）                   │
        │  这条路线的数字过没过阈值？           │
        └──────────────┬──────────────────────┘
                       │ ④ 过 / 不过 / 未定
                       ▼
                 LLM 决定下一步（继续 / 换路线 / 收敛）
```

### 关键设计：LLM 只碰「决策」，不碰「计算」

| 环节 | 谁做 | 为什么 |
|---|---|---|
| 提建模路线 | **LLM** | 需要读题意、跨领域联想，插件只有关键词表 |
| 写目标函数 | **LLM** | 需要数学形式，这是 LLM 的本职 |
| 算数字 | **插件** | LLM 会编，插件不会 |
| 画图 | **插件** | 确定性 |
| 判断"这条路线行不行" | **LLM**，但**必须引用插件的数字 + 阈值** | 自由判断会瞎说 |
| 写论证文字 | **LLM** | 但每个数字要溯源 |
| 组装 LaTeX / 编译 | **插件** | 确定性 |

**一句话：LLM 负责「想什么」，插件负责「是多少」。**

---

## 二、提案的契约（这是拟合的关键）

LLM 提的每条路线必须是一个**结构化对象**，不是一段话：

```json
{
  "route_id": "A",
  "title": "dimensional analysis + power-law fit",
  "reasoning": "题目是传热问题，量纲分析后 Nu 应是 Re 和 Pr 的幂函数",
  "target": "无量纲热阻",
  "features": ["针肋宽度比", "歧管深高比"],
  "method": "run",
  "method_args": {"--y": "无量纲热阻", "--x": "针肋宽度比,歧管深高比"},
  "success_criteria": {
    "cv_rmse_max": 0.012,
    "r2_min": 0.45
  },
  "falsifiable_assumption": "如果热阻与几何比无关，则偏相关应接近 0"
}
```

**为什么必须是 JSON**：
1. 插件能直接映射成命令，不用 LLM 再翻译
2. `success_criteria` 让「好坏」由数字决定，不由 LLM 感觉决定
3. `falsifiable_assumption` 强制它写「如果这条假设错了，数据会怎样」——写不出来说明这条假设是空的

### 校验规则（闸门①）

| 检查 | 不通过怎么办 |
|---|---|
| `method` 是插件真实存在的子命令 | 退回，列出可用子命令 |
| `method_args` 能交给 argparse 解析 | 退回，报错信息原文给它 |
| `success_criteria` 里每个键都是插件能算的指标 | 退回，列可用指标 |
| `falsifiable_assumption` 非空且含可比对象 | 退回，要求重写 |
| 至少 3 条路线，且**不允许全部同构** | 退回（防止「三个变体」充数） |

最后一条最重要：**三条路线全是「线性 / 二次 / 岭回归」等于只提了一条。**
判据：`method_args` 的差异度——如果三条只是 `--x` 换个顺序，拒收。

---

## 三、规正：六道闸门

### 闸门① 提案可执行性
> 想得再好，映射不成命令就是空话。

### 闸门② 数字溯源
> 论文里的每个数字，必须原样出现在插件输出里。

实现：`verify.py` 扫描 `.tex` 里的所有数字，逐个在插件 `out/*.json` 里找。
找不到的标 `[未溯源]`，不允许进正文。

**这条能挡掉 90% 的「瞎编」。**

### 闸门③ 判据外部化
> 「这条路线好」不能是 LLM 的感觉，必须是数字过阈值。

`success_criteria` 由 LLM 提，但**数值由插件算**。
而且插件可以给出经验区间（从历史题），LLM 提的阈值超出区间就提示"这个阈值不现实"。

### 闸门④ 矛盾检测
> 两条独立路线得出相反结论 → 标记「未定」，不能选一个当结论。

例：路线 A 说热阻随宽度单调降，路线 B 说先降后升 → 两者都过阈值也**不能下结论**。

### 闸门⑤ 假设可证伪
> 每条假设必须写「如果它错，数据会怎样」，且插件能检验。

写不出来 = 这条假设是装饰，删掉。

### 闸门⑥ 失败隔离
> 失败的路线进「死路表」，但**不进下一轮的提案上下文**。

依据（Archon 论文原话）：上下文里堆积的失败记录会让 agent 丧失坚持意愿。
所以：`dead_ends.json` 只给「别再试这个」的摘要，不给完整的失败过程。

---

## 四、具体实现：三个新文件

### 1. `contract.py` — 提案的 schema 与校验

```python
"""提案校验：LLM 想的东西必须能落地。"""

ROUTES_SCHEMA = {...}   # 上面的 JSON 结构

def validate(proposal, available_cmds, available_metrics) -> list[str]:
    """返回错误列表，空列表表示通过。"""
    errs = []
    if proposal.get("method") not in available_cmds:
        errs.append(f"method {proposal.get('method')!r} 不存在，"
                    f"可用：{sorted(available_cmds)}")
    for k in (proposal.get("success_criteria") or {}):
        if k not in available_metrics:
            errs.append(f"指标 {k!r} 插件算不了，可用：{sorted(available_metrics)}")
    if not proposal.get("falsifiable_assumption"):
        errs.append("缺 falsifiable_assumption —— 这条假设能怎么被推翻？")
    return errs

def check_diversity(routes) -> list[str]:
    """三条路线不能同构。"""
    sigs = [tuple(sorted(r["method_args"].items())) for r in routes]
    if len(set(sigs)) < 2:
        return ["所有路线参数完全相同，等于只提了一条"]
    return []
```

### 2. `verify.py` — 数字溯源

```python
"""论文里的每个数字都必须能在插件输出里找到。"""

def trace_numbers(tex, plugin_outputs):
    """tex 里的数字 → 在输出里找 → 找不到的标红。"""
    tex_nums = extract_numbers(tex)      # 排除页数、年份、文献编号
    out_nums = {n for o in plugin_outputs for n in extract_numbers(o)}
    return [n for n in tex_nums if n not in out_nums]
```

### 3. `orchestrate.py` — 循环

```python
"""LLM ↔ 插件的对话循环。LLM 由外部调用，这里只编排。"""

def run_loop(data_path, max_rounds=4):
    ds_summary = describe_data(data_path)     # 插件生成
    routes = []                                # LLM 提
    dead = []
    for rnd in range(max_rounds):
        routes = llm_propose(ds_summary, dead)          # ← LLM
        for r in routes:
            errs = contract.validate(r, CMDS, METRICS)  # ← 闸门①
            if errs:
                dead.append({"route": r, "why": errs})
                continue
        results = {r["route_id"]: exec_plugin(r) for r in routes}  # ← 插件
        verdicts = judge(results, routes)                        # ← 闸门③
        if any(v == "pass" for v in verdicts.values()):
            break
        dead += collect_dead(results, verdicts)
    return results, verdicts, dead
```

**注意 `llm_propose` 和 `judge` 是外部调用**——插件本身不调模型，它只负责「编排 + 闸门」。
这样 LLM 可换（DeepSeek / GPT / Claude），插件不变。

---

## 五、50% 的工作量在闸门，不在 LLM

| 工作 | 占比 | 说明 |
|---|---|---|
| 保留现有插件 | **0%**（不改造） | 17 个子命令、12 种图、250 断言全部保留 |
| 写 contract 校验 | 20% | 提案 schema + 5 条规则 |
| 写数字溯源 | 25% | 这条最能止损 |
| 写编排循环 | 20% | 状态机，不复杂 |
| 接 LLM 调用 | 10% | 一个 HTTP 调用 |
| 等 LLM 收敛 | 25% | 迭代时间 |

**插件一行不用改**——这就是「不浪费 55%」的意思：
现在的 `run / forecast / plot / merge / clean / advise` 全部变成「被 LLM 调用的工具」。

---

## 六、一个具体例子（B 题）

**第 1 轮 LLM 提案**（3 条）：

```json
[
  {"route_id": "A", "title": "纯统计回归",
   "method": "run", "method_args": {"--y": "无量纲热阻", "--x": "针肋宽度比,歧管深高比"},
   "success_criteria": {"cv_rmse_max": 0.01, "r2_min": 0.5},
   "falsifiable_assumption": "若几何参数无影响，偏相关应≈0"},
  {"route_id": "B", "title": "量纲分析 + 幂律",
   "method": "run", "method_args": {"--y": "无量纲热阻", "--x": "针肋宽度比,歧管深高比", "--log": "all"},
   "success_criteria": {"cv_rmse_max": 0.01},
   "falsifiable_assumption": "若幂律成立，log-log 斜率应显著非零"},
  {"route_id": "C", "title": "多目标权衡",
   "method": "plot", "method_args": {"--kind": "pareto", "--min": "热阻,压降"},
   "success_criteria": {"front_size_min": 5},
   "falsifiable_assumption": "若两目标无关，前沿应占大多数点"}
]
```

**闸门检查**：
- A、B 的 `method_args` 只差 `--log` → **退回**：「A 和 B 是同构的，换一条」
- C 用了不同的 method → 保留

**第 2 轮** LLM 改写 B 为「按 REP 分组做分层回归」→ 通过。

**执行**：
- A → `cv_rmse = 0.00743` ✅（< 0.01）
- C → `front = 9` ✅（> 5）
- B → 失败

**判断**：A 和 C 都过 → 收敛。

**关键**：整个过程 LLM 没有编任何数字——`0.00743` 和 `9` 都是插件算的。

---

## 七、为什么这样就不瞎想了

| 瞎想的表现 | 哪道闸门挡 |
|---|---|
| 编一个 R²=0.85 | ② 溯源：插件算的是 0.5918 |
| 说「这条路线更好」但说不出依据 | ③ 判据外部化：必须报数字 + 阈值 |
| 提一个插件没有的方法 | ① 可执行性 |
| 三条路线其实是一条 | ① 多样性检查 |
| 假设写得像套话 | ⑤ 必须可证伪 |
| 一直试同样的死路 | ⑥ 失败隔离 |

**核心：LLM 的自由度被限制在「提案」和「引用数字做判断」，它没有权力决定数字是多少。**
