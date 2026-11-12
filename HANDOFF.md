# 交接 · model1-arch

> **新会话第一件读这个。** 一页纸：现在什么状态、下一步做什么、哪些坑别踩。
> 状态段由 `python tools/handoff.py` 自动刷新，**不要手改**（手抄的状态第二天就是错的）。
> 更细的规矩在 `AGENTS.md`，命令清单在 `插件速查.md`。

---

## 0. 三十秒上手

```powershell
$env:PYTHONIOENCODING="utf-8"; $env:PYTHONUTF8="1"
$env:Path=[System.Environment]::GetEnvironmentVariable("Path","Machine")+";"+[System.Environment]::GetEnvironmentVariable("Path","User")
$py = "C:\Users\21246\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
cd C:\Users\21246\Documents\deepseek-harness\default-workspace\model1-arch

& $py tools\handoff.py            # ① 先看状态（跑真实仪表，30 秒）
& $py gate.py out/final           # ② 看当前红项
& $py tests\run_all.py            # ③ 确认代码没被改坏（344 秒，别给更短超时）
```

**三条都不能省。** 第 ③ 条超时设 300 秒会把正常一圈读成「断」。

---

## 1. 当前状态

<!-- AUTO -->
```
gate（out/final，35 项）
  硬门  OK 10 / FAIL 0     硬门失败 0，警告 1
  软门  OK 17 / FAIL 2 / WARN 1 / 不适用 5
  红项  redteam, prompt

溯源 数字溯源：199/199
架构不变式 不成立：0 / 12
图的机械检查 A/B 无问题
质量门自校 自校通过：坏样本两道都拦住，好样本两道都放行。
```
<!-- /AUTO -->

---

## 2. 这个插件是什么、不是什么

**是**：给 LLM 用的数学建模能力 + **验证护栏**。35 道门、冻结数字表、红队分板、图的内容检查。

**不是**：出稿机。`mmkit.py run` 一条龙会替你做掉全部建模决定，产出模板。**禁止使用。**

**核心主张**：LLM 主导建模，工具只算与验；**门在哪，注意力就在哪**。

---

## 3. 最近四轮（R121–R124）加了什么

| 轮 | 加的东西 | 现在是什么状态 |
|---|---|---|
| **R121** | `redteam.py` 分板（板数 = `\section` 数） | 12 板 12 角色，`selftest` 28/28 |
| **R122** | 发现「7 个角色掩盖 5 段没人审的正文」 | 已修，比例关系钉进 `selftest` |
| **R123** | 冻结表 `generated_from`、`significance` 门、`prompt` 门、`figure` 下限、文献下限 | 全部进 gate |
| **R124** | `proof` 门、`iterlog` 门、`fig_visual`（图的内容）、`paper_pipeline`、`paper_hygiene`、`redteam_orchestrate auto`、`bootstrap_ci`、A/B 对照实验 | 见状态段 |
| **R124 末** | `check_write.py`（写后控制字符校验）、`numeric_genre.py`（数字四类）、`handoff.py`；门 33→35；项目定位升级为「鉴真 / veridical」；十份 Q2 大纲 | 见 `out/交接-第102轮.md` |

**35 道门的分布**（硬 12 / 软 23）：

```
硬：compile pdf code numbers rules abstract abs_page bare_pct refs
    domain leakage math
软：rules_apmcm rigor required innovation ai_taste claims causal biblio
    analysis method_argument self_correction deployment redteam cross
    figures falsify extrap sensitivity significance prompt proof iterlog stamp
```

---

## 4. 下一步（按性价比排，带成本）

| # | 做什么 | 为什么 | 成本 | 状态 |
|---|---|---|---|---|
| **0** | **定位已改：从「落地到医学」改为「对齐 LLM 事实性评测（FActScore/HaluEval）」** | 医学那条路要 2-3 周 + 医学合作者；对齐 AI 领域半天就能跑，且评审不需跨界 | **已测前置事实** | **做了** |
| **0b** | **数字类别分布已测**：23 篇 9337 个数字，计算值 **47.3%**、config 27.1%、结构 17.6%、时间 8.0% | 「知识源能覆盖的上界只有 35.1%」，这是「需要计算谱系判据」的量化依据 | — | **做了**，见 out/数字类别分布.md |
| **0c** | **没跑真 FActScore** | 本环境无 openai/transformers/torch，它依赖 LLM 拆原子事实 | 需 API key | **未做** |
| **1** | **加 baseline 对比**（`nbval` / `papermill` / `pytest --doctest-modules`） | 论文零 baseline，这是 Q2 的硬门槛。若它们也能到 90% 溯源率，核心贡献就只剩「七类分类」 | **半天** | **未做** |
| **2** | **A/B 扩到 5–10 个任务** | 现在 n=1，4 分差在评分噪声内 | 每题 ~40 分钟 | 未做 |
| **3** | **24 张图逐张打开看** | 规矩写了（`AGENTS.md` 有硬规矩），**动作没执行** | 1 小时 | **未做** |
| **4** | **豁免显式化** | `declaration.json` 的 `no_dataset` 应写明「为什么该门不适用」且被红队复核 | 20 分钟 | **未做** |
| **5** | 版本化 + CHANGELOG | `dsh-purge` 有 57 版记录，这边一个版本号都没有 | 低 | 未做 |
| **6** | 拆 `mmkit.py`（5,558 行单文件） | purge 拆 5,600 行文件的理由是「改表结构要翻过 500 行计分逻辑」 | 中 | 未做 |

