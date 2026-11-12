# model1-arch · 数学建模插件

**这是一层给 LLM 用的数学建模能力 + 验证护栏，不是出稿机。**

新会话先读 `插件速查.md`（一页纸：23 命令 / 6 道护栏 / 已知坑 / 23 道回归基线）。

**但第一件该做的是读 `HANDOFF.md`** —— 它只讲三件：现在什么状态、下一步做什么、哪些坑别踩。
状态段由 `python tools/handoff.py` 自动刷新（跑真实仪表），**不要手改**：手抄的状态第二天就是错的。
`AGENTS.md` 是你的长期规矩，`HANDOFF.md` 是这一轮的现场。

---

## 三条硬规则

1. **LLM 主导建模，插件只提供计算与验证。**
   **不要用 `mmkit.py run` 一条龙**——那是自动模式，会替你做完所有建模决定，产出的是模板论文。

2. **每个数字过 `verify.py`，每个结论过 `falsify.py` + `lanes.py`。**
   编一个 R² 会让整篇论证建立在假数据上。

3. **`gate.py` 硬门失败 0、警告 0 才算这一战打完。**
   红了就修，不解释。

---

## 最短路径

```powershell
$env:PYTHONIOENCODING="utf-8"; $env:PYTHONUTF8="1"
$env:Path=[System.Environment]::GetEnvironmentVariable("Path","Machine")+";"+[System.Environment]::GetEnvironmentVariable("Path","User")
$py = "C:\Users\21246\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"

& $py mmkit.py advise --data X.xlsx                        # 定题 + 可复核依据
& $py mmkit.py race --data X --y Y --x A,B --json          # 模型赛马（JSON 已净化）
& $py verify.py out/runs/X/paper.tex                       # 数字溯源
& $py gate.py out/runs/X                                   # 出稿前 23 项
& $py tools\verify_all.py                                  # 23 道回归 + 补丁
```

---

## 红队规矩（第 123 轮硬化，必须执行）

**论文有几个板块，就有几个对应的审核。一板一个独立审核者，角色不得复用。**

板数**不是固定值**：它等于 `paper.tex` 里 `\section` 的个数。论文写成 4 部分就要 4 个审核，
写成 12 节就要 12 个。这条已经钉进代码与自检（`redteam.py selftest` 用 4/12/20 节三篇最小论文验证）。

开工第一步，不要凭记忆建几个：

```powershell
& $py redteam.py roster          # 论文几板 → 需要几个审核者，每板什么角色/探针/有没有交
& $py redteam.py roster --json   # 同上，结构化
```

硬性约束与做法：

| 项 | 规矩 |
|---|---|
| 板数 | 从 `paper.tex` 解析，不写死。`gate` 的 `redteam` 项会报「论文有 N 个板块，只有 M 个有审核」 |
| 角色 | 一板一角色，**不得复用**。gate 会把复用的角色判 FAIL |
| 判定 | 每条探针给 `pass` / `finding`；**每条 pass 必须写 `tried` >= 30 字**（「没找到」与「根本没查」必须可区分） |
| 证据 | 每条 finding 必须写 `where`（文件）+ `evidence`（该文件里逐字存在的标记 >= 3 字符）。gate 亲自 grep |
| 关闭 | 有 finding 必须写 `resolved`；正文没处理的写「未处理」并保留 finding |
| 团队上限 | **8 个 teammate**（含第二编码者）。板数 > 可用名额时**分批**：上一批 inactive 后再派下一批，**同一 agent 不许同时审两板** |
| 独立性 | 各审核者**不许读其他板的报告**。独立性靠这个，不是靠角色名不同 |

产出：`out/红队七板/<板块>-<角色>.json`（格式同 `out/final/redteam.json` 的 reviews 项）+ 同名 `.md`。

### 从「名单」到「真的各派一个」——两条命令，新会话照做

**光有名单不等于审了。** 名单到「12 份独立审核」之间原来是靠 agent 手工拼 prompt，
新会话不知道怎么拼，于是又回到凭记忆建 7 个。现在分工固定：