**不要先做 CI**：`run_all` 的输入是人（要真改论文、真重编译），CI 自动化不了。

---

## 5. 五个必须知道的坑

| 坑 | 症状 | 怎么避 |
|---|---|---|
| **`run_all` 344 秒** | 给 300 秒会把正常一圈读成「断」 | 超时给 600 |
| **`[IO.File]::WriteAllLines` 写 CRLF** | `paper_bytes` 会差「行数」那么多字节，`I12` 报图旧于数据 | 用 `WriteAllText` + `-replace "\r\n","\n"` |
| **PowerShell heredoc 吞引号/转义** | `derived["x"]` 变成 `derived[x]`，`\U` 报 unicode 错 | 写临时 `.py` 文件再跑，或 `[char]34` |
| **`\code{}` 逃过 `numbers` 门** | tokenizer 会 blank 掉参数，里面的数字不判 | 用 `tools/example_audit.py`，但「找到 ≠ 对」 |
| **检测器自己会错** | 本会话已修：`fig_visual` 按脚本名匹配（sim 全场 0）、所有×所有（4 个误报）、`roster` 忽略路径、`triage` 忽略路径 | **每次先跑 `--selftest`** |

**最贵的一条**：**报「拦住 N/M」不算证据**。必须构造缺陷 + 调用真围栏，且变异测试证明它敏感（`tools/fence_mutation.py` 期望「假测试 0/4」）。

---

## 6. 改论文后的固定链路（漏一步就静默过时）

```powershell
& $py tools\paper_pipeline.py out/final      # 编译×2 → 采集 → 上下文 → 画图 → 冻结 → gate×2
& $py tools\paper_pipeline.py out/final --dry  # 只看会跑什么
```

**顺序不能换**。`make_ab_figs` 已加进 pipeline（否则每次更新 `data2.json` 都让 fig21–24 变旧，`I12` 反复红）。

---

## 7. 三处「不要」写错了

| 不要 | 改成 |
|---|---|
| 「gate 全绿所以是对的」 | 说清哪几项绿、分母是多少、哪几项豁免 |
| 「图都检查过了」 | 看了哪几张、核了哪五项（轴标签/有数据/与正文一致/没截断/灰度可辨） |
| 「N/N 可溯源」不带口径 | 「199/199，按全 token 口径；gate 只判小数 43/43」 |

---

## 8. 外部产物在哪

| 位置 | 内容 |
|---|---|
| `out/final/` | 工具论文（30 页）+ 冻结表 818 条 + 24 张图 |
| `out/d2026c/` | DWTS 竞赛稿（19 页）+ 12 板红队 30 条 finding |
| `out/_阅卷细则.md` `out/_阅卷入口.md` | 阅卷器判据（23 项，6 否决 + 17 扣分） |
| **`out/交接-第102轮.md`** | **本次会话的交接**：改了什么、发现了什么、不修的那个问题、GitHub 状态、Q2 判决 |
| `out/Q2大纲-终稿.md` | Q2 论文大纲（376 行，唯一必读；其余 v1–v9 是过程记录） |
| `tools/grade.py` | 阅卷器，`--selftest` 自校 |
| `C:\Users\21246\Desktop\AB对照实验\` | A/B 两份完整提交 + 分析 + 四张对比图 |
| `C:\Users\21246\Documents\_sealed_answers\` | 实验组封存副本 + 封存记录 |

---

## 9. 一句话

**这个插件的产出不是一个 PDF，是一条循环：做工作 → 写进论文 → 红队攻 → 分诊 → 修 → 再攻。**

**每一环都有仪表，只有每环可测，整圈才不会空转。**