| 谁 | 干什么 |
|---|---|
| **脚本** | 切正文、拼 prompt、收结果、合并 JSON |
| **agent** | 真的派 subagent、真的读文件、真的判断 |

```powershell
# 1) 为每一板生成一份自足的任务书（含该板正文 + 角色 + 4 探针 + 禁读别板 + JSON 形状）
& $py tools\redteam_orchestrate.py prompts out/d2026c
#    → out/d2026c/红队/prompts/index.md（派工单：几板、几个角色、每个 prompt 文件）
#    → out/d2026c/红队/prompts/NN-<key>.md
#    → out/d2026c/红队/results/（审核者把结果写这里）

# 2) agent 按 index.md 逐个派独立审核者（每人只拿自己那份 prompt）
#    产出写到 results/ 下同名 .json

# 3) 合并
& $py tools\redteam_orchestrate.py collect out/d2026c
& $py redteam.py out/d2026c
& $py gate.py out/d2026c
```

**并行上限是 8，不是 10、不是 12。** 实测 `workflow` 的 `parallel` 一次只能起 8 个子代理，
第 9 个报 `subagent limit reached (active child limit: 8)`。板数 > 8 就**分批**：

```
12 板 → 第 1 批 8 个 + 第 2 批 4 个（上一批全部返回后再起下一批）
```

**这不是「固定 12」**：4 节论文就 4 份 prompt，20 节就 20 份（20 要分 3 批）。
`redteam.py selftest` 用 4/12/20/21 节四篇最小论文钉死了这条比例关系。

### 派工时必须写进 prompt 的硬约束

1. **只审这一板**，不评价别的板块，不提「建议补充第 N 节」
2. **不许读** `红队/results/` 下其它文件，也不许读 `redteam.json` —— 独立性靠这个
3. `pass` 必须写 `tried`（≥30 字，说清查了哪些行、重算了什么数）
4. `finding` 必须写 `where` + `evidence`（在被指文件里**逐字存在**，≥3 字符）
5. `finding` 必须有 `disposition`（`fixed`/`blocked`/`rejected`/`open`），**缺省按 `open` 计**
6. `blocked`/`rejected` 还要写 `falsifier`（什么证据会推翻）

### 实测（第 123 轮，`out/d2026c`）

```
12 板 → 12 份 prompt → 8+4 两批派 → 12 份 results 全部交齐
→ 合并 redteam.json → redteam 判「12 板 12 角色，30 条 finding 全部 open」
```

**30 条全 open 是正确结果**：稿子还没改，finding 就该是 open。**gate 该红。**

### 三个踩过的坑（都会让新会话误判）

| 坑 | 症状 | 已修 |
|---|---|---|
| `roster` 忽略路径参数 | `roster out/d2026c` 报「12 板齐」，gate 报「没有 redteam.json」——两个工具看不同目录 | 取 `sys.argv[2]` |
| 列宽写死 26 | 长角色名挤进下一列，读起来像 `memo-to-the-producersmemo-to-the-producers`（是排版溢出，不是重复） | 列宽自适应 |
| review 级 `resolved` 与 finding 级 `disposition` 并存 | 12 板 30 条 finding 全写了 `disposition=open`，却因缺 review 级 `resolved` 被判「没写怎么处理」 | 有 disposition 就不再要求 resolved |

**为什么这条要写死在代码里**：第 122 轮之前 `redteam.py` 的 `SPEC` 只有 7 板，而 `paper.tex` 有 12 节
—— 5 段正文（题面重述 / 假设 / 符号 / 自我评价与扩展 / 结论）从来没有独立审核者，
而 gate 照样报「七板七角色，13 条 finding 且均已关闭」。**用 7 个角色名掩盖 5 段没人审的正文，这就是自欺。**

---

## 生态飞轮（第 123 轮定形，每圈都跑）

**这个插件的产出不是一个 PDF，是一条循环：做工作 → 成果写进论文 → 红队攻 → 分诊 → 修 → 再攻。**

六环，每环都有独立仪表；只有每环可测，整圈才不会空转：

| 环 | 内容 | 仪表 |
|---|---|---|
| 1 | 做工作（改代码/改论文） | `python tests/run_all.py`（**344 s**）、`python tools/attack_self.py`、`python tools/e_verify.py` |
| 2 | **成果写进论文**（算出来的必须进正文） | `python gate.py out/final`（numbers）、`python tools/live_vars_check.py` |
| 3 | 红队攻（板数 = 论文 `\section` 数） | `python redteam.py roster`、`python redteam.py out/final` |
| 4 | 分诊（四态：fixed/blocked/rejected/open） | `python tools/triage_findings.py` |
| 5 | 修（改论文 + 更新证据 + 重盖章） | `python gate.py out/final --stamp` |
| 6 | 台账（这一圈净修几条） | `python tools/flywheel.py --log` |

一条命令看六环：

```powershell
& $py tools/flywheel.py            # 快照 + 断点
& $py tools/flywheel.py --log      # 追到 out/flywheel_ledger.jsonl
& $py tools/flywheel.py --history  # 净修曲线
```

**每环实测会怎么骗人**（都踩过）：

| 环 | 骗法 | 后果 |
|---|---|---|
| 2 | 只判带小数的 token | `29 checks`/`51 of 51`/`30 rounds` 全是整数 → 静默过时，gate 还报「100% 可溯源」 |
| 3 | 拿错基准 | conclusion 板拿 `out/d2026c`（DWTS）的 10 问去要求 `out/final`（工具论文）→ 假 finding，必须能 `rejected` |
| 4 | 「未处理」当关闭 | 40 条 finding 全报「已关闭」，正文一个字没改 |
| 4 | 整板说明代替单条关闭 | 一条 review 4 条 finding，修 1 条让另 3 条跟着变色 |
| 5 | 改论文让 evidence 失效 | 这是**正确行为**（防造假），用 `close_finding.py`/`patch_finding.py` 指到新文本 |
| 1 | 仪表自己超时 | run_all 344 s，给 300 s 会把正常一圈读成「断」 |

**判定口径**：`gate` 唯一的红项应当是 `软 redteam` 的 open 数 —— 那是论文的真实缺陷清单，不是仪表故障。
`环 4` 通了（open=0）才叫这一战打完。

---

## 围栏有效性的举证要求（第 123 轮，硬规矩）

**报「拦住 N/M」本身证明不了任何事。** 三处可以被自己操控：样本是自己选的、期望是自己定的、判定是自己写的。前两条无法根除（一个作者、一个语料），**第三条必须根除**。

| 要说的话 | 必须附的证据 |
|---|---|
| 「这道门能拦住 X」 | **构造出来的 X 样本** + 该门报错的输出 |
| 「这套判据有效」 | `python tools/fence_mutation.py` 输出「假测试 0/N」 |
| 「测试通过了」 | 说明样本是**构造缺陷**还是**只读当前状态**；后者不算测试 |

### 样本必须同时满足两条，缺一条就是假测试

1. **构造缺陷**（不能读已被修好的当前状态）
2. **调用真围栏**（不能把围栏逻辑抄进样本）

第 123 轮两次踩坑，都是变异测试抓出来的：

| 自欺 | 症状 | 变异测试怎么抓 |
|---|---|---|
| 复制围栏逻辑 | 把真围栏改坏，样本照样报「拦住」 | 改坏 `freeze._match_written` → 样本不变 → 假测试 |
| 只读当前状态 | 围栏改成「永远成立」，样本照样报「拦住」 | 改坏 `i11`/`i12` → 样本不变 → 假测试 |

### 唯一站得住的验证：变异测试

```powershell
python tools/fence_mutation.py     # 期望「假测试 0/4」
```

把每道围栏改成「永远通过」，对应样本必须变成「漏检」。改坏了不报错，那条测试就是假的。

**变异器自己也会错**：`i11(spec=...)` 带参数，变异写成 `lambda: ...` 会 `TypeError`，被误读成「没变化」。修成 `lambda *a, **k: ...` 才 4/4 敏感。

### 仍不能证明的事

- 未知缺陷的检出率（样本全是已知的坑）
- 期望本身对（如「合法舍入该放行」也只是判断）

**禁止的写法**：「我检查过了，没问题」「gate 全绿，所以是对的」「36/36 可溯源」（不说明分母口径就是废话）。

**调查报告**：`out/围栏有效性调查.md`（两处自欺的完整过程 + I12 抓出孤儿图的链条）。

---

## 转义规矩（第 124 轮，硬规矩）

**这一条不是「AI 的失误」，是工具链缺防呆。** 本项目的写文件操作有一半是经
PowerShell 的 heredoc (`@"..."@`) 传给 python 的，而 **PowerShell 用反引号做转义**，
于是这些字符被静默改写：

| 写了 | 变成 | 后果 |
|---|---|---|
| `` `a `` | **BEL** (`\x07`) | 看不见，但 `` `aidc2026` `` 变成 `<BEL>idc2026` |
| `` `t `` | **TAB** (`\x09`) | 在 Markdown 表格里破坏对齐 |
| `` `b `` | **BS** (`\x08`) | `` `baidu` `` 变成 `<BS>aidu` |
| `` `f `` | **FF** (`\x0c`) | `` `falsify` `` 变成 `<FF>alsify` |
| `` `n `` | **LF** | 字符串里凭空多一个换行 |

**实测踩到 6 次**，其中 3 处污染一直留到了 v8 和 README 里，是 `check_write.py` 抓出来的
（`` `analysis` ``/`` `falsify` ``/`` `ai_taste` `` 三个词的开头各被吃掉）。

### 两条规矩

1. **含反斜杠、反引号、引号的内容，用 `write` 工具直接写，不经过 shell。**
   这是第一道防线，但它靠记性。
2. **写后跑 `python tools/check_write.py <file>`。** 这是兜底，因为它不靠记性。

### 工具抓什么

| 类 | 判据 |
|---|---|
| **BEL / NUL / BS / FF / ESC** | 任何文本文件都不该有 |
| **TAB** | `.md` / `.json` / `.txt` 里禁止（`.py` / `.tex` 允许） |
| **零宽字符**（`\u200b` / `\u200c` / `\u200d`） | 任何文本文件都不该有 |
| **UTF-16 BOM** | `out/` 下 48 个 `.txt` 就是这样——**PowerShell 的 `>` 默认写 UTF-16** |
| **CR/LF 混用** | 同一文件里不许混 |
| **BOM 出现在文件内部** | 只许在开头 |

```powershell
& $py tools\check_write.py --selftest          # 先自校：干净样本放行，三类污染抓住
& $py tools\check_write.py AGENTS.md README.md # 扫指定文件
& $py tools\check_write.py --dir out           # 扫目录
```

**自校用的是构造样本**（4 个：1 干净 + TAB/BEL/零宽各 1），不是读当前文件——按围栏规矩。

---

## 图必须逐张打开看（第 124 轮，硬规矩）

**用户点出来的缺口。** `figcheck` 只看技术规格：DPI / 尺寸 / 背景色 / 长宽比 / 是否矢量。
**它不打开任何一张图看里面画了什么。** 它报「均分 8.0/10（24 张，A24）」时，
给人的印象是「图都很好」—— 那是**技术分，不是内容分**。

### 实测踩到的两类

1. **图内标题与 caption 说同一句话**
   matplotlib 的 `ax.set_title(...)` 与 LaTeX 的 `\caption{...}` 意思重叠，
   读者在图上方和下方各读一遍。A/B 那四张图就是这样，被外部评审点出来。
2. **孤立图**
   定义了 `\label{fig:x}` 但正文一次没有 `\ref{fig:x}`。
   `gate` 的 refs 项只在部分情况下抓，需要专门查。

### 两道可机械判的检查

```powershell
& $py tools\fig_visual.py out/final        # 图内标题 vs caption + 孤立图
& $py tools\fig_visual.py --selftest       # 先自校：三类句子必须分得开
```

| 判据 | 阈值 |
|---|---|
| 图内标题与 caption 相似度 | ≥0.75 判「几乎逐字重复」；≥0.45 判「意思重叠」 |

**相似度按去停用词后的词重叠 / 较短句词数**，不是编辑距离。

**映射必须按 `savefig` 路径建立「脚本 → 输出文件」**：
- 按脚本名匹配 → 全场 sim=0（脚本名不含图名，实测踩到）
- 按「所有标题 × 所有 caption」→ 张冠李戴（实测出 4 个误报）

### 机械做不了的部分 —— 出稿前必须人工逐张看

工具会打印「逐张人工核对清单」。至少核这五项：

1. **坐标轴标签可读** —— 缩到论文宽度后还看得清吗
2. **图里有数据** —— 不是空白、不是只有框架
3. **图与正文一致** —— 正文说 x 上升，图里 x 就不能是平的
4. **没有截断** —— 边距是否裁掉了标签或图例
5. **灰度可辨** —— 黑白打印时颜色还能区分吗

**禁止的写法**：「图都检查过了」「figures 门绿了所以图没问题」。
要写就写清：看了哪几张、核了哪五项、发现并改了什么。

---

## 题面必须落地、逐字引用、逐问回应（第 123 轮，硬规矩）

用户的原话：**「要约束 LLM 认真地读取题目信息，不允许猜，不允许跳过！」**

### 这三件事原来零约束

`paper.tex` 里有 `\section{Restatement of the problem}` 就算过 —— 而这一节**完全可以凭记忆写**。
实测 `out/d2026c`：目录里**没有任何题面原文**，正文的 `What the problem asks` 是
「The task is to reconstruct it, to say how much confidence..., to compare..., to quantify...」
—— 这是转述。转述不是错，但**无法核实它是否忠实**：读者不知道题面是不是真的这么问。

### 新门 `chk_prompt`（gate 第 33 项）三条判据

| | 判据 | 抓什么 |
|---|---|---|
| **A** | `out/<dir>/题目.md`（或 `prompt.md`/`题目.txt`）存在，且 **≥200 字符** | 题面没落地 → 「认真读题」无从核实 |
| **B** | `paper.tex` 的 Restatement 里有 **≥40 字与题面逐字连续一致**（比对前归一 LaTeX 转义与空白） | Restatement 是凭空转述 |
| **C** | 题面的编号小问（`(1)`/`1.`/`Problem 1`/`问1`）**全部**在正文被回应 | **跳过某一问** |

`deliverable` 目录判 FAIL，非交稿判 WARN。

### 开工第一步

```powershell
# 1) 先把题面原文存成 out/<dir>/题目.md（不许用概括代替）
# 2) 从 runs.json 的 problem 字段能自动落地的，只是**题名**，不是原文：
& $py tools\prompt_fidelity.py --seed      # 只写题名，不能代替原题
# 3) 查
& $py tools\prompt_fidelity.py --all       # 只扫 deliverable 目录
```

**`--seed` 的能力边界（实测）**：`runs.json` 的 `problem` 字段只有 **9–52 字符**
（`heat sink`、`forecast monthly sales from price and advertising`），那是**题名**。
所以 `--seed` 写出的 `题目.md` 只有 100 来字节，过不了 A 条的 200 字符门槛 —— **必须人工补原文**。

### 实测（两份交稿都红，这是正确结果）

```
out/final    FAIL  没有题面原文 —— 正文的 Restatement 可能是凭记忆转述的
out/d2026c   FAIL  题面只有 112 字符（< 200）；正文与题面没有 40 字以上逐字一致片段
```

**这不是插件故障**：`out/d2026c` 的题面（2026 MCM Problem C 全文）**从来没有存进插件**，
而 `out/final` 是方法论文，题面是「写这篇论文要回答什么」，也一样没存。
**补原文是人的活，我不能编。**

---

## 先查文献再动手（第 123 轮，硬规矩）

**凡是要引入一个方法论，先搜它的学术名称，再动手。** 自己推理一遍的代价不是「慢」，是**漏掉已知的反例**。

| 触发 | 动作 |
|---|---|
| 要用「变异测试 / 改坏检查看测试报错」 | 搜 **mutation testing**（Jia & Harman, IEEE TSE 2011） |
| 要用「样本通过率」当有效性证据 | 搜 **mutation score confidence**（Holling et al., Nequivack, ICSTW 2016）—— 分数是估计量，**有置信区间**，12 个样本的 11/12 不能当点估计 |
| 要声称「多个独立审阅 / 独立实现」 | 搜 **multiversion programming**（Knight & Leveson 1986）—— **独立实现并不独立**，共用同一底座模型的多个 agent 更不独立 |
| 要用「结论在参数域上恒成立」 | 搜 **metamorphic testing**（Chen et al.）与 **global sensitivity indices**（Sobol 2001） |
| 要断言「这件事做不到 / 只能这样」 | 搜有没有**不可能性结果**（如 *A Theory of Black-Box Tests*, arXiv:2006.10387：非平凡禁令在任何测试框架下不可验证） |
| 要引用名言（如 Dijkstra） | 查原话与常见误引，别引二手版本 |

**禁止**：把「我是这么想的」当成方法论依据。凡要写进本文件或论文的做法，必须有文献名或实测数据。

**为什么加这条**：前 12 轮我自己推出了「变异测试」「变异分数不可当点估计」「独立审核不独立」「证明有边界」—— 这四件事文献里都有，而且**都比我说的更严格**。最刺眼的是我还把「12 板独立审核」当优点写进了论文，而 Knight-Leveson 1986 早就否证了那个前提。

对照表与完整出处：`out/文献与论证对照.md`。

---

## 例子必须逐字核对（第 123 轮，硬规矩）

**`\code{}` 里的字面量和正文里的整数例子，`numbers` 门都看不见** —— tokenizer 会 blank 掉 `\code{...}` 的参数，而整数本来就不在判定范围内。两件事叠加成一个盲区。

### 实测事故（这一条是拿自己的错误换来的）

我写「take one page of the heat-sink report. It prints a fitted coefficient to six decimals, a **table row numbered `12`**, a **year `2019`** copied from the input file, and a **significance level `0.05`**」。

核实结果：

| 我写的 | heat_sink 实际 |
|---|---|
| 六位小数的系数 | ✓ 真（`0.007434`） |
| 「`2019` 年的年份」 | **0 次命中，这篇根本没有年份列** |
| 「编号 `12` 的表行」 | `12` 是 Pareto 表**第一列的设计编号**，不是行号 |
| 「`0.05` 显著性水平」 | 实际是 Breusch–Pagan 的**临界值** |

**三个例子两个是编的，而 gate 全绿。**

### 规矩

| 要写 | 必须做 |
|---|---|
| 引用某篇报告里的数/标识符 | 到**那个文件**里逐字 grep 一次，确认行号 |
| 举一个假想的例子 | 正文写明 `for instance` / `say`，**不要**写成 `the report prints` |
| 用 `\code{}` 包 | 它逃过 `numbers` 门，所以**更要核对** |

**工具**：`python tools/example_audit.py` —— 列出所有 `\code{}` 含数字的项，报每个字面量在哪些工件里找到。

**但「找到 ≠ 对」**：`12` 在 36 个文件里都有，`0.05` 在 27 个里都有 —— 工具能证明「这个字面量存在于语料」，**不能证明它出现在正文声称的那一篇里**。最后一步只能靠人去核对。

---

## 稿件级的四条规矩（第 125 轮，硬规矩）

**这一节管的是「稿子本身」，不是「门」。** 四条都不是排版偏好，每一条都对应一次真实事故。

### 1. 每个 `\bibitem` 必须至少被 `\cite` 一次

**判据**：`set(\bibitem 的 key) − set(\cite 里的 key)` 必须为空。

**事故**：`aidc2026/big/main.tex` 有 12 条参考文献，`\cite` 次数为 **0**。
等于把「读过这个领域」的证据放在那里不用，审稿人第一条就会问「相关工作在哪」。
修法是补 4 条 LLM 领域引用（FActScore / HaluEval / Lost in the Middle / Black-Box Tests）
并让 16 个 key 全部被引。

**注意**：`\bibitem` 有而 `\cite` 无，是**死引用**；`\cite` 有而 `\bibitem` 无，是
**未解析引用**（编译期会报 `Citation undefined`，反而容易发现）。**难发现的是前者。**

### 2. 时间只写「文件系统里真的留下了时间戳」的项，其余写「未记录」

**判据**：出现年份或时刻的单元格，必须能追到一个文件的 `mtime` 或一行日志；
追不到的，写「未记录」。

**禁止**：写「大约 2024 年」「应为本月初」这类推断。

**为什么这条最要紧**：它不是排版要求，是**本文的判据本身**——
没有记录的时间不能事后追认，只能如实标空。

**已落地的地方**：`aidc2026/big/main.tex` 的 `tab:phases` 末列，
6 行里 3 行是「未记录」，只有 R124/R125 有真实时间戳
（`ablation_ab.json` 的 05:14:27、`quality_doors.py` 的 12:40:39）。

### 3. 正文不许出现手写的 `§2.5`，一律用 `§\ref{label}`

**判据**：`grep -n '§[0-9]'` 必须为 0。

**事故**：同一份稿子里有两处 `§2.5`，而「一次自欺的形状」实际是 **§2.4**。
**手写节号在插入新节后会静默错位**，而读者会以为「没有这一节」——比编译错误更难发现。

**修法**：给目标节加 `\label{sec:xxx}`，正文改 `§\ref{sec:xxx}`。

### 4. 摘要里的计数必须等于实际对象数

**判据**：摘要里出现「三次 / 四次 / 35 项」这类计数时，必须与正文的实际数目一致。

**事故**：加了第四次转折之后，摘要仍写「三次由该工具自己抓出来的自欺」——
因为「三次」被 `\textbf{}` 包着，一次 `replace` 匹配不到，差点漏掉。

**这条是弱规矩**（通常写完就忘），但**代价低、查起来快**，所以列进来。

---

### 这四条都能做成 gate 检查，但暂时没做

| 门 | 判据 | 成本 | 状态 |
|---|---|---|---|
| `bibcov` | `\bibitem` − `\cite` 差集为空 | 20 min | **未实现** |
| `timesrc` | 含年份的单元格必须有 `mtime` 来源或写「未记录」 | 40 min | **未实现**（半可判） |
| `refhard` | `§\d` 计数为 0 | 15 min | **未实现** |
| `abscount` | 摘要计数 = 实际节数/项数 | 30 min | **未实现**（需定义"实际"） |

**没做的原因不是难，是优先级**：这三条都是「稿件级」的，而 gate 现在只管
「交付目录级」。等 `proof` / `iterlog` 自己的构造样本补上（X 从 4 到 6）之后再说。

**在那之前，这四条靠人工执行**——所以写在这里，而不是只写在某一篇稿子的备注里。

---

## 交付标准（第 123 轮进 gate，对**每一份** deliverable 生效）

用户的原话：**「不是只有这篇论文是，而是用这个插件必须要遵循如此的规则。」**
所以下面四条写进 `gate.run_all`，不是对某一篇的建议：

| 门 | 门槛 | 为什么 | 覆盖方式 |
|---|---|---|---|
| `refs` | **≥ 10 条文献**，且每条有 `\cite` | 文献量不是装饰：评委据此判断作者读没读过这个领域 | `<figdir>/standard.json` 的 `min_bib` |
| `figures` | **≥ 6 张图** | 只查质量不查数量，「4 张图 + 9 张表」会拿满分；但评委翻页第一印象是图 | `min_figs` |
| `sensitivity` | **实质性**：① sensitivity/robustness 表述 ② 一个参数范围（`0.30--0.70`/`±10\%`）③ 扰动后的判断（unchanged/stable/结论不变） | 敏感性分析是分水岭之一；只查关键词会被堆词通过 | 缺哪件点名缺哪件 |
| `significance` | ① 置信/区间/误差的表述 ② **一个具体区间或误差数值**，且**不能是 `[0,1]` 这种定义域** | 对应 **NeurIPS Paper Checklist 第 7 项**（Experiment Statistical Significance）：只给点估计等于不知道自己多不确定 | 平凡区间在代码里排除 |
| `redteam` | 按 `\section` 数，每板一份审核 | 已在「红队规矩」一节 | — |

**三源对照**（本地 / `purge` / NeurIPS 清单）：`out/围栏三源对照.md`。从 `purge` 借鉴了「逐项计数 + 缺口点名 + 分类」，从 NeurIPS 补了 `significance`；**仍缺**「数据代码开放声明」（第 5 项）、「实验设置细节」（第 6 项）、「审计流水」。

**门槛值本身是设计选择不是定理**（优秀论文的文献量/图数只有经验区间），所以：
① 写成模块常量，可被 `standard.json` 覆盖；② 结论行打印「实际值 / 门槛」；③ 只对 `_is_deliverable` 为真的目录生效。

### 关键教训：不写 `deliverable: true`，所有交付标准都不生效

实测：`out/d2026c`（17 页手工竞赛稿）的 `declaration.json` 只写了 `no_dataset`，**没写 `deliverable`** → 文献下限、图数下限、敏感性门、红队分板**四道全不生效**，gate 报「4 张图 8.0/10」，看着比交稿还漂亮。

补上 `"deliverable": true` 之后，它立刻暴露 **5 个真缺陷**：

```
[FAIL] numbers    70/72 + 冻结表没写 generated_from（交稿要求能追到生成它的脚本）
[FAIL] refs       全文 0 条 \cite
[FAIL] redteam    没有 redteam.json —— 论文 12 个板块都没有审核记录
[FAIL] figures    只有 4 张图，低于交付下限 6 张
[OK  ] sensitivity  有扰动范围（3 处）且有扰动后的判断
```

**其中 `generated_from` 和 `redteam` 两条，在补声明之前完全看不见。**

**规矩**：新建任何准备拿出去的目录，第一步写 `declaration.json` 且带 `"deliverable": true`；不写就是「草稿」，所有交付标准静默豁免。

---

## 这个目录里有什么

| 文件 | 是什么 |
|---|---|
| `插件速查.md` | **先读这个**。一页纸总览 |
| `mmkit.py` | 统一入口，23 个子命令（以 `schema.json` 的 `n_commands` 为准） |
| `mm.py` / `engine.py` | 计算内核 |
| `paper.py` | 出稿（**自动模式**，DSH 主导时不用） |
| `verify.py` / `falsify.py` / `lanes.py` | 验证三件套 |
| `gate.py` | 23 项质量门（实测 `len(run_all(...)['checks'])`） |
| `schema.py` → `schema.json` | 能力清单（含每个命令的 desc 和实际读取的参数） |
| `contract.py` / `orchestrate.py` | 提案契约 + 试错循环。**已接进主流程**：`mmkit.py contract --proposal` / `mmkit.py experiment`（实测可用；已进回归链） |
| `runs.json` | 23 道题的配置（数据 / y / x / min / 题面 / 产物目录） |
| `tools/battle.py` | 按配置批量跑 |
| `tools/verify_all.py` | 逐题过 gate + 回归 + 补丁 |
