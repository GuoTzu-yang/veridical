# 优化记录（第 80 轮）

目标：把「跑一次要等多久」降下来。所有数字都是本机实测，可复现的命令写在每节末尾。

## 总账

| 指标 | 优化前 | 优化后 | 倍数 |
|---|---|---|---|
| `mmkit.py run`（全流程） | 21.37s | 0.35s（热）/ 0.75s（冷） | **28~61x** |
| `ledger.py replay` | 113.52s | 53~66s | **~2x** |
| 完整回归（50 套件） | 325.2s | 148.2s | **2.18x** |

验证方式：`python tests/run_all.py` 全部 ALL PASS（退出码 0），
改动前后断言数不变（CORE 12 项 + SUITE 36 项）。

---

## 一、`mmkit run` 21.4s → 0.35s：找文件，不是算数学

**症状**：84 行数据跑一个数模流程要 21.4 秒。

**剖析**：`cProfile` 显示 10.8 秒里 **10.5 秒在 `glob.glob("**/*.xlsx", recursive=True)`**，
真正算东西不到 0.3 秒。

**根因**：工作区里的 `knowledge-base/` 有 **298,402 个文件**，
递归 glob 会把它整个走一遍（3.86 秒纯遍历，glob 自身开销更大）。
而这个慢搜索在 `mm.py` 和 `lanes.py` 里**各写了一遍**。

**做法**：
1. 新建 `datapath.py` 作为唯一来源，`mm.find_xlsx` 与 `lanes.load_apmcm` 都改成调它
2. 用 `os.walk` + 就地剪枝 `dirnames[:]` 跳过 `knowledge-base` 等大目录
   （`glob` 的 `recursive=True` 做不到剪枝）
3. 磁盘缓存扫描结果（缓存**列表**而不是单个路径）

**踩到的坑（都被自己的断言逮住）**：
- 第一版缓存了「最终选中的那一个路径」，于是 `prefer` 参数在缓存命中时被忽略，
  `lanes.load_apmcm` 要的「附件 2」拿不到 → 改成缓存扫描结果、检索时再按 `prefer` 排序
- 缓存里的文件被挪走后会返回死路径 → 排序时剔除不存在的文件

**复现**：
```bash
python datapath.py                    # 15 项自检
MMKIT_REFRESH=1 python mmkit.py run --y 热阻 --x 宽度,深高,排数   # 冷启动
python mmkit.py run --y 热阻 --x 宽度,深高,排数                   # 热启动
```

---

## 二、`ledger replay` 113.5s → 53s：两处纯浪费

**症状**：一个自检跑两分钟。

**剖析**（按域分组计时）：

| 域 | 样本数 | 耗时 |
|---|---|---|
| http | 12 | 77.53s |
| sql | 10 | 34.77s |
| data | 46 | 0.65s |
| explain | 10 | 1.54s |
| file | 14 | 0.00s |
| image | 7 | 0.37s |

**浪费一：重复执行。** http 域 12 条里 **6 条是逐字相同的 task**
（`github.com` / `example.com` / `.invalid` / `ftp://` / `not-a-url` 各两次）。
同一个 task 跑两次结果必然一样 —— 单这一项 114.4s → 76.7s。

去重粒度是 **task 而不是记录**：两条记录 task 相同但当初记的 `success` 可能不同，
重跑后各自跟自己的记录比。**语义零变化已逐一验证**：

```
ok 91 / drift 0 / unavailable 8 / no_spec 64  —— 去重前后样本 ID 集合完全相同
```

**浪费二：超时窗口过长。** 实测 6 个 URL 里 **3 个各自跑满 12 秒超时**
（`github.com` 不可达、`ftp://` 的 urllib handler 直接挂死、404 仓库同样不可达）。
而 replay 判的是**漂移**，超时归入「环境不可用」不算漂移 ——
窗口从 12 秒收到 5 秒**不削弱漂移检测**（活探测仍用 12 秒，网络余量不打折）。
76.7s → 53s。

**复现**：
```bash
python ledger.py replay
```

### 补充：replay 剩下的 60 秒到底是什么（第 80 轮二次核查）

第一次归因写成「sql 域 36 秒」，**不准确，已修正**。逐条实测：

```
replay 的 11 条 sql 任务：
  逐条跑合计  1.57s
  一次批量跑  0.19s
  （最快的 0.12s，最慢 0.29s —— 没有慢查询）
```

`systemctl start seekdb` 在服务**已运行**时也只要 0.15~0.21s。

所以剩下的 60 秒来自：**seekdb 没在运行时，`systemctl start` 要真的启动它（约 28~35 秒）**。
而 seekdb 跟着 WSL 一起被回收（见第四节），所以只要某次 SQL 调用距离上一次超过约 20 秒，
就要重付这 30 秒。

`replay` 里 http 段仍占 ~17s：3 个不可达 URL 各跑满 5 秒窗口。
没有继续收窄到 2 秒 —— 那会让"慢但活着"的 URL 从 `ok` 变成 `unavailable`，
是拿检测覆盖换速度，不值。

---

## 三、回归 325.2s → 148.2s：查 FTS 虚表，查错了对象

**症状**：`kb.py selftest` 49.85s，`extend.py` 45.55s。

**剖析**：`kb.stats()` 一个函数占 31.85 秒。它查的是 `files` 表 ——
而 `files` 是 **FTS5 虚表**（298,500 行），
`SELECT count(*)` / `DISTINCT` 在它上面只能全表扫，**单条约 2 秒**。

**根因**：库里本来就有两张普通表装着同样的信息：

| 表 | 行数 | 内容 |
|---|---|---|
| `meta` | 298,500 | 每文件一行，带 `repo` |
| `repos` | 30 | 每仓库一行，带 `category` |

**做法**：`count(*)` 与 `DISTINCT repo` 改查 `meta`，`DISTINCT category` 改查 `repos`。

**结果逐项比对（不验证就换＝拿正确性换速度）**：

```
原始（FTS）   count 2.036s + repo 2.104s + category 1.908s = 6.048s
候选（普通表） count 0.020s + repo 0.026s + category 0.000s = 0.046s
                 → 131 倍
文件数相同: True (298500 vs 298500)
repo 列表逐字相同: True (30 个)
category 列表逐字相同: True (21 个)
```

收益是双份的：`kb.py` 49.85→2.62s，`extend.py` 45.55→0.26s
（`extend.py:1054` 也调 `_kb.stats()`）——合计 **-92.5 秒**。

**复现**：
```bash
python tools/verify_kb_stats_equiv.py   # 证明两种实现结果相同
python kb.py selftest
```

---

## 四、试过但**做不到**的：WSL 常驻

**动机**：回归里 `harness.py` 呈双峰 —— 1.32s（WSL 热）/ 38.49s（WSL 冷），
`probe.py` 同样 0.25s / 39s。冷的那一次付的是
「WSL 引导 ~6s + `systemctl start seekdb` ~28s」。
若几个套件各付一次，合计约 110 秒。

**尝试（三条路，全失败）**：

| 做法 | 结果 |
|---|---|
| `nohup setsid ... sleep infinity &` | 随 wsl.exe 会话一起被带走，`pgrep` 只匹配到自己 |
| `systemd-run --unit=m1-wsl-keeper sleep infinity` | 单元确为 `active`，实例仍在 ~25 秒后终止 |
| 交替 A/B 计时（2 轮） | 同条件两次差 36s > 两种条件差 7s，**在噪声内，测不出收益** |

**结论**：WSL2 实例在最后一个命令后 **20~25 秒**必然终止，
回收看的是「有没有 wsl.exe 会话」，**不看 systemd 服务状态**。
仓库内部无法保活，代码已撤（撤掉后仍是 ALL PASS）。

**真要消除**：只能改 `%UserProfile%\.wslconfig` 的 `vmIdleTimeout`。
当前该文件只有 `memory=8GB / swap=4GB`，没有这一项。
**这是机器级改动**（会一直占着 8GB 的 VM），影响这台机器上所有项目，
不属于本仓库能单方面决定的事 —— 所以只报告，没有擅自改。

**复现**：
```bash
python tools/probe_wsl_lifetime.py   # 看实例在调用之间怎么退出
```

---

## 五、测量工具本身也错过一次

第一版 `tools/time_suites.py` 用「先找 `tests/` 再找根目录」解析脚本路径，
于是 CORE 里的 `probe.py` 实际跑的是 `tests/probe.py`（另一个脚本），
耗时归属整个错位（报 39.2s，真值 0.22s）。

`run_all.run()` 的规则是 `os.path.join(cwd, script)`：
**CORE → 仓库根，SUITE/ENTRY → tests/**。已按这个改回来。

教训与仓库一贯记录一致：**检测器自己也要先被验证**。

---

## 六、留下的工具

| 工具 | 用途 |
|---|---|
| `tools/time_suites.py` | 逐套件计时（路径解析已与 run_all 对齐） |
| `tools/verify_kb_stats_equiv.py` | 证明 kb 优化前后结果逐字相同 |
| `tools/probe_wsl_lifetime.py` | 观察 WSL 实例生命周期（为将来的决策留证据） |

其余一次性诊断脚本在记录完成后已删除；它们的结论都在上面。

---

## 七、还没做的

- WSL 冷启动（约 110s/轮）需要机器级配置，见第四节
- `probe._do_sql_batch` 的 40 次轮询在 seekdb 真起不来时会空转 40 秒。
  实测 `systemctl start seekdb` 是阻塞的（返回即就绪），所以这条路径罕见，
  暂不优化 —— 没有证据表明它常发生
- `replay` 的 http 段仍剩 ~17s（3 个不可达 URL × 5s 窗口）

---

# 优化记录（第 81 轮）：四个洞，其中三个在自己的检查器里

起点：用户要求「优化插件 排查漏洞 迭代升级」。这一轮没碰算法，只查护栏 ——
结果四个洞里有三个在**检查器自身**：假绿、串题、假阳性。

## 总账

| 项 | 修复前 | 修复后 | 怎么证的 |
|---|---|---|---|
| 假绿（检查没跑成算通过） | `--strict` 是可选；判据靠 detail 文本匹配 | 默认严格；`na_kind=absent\|failed` 类型化 | 打开严格后 22 题立刻红，说明之前全是假绿 |
| 数据表定位 | `mm.find_xlsx()` 恒返回 APMCM B 题附件 | 显式 → runs.json → `out/data/<题名>` → 放弃并说明 | 23 题各拿自己的表；`_resolve_data` 4 项断言 |
| abs_page | 12 题误判跨页；真跨页可能漏判 | 主判据＝「摘要结尾是否落在第 1 页」 | 长短摘要双向对照（短 PASS / 长 FAIL） |
| 补丁账本 | 断言挂在注释文字上，改注释即 113/114 | 断言挂在生成的字体声明上 | 114/114 |

## 一、假绿：22 题的 leakage 从未在正确的表上跑过

**症状**：`gate.py` 对 23 道题全绿。

**根因两层**：
1. `chk_leakage` 抛异常时返回 `N/A`，而硬门的 `hard_ok` 把 `N/A` 当通过。
   代码里本有 `--strict` 把「检查没跑成」降级为 FAIL，但**默认关闭**。
2. 判定「是不是没跑成」靠 `_NA_ERR_MARK` 匹配 detail 文本。
   文案里出现 `KeyError` 就算崩溃，自定义异常名（`MyBug`）就漏。

**做法**：
- 新增 `NA_ABSENT / NA_FAILED` 与 `_na / _na_err / _is_failed_na`；
  异常路径统一走 `_na_err`，17 个 except 返回点全部改写。
- `run_all(strict=True)` 改为默认；新增 `--lenient` 恢复旧行为。
- `_na_is_error` 保留为 legacy 兜底（没带 `na_kind` 的老调用点）。

**证据**：打开严格后 22 题 FAIL 是第一步；再查 detail 才发现下一层洞。

## 二、串题：`mm.find_xlsx()` 让 22 道题共用一张表

**症状**：恒报 `KeyError: 没有数值列 'placement'；有 ['样本编号','针肋宽度比','歧管深高比',…]`。

**根因**：`chk_leakage` / `chk_falsify` 在没有 `--data` 时调 `mm.find_xlsx()`，
那是在**工作区里找一个 xlsx**。实测它恒返回 APMCM 2026 B 题附件（热阻表），
于是 22 道题拿热阻表去查自己的 `y` 名，必然 KeyError，必然 N/A，必然绿。
也就是说这道硬门**从未在正确的表上执行过**。
（`chk_leakage` 的 docstring 早就写着这个风险，但代码里的兜底没删。）

**做法**：
- 新增 `_resolve_data(figdir, data)`：显式路径 → `runs.json` 登记（先按题名，
  再按**产物目录反查**，因为 `dwts2026c` 的目录叫 `out/d2026c`）→
  `out/data/<题名>.xlsx` → 放弃并说明原因。**不再扫描工作区。**
- 新增 `_pick_col(ds, name)`：精确 → **唯一**包含匹配（「热阻」→「无量纲热阻」），
  多解则放弃，不猜。
- 拿不到表时：`leakage` 报 `failed-N/A`（硬门没跑成不能绿）；`falsify` 同理。
- `heat_sink` 的表补进 `out/data/heat_sink.xlsx`（原文件在 apmcm2026 题库里）。

**结果**（23 题）：
- 修复前：leakage 22 × FAIL(检查未执行，因为我传错路径) 或 22 × N/A(静默)
- 修复后：**15 PASS / 8 WARN / 0 FAIL**
- 8 条 WARN 全部落盘 `out/arch/leakage_findings.json`，带题名、相关系数、解析到的表

**副产品**：论文 `Plugin-Agent-Architecture.pdf` 里那个「8 of 22」得到独立复核。
`dwts2026c` 是后加的 companion 题、不在 8 条之内，所以 8/22 与 8/23 普查一致，
论文那个数不需要改。

## 三、假阳性：`abs_page` 把正文续行当成摘要残留

**症状**：12 道题报「第 2 页正文前残留 1500 字符」。

**根因**：旧判据 B 数「第 2 页第一个章节标题之前的字符」。而章节标题
可能正好落在**第 1 页底部**（queueing 第 1 页底部就印着「1 Introduction」），
此时第 2 页是从句子中间开始的正文续行，正则认不出标题，
于是**整页正文**被当成摘要残留。

**第二层**：`p2 = text[:1500]` —— 报出来的「1500 字符」是判据自己的截断常量，
真实溢出是 1194–1660。把下界当测量值，等于把「不知道多严重」写成「正好 1500」。

**做法**：
- 主判据改为：从 `paper.tex` 取 `abstract` 环境正文 → 归一化成纯字母数字 →
  取末尾 40 字符 → 在**第 1 页**的归一化文本里找。找到＝止于第 1 页。
  这一条不推断版面位置，两个方向的错都不会犯。
- 兜底依次为：正文首节是否已在第 1 页 → Keywords 是否在第 2 页 → 摘要收尾句。
- 长度一律报真实值，不再截断。

**结果**：23 题里 **1 道真跨页**（`nflis`，第 1 页以「because」断句收尾，
已渲染核对）。`paper.py` / `verify_all.py` 里「12 道摘要溢出」的注释
全部更正 —— 那 12 是假阳性，不是模板缺陷。

## 四、补丁账本自损：断言挂在注释上

**症状**：改完注释后 `patches.py verify` 从 114/114 掉到 113/114，
P73 报 `abstract not smaller`。

**根因**：P73 的判据是 `"\small" in paper.py` —— 而 `\small` 只出现在**一句注释**里。
改注释就让已达成的补丁回退成 PENDING。

**做法**：改成断言实际生成的字体声明
`re.search(r"\\begin\{abstract\}[^\]]*\\(small|footnotesize|scriptsize)", paper.py)`。
**断言要挂在行为上，不挂在说明文字上。**

## 新增回归

`tools/test_gate_strict.py`（16 项，退出码 0）：

- A 类型化判定不看文案（absent 带异常词 / failed 文案干净）
- C 老调用点兼容
- B 端到端：坏 JSON 让 `numbers` 抛异常 → 默认 FAIL、`--lenient` 回 N/A（进程内 + CLI 各一遍）
- D 数据表定位：按题名 / 按产物目录反查 / 未知题带原因 / 四题各拿自己的表
- E **abs_page 双向对照**：短摘要必须 PASS、长摘要必须 FAIL
  （只测一边会把自己的判据改松而看不出来）

## 复现

```powershell
$py = "C:\Users\21246\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
cd model1-arch
& $py tools\test_gate_strict.py     # 16 项，退出码 0
& $py patches.py verify             # 114/114
& $py tools\verify_all.py           # 质量门 + 回归 + 补丁
```

## 未做（下一轮）

1. `nflis` 真跨页：模板摘要需要**按预算裁段**（不是再缩字号 —— 已到 `\scriptsize`）。
2. 自动模式应剔除 `|corr(x, y)| > 0.95` 的候选自变量：现在只是**报** WARN，
   治因的做法是在选 `x` 时就剔除。8 条 WARN 里「年份 vs 人口」「pop2000 vs pop2005」
   都属于这一类。
3. `falsify` 仍未从 `paper.tex` 的主张里取检验方向，仍是「取前 3 列当 x、4-5 列当 y」的
   盲测 —— 这条 SOFT 检查目前的信息量很低。
---

# 优化记录（第 82 轮）：把「事后报 WARN」推进到「事前分辨」

起点：第 81 轮结束时留了三项，本轮做掉两项，并新增一条精确度升级。

## 总账

| 项 | 修复前 | 修复后 |
|---|---|---|
| `falsify` 测什么 | `cols[:3]` 当 x、`cols[3:5]` 当 y —— 与论文主张无关 | 23/23 用论文声明的 y/x |
| `falsify` 的「承认」判据 | 字面 `"fails locally"`（d2026c 写的是 `fail locally`）→ 误判没承认 | 正则 `fail(s|ed)? locally`、`no claim of monotonic` 等 |
| `leakage` 阈值 | 一条 0.95 阈值，把「时间趋势共变」和「拿响应当自变量」混为一谈 | 时间/序号列单列一类；8 条 WARN → 5 条真泄漏 |
| 时间列识别 | 无（不存在这个函数） | `_is_time_like`，只认完整词形 |

## 一、`falsify`：名字是证伪，做的是随机稳健性探测

**症状**：23 题结论都是「N 组边际反例」，但没人知道它测的是哪两个变量的关系。

**根因**：
```python
xs = cols[:3]      # 前 3 个数值列
ys = cols[3:5]     # 第 4-5 个
```
与论文声称的任何关系都无关。读者看到「控制后符号仍矛盾」，会以为在检验论文的主张。

**做法**：与 `leakage` 共用 `冻结数字.json` 的 y/x + `_pick_col` 对名；
拿不到才退回盲测，并在 detail 里**明确标注「严格说这是盲测」**，不冒充实测。

**结果**：20 PASS / 3 N/A（数值列不足 4 个）/ 0 WARN。

**副作用（要写下来）**：模板论文恒定声明「局部非单调」，所以这条检查对模板题
几乎没有区分度 —— 它的价值只在「有反例且**不**承认」时才体现。
目前它更像一条「论文有没有诚实交代」的存在性检查，不是证伪。这一点不要忘记。

## 二、`falsify` 的承认判据：差一个 s

`d2026c` 原文是「... hold on average but **fail locally**, and we make no claim
of monotonicity」，而判据写的是 `"fails locally"`（多一个 s）→ `_admits=False`
→ 明明承认了却报 WARN。

改为正则集合：`fail(s|ed)? locally`、`no claim of monotonic`、
`[Nn]ot monoton|non-?monoton`、`local reversal`、中文三种写法。
**关键词匹配不是语义理解**，注释里写清「匹配不到 ≠ 没写」。

## 三、`leakage`：一条阈值混了两件事

8 条告警里：

| 题目 | 相关 | 实际是什么 |
|---|---|---|
| prediction | 月份→销量 +0.968 | **时间趋势**，正当建模 |
| population | 年份→人口 +0.998 | **时间趋势** |
| pop_panel | 1953→2005 +0.987 | **时间轴**（持续性模型） |
| clustering | 消费金额→客户价值 +0.995 | **真泄漏**：响应当自变量 |
| icm2006c | pop2000→pop2005 +1.000 | **真泄漏**：另一年的响应 |
| mcm2020c | total_votes→helpful_votes +0.997 | **真泄漏** |
| review_microwave | helpful_votes→total_votes +0.997 | **真泄漏** |
| review_pacifier | helpful_votes→total_votes +0.985 | **真泄漏** |

用时间解释趋势是模型本身；把它报成「疑似把响应当成了自变量」是假警报，
而假警报会让真警报失效。

**做法**：新增 `_is_time_like`，时间/序号列单独归类，报「属时间/序号列（趋势共变，
不是泄漏）」。结果 8 WARN → **5 WARN**，剩下的 5 条全是真泄漏。

### 这里踩了一个坑，靠双向测试抓到

第一版 `_is_time_like` 用裸字包含（`"年" in name`），于是
**「年龄」被判成时间列** —— 一条真的「年龄→目标」高相关会被静默放过。
测试里那条「拿响应当自变量仍报 WARN」立刻 FAIL，才发现。
改成只认完整词形（年份/月份/日期/年度/季度/周次/期数/时间/编号/序号，
英文按 `\b` 词边界），并把这四个反例加进测试：
`年龄 / 周龄 / 年收入 / 期初库存` 都必须判 False。

## 新增回归

`tools/test_gate_strict.py` 从 16 项扩到 30 项，新增 F 组：

- `_is_time_like` 12 个正反例（含上面四个裸字陷阱）
- 造一份「时间列与响应相关≈1」的表 → `chk_leakage` 必须 PASS 且说明里点出时间列
- 造一份「消费金额≈客户价值」的表 → `chk_leakage` 必须 WARN

## 当前账目（23 题）

| 项 | 值 |
|---|---|
| 硬门全绿 | 22 / 23 |
| FAIL | `abs_page` ×1（`nflis`，真跨页） |
| WARN | `leakage` ×5（全是真泄漏，在模板的 x 选择里） |
| `falsify` | 20 PASS / 3 N/A / 0 WARN |

那 5 条泄漏**不改成绿**：它们是真的（模板把另一个响应当自变量）。
要治因得改 `runs.json` 里那 5 道题的 x 并重跑，而那会让已归档的产物与其配置不一致 ——
两者都要动，属于内容决策，不在护栏里偷偷改。

## 未做（下一轮）

1. `nflis` 真跨页：模板摘要要按预算裁段（已到 `\scriptsize`，不能再缩字号）。
2. `falsify` 的判据太容易满足（模板恒定声明非单调），考虑要求「承认语句必须
   落在 Limitations 节内且带具体变量名」，否则退回 WARN。
3. 5 条真泄漏对应的 `runs.json` x 需要与已归档产物一并重做。
---

# 优化记录（第 83 轮）：把「摘要跨页」修到源头，并纠正上一轮的一个错判

## 总账

| 项 | 第 82 轮末 | 现在 |
|---|---|---|
| `falsify` | 20 PASS / 3 N/A / 0 WARN | **23 PASS / 0 N/A / 0 WARN**，且每条报出证据节名 |
| 摘要跨页 | `nflis` 真跨页（模板无机制） | 模板加**词预算删段**；重新生成后 `abs_page` PASS |
| 护栏自测 | 30 项 | **40 项** |

## 一、上一轮我判断错的一条：「必须在 Limitations 节」

第 82 轮我提议「承认语句必须落在 Limitations 节内」。这一轮先查了事实：

| 论文 | 有叫 Limitations 的节吗 | 承认语句实际在哪 |
|---|---|---|
| 模板论文（queueing/nflis/…） | **没有** | `Evaluation` |
| d2026c | **没有** | `What each claim rests on` |

按标题硬判会把 20 篇合格论文打成 WARN。**这条提议本身是错的**，已撤回。

改为：`_admission()` 只**报出证据所在节名**（`论文「Evaluation」节已承认`），
不假装能判断位置是否恰当。护栏该给证据，不该给没有依据的判决。

## 二、`falsify` 列数门槛：4 → 2，但不能只改数字

`len(cols) < 4` 是「前 3 列当 x、后 2 列当 y」盲测时代留下的。改用论文声明的
y/x 后只需 2 列。

但只改数字会**引入一个更糟的错误**：没有第三个数值列时 `signs` 为空，
原代码会落到「控制后符号一致（来自混淆）」那条 PASS —— 明明没做控制，
却说控制后一致。所以新增 `uncontrolled` 计数，如实报
「N 组边际反例，无第三个数值列可控制，无法排除混淆」。

再把「已承认」的覆盖范围修对：`_admits` 原来只覆盖已控制的反例（`real`），
不覆盖无对照的反例（`uncontrolled`），导致 `real_c2024`（2 列）明明论文承认过
却仍被判 WARN。改为 `_nrev = len(real) + uncontrolled`。

结果：`real_c2024` → `PASS 1 组局部非单调，论文「Evaluation」节已承认，另有 1 组无数值列可对照`。

**要写下来的弱点**：本批 23 篇全部 PASS，因为模板恒定声明非单调 —— 这条 SOFT 检查
在模板题上没有区分度，价值只在「有反例且**不**承认」时体现。

## 三、摘要跨页：先测出真实溢出量，再改机制

上一轮的注释写着「12 道跨页、残余 1500/1208 字符/12 行」，全是旧判据的产物。
这一轮做了个实验把真值测出来：

1. 量 `nflis` 摘要：**533 词 / 9 段**。
2. 在副本里删掉第 1 段（57 词背景）→ 476 词，重新编译 → `abs_page` **PASS**。
3. 结论：溢出量是**约 45 词**，不是「12 行」。

据此在 `paper.py` 加机制：

```python
ABS_WORD_BUDGET = 450          # 实测边界 476 通过 / 533 跨页，取 450 留余量
_LTX_CMD = re.compile(r"\\[a-zA-Z]+\*?")
def _abs_words(lines) -> int:  # 只去命令名，保留花括号正文
def _trim_abstract(lines, budget):  # 超预算就整段删，至少留 2 段
```

删除顺序：先删第一段（背景，信息密度最低，删掉后「Problem 1 asks …」仍交代任务），
再删倒数第二段，末段（结论）最后才动；**至少保留 2 段**，避免删成一句话。

不缩字号的理由：已经 `\scriptsize`（约 7pt），再缩是把版面问题转嫁给评委。

### 这里又踩了一个自己挖的坑

第一版 `_LTX_CMD` 写的是 `\\[a-zA-Z]+\*?(\[[^\]]*\])?(\{[^{}]*\})?`，
会把 `\textbf{Hello}` **整块**吃掉，连「Hello」都不计词 —— 带内联强调的摘要
会被少算词、进而裁得不够。测试里那条 `_abs_words` 断言（期望 6，实际 4）
当场抓到，改成只去命令名 + 去括号。

## 四、端到端验证（不是只跑单元测试）

```
mmkit.py run --data out/data/nflis.xlsx --y TotalDrugReportsState \
             --x YYYY,FIPS_State,FIPS_County,FIPS_Combined \
             --tex out/_absfix/tpl/paper.tex
   → 摘要超预算，删段 2 个 -> 408 词（预算 450）
   → LaTeX 论文已写入 out/_absfix/tpl/paper.tex
pdflatex ×2 → 25 页
gate.chk_abs_page(out/_absfix/tpl) → PASS | 摘要结尾落在第 1 页
```

重新生成的产物留在 `out/_absfix/tpl/`（故意保留作证据，不是垃圾目录）。
归档的 `out/runs/nflis/` **没有动** —— 它是历史产物，修机制不等于改历史。

## 新增回归（`tools/test_gate_strict.py`，40 项）

- G：`_admission` 定位 Evaluation / 自定义节名 / 无承认语句；两列数据不再报「不足 4 个」
- H：`_abs_words` 保留花括号正文；超预算裁到预算内；未超预算不改动；
     只有 2 段时宁可不裁

## 未做（下一轮）

1. 5 条真泄漏（`clustering / icm2006c / mcm2020c / review_microwave / review_pacifier`）
   的 `runs.json` x 需与归档产物一并重做 —— 内容决策，仍未动。
2. `falsify` 在模板语料上无区分度（全 PASS），可考虑要求「承认语句点名具体变量」。
3. `abs_page` 的 A2/B/C 兜底判据在 A（摘要结尾定位）可用时永远走不到，
   考虑删掉以减面，或保留作解析失败时的退路（当前保留）。
---

# 优化记录（第 84 轮）：把 5 条真泄漏清掉，并承认有一条清不掉

## 总账（23 题）

| 项 | 第 83 轮末 | 现在 |
|---|---|---|
| 异常条目 | 6（5 leakage WARN + 1 abs_page FAIL） | **1**（1 leakage WARN） |
| 归因清楚的假警报 | 3 条时间趋势已豁免 | 另加 1 条滞后项豁免 |
| 护栏自测 | 40 项 | 40 项（新增滞后判据 8 个用例） |

## 一、先分清「配置写错」还是「算法没防护」

查 `runs.json`：5 处全是**手写 x 列表**，不是算法自动选的 → 属配置问题。

| 题目 | 泄漏对 | 相关 | 是什么 |
|---|---|---|---|
| clustering | 消费金额→客户价值 | +0.995 | 客户价值的组成部分 |
| icm2006c | pop2000→pop2005 | +1.000 | **同一序列的滞后项**，正当建模 |
| mcm2020c | total_votes→helpful_votes | +0.997 | 包含关系（helpful ⊂ total） |
| review_microwave | helpful_votes→total_votes | +0.997 | 同上 |
| review_pacifier | helpful_votes→total_votes | +0.985 | 同上 |

## 二、新增第三类豁免：同一序列的滞后项

`pop2000 → pop2005` 用上一期同口径值预测下一期，是人口/存量问题的标准做法
（队列存活、持续性模型），报成泄漏是假警报。
而 `total_votes → helpful_votes` 看着也高度相关，却是**包含关系**
（helpful 是 total 的一部分），那才是拿响应凑响应。

判据 `_is_lag_pair`：去掉结尾数字/分隔符后主干相同、数字部分不同。

```
pop2000/pop2005      -> True     （滞后）
life1995/life2005    -> True     （滞后）
total_votes/helpful_votes -> False  （主干不同 → 仍按泄漏）
消费金额/客户价值        -> False
star_rating/total_votes  -> False
pop/pop2005          -> False  （一边没有数字，不算滞后）
```

## 三、顺带修掉一个「只看最相关」的漏检

原来只取**最相关的那一列**再分类。若最大者是正当的滞后项（pop2000→pop2005 相关 1.000），
后面真正的泄漏就被掩盖。改成收集**所有** >0.95 的列，逐个分类：
有任何一个非豁免项就 WARN，并报出最严重的那一条 + 「另 N 列同类」。

## 四、改配置并重跑 3 题

| 题目 | 旧 x | 新 x |
|---|---|---|
| mcm2020c | star_rating,total_votes,review_headline_len,body_len | star_rating,review_headline_len,body_len |
| review_microwave | star_rating,helpful_votes | star_rating |
| review_pacifier | star_rating,helpful_votes | star_rating |

重跑后三条全部 `leakage PASS`（最高相关分别降到 +0.222 / -0.000 / -0.120）。
`review_*` 只剩一个自变量 —— 弱就弱，不编列。

旧产物备份在 `out/runs_backup_r4/`。

## 五、`nflis` 的 abs_page 不再靠白名单

第 83 轮加的摘要词预算机制生效了：重跑 `nflis` 时打印
「摘要超预算，删段 2 个 -> 408 词（预算 450）」，编译后
`abs_page → PASS | 摘要结尾落在第 1 页`。归档已更新（旧产物同样备份）。

## 六、有一条清不掉，原因是数据本身循环

`clustering` 换成 5 个自变量后仍报 WARN，于是量了全表：

| 列 | 与 客户价值 的相关 |
|---|---|
| 消费金额 | +0.9953 |
| 购买频次 | +0.9687 |
| 会员等级 | +0.9667 |
| 品类数 | +0.8450 |
| 最近购买天数 | -0.8292 |
| 年龄 | +0.0206 |

**客户价值本身就是 RFM 的加权构造**，任何有意义的预测变量都是它的组成部分；
唯一独立的「年龄」与它无关（0.02），拿它预测等于没建模。
所以这不是配置能修好的，是这道题的构造问题。

处理：把 `clustering` 的配置与产物**一起回滚**到原状（保持 config 与 artifact 一致），
把这个 WARN 留在账上，并在下面记清楚它是「数据构造循环」而非「配置笔误」。

**不改成绿**：把它豁免掉，就等于把「这道题是循环的」这个事实藏起来。

## 七、当前唯一残留

```
clustering  leakage WARN  消费金额 与 客户价值 相关 +0.995，疑似把响应当成了自变量，另 1 列同类
```

要真正清零，只有两条路：重做 `clustering` 这道题（换一个不由 RFM 派生的响应），
或在 `leakage` 里加一条「响应是自变量的函数」的显式白名单 —— 后者是藏事实，不做。

## 复现

```powershell
$py = "C:\Users\21246\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
cd model1-arch
& $py tools\fix_leaking_x.py     # 幂等：把 4 处 x 改成不泄漏的版本
& $py tools\test_gate_strict.py  # 40 项
& $py tools\verify_all.py        # 质量门 + 回归 + 补丁
```
## 补记：新规则当场抓到了我测试样例的缺陷

加完「检查所有超阈值列」后，护栏自测红了 2 项：

```
[FAIL] 时间趋势共变不报 WARN  <- WARN / 价格 与 销量 相关 +1.000 ...
[FAIL] 说明里点出是时间列
```

原因是我的样例里 `价格 = linspace(10,20)` 也是**单调斜坡**，与 `销量` 同样相关 1.000。
旧代码只看最相关的一列（年份），所以 `价格` 从没被检查到；新代码把两列都拿出来，
于是判成非豁免的真泄漏。

**这是样例设计缺陷，不是规则太严。** 修法是把价格改成非单调（固定种子正态），
不是放宽断言。改完 40 项全过。

教训：一条只检查「最大值」的判据，会让第二个同样越界的量永远不被看见。
---

# 优化记录（第 85 轮）：泄漏判定下沉到建模入口，并合成单一定义处

## 总账

| 项 | 第 84 轮末 | 现在 |
|---|---|---|
| 泄漏判定的定义处 | 只在 `gate.py`（事后检查） | `mm.py` 一处，gate 委托 |
| 配置写错的发现时机 | 出稿后跑 gate 才知道 | **建模入口当场打印；`--strict` 直接拒绝（exit 2）** |
| 护栏自测 | 40 项 | **51 项** |

## 一、为什么必须下沉

第 83/84 轮我两次写「治因而非治症」，但一直只在 gate 里做事后检查。
配置写错 → 论文照出 → gate 才发现，中间已经浪费一次生成。

现在 `mm.fit` 自己算：

```python
leak = suspect_leak(ds, yname, xnames)
[泄漏] 自变量里有响应的组成部分：
  · 购买频次 与 客户价值 相关 +0.969
  → 删掉这些列后重跑；它们的系数没有解释意义
```

`mmkit run` 接住它：

```
[拒绝] 自变量里有响应的组成部分：消费金额、购买频次。删掉这些列后重跑；保留它们的系数没有解释意义。
exit=2
```

（`--strict` 时硬拒，默认只警告 —— 不打断已有的批量脚本。）

## 二、合并成单一定义处，防止两份实现漂移

`_is_time_like` / `_is_lag_pair` 原来只写在 gate 里。若在 mm 里再抄一份，
两份会各改各的 —— 本轮已经出现过一次同类事故（`patches.py` 的断言挂在注释文字上）。

做法：定义搬到 `mm.py`（`is_time_like` / `is_lag_pair` / `LEAK_THRESHOLD` / `suspect_leak`），
`gate._is_time_like` 改成三行委托。测试里加了「两个入口对同一名字判定必须一致」：

```
[PASS] gate 与 mm 对 '年份' 判定一致
[PASS] gate 与 mm 对 '年龄' 判定一致
[PASS] gate 与 mm 对 'pop2000' 判定一致
[PASS] gate 与 mm 对 'total_votes' 判定一致
[PASS] gate 与 mm 对 '1953' 判定一致
```

## 三、`suspect_leak` 的三分类与「查所有列」

返回 `[(列, 相关, 类别)]`，类别 `time / lag / leak`：

```
[PASS] 时间列归为 time
[PASS] 同序列滞后归为 lag
[PASS] 其余高相关归为 leak
[PASS] 低相关列不进入结果
```

仍然逐个检查**所有**超阈值的列（第 84 轮修的那个掩盖问题一并保留在这个函数里）。

## 四、又踩了同一个测试样例陷阱（第三次）

写 part_i 时把「应当无关」的列写成 `np.linspace(20, 40, n)`，
它与响应同样是斜坡 → 相关 1.0 → 被判成 leak，断言红。

这是本文件里第三次踩同一个坑（前两次：`价格`、`年龄`）。
已把结论写进测试文件注释：

> 「应当无关」的列**绝不能用 linspace 斜坡**。同一索引上的两条斜坡彼此相关 1.0。

改成固定种子正态后全过。

## 复现

```powershell
$py = "C:\Users\21246\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
cd model1-arch
& $py tools\test_gate_strict.py                 # 51 项
& $py mmkit.py run --data out/data/clustering.xlsx --y 客户价值 `
        --x 消费金额,购买频次,最近购买天数 --strict --no-gate   # 期望 exit 2
```

## 未做（下一轮）

1. `clustering` 这道题本身循环（响应是自变量的函数），仍未重做。
2. `falsify` 在模板语料上仍全 PASS，区分度为零。
3. `mmkit` 的 `run` 只接住了 `fit` 段的泄漏；`race` / `solve` 等子命令仍不看 `leak_bad`。
---

# 优化记录（第 86 轮）：`falsify` 原来在给噪声判卷

## 总账

| 项 | 第 85 轮末 | 现在 |
|---|---|---|
| `falsify.counterexamples` | 重尾 ties 上量的是组内噪声 | 先聚合再判单调，如实报 `aggregated/n_groups` |
| `falsify` 的方向前提 | 不检验方向是否显著 | t 检验不显著就不判（→ 诚实 N/A） |
| `falsify` 能否失败 | 未验证 | **同一份数据：未承认 → WARN，承认 → PASS** |
| `mmkit race` | 不看 `leak_bad` | 与 `run` 同一套判定，`--strict` 拒绝 |
| 护栏自测 | 51 项 | **54 项** |

## 一、发现的真 bug：滑窗落在重复值内部

`falsify.counterexamples` 按 x 排序后取连续 8 点滑窗。而 `queueing` 的
「服务台数」只有 **5 个不同取值**（24 行），窗口其实落在同一取值的重复值内部 ——
量的是组内噪声，不是沿 x 的反转。

实测后果：`服务台数→等待时间` 算出「覆盖率 100%」，看着像处处违反。
真实数据是 U 形（组均值 31.79 → 31.47 → 22.70 → 24.07 → 25.76）。

**修法**：不同取值数 < max(3, n/3) 时先按 x 分组取 y 均值，在组均值序列上做滑窗；
`min_seg` 自适应；返回 `aggregated / n_groups / n_test` 让人知道自己在看什么。
修后 queueing 从 100% 降到 60%（5 组）。

## 二、更大的问题：方向没建立就去检验「方向是否反转」

修完 ties 后，`evaluation`/`population` 仍是 100% 覆盖。查数据：

```
交付周期 → 综合得分   pearson = -0.157
```

本质是噪声。方向本身不存在，却拿它当「论文的主张」去检验反转 ——
那是在给噪声判卷，结论（100% 违反）毫无意义。

**修法**：用 t 检验（`mm._t_quantile`，不引 scipy）判方向是否显著；
不显著的对**跳过**，并在结果里如实说「N 组相关不显著，方向未建立，未做单调性检验」。

修后：`prediction / population / review_microwave` 变成诚实 N/A，
其余 20 题 PASS（其中多数是「已承认」）。

## 三、证明它还能红（不是恒真）

只测恒真的一侧等于没测。新加一组对照，**同一份数据**改论文措辞：

```
[PASS] 方向显著+尾部反转+未承认 → WARN
[PASS] 同样数据但已承认 → PASS
```

数据：`x=0..39`，`y = 100-3x (x<30)`，之后 `y = 13+2(x-30)` —— 整体强负相关、
尾部上升；无第三列可控制；论文先说「处处下降」→ WARN，改成「上尾局部失效」→ PASS。

## 四、`mm.fit` 不该打印（自己挖的坑）

第 85 轮我在 `mm.fit` 里加了 `print("[泄漏] ...")`。结果 `gate` 的数值对拍
（用合成 x/y，天然相关 1.0）被刷了几十条告警 —— 库函数打印污染了调用方。

**修法**：`mm.fit` 只把 `leak_suspects/leak_bad` 放进返回 dict，不打印；
提示留在 CLI 层（`mmkit run` / `race`）。

## 五、`mmkit race` 补上同一判定

```
[拒绝] 自变量里有响应的组成部分：消费金额、购买频次。删掉这些列再比结构。  exit=2
（干净配置 年龄 → exit=0，不拦）
```

## 复现

```powershell
$py = "C:\Users\21246\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
cd model1-arch
& $py tools\test_gate_strict.py     # 54 项
& $py falsify.py selftest           # 11 项
& $py tools\verify_all.py
```

## 未做（下一轮）

1. `clustering` 这道题本身循环（响应是自变量的函数），仍未重做。
2. `falsify` 在诚实语料上仍不出 WARN —— 这是结果，不是缺陷；但值得加一条
   「承认语句必须落在正文某节且带具体变量」的可选严格档。
3. `mmkit solve` / `contract` 仍未接 `leak_bad`。
---

# 优化记录（第 87 轮）：`verify.py` 的六个抽取缺陷

起点：上一轮曾看到 `python verify.py out/arch` 退出码 1 却没有任何输出。
静默失败比报错更危险，这轮从那里往下挖。

## 总账（同一批论文，三个数字）

| 论文 | 修前 | 修后 | 分母变化 |
|---|---|---|---|
| `out/arch`（8 页报告） | 156/208 = 75.0% | **169/184 = 91.8%** | 208 → 184 |
| `out/runs/queueing` | 164/175 = 93.7% | **167/174 = 96.0%** | 175 → 174 |
| `out/d2026c`（17 页论文） | 217/232 = 93.5% | 217/232 = 93.5% | 不变 |

分母同时变小 —— 幻影数被清掉了，这是正确方向：**数更少、更可信**。

## 六个缺陷（每个都有实测反例）

### ① 给目录就崩，还说是权限问题

```
PermissionError: [Errno 13] Permission denied: 'out\\arch'
```

位置参数被当成文件路径直接 `open()`。目录是很容易犯的错，而
`Permission denied` 会把人引到权限排查上去。

修：目录 → 自动找里面的 `paper.tex`；找不到就说清楚；文件不存在/不是普通文件/读不了
各有独立措辞与退出码 2。

### ② 跨行命令的参数被当成论文主张

`\geometry{a4paper, left=3.0cm,\n  top=2.8cm, ...}` 的闭合括号在下一行，
逐行正则永远匹配不上 → `top=2.8cm` 的 `2.8` 被报「无出处」。

修：`_blank_multiline_args` 把跨行 `\cmd{...}` 的内容抹成**等长空格**
（保留换行，行号与报错上下文仍对得上）。

### ③ 前导区整段不该数

抹掉跨行参数后，还剩 `\definecolor{ink}{HTML}{8A3324}`（→ 3324）
和 `\@startsection{-2.4ex\@plus…}`（→ -2.4 / -0.9 / -0.2）。

修：`\begin{document}` 之前整段抹空（保留行数）。

### ④ 写成整数的数按 1 位小数判

`_decimals` 用 `repr(float(x))`：`repr(52.0) = '52.0'` → 认为写了 1 位小数。
于是论文写「a factor of 52」、输出里是 52.5 时，
`round(52.5, 1) = 52.5 ≠ 52` → 判无出处（假阳性）。

修：`_written_decimals(tok)` 按**原始字符串**数小数位；`_near` 接受外部精度。
**没有放松防编造那条**：`0.9999` 仍要求输出有 4 位（自检里专门钉住）。

### ⑤ 溯源池只读 JSON，不读 CSV

插件的 `abilities.csv / layers.csv / topsis.csv / greedy_vs_opt.csv` 都是一等产物。
只读 JSON → 「来源就在隔壁表里」的数被判无出处。

修：`load_outputs` 同时收 `.csv`（按文本读，数字仍走同一抽取器）。
`out/arch` 因此从 82.1% → 90.8%。

### ⑥ `0.19--0.57` 抽出幻影 `-0.57`

LaTeX 的 `--` 是破折号，正则却把 `--0.57` 读成负号 + 数。
原文里没有 `-0.57` 这个值。

修：数字之间的 `--` / `–` / `—` 先改成空格再抽取。

## 自检从 9 项扩到 16 项

```
[PASS] 区间写法不产生幻影负数  — ['0.19','0.57','0.19','0.57','1965','1970']
[PASS] 写成整数时按 0 位小数判
[PASS] 52 <- 52.5 视为同源（舍入）
[PASS] 0.9999 仍要求输出有 4 位精度      ← 防编造那条没被放松
[PASS] 前导区的宏定义不产生数字  — ['0.00743']
```

## 顺带查清的一件事：两个溯源工具口径不同

`gate.chk_numbers`（走 `freeze.check_paper`）与 `verify.py`（走 `trace`）对同一篇论文
给出相反结论：gate 说 `queueing` 115/115 全溯源，verify 说 167/174。

根因是**口径**，不是谁坏：

| | 抽什么 | 和谁比 |
|---|---|---|
| `gate.chk_numbers` | 只抽**带小数点**的数 | 冻结表 `items`（251 条），±2% |
| `verify.py` | 抽所有数（含整数） | 目录里全部 JSON + CSV，按书写精度舍入 |

`gate` 因此漏掉整数形式的百分比（`280\%`、`2057\%`），
`verify.py` 则会把派生量（`30\%` 是两个数算出来的）算作无出处。

我试着给 gate 补整数百分比，量了一下：22 道题里 9 个候选无出处，其中 `30` 出现 4 次、
`3477/4248/182` 都是派生量。**用查表法判派生量必然误报**，所以不加这条规则，
只把口径差异写清楚（见上表），而不是加一条会误报的检查。

## 复现

```powershell
$py = "C:\Users\21246\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
cd model1-arch
& $py verify.py            # 自检 16 项
& $py verify.py out/arch   # 目录也行
& $py tools\test_gate_strict.py
& $py tools\verify_all.py
```

## 未做（下一轮）

1. `clustering` 这道题本身循环，仍未重做（唯一残留警告）。
2. `2026` 这类日期仍被算作「无出处」——需要一个日期/年份白名单，但白名单
   可能盖住真的年份数据（如 `age_struct` 里 `1953` 是数据），要按上下文判，不急着加。
3. `-012`（文件名片段）仍被抽成数。
---

# 优化记录（第 88 轮）：清掉最后一条告警，账目转 ALL GREEN

## 总账

| 项 | 第 87 轮末 | 现在 |
|---|---|---|
| 质量门 | 22/23 通过，1 道警告 | **23/23 通过，0 道警告** |
| 回归 / 补丁 | ALL PASS / 114 | ALL PASS / **114/114** |
| 结论 | 有 1 项未通过 | **ALL GREEN**（exit 0） |

这是这一系列第一次达到 AGENTS.md 的完工线：硬门失败 0、警告 0。

## 一、为什么这道题清了四轮

`clustering` 的告警是「消费金额 → 客户价值 +0.995」。前几轮我把它当「配置笔误」，
改过两次 x 都仍然红，直到第 84 轮量出全表：

| 列 | 与 客户价值 相关 |
|---|---|
| 消费金额 | +0.9953 |
| 购买频次 | +0.9687 |
| 会员等级 | +0.9667 |
| 品类数 | +0.8450 |
| 最近购买天数 | −0.8292 |
| 年龄 | +0.0206 |

**客户价值本身就是 RFM 的加权构造**，任何有意义的预测变量都是它的组成部分。
唯一独立的「年龄」与它无关（0.02），拿它预测等于没建模。
所以这不是配置能修的，是**题目构造**的问题 —— 当时我选择回滚并如实留一条红。

## 二、这轮的解法：换一个有意义的因变量，而不是换一个更松的判据

把全部相关矩阵打出来，找「与所有其它列 |r| < 0.95」的候选：

| 候选因变量 | 最大 \|r\| |
|---|---|
| 最近购买天数 | 0.852 |
| 品类数 | 0.885 |
| 年龄 | 0.103 |

选 `最近购买天数`（recency）作因变量：

```
y   = 最近购买天数          （留存指标）
x   = 消费金额, 品类数, 年龄   （假设的驱动因素 + 对照）
min = 消费金额, 品类数, 最近购买天数
problem = customer retention: what drives purchase recency
```

先用 `mm.suspect_leak` 验过再跑：

```
y=最近购买天数  x=['消费金额','品类数','年龄']   超阈值: 无   leak_bad: 无
y=客户价值      x=['消费金额','购买频次','最近购买天数']
                超阈值: 消费金额 0.995 / 购买频次 0.969   leak_bad: 两个
```

语义上也站得住：「花钱多、品类广的客户是不是更近期来过」是标准的留存问题；
消费额与购买频次（会员等级的定义依据）已排除在外。相关 0.852 是有意义的相关，
不是定义性重合。

## 三、结果

重新生成后：

```
23 题异常：无
gate 硬门: True
verify_all: 23/23 通过，0 道有警告 → ALL GREEN
```

新摘要抽样（确认不是循环论证）：

> This report models customer retention: what drives purchase recency …
> the cleaned data give 36 usable observations over 8 numeric variables …
> The selected structure, Linear, attains a cross-validated RMSE of 13.5 …

RMSE 13.5 天，量级合理（recency 以天计）。

旧产物仍在 `out/runs_backup_r4/clustering/`。

## 四、要记下的一点

`min` 沿用模板的「全部最小化」约定。对这道题，同时最小化消费额、品类数、
最近购买天数在语义上略怪（像是在找「最不活跃的客户」），
数学上没问题。若要把这一问讲得更自然，应改成有方向的目标
（如最小化 recency、最大化 spend），但那是模板层面的方向支持，不在本轮范围。

## 复现

```powershell
$py = "C:\Users\21246\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
cd model1-arch
& $py tools\verify_all.py     # 期望 ALL GREEN / exit 0
```

## 未做（下一轮）

1. 还没系统审过的模块：`lanes.py`、`abstract.py`、`figcheck.py`、
   `falsify.limit_behavior`、`datapath.py`。前七轮的洞全在 gate/verify/freeze/
   falsify/mm.fit 上，其余模块同类缺陷没人查过。
2. `verify.py` 仍把 `2026` 这类日期算「无出处」，`-012` 文件名片段仍被抽成数。
3. 模板的方向支持（见第四节）。
---

# 优化记录（第 89 轮）：摘要硬门能被「换个环境名」绕过

第 88 轮 ALL GREEN 后我列了「还没系统审过的模块」，这轮从 `abstract.py` 开始。
它是**硬门**（摘要 8 项自检），而 `chk_abstract` 在识别不到摘要时返回裸 N/A ——
裸 N/A 在硬门里算通过。

## 总账

| 项 | 第 88 轮末 | 现在 |
|---|---|---|
| 摘要识别形式 | 只认 `\begin{abstract}` / `\section{Summary}` | + `abstractbox` 类环境、`\section{Abstract|摘要}` |
| 识别不到时 | N/A（算通过） | **failed-N/A（严格模式算失败）** |
| `abstract` 自检 | 10 项 | **17 项** |
| `out/arch` 摘要 | 84.2/100（未过「逐问一一对应」） | **100.0/100（317 词，4 处锚点）** |

## 一、洞：真有摘要，硬门却说「没有摘要」

`extract` 只匹配 `\begin{abstract}` 与 `\section*{Summary}`。
而本仓库自己的技术报告用的是自定义环境：

```latex
\begin{abstractbox}
...
\end{abstractbox}
```

实测：

```
out/arch          extract=False  items=0  gate=N/A   没有摘要（abstract 或 Summary 节）
```

**一篇真有摘要的论文，因为环境名不叫 abstract，就整段绕过了摘要 8 项自检。**

修法两条：
1. `extract` 认三类写法 —— 名字含 `abstract` 的任意环境、`\section{Abstract|摘要}`、
   `\section{Summary}`。
2. 认不到时返回 **failed-N/A**（严格模式计失败）。摘要是竞赛必交项，
   「找不到」不等于「没有」，但更不能算通过。

修完立刻打中自己的交付物（见第三节）。

## 二、洞：`"a model" in low` 把「a modelling」判成笼统表述

第 ④ 项「模型名具体」用子串匹配：

```python
vm = [w for w in VAGUE_MODEL if w in low]
```

`"a modelling team"` 里含 `"a model"` → 判成「笼统表述」。

实测：`out/arch` 摘要开头就是「A modelling team that pairs …」，
于是 73.7 分里有一项是这么丢的。

修：ASCII 短语改词边界匹配 `(?<![a-z])…(?![a-z])`；中文仍用子串。
自检里加了双向对照：

```
[PASS] 「a modelling」不算笼统表述「a model」
[PASS] 真写了「a model」仍被抓出
```

## 三、修完判据后暴露的真问题：摘要没对准正文

`out/arch` 变成 84.2/100，只剩「逐问一一对应」（0 处锚点）。

这不是假警报：那份报告正文就是按 Problem 1–4 组织的
（§3 能力分配 / §4 验证预算 / §5 泄漏率 / §6 时间去向），摘要却没点出来。
**改摘要，不是改判据**：

```
Problem 1 asks how capabilities should be allocated, Problem 2 how much
verification is worth buying, Problem 3 how well the gate-trip rate is
known, and Problem 4 where the time actually goes.
```

重编译后：

```
abstract -> PASS | 100.0/100（317 词，4 处锚点）
8 页，逐页墨迹 5.8%–11.2%，无空白/过密页
```

桌面版已更新：`C:\Users\21246\Desktop\Plugin-Agent-Architecture.pdf`。

## 四、自检 10 → 17 项

```
[PASS] 认得出「环境 abstractbox」
[PASS] 认得出「节 Abstract」/「节 摘要」
[PASS] 仍然认不出真正的无摘要
[PASS] 「a modelling」不算笼统表述「a model」
[PASS] 真写了「a model」仍被抓出
```

## 五、顺手修的

`extract` 的新 docstring 里有 `\section{...}`，触发 `SyntaxWarning: invalid escape sequence '\s'`。
改成 raw docstring。

## 未做（下一轮）

1. 仍未系统审：`lanes.py`、`figcheck.py`、`falsify.limit_behavior`、`datapath.py`。
2. `abstract.py` 的 ②「逐问一一对应」只数 `problem\s*[1-9]` 的出现次数 ≥2，
   不检查是否 1..N 齐全 —— 写「Problem 4 / Problem 5」也能过。这一条还没收紧。
3. ③「每问有量化结果」的分段判据只要求段内有任意数字（`\d+\.?\d*`），
   年份、编号也会满足。可以要求「至少一个小数」或「与冻结表对得上」。
---

# 优化记录（第 90 轮）：摘要锚点收紧 + 一张 1.09 亿像素的图

## 总账

| 项 | 第 89 轮末 | 现在 |
|---|---|---|
| `abstract` 自检 | 17 项 | **20 项** |
| 「逐问一一对应」 | 只数出现次数 ≥2 | **要求锚点从 1 起连续** |
| 图检查 | 解码超大图（437 MB/次） | 超预算降采样；过大本身记为缺陷 |
| 热力图列数 | 无上限（261 列 → 10515 px） | 上限 24 列（按方差） |
| 官方账目 | ALL GREEN | ALL GREEN（未破） |

## 一、收紧「逐问一一对应」

原来只数 `problem\s*[1-9]` 出现次数 ≥2 —— 写「Problem 4 / Problem 5」也能过，
而 1..3 一个没提。

改成：取全部锚点编号（含中文「问题一/二/…」），要求**从 1 起连续**。

改之前先量了全部论文：23 道模板题 + 技术报告的锚点集合都是 `[1..N]` 连续，
所以收紧不会误伤。改完复测：`逐问一一对应未过: 无`。

负向对照（新加进自检）：

```
[PASS] 锚点 1..2 连续 → 过        — 2 个问题锚点 [1, 2]
[PASS] 只提 Problem 4/5 → 未过    — 锚点 [4, 5] 缺第 [1, 2, 3] 问
[PASS] 提 1/3 缺 2 → 未过          — 锚点 [1, 3] 缺第 [2] 问
```

## 二、先撤回一个我自己的误判

我一度以为 `chk_figures` 从未真正跑过（因为直接调 `figcheck.audit_dir` 只看顶层，
而图在 `fig/` 子目录里）。实测 `gate.run_all` 后：

```
heat_sink  PASS  均分 8.0/10（12 张，A12 B0 C0 D0）
...（23 道全是 8.0 / A12）
```

**图检查一直是有效的**，是我直接调错了入口。这条判断当场撤回。

## 三、真问题：一张 10515×10387 的图

`out/runs/pop_panel/fig/corr.png`：**1.09 亿像素**，2.41 MB。

- `check_background` / `check_unicode_boxes` 各做一次 `convert("RGB")` → 每次约 437 MB，
  一张图就能把 gate 撑爆，并触发 PIL 的 `DecompressionBombWarning`。
- 10515×10387 在 15 cm 版面上每格约 0.57 mm —— 读不出来。

根因在 `mmkit.plot_corr`：
```
cell = max(30, min(96, 900 // n))     # n=261 → 900//261=3 → max(30,3)=30
W = pad_l + cell*n + 40               # 30*261 = 7830 逻辑像素
```

修两层：
1. `figcheck`：像素预算 `MAX_PIXELS = 30M`；超预算的图**降采样后再判**
   （背景色与极端像素占比看的是整体，缩到 2000 px 长边不影响结论），
   同时把「过大」本身记成缺陷：
   `尺寸 10515x10387（109.2M 像素）过大：按版面宽度无法辨认，且显著增大 PDF`。
   实测：该图评分从 A 降到 B，耗时 1.94 s，不再有 DecompressionBomb 警告。
2. `plot_corr`：列数上限 24，按方差取前 24 列，并在返回里写 `note`。
   直接验证（不改产物）：

```
数值列数: 56
note: 显示 24 / 56 列（按方差取前 24）
新 corr.png: 2156x2136 = 4.61 M px, 0.05 MB     ← 原 109.22 M px / 2.41 MB
```

## 四、一个没做完的地方（要记住）

`mmkit run` **复用已存在的图**：我删掉 `out/runs/pop_panel/fig/corr.png` 再跑，
它没有重画（新文件根本没生成，只能从备份恢复）。磁盘上的图时间戳仍是 11-09 13:56。

所以上限目前只在新生成时生效。要让 pop_panel 立刻变好，需要同时清掉
`out/fig/corr.png` 再重跑——本轮没做，避免在没验证的情况下动共享产物。
产物已恢复原状，账目未受影响。

## 复现

```powershell
$py = "C:\Users\21246\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
cd model1-arch
& $py abstract.py selftest     # 20 项
& $py figcheck.py selftest     # 11 项
& $py tools\test_gate_strict.py
& $py tools\verify_all.py
```

## 未做（下一轮）

1. 清 `out/fig/corr.png` 后重跑 pop_panel，把 109 M px 那张图真正换掉。
2. 仍未系统审：`lanes.py`、`falsify.limit_behavior`、`datapath.py`。
3. `abstract.py` ③「每问有量化结果」仍只要求段内有任意数字（实测模板论文第一段
   只有「24 个观测 / 6 个变量」这类整数，若要求小数会 22 篇同时红，故不动）。
---

# 优化记录（第 91 轮）：缓存让同一份数据得出不同判决

## 总账

| 项 | 第 90 轮末 | 现在 |
|---|---|---|
| `lanes` 自检 | 67 项 | **70 项** |
| 缓存往返 | **丢 veto 标志** | 六字段全保留 |
| `pop_panel` 热力图 | 109.2 M px（缓存未刷） | **4.61 M px，11 张全 A** |
| 官方账目 | ALL GREEN | ALL GREEN（未破） |

## 一、先收尾上一轮遗留：把 109 M px 那张图真正换掉

`mmkit run` 复用已存在的图，所以上轮只改了代码没换图。
这轮直接调 `plot_corr` 就地重画：

```
note: 显示 24 / 56 列（按方差取前 24）
corr.png: 2156x2136 = 4.61 M px, 0.05 MB        ← 原 109.22 M px / 2.41 MB
corr.pdf: 86.9 KB
```

重编译后：

```
pdf      PASS  24 页 / 600419 字节              ← 原 25 页 / 691159
figures  PASS  均分 8.0/10（11 张，A11 B0 C0 D0）  ← 原是 A11 B1
abs_page PASS  摘要结尾落在第 1 页
```

PDF 小了 91 KB，唯一的 B 级图消失。

## 二、主发现：缓存往返把 veto 丢了，判决随之翻转

`run_cached` 存/取缓存时这样重建 Vote：

```python
Vote(v.verdict, v.strength, v.why, v.lane, v.source)   # 五个位置参数
```

而 `Vote.__init__` 的第六个参数是 `veto=False`。于是**否决标志被静默丢弃**。

实测（同一份主张、同一批票）：

```
首次运行    grade=弱  vetoed=True
缓存命中后  grade=中  vetoed=False
判决是否改变: True
```

变的方向正是危险方向 —— 第 15 轮加 veto 就是为了防「方向错被多数票淹没」，
而缓存一命中，这道保险就没了。

修法：抽一个 `_copy_vote`，缓存进出都走它。

```python
def _copy_vote(v):
    return Vote(v.verdict, v.strength, v.why, v.lane, v.source, v.veto)
```

抽成函数的理由写进注释：以后 `Vote` 再加字段，只有一处要改，
不会再出现「新字段在缓存路径上静默蒸发」。

修后：

```
首次 grade=弱 vetoed=True | 缓存后 grade=弱 vetoed=True | 一致=True
```

## 三、检查过、但**没有**问题的几处（免得以后重复怀疑）

1. **判决映射**：空票 → `无`(C=3, reject)；全 UNKNOWN → `弱`(reject)；
   1 票 veto 反对 → reject；2 源强支持但未声明 reproduced → degrade(C=4)；
   声明 reproduced 后 → pass(C=5)。没有假通过路径。
2. **缓存键**：`fingerprint` 哈希了 X 的字节、y 的字节、排序后的 sign 与 meta，
   是内容寻址，换数据必然换 key。
3. **meta 取数**：全仓只有 `fingerprint` 用 `meta`，没有 lane 从 `meta` 里读文件，
   所以「同路径换文件内容但指纹不变」这条隐患不存在。

## 四、顺带记一条设计观察（不是缺陷）

`GRADE_TO_E2 = {"强": 1, "中": 1, "弱": 0, "无": 0}` —— 强度只区分「弱/非弱」，
`强` 与 `中` 在判决上完全等价。第 4、6 轮花力气让强度参与决策，
实际只在 `弱` 这条边界上生效。这是架构决定的（e2 最高 1，单份数据撑不起 e2=2），
不是 bug；但读代码的人容易误以为 `强` 比 `中` 更有分量。

## 复现

```powershell
$py = "C:\Users\21246\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
cd model1-arch
& $py lanes.py selftest        # 70 项
& $py tools\verify_all.py
```

## 未做（下一轮）

1. 仍未系统审：`falsify.limit_behavior`、`datapath.py`、`harness.py`（`run_gates` 本体）。
2. `abstract.py` ③ 仍只要求段内有任意数字（有证据的克制，见上轮）。
## 五、我的改动触发了回归基线（已按正确方式处理）

加完 3 条断言后，`tools/verify_all.py` 报 `回归：FAILED: 1 项`：

```
FAIL lanes.py   70/67 断言  (重试过一次)  (退出码 0)
```

原因不是行为退化，而是 `tests/run_all.py` 把 `lanes.py` 的断言数**钉死成 67**：

```python
("lanes.py", ["selftest"], 67),   # 断言数变了要主动改这里
```

这条钉数的作用是防「有人删掉断言让测试变绿」。加断言属于正当变更，
正确处理是把钉数从 67 改成 70，而不是放宽比较 —— 后者会让「删断言」也蒙混过关。

改完：

```
回归：ALL PASS
补丁：114/114 已落实（100.0%）
ALL GREEN
```

记下来是因为这类失败很容易被误判成「我的改动弄坏了东西」而回滚掉。
---

# 优化记录（第 92 轮）：一次"搜到哪个文件"的静默选择，连带四个缺陷

起点：审 `datapath.py`。它已经害过我一次（第 83 轮，22/23 道题的泄漏检查
其实查的是同一张表），这轮把它彻底查了一遍。

## 总账

| 项 | 第 91 轮末 | 现在 |
|---|---|---|
| `find_xlsx` 选文件 | 静默、不可见 | 记录并在 CLI 披露候选数 |
| 生产磁盘缓存 | 任何一次外部扫描都会覆盖 | 只接受默认根那次扫描 |
| `mm.DS` 读坏文件 | 裸抛 `BadZipFile` traceback | 说清原因 + 指向 `--data` |
| `_data_note` 诊断输出 | 全走 stdout（`--json` 会被污染） | JSON 模式走 stderr |
| `mmkit_smoke.py` | 依赖「任意搜到的附件」 | 固定 `MMKIT_DATA` |
| 官方账目 | ALL GREEN | ALL GREEN（未破） |

## 一、根缺陷：`find_xlsx()` 的选择不可见

```python
hits = _rank(_XLSX_CACHE, prefer)      # prefer="" 时按遍历顺序
return hits[0][1] if hits else ""
```

工作区 80 多个 xlsx，不传 `prefer` 就返回**遍历顺序第一个**，对每道题都是同一个文件，
而且**永远不返回空** —— 选错了毫无提示。这就是第 83 轮白跑一整轮的原因。

契约不能改（自检钉住了「prefer 匹配不到就退回默认」），所以改成**记下来**：

```python
LAST_PICK = {path, n_candidates, prefer, ambiguous}
```

再在 `mmkit._data_note`（20 处命令的公共汇聚点）披露：

```
⚠ 工作区里找到 82 个 xlsx，本次用的是 附件 2：….xlsx（按遍历顺序取的）—— 要指定请加 --data
```

## 二、我在验证时踩到的第二个洞：外部扫描会覆盖生产缓存

用临时目录探 `find_xlsx(base=tmp)` 行为，结果那句话把三个假 `.xlsx`
写进了**共享磁盘缓存**。随后 `mmkit.py advise`（不带 `--data`）取到假文件，
openpyxl 抛 `BadZipFile` 直接崩：

```
zipfile.BadZipFile: File is not a zip file
```

修法：`_save_disk_cache` 只在「写的是**生产缓存文件**」且「扫的是默认根」时才落盘。
用 `_PROD_CACHE`（模块加载时的路径）与 `CACHE_FILE` 是否相等来区分生产/测试调用 ——
第一版我按「base 是不是默认根」判，把自检也拦了（2 项红），因为自检**故意**
用临时 base 去验证缓存机制。改判据后 15/15 通过，且实测：

```
默认根 -> 附件 2…xlsx | 候选 82 | 缓存已写: True
外部扫描后生产缓存被改写: False
缓存里含临时路径: False
```

## 三、第三个洞：坏文件裸抛异常

`mm.DS()` 直接让 openpyxl 的 `BadZipFile` 冒到命令行。在唯一汇聚点包一层：

```
读不了数据文件 '…\假的.xlsx'：BadZipFile: File is not a zip file。
如果它不是真正的 xlsx/csv，请用 --data 指定正确的文件。（这个文件是从工作区里搜出来的，共 N 个候选；要指定请加 --data）
```

## 四、第四个洞（早就存在，这轮被我自己引爆）：`--json` 被诊断输出污染

`mmkit` 里本来有 `if a.json: sys.stdout = sys.stderr` 的重定向。我给 `_data_note`
加了一行披露后，`mmkit_smoke.py` 立刻红：

```
[FAIL] --json 输出可解析且字段齐 — verify/fit/eda 都要在
```

原因不是重定向失效，而是**缓存改动让 `find_xlsx()` 选了另一个附件**
（附件 2 里没有 `宽度/深高/排数`）→ `run` 失败 → JSON 缺字段。

顺着这条线索查清了真正的测试缺陷：

> `mmkit_smoke.py` 的所有用例都不给 `--data`，全指望 `find_xlsx()` 搜到那个热阻附件。
> 那是一次任意选择，顺序一变就红，而代码其实没问题。

修法：在 `run()` 里给子进程设 `MMKIT_DATA`（`find_xlsx` 的第一优先级分支），
一处覆盖全部调用。`MMKIT_DATA` 分支**不受**磁盘缓存影响，测试从此确定。

同时把 `_data_note` 的 7 处 `print` 统一改走 `_note()`，
按 `_JSON_OUT` 决定 stdout/stderr —— 把「诊断输出污染 JSON」这类问题
收进一个函数，以后不会再零散复发。

## 五、修完的结果

```
mmkit_smoke exit=0（全部 PASS）
datapath selftest 15/15
mmkit selftest 79 通过
23/23 通过，0 道有警告
回归：ALL PASS   补丁：114/114
ALL GREEN
```

## 教训（值得单独记）

这一轮四个缺陷是**一条链**：一个不可见的任意选择，牵出缓存污染、裸异常、
测试漂移。它们都不是"写错了一行"，而是**"默认行为没人负责"**——
函数永远返回点东西、缓存永远能被任何人覆盖、异常直接往终端抛。
判据：**任何"替你选"的默认行为，都必须能被看见、被覆盖、被测试固定。**

## 未做（下一轮）

1. `falsify.limit_behavior` 仍未系统审。
2. `_rank` 里 `rest` 没有按优先级排序（`pref + rest` 保留了原顺序）—— 影响很小，
   但「按 PREFERRED 加权」在有空 prefer 时并不完全生效。
---

# 优化记录（第 93 轮）：能力清单在骗调用它的人

起点：查 `schema.json`（LLM 照它调参的能力清单）与真实 argparse 有没有漂移。

## 总账

| 项 | 第 92 轮末 | 现在 |
|---|---|---|
| `cmd` 的 choices | 26 个，其中 3 个不是命令 | **23 个，与实现一一对应** |
| `schema.json` | 8-小时前那份，比源码少 3.2 KB | 与源码同步（且进了验收） |
| `fuzzy` 在 schema 里 | **整条消失** | 有 desc + 12 个参数 |
| 文档命令数 | 19 / 22 / 26 三种说法 | 23（三处对齐实测） |
| 官方账目 | ALL GREEN | ALL GREEN + 新增「能力清单」一项 |

## 一、最严重的一条：三个"命令"其实不存在

`mmkit.py` 的 `cmd` choices 里放着 `cand`、`surface`、`formula`。

- `cand`、`surface` 是 **`plot --kind` 的取值**
- `formula` 根本没有实现

argparse 会照收，然后一路走到 `main()` 末尾的 `run()` 兜底。实测：

```
$ mmkit.py cand --y 热阻 --x 宽度
====================================================================================
数学建模插件 · heat_sink.xlsx
====================================================================================
  sheet=Sheet1  表头第 2 行  84 行 × 7 数值列
```

**它直接开始跑整篇论文。** 要一张 cand 图的人拿到一篇论文，还以为成功了。

修法：从 choices 移除。现在 `mmkit.py cand` 立刻报

```
mmkit.py: error: argument cmd: invalid choice: 'cand' (choose from run, solve, …)
```

而 `plot --kind cand` 仍然可用（验证过：74128 字节 PNG + 12673 字节 PDF）。

## 二、schema 漏了整个 `fuzzy`

`schema._parse_branches` 只认 `a.cmd == "x"`，而 fuzzy 是这么分派的：

```python
if a.cmd in ("greyrel", "fuzzy"):
```

于是 `fuzzy` **从 schema.json 里整条消失** —— LLM 看清单，根本不知道有这个命令。

改的过程中我犯了个错并当场发现：先按「下一个 `a.cmd` 标记」切分支，结果 greyrel 有参数、
fuzzy 是空 —— 因为真实结构是**外层 `in (...)` 里嵌着 `if a.cmd == "greyrel"`**，
按标记切会把外层砍在嵌套处。

正确做法是**按缩进**判分支范围。改完：

```
fuzzy -> ['--ahp','--directions','--grades','--json','--matrix','--membership',
          '--names','--normalize','--operator','--ref','--rho','--weights']
```

## 三、四个命令没有 desc

`fuzzy` / `experiment` / `contract` / `skeleton` 的 `DESC` 是空的：
清单告诉 LLM「有这个按钮」，却不说它干什么。补齐四条。

## 四、文档三处互不一致

| 位置 | 原值 |
|---|---|
| `插件速查.md` 标题 | 19 个命令 |
| `AGENTS.md` 第 5 行 | 19 命令 |
| `AGENTS.md` 表格 | 22 个子命令 |
| argparse（真） | 26 choices，其中 3 个假的 → **23** |

而 `插件速查.md` 的命令表本身也在骗人：它把 `cand`/`surface` 列成两行命令，
又漏了 `fuzzy`/`experiment`/`contract`/`skeleton` 四个真命令。

全部按实测改为 23，删两行假的、补四行真的，并注明 cand/surface 是 `plot --kind`。
顺带把 `gate.py` 的「19 项」改成实测的 **21 项**（`len(run_all(...)['checks'])`）。

## 五、加一道防线，让它不能再悄悄变陈

`schema.json` 只由 `schema.py build` / `selftest` 写出，没有任何流程定期重建。
`tools/verify_all.py` 现在多跑一项：

```
能力清单：与源码同步
```

比对时忽略 `generated_at`。双向验证过：

```
（手工把 n_commands 改成 19）-> DRIFT
（schema.py build）           -> SYNC
```

现在它进账了：漂移会让 `verify_all` 变红，不再是「没人看于是没人发现」。

## 复现

```powershell
$py = "C:\Users\21246\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
cd model1-arch
& $py mmkit.py cand --y 热阻        # 期望 exit 2 + invalid choice
& $py mmkit.py plot --kind cand --y 热阻 --x 宽度,深高 --out-png out/_t/c.png
& $py tools\probe_schema_vs_help.py  # 23 = 23，无差集
& $py tools\verify_all.py            # 含「能力清单：与源码同步」
```

## 未做（下一轮）

1. `falsify.limit_behavior` 仍未系统审。
2. 全局 `~/.dsh/AGENTS.md` 里也写着「19 命令 / 22 道回归基线」，同样过时。
   那是用户级配置，不在本仓范围，留待确认后一起改。
3. `_rank` 里 `rest` 未按 PREFERRED 优先级排序（第 92 轮记的，仍未动）。
---

# 优化记录（第 94 轮）：验证三件套有一半不在验收链上

起点：审 `falsify.limit_behavior`（第 92/93 轮记下的未审项）。

## 总账

| 项 | 第 93 轮末 | 现在 |
|---|---|---|
| 回归锁住的模块 | 14 项（缺 falsify/verify/freeze/abstract/figcheck/schema） | **20 项，全部现场量过** |
| `limit_behavior` 外推公式 | `/xstd*xstd` 自消（恒等于 1） | 直白原始单位公式 + 断言钉死 |
| 荒谬外推判据 | 只有 `y_bounds`（需人为阈值） | 新增**零穿越**（不需要阈值） |
| `_rank` 的 PREFERRED 加权 | prefer 不命中时失效 | 两级都对 |
| `falsify` 自检 | 11 项 | 15 项 |
| `datapath` 自检 | 15 项 | 17 项 |

## 一、最大的发现：三个验证模块不在验收链上

查 `tests/run_all.py` 的 CORE 清单，14 项里只有 `lanes.py` 属于验证三件套。
**`falsify.py` / `verify.py` / `freeze.py` 一条都不在。**

后果很直接：我改坏 `falsify`，`tools/verify_all.py` 照样报 ALL GREEN。
第 9~13 轮我动了 `abstract.py`、`figcheck.py`、`datapath.py`、`schema.py`，
其中只有 `datapath`（旧钉数）在链上 —— 其余四个的自检从来没人跑。

补上六项，数字全是现场跑出来的（不是抄的）：

```
falsify.py selftest   15 项
verify.py             16 项
freeze.py selftest    12 项
abstract.py selftest  20 项
figcheck.py selftest  11 项
schema.py selftest    15 项
```

同时把 `datapath.py` 的钉数从 15 改成 17（本轮加了 2 条）。

```
OK   falsify.py         15/15 断言
OK   verify.py          16/16 断言
OK   freeze.py          12/12 断言
OK   abstract.py        20/20 断言
OK   figcheck.py        11/11 断言
OK   schema.py          15/15 断言
ALL PASS
```

## 二、`limit_behavior` 的公式是自消的

```python
yhat = intercept + coef * (x - xmean) / (xstd or 1.0) * xstd
```

`/ xstd * xstd` 恒等于 1（xstd ≠ 0 时）。看着像「先标准化再还原」，
实际什么都没做 —— 而这种写法比写错更危险：读的人会以为传标准化系数也行。

改成直白公式，并**用断言钉住**，防止有人再加回去：

```
[PASS] 外推按原始单位公式算（/xstd*xstd 是自消的）
[PASS] 外推网格给出 6 个点  — 6
```

## 三、加一条不需要人为阈值的荒谬判据：零穿越

原来只有 `y_bounds=(lo, hi)` —— 得先知道「热阻不能为负」，也就是得有人为阈值。
新增 `y_sign`：

> 观测到的响应**全部同号**时，外推出现反号（穿过零点）就是荒谬。

这一条不依赖量纲、不需要阈值，只要数据本身能告诉你方向。

```
[PASS] 观测全正但外推穿零 → 报荒谬
[PASS] 外推未穿零 → 放行
[PASS] 不给约束时保持旧行为（只给网格）
```

## 四、`_rank` 的 PREFERRED 加权只在无 prefer 时生效

```python
pref = [(0, p) ...]; rest = [(pri + 1, p) ...]
return pref + rest          # rest 保持原顺序，没按 pri 排
```

于是传了 prefer（哪怕不命中）之后，带「附件」的文件反而可能排在不带的后头。
改成 `rest = sorted(...)`，两级都验过：

```
prefer 不命中时: ['附件 9.xlsx', 'y 中间.xlsx', 'z 其他.xlsx']
prefer 命中时:   ['y 中间.xlsx', '附件 9.xlsx', 'z 其他.xlsx']
```

## 五、一个如实记下的空白

`limit_behavior` **没有任何生产调用方** —— 只有它自己的自检在调。
冻结表 `冻结数字.json` 里只有 `{path, value}`，没有系数/截距，
所以 gate 现在拿不到 `coef/intercept` 去跑外推检验。

要真正接进去，需要：① 冻结表记下最优模型的系数与截距，或 ② gate 现场重拟合。
这轮没做，避免在半懂的状态下改 gate 的判决。

## 复现

```powershell
$py = "C:\Users\21246\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
cd model1-arch
& $py falsify.py selftest      # 15 项
& $py datapath.py selftest     # 17 项
& $py tools\verify_all.py
```

## 未做（下一轮）

1. 把 `limit_behavior` 接进 gate（需先解决系数来源，见第五节）。
2. 全局 `~/.dsh/AGENTS.md` 的「19 命令 / 22 道回归基线」仍过时（用户级配置）。
---

# 优化记录（第 95 轮）：外推判据先量后接，结论是「不能直接接」

## 总账

| 项 | 第 94 轮末 | 现在 |
|---|---|---|
| `limit_behavior` | 只会越界判据（需人为阈值） | + 零穿越判据 + **自变量定义域钳制** |
| 触发面（23 题） | 未测 | 未钳制 11 题 → 钳制后 **7 题** |
| `falsify` 自检 | 15 项 | 16 项 |
| 外推审计 | 无 | `tools/probe_extrapolation.py`（可跑、带退出码） |
| 官方账目 | ALL GREEN | ALL GREEN（未破） |

## 一、先量，再决定接不接

上一轮把 `limit_behavior` 判成「无生产调用方」，这轮本来打算直接接进 gate。
按规矩先量一遍：23 题的配置全跑，看会红多少。

**未钳制：11 题触发。** 但看数值就知道大半是空话：

```
icm2006c   外推到 x=-1511659.86 时预测 -4340578.64（穿过零点）
pop_panel  外推到 x=-1511681.67 时预测 -4313826.99（穿过零点）
queueing   外推到 x=-10.29      时预测 -17.18（穿过零点）
```

「服务台数 = -10」「人口 = -151 万」——**自变量本身已经不成立**，
再说因变量荒谬没有意义。

## 二、补一条：自变量也必须物理可行

`limit_behavior` 新增 `x_sign`：观测到的 x 全部同号时，把外推网格限制在同号半轴内。

```
不钳制: [-0.22, -0.08, 0.06, 1.04, 1.18, 1.32]
钳制后: [0.06, 1.04, 1.18, 1.32]
```

钳制后重测：**7 题**，且 x 都落在可行区间：

```
evaluation  x=23.33（交付周期）  y 预测 -11.34
queueing    x=1.94（服务台数）   y 预测 -13.26
population  x=1986.2（年份）     y 预测 -4759.82
simulation  x=0.10（服务率）     y 预测 -3.75
birth_rate  x=5.90               y 预测 -34.11
nflis       x=2005.8（年份）     y 预测 -3956300
dwts2026c   x=0.4（年龄）        y 预测 -2.31
```

这 7 条是**真信号**：线性模型稍一外推就预言负的计数/比例，而论文里没有一句话
说明「本模型只在观测区间内有效」。

## 三、结论：不接进 gate，先做成可跑的审计

接进去 = 7 道题立刻变红，而它们缺的是一句声明，不是数据错。
所以这轮做的是：

- `falsify.limit_behavior` 具备完整判据（越界 / 零穿越 / 自变量钳制）
- `tools/probe_extrapolation.py` 可跑、带退出码（0 无、1 有）、`--json` 可机读

**没有假装它在账目里。** 下一步要接，得先给模板加一段「适用区间」声明，
再重跑那 7 道题 —— 那是下一轮的事，不是顺手能做的。

## 四、自检 15 → 16 项

```
[PASS] x_sign 剔掉非正的自变量取值  — [0.06, 1.04, 1.18, 1.32]
```

回归钉数同步 15 → 16。

## 复现

```powershell
$py = "C:\Users\21246\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
cd model1-arch
& $py falsify.py selftest                # 16 项
& $py tools\probe_extrapolation.py       # 期望 7 题、exit 1
& $py tools\verify_all.py                # ALL GREEN
```

## 未做（下一轮）

1. 给 `paper.py` 加「适用区间」声明段，然后把这 7 道题重跑，再把判据接进 gate。
2. 剩余 12 题里 5 道 y 有正有负，零穿越判据不适用 —— 需要一个「合理区间」的替代判据
   （例如偏离观测均值 N 个标准差），但那要人为阈值，先不做。
3. 全局 `~/.dsh/AGENTS.md` 的「19 命令 / 22 道回归基线」仍过时（用户级配置）。
---

# 优化记录（第 96 轮）：外推判据落进论文，并纠正上一轮的一个错数

## 总账

| 项 | 第 95 轮末 | 现在 |
|---|---|---|
| 触发「外推荒谬」的题 | 报 7 题 | **实为 5 题**（上一轮常数项错位，见第一节） |
| 论文里的适用区间声明 | 无 | **4 道题已写入**（network/clustering/birth_rate/simulation） |
| `falsify` 约定 | `limit_behavior` 与 `polyfit` 混用 | 新增 `fit_centered`，调用方不可能传错 |
| 官方账目 | ALL GREEN | ALL GREEN（未破） |

## 一、先纠正上一轮：7 题是错的，实为 5 题

`limit_behavior` 用的是**中心化**公式 `intercept + coef*(x - xmean)`，
而 `np.polyfit` 给的截距是 **x = 0 处**的值。我的探针直接把 polyfit 的结果喂进去，
**常数项整体平移了 `coef*xmean`** —— 预测值错位，报出一批不存在的荒谬。

改正后（同一批数据）触发的题目**换了一组**：

```
旧（错）：evaluation / queueing / population / simulation / real_c2024 /
         icm2006c / pop_panel / age_struct / birth_rate / nflis / dwts2026c   （11 条）
新（对）：network / clustering / simulation / birth_rate / dwts2026c           （5 条）
```

修法不是调数字，是**消灭两套约定**：新增 `falsify.fit_centered(xs, ys)`，
返回的 dict 可直接作为 `limit_behavior(**d)` 的入参，并在 docstring 里写清
intercept 是 x = xmean 处的值。断言钉住：

```
slope 应为 3.0 : 3.0
intercept 应是 x=3 处的值 16.0 : 16.0
```

## 二、论文里补上「适用区间」小节

`mmkit._applicability(ds, xs, ycol)` 算出每个因子的观测区间、斜率、零点位置，
写进 `rep` （因此也会被冻结、可被 `verify.py` 溯源）。`paper.py` 据此生成：

> **Where this model is valid**
> Every coefficient above was estimated on the observed range and carries no
> information outside it: Service rate in $[1.02189,\, 1.59547]$; …
> On that range the sign of the slope is well determined. Pushed past it, the
> same straight line reaches zero at Service rate $= 1.65415$ and turns negative
> beyond, which is not a physically admissible value for this response.
> The linear form is therefore an interpolation, not an extrapolation.

数字全部来自数据，不是手写。已重生成 4 道题，`numbers` 检查仍 PASS
（simulation：114/115 可溯源，0.9%）。

## 三、三个自己挖的坑（当场发现并修掉）

1. **顺序反了**：`rep["applicability"]` 原本在论文写完之后才计算，
   于是 ctx 里没有、正文里也就没有这一节。移到 ctx 构造之前。
2. **同一个 dict 加两次键** → `SyntaxError: keyword argument repeated: applicability`。
3. **因子名没转义**：`judge_avg` 带下划线直接写进正文 →
   `! Missing $ inserted` → d2026c 编译失败。改成走 `describe` + `esc_tex`。

第 3 条暴露了一个更大的问题：**我用 `mmkit run` 重生成 d2026c，产物不等于原件**
（原件 17 页、带 `evidence.json` / `model_stats.json` / claims 节；
重生成 19 页、无 claims、abstract 掉到 84.2 分）。

按规矩先找备份，发现 `out/runs_backup_r4/dwts2026c/` 正是原件（719192 B / 17 页），
**已恢复，gate 无异常**。d2026c 的适用区间小节这轮没加 ——
它的生成路径与 `run` 不等价，手改又会引入未溯源数字，留待下一轮按原路径重做。

## 四、当前状态

```
23 题异常：无
network / clustering / birth_rate / simulation：均已含适用区间小节
23/23 通过，0 道有警告
回归：ALL PASS   补丁：114/114   能力清单：与源码同步
ALL GREEN
```

## 复现

```powershell
$py = "C:\Users\21246\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
cd model1-arch
& $py tools\probe_extrapolation.py    # 期望 5 题、exit 1
& $py falsify.py selftest             # 16 项
& $py tools\verify_all.py
```

## 未做（下一轮）

1. d2026c 的适用区间小节（需先复现它的原始生成路径）。
2. 把判据接进 gate：现在 5 题里有 4 题已写声明，d2026c 还没写 —— 接进去会红 1 道。
3. 全局 `~/.dsh/AGENTS.md` 的「19 命令 / 22 道回归基线」仍过时（用户级配置）。
---

# 优化记录（第 97 轮）：外推判据正式接进 gate

三轮的线在这里收口：先量（95）→ 补声明（96）→ 接进验收（97）。

## 总账

| 项 | 第 96 轮末 | 现在 |
|---|---|---|
| gate 检查项 | 21 | **22**（新增 `extrap`） |
| `extrap` 判据 | 只有独立审计工具 | **进 gate，SOFT** |
| 23 题结果 | — | `extrap` 22 PASS / 1 WARN → 补声明后 23 PASS |
| `mm.applicability` | 在 mmkit 里（`_applicability`） | 移到 `mm.py`，与 gate 共用单一定义 |
| 护栏自检 | 53 项 | **56 项** |
| 官方账目 | ALL GREEN | ALL GREEN |

## 一、先确认 d2026c 本来就有声明

上一轮我以为 d2026c 缺这一节。查它的 tex，`\subsection{Scope of extrapolation}`（L579）已经写着：

> The model is fitted on seasons 1 to 34 and should not be extrapolated outside
> that observed range. … beyond it, no claim is made.

所以 5 道触发题里，4 道靠模板新生成、1 道本来就有 —— **不必再动 d2026c**
（它的生成路径与 `mmkit run` 不等价，上一轮已经踩过并回滚）。

## 二、`_applicability` 移进 mm.py

`gate` 也要用它判「论文有没有说清适用区间」，而 `mmkit` 不能反向依赖 gate。
按第 85 轮 `suspect_leak` 的做法：定义搬到 `mm.py`（`mm.applicability(ds, xs, y)`），
`mmkit` 改成调用它，gate 直接调。搬完实测：

```
mm.applicability 正常: 3 条
   到达率 absurd= False
   服务率 absurd= True
   服务台数 absurd= False
```

## 三、新检查 `chk_extrap`

判据（全部来自数据，没有人为阈值）：

1. 用 `mm.applicability` 逐个因子算：观测区间、斜率、零点位置；
2. 只在「因变量同号 + 零点落在观测区间外一步之内」时才算荒谬；
3. 荒谬 → 论文必须出现声明（`should not be extrapolated` / `outside the
   observed range` / `scope of extrapolation` / `where this model is valid` /
   适用区间 / 外推 …）；
4. 没声明 → WARN，并点名哪个因子、零点在哪。

接进 gate 后的真实结果：

```
extrap 分布: {'PASS': 22, 'WARN': 1}
  icm2006c  WARN  1 个因子外推一步就穿零（pop2000（零点 58.2481）），
                  但论文没说哪里不适用
```

`icm2006c` 是这轮新抓出来的（不在上一轮审计的 5 道里）：人口列推到 2000 年
58 人以下，2005 年人口会算成负数。用新模板重生成后转 PASS（24 页 / 606994 字节）。

## 四、双向回归

```
J. 外推判据：会穿零就必须声明适用区间（双向）
  [PASS] 会穿零且未声明 → WARN
  [PASS] 会穿零但已声明 → PASS
  [PASS] 不穿零时不要求声明
```

第三条是负向对照：别把「不穿零」也拖进来要求声明。

## 五、当前状态

```
23/23 通过，0 道有警告        （gate 22 项）
回归：ALL PASS   补丁：114/114   能力清单：与源码同步
护栏自检 56 项；falsify 自检 16 项
ALL GREEN
```

## 复现

```powershell
$py = "C:\Users\21246\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
cd model1-arch
& $py gate.py out/runs/icm2006c      # 期望 extrap PASS
& $py tools\test_gate_strict.py      # 56 项
& $py tools\verify_all.py            # ALL GREEN
```

## 未做（下一轮）

1. `extrap` 目前只查「零点」这一种荒谬；`y_bounds`（超出物理上下界）没有配置来源，
   仍是空着的分支。
2. 全局 `~/.dsh/AGENTS.md` 的「19 命令 / 22 道回归基线」过时（用户级配置，待确认）。
3. 25 轮前记的 `contract.py` / `orchestrate.py`「未接进主流程」，一直没人审。
---

# 优化记录（第 98 轮）：试错循环的判据恒真，以及两个被文档误标为「未接线」的模块

## 总账

| 项 | 第 97 轮末 | 现在 |
|---|---|---|
| `contract` / `experiment` | 文档标「未接进主流程」 | **实测可用**，已进回归链 |
| 编排判据 | 空判据 → 全部 pass | 空判据 → `unknown`；劣于基线 → `fail` |
| 回归锁住的模块 | 20 项 | **22 项**（+contract 7、+orchestrate 19） |
| `orchestrate` 自检 | 15 项 | **19 项** |
| 官方账目 | ALL GREEN | ALL GREEN |

## 一、先验证「未接线」这句话

AGENTS.md 写着 `contract.py` / `orchestrate.py`「**未接进主流程**」。实测：

```
$ mmkit.py experiment --rounds 1
编排结果：1 轮 / 3 次尝试 / 0.02 min
停止原因：第 1 轮达标且是最优（A）
  R1 A race  OK pass resid.r2_structure=0, resid.bp=1.942
  R1 B run   OK pass fit.best_rmse=0.01248, fit.baseline_rmse=0.01933
  R1 C solve OK pass rmse=0.01465
```

**两条命令都在主流程里且能跑。** 文档那句是陈的（这已是第 4 处陈文档）。

## 二、但「3 条全 pass」值得怀疑——果然有洞

`default_judge` 的循环体：

```python
ok = True
for name, target in crit.items():   # crit 为空 → 一次都不跑 → ok 恒为 True
```

**空判据 → 每条路线都 pass。** 实测 `mmkit.py contract` 就要求每条提案必须有
`success_criteria`，所以内建提案不会踩到；但 LLM 给的提案若不写，就会静默全 pass。

顺带看清另一件事：内建提案的判据是**故意恒真**的
（`cv_rmse_max: 1e9`、`n_rows_min: 1`），注释写着「只表达算出了有效数值」——
可输出却打印「达标且是最优」，读起来像质量结论。

修两条：
1. **空判据不再判 pass**：拿得到 `best_rmse` 与 `baseline_rmse` 就按
   「打不过均值基线等于没建模」判，拿不到判 `unknown`。
2. **声明判据不能豁免基线**：即使 `cv_rmse_max: 1e9` 满足了，
   只要同时有两个 RMSE 且 best ≥ baseline，仍判 `fail`。

## 三、四条断言钉住（双向 + 边界）

```
[PASS] 空判据但优于基线 → pass
[PASS] 空判据且劣于基线 → fail
[PASS] 空判据且无指标 → unknown（不冒充通过）
[PASS] 恒真判据 + 劣于基线 → fail
```

修完 `experiment` 的输出没变（B 的 0.01248 < 0.01933，本来就该过）——
说明改动没有把正常路径误伤。

## 四、补进回归链

`contract.py`（7 项）与 `orchestrate.py`（19 项）同样**不在 `tests/run_all.py` 里**。
第 14 轮刚补过六个模块，这次又发现两个 —— 说明「哪些模块上了链」这件事
一直是靠人记，而不是靠机制。

```
OK   contract.py        7/7 断言
OK   orchestrate.py     19/19 断言
ALL PASS
```

## 五、端到端确认 contract 真的会拒

```
（1 条提案）      -> {'ok': False, 'batch_errors': ['只提了 0 条，至少 3 条']}
（3 条缺字段）    -> {'ok': False, 'per_route_errors': {A/B/C: ["缺字段 'success_criteria'"]}}
（3 条齐字段）    -> {'ok': True}   exit=0
```

小瑕疵（未改）：递单个 dict 而非列表时，报「只提了 0 条」而不是
「提案必须是列表」。措辞不准，但拒绝行为是对的。

## 六、文档同步

`AGENTS.md` 两处：`gate.py` 21 → **22** 项；`contract/orchestrate` 改成
「已接进主流程（实测可用；已进回归链）」。

## 复现

```powershell
$py = "C:\Users\21246\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
cd model1-arch
& $py mmkit.py experiment --rounds 1     # 3 条路线 + 判定
& $py orchestrate.py selftest            # 19 项
& $py tools\verify_all.py                # ALL GREEN
```

## 未做（下一轮）

1. `experiment` 的措辞：「达标」应改成「产出有效数值」或直接报是否打过基线。
2. `contract` 对「单个 dict 而非列表」的报错措辞。
3. `extrap` 的 `y_bounds` 分支仍无配置来源。
4. 全局 `~/.dsh/AGENTS.md` 的「19 命令 / 22 道回归基线」过时（用户级配置）。
---

# 优化记录（第 99 轮）：两句会误导人的话

这两处都不是算法错，而是**输出文案在冒充它没有的判断**。

## 总账

| 项 | 第 98 轮末 | 现在 |
|---|---|---|
| `experiment` 停止原因 | 「第 1 轮达标且是最优」 | 「有路线过判据且为当前最优；判据来自提案，不代表质量结论」 |
| `contract` 收到单个 dict | 「只提了 0 条」（像是文件空了） | 「提案必须是列表…现在收到的是单个路线对象」+ 示例 |
| `y_bounds` 分支 | 无配置来源 | **实测后决定不接**（见第三节） |
| 官方账目 | ALL GREEN | ALL GREEN |

## 一、`experiment` 的「达标」

上一轮把判据的漏洞修了（空判据 → unknown，劣于基线 → fail），但这句文案还在：

```
停止原因：第 1 轮达标且是最优（A）
```

内建提案的判据是 `cv_rmse_max: 1e9` 这种恒真式 —— 「达标」二字读起来像质量
结论，实际只说明「过了一个很松的筛子」。改成：

```
停止原因：第 1 轮有路线过判据且为当前最优（A）；判据来自提案，不代表质量结论
```

同时把「跑满 N 轮，未达标」改成「没有路线过判据」、「判据过松（达标但不是最优）」
改成「过判据但不是最优」—— 让「判据」与「质量」在措辞上分开。

## 二、`contract` 把「形状错」报成「内容空」

```python
batch = pj.get("proposals") if isinstance(pj, dict) else pj
```

递一个**单个路线对象**时，`pj.get("proposals")` 是 None → `[]` →
报「只提了 0 条，至少 3 条」。那句话会让人以为文件是空的，而文件里明明有内容。

改成先看形状：

```
提案必须是**列表**（或 {"proposals": [...]}），现在收到的是单个路线对象。
示例：[{...}, {...}, {...}] —— 至少 3 条。
```

双向验过：

```
单个 dict        -> 上面两句 + exit=2
{"proposals":[…]} -> 提案 3 条；{'ok': True, ...} + exit=0
```

## 三、`y_bounds`：量了之后决定不接

`limit_behavior` 的 `y_bounds`（物理上下界）一直没有配置来源。
本来想用一条不需要配置的规则补上：**响应全在 [0,1] 内就当比例，界取 [0,1]**。

先量：23 道题里响应落在 [0,1] 的只有 **1 道**（heat_sink，0.722–0.774）——
而它是**无量纲热阻**，不是比例。那条规则会在这一道题上「碰巧成立」，
理由却是错的。

所以不接。这条分支继续留着（自检里有 `y_bounds=(0,10)` 的用例覆盖它），
但要接进 gate 得先有每题的真实物理界，那属于配置层的事。

## 四、当前状态

```
23/23 通过，0 道有警告        （gate 22 项）
回归：ALL PASS   补丁：114/114   能力清单：与源码同步
orchestrate 自检 19/19；contract 7/7
ALL GREEN
```

## 复现

```powershell
$py = "C:\Users\21246\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
cd model1-arch
& $py mmkit.py experiment --rounds 1     # 停止原因应说明「不代表质量结论」
& $py mmkit.py contract --proposal <单个对象的 json>   # 期望清晰的形状提示
& $py tools\verify_all.py
```

## 未做（下一轮）

1. `y_bounds` 需要每题的真实物理界（配置层）。
2. 全局 `~/.dsh/AGENTS.md` 的「19 命令 / 22 道回归基线」过时（用户级配置）。
3. `tests/run_all.py` 的 CORE 清单仍靠人记着补（第 14、18 轮各漏过一批）。
   可以加一条自检：仓库里所有带 `selftest` 的模块必须在 CORE 里出现。
---

# 优化记录（第 100 轮）：一半的自检从没跑过，其中一个早就崩了

## 总账

| 项 | 第 99 轮末 | 现在 |
|---|---|---|
| 带 selftest 的模块 | 46 个 | 46 个（不变） |
| 其中在回归链上 | 20 个（43%） | **41 个（89%）** |
| CORE 条数 | 22 | **42** |
| `patches.py selftest` | **崩溃**（IndexError） | 12/12 通过 |
| `verify_all` 的回归行 | 「最近一次失败：ALL PASS」 | 「ALL PASS」 |
| 官方账目 | ALL GREEN | ALL GREEN |

## 一、先量：到底有多少模块的自检没人跑

```
带 selftest 的模块: 46
CORE 已登记: 20
未登记: aitaste / cards / chk_cross / cite / dataprof / distill / gate /
        innovation / kb_loader / kind / limit / patches / pipeline /
        plot_mpl / q4 / review / rules / rules_apmcm / score /
        verify_math + tools 下 7 个
```

**超过一半的自检从没进过验收。** 第 14、18 轮各补过一批，都是碰巧想起来的。

## 二、逐个跑一遍，抓到一个真崩溃

26 个未登记模块里 25 个通过，`patches.py` 崩了：

```
IndexError: list index out of range
  ck("下一步不推荐已完成的", ..., nu.splitlines()[1][:40])
```

崩因很能说明问题：补丁**已经 114/114 全落实**，`next_up(3)` 没有可推荐的 →
返回的行数不足 2 → 取不到第 2 行。也就是说**补丁做完的那天它就崩了**，
而它的自检不在链上，一直没人发现。

顺带发现断言本身也写错了：

```python
ck("有待做的", any(not r["ok"] for r in rows), ...)
```

这条要求「必须还有未落实的补丁」—— 等于**断言项目永远不许完工**。
全落实是合法终态，改成一致性断言「已落实 + 待做 = 总数」。

修完：

```
[PASS] 已落实 + 待做 = 总数  — 114 + 0 = 114
[PASS] 全部落实时 next_up 明说没有待做的
ALL PASS  12/12
```

`next_up` 也补了一句人话（原来是「下一步（0 项）：」后面什么都没有）：

```
下一步（0 项）：
  （没有待做的补丁：全部已落实）
```

## 三、计数规则要认两种输出格式

`run_all.py` 原来只数 `[PASS]` 行。但一半模块不逐条打点，只在末尾印
`ALL PASS 12/12` —— 钉进去就是 0/N 恒失败。

加了回退：没有 `[PASS]` 行时从 `ALL PASS n` 里取 n。三个模块因此先钉错、
复跑后改正（`chk_cross` 4、`rules_apmcm` 4、`verify_math` 20——
最后这个是「自报 8/8 但实际打了 20 条 `[PASS]`」）。

## 四、顺手修显示

```
回归：最近一次失败：ALL PASS      ← 旧
回归：ALL PASS                   ← 新
```

原来只要行里含 `ALL PASS`/`FAILED` 就算，抓到了重试日志的回显，读起来像回归挂了。
改成只认**以这两个词开头**的结论行，并取最后一条。

## 五、当前状态

```
23/23 通过，0 道有警告        （gate 22 项）
回归：ALL PASS（CORE 42 条，覆盖 41 个模块）
补丁：114/114   能力清单：与源码同步
ALL GREEN
```

## 复现

```powershell
$py = "C:\Users\21246\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
cd model1-arch
& $py tools\probe_selftest_coverage.py   # 哪些带自检的模块不在链上
& $py patches.py selftest                # 12 项
& $py tools\verify_all.py                # ALL GREEN
```

## 未做（下一轮）

1. 剩下 5 个带 selftest 但未上链的：`chk_cross` 之外还有 tools 下 7 个
   （`dp / fit_params / mip / net_metrics / queueing / stat_tests / topsis`），
   它们都通过，但要不要每次验收都跑要权衡时长（`limit.py` 就要 31 秒）。
2. `verify_math.py` 自报 8/8 与实际 20 条 `[PASS]` 不一致；它还把「故意喂错值」的
   演示打成 `[FAIL]`，容易与真失败混淆。建议换成 `[EXPECT-FAIL]` 之类的标记。
3. 全局 `~/.dsh/AGENTS.md` 的「19 命令 / 22 道回归基线」过时（用户级配置）。
---

# 优化记录（第 101 轮）：自报 8、实际打 20 —— 钉数该信谁

## 总账

| 项 | 第 100 轮末 | 现在 |
|---|---|---|
| `_count` 取值规则 | 优先数 `[PASS]` 行 | **优先读模块自报的 `n/n`** |
| `verify_math` 钉数 | 20（数的是演示行） | **8（自报断言数）** |
| 故意的 `[FAIL]` | 混在日志里像真失败 | 打印前先说明「下一条是故意的」 |
| 重试日志措辞 | 「重试 1 次，其中通过 0 次」 | 「历史上重试 N 次（非本次结论）」 |
| 官方账目 | ALL GREEN | ALL GREEN |

## 一、先量：41 个模块里只有一个自报与输出不一致

写了 `tools/probe_count_consistency.py` 把 CORE 里每个模块的「自报数」与
「`[PASS]` 行数」都比了一遍：

```
不一致（自报 ≠ [PASS] 行数）: 1
  verify_math.py: 自报 8 / [PASS] 20 / 当前钉数 20
```

其余要么一致（kind 7/7、cards 19/19…），要么没有自报（`graph.py`、`mmkit.py`）。

## 二、`verify_math` 为什么是 8

它自己有 8 条 `ck(...)`：

```
5 条比较器逻辑 + 能抓出错值 + 三层都能跑出结果 + 真数据全部通过 = 8
```

另外 12+11 条 `[PASS]` 是 `report(rows)` 打印的**数据对拍行**，不是自检断言。
所以 8 才是它的断言数，20 是我上一轮按 `[PASS]` 行数钉错的结果。

钉错的后果不只是数字难看：数据一变（多一对比较）钉数就漂，而断言一条没变。

**修法：`_count` 优先读模块自报的 `ALL PASS n/n`，没有再数 `[PASS]` 行。**
这样钉的是「它自己承认做了几条断言」，比数打印行稳定。

## 三、顺带两处措辞

1. `verify_math` 那条故意的失败，在日志里长这样：

```
最近一次失败：[FAIL] 故意错   实得 3   期望 2
```

读起来像真失败。现在打印前先说一句：

```
（下一条 [FAIL] 是故意的：验证对拍器能抓错）
```

2. 回归末尾的重试汇总来自 `RETRY_LOG`——**跨运行累积**的历史。
原来写「重试 1 次，其中通过 0 次」，而底部明明 ALL PASS，两句话互相矛盾
（那记录还是我第 11 轮钉错数时留下的）。改成：

```
历史上重试 2 次（通过 0 次，非本次结论）  ← 反复重试，本身不稳
```

## 四、当前状态

```
23/23 通过，0 道有警告        （gate 22 项）
回归：ALL PASS（CORE 42 条，覆盖 41 个模块）
补丁：114/114   能力清单：与源码同步
ALL GREEN
```

## 复现

```powershell
$py = "C:\Users\21246\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
cd model1-arch
& $py tools\probe_count_consistency.py   # 期望「不一致: 0」
& $py tests\run_all.py                   # verify_math 应显示 8/8
& $py tools\verify_all.py                # ALL GREEN
```

## 未做（下一轮）

1. `RETRY_LOG` 只加不减，会一直长。该加个上限（保留最近 N 条）。
2. 剩 5 个带 selftest 未上链（tools 下 7 个都通过，但要不要每次跑要权衡时长）。
3. 全局 `~/.dsh/AGENTS.md` 的「19 命令 / 22 道回归基线」过时（用户级配置）。
---

# 优化记录（第 102 轮）：覆盖率收口到 46/46

## 总账

| 项 | 第 101 轮末 | 现在 |
|---|---|---|
| 带 selftest 的模块 | 46 | 46 |
| 其中在回归链上 | 41（89%） | **46（100%）** |
| CORE 条数 | 42 | **49**（47 个模块 + 2 条同模块其它子命令） |
| `RETRY_LOG` | 只加不减 | 上限 400 条，保留最新 |
| 官方账目 | ALL GREEN | ALL GREEN |

## 一、tools/ 下 7 个一次钉完

上一轮量过它们的耗时：dp 0.1s / fit_params 0.7s / mip 0.1s / net_metrics 0.1s /
queueing 0.0s / stat_tests 0.0s / topsis 0.1s —— **合计约 1.1 秒**，不构成负担。

它们只打 `[PASS]` 行、汇总没有 `n/n`，所以按行数钉：

```
OK   tools/dp.py          27/27 断言
OK   tools/fit_params.py   5/5 断言
OK   tools/mip.py         13/13 断言
OK   tools/net_metrics.py 14/14 断言
OK   tools/queueing.py    16/16 断言
OK   tools/stat_tests.py  13/13 断言
OK   tools/topsis.py       5/5 断言
```

收口后复量：

```
CORE 条数: 49   去重模块数: 47
带 selftest 的模块: 46
仍未上链: 无
```

（49 > 46 是因为 `ledger.py` 占三条：`guard` / `audit` / `replay`。）

## 二、`RETRY_LOG` 加保留上限

那个文件跨运行累积，攒几百条以后「最近 6 次」的窗口会被更早的记录挤掉。
现在写满 400 条就重写保留最新 400 条。实测：

```
写入 450 条后实际保留: 400
保留的是最后几条: [..., "r448", "r449"]
```

## 三、当前状态

```
23/23 通过，0 道有警告        （gate 22 项）
回归：ALL PASS（CORE 49 条，覆盖 46/46 个带自检的模块）
补丁：114/114   能力清单：与源码同步
ALL GREEN
```

## 复现

```powershell
$py = "C:\Users\21246\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
cd model1-arch
& $py tools\probe_selftest_coverage.py   # 期望「未上链」为空
& $py tests\run_all.py                   # 49 条全部 OK
& $py tools\verify_all.py                # ALL GREEN
```

## 未做（下一轮）

1. 全局 `~/.dsh/AGENTS.md` 的「19 命令 / 22 道回归基线」过时（用户级配置，我一直没动）。
2. 剩下没被任何检查覆盖的东西：`contract.py` 的 `validate_batch` 有 7 条断言，
   但「提案字段语义」（例如 method 与实际参数是否匹配）只做了反射比对，
   没有端到端跑通一条真提案 → 真跑。
3. `orchestrate` 的 `_better()` 比较规则还没审。
---

# 优化记录（第 103 轮）：谁算「最优」这条规则本身是错序的

## 总账

| 项 | 第 102 轮末 | 现在 |
|---|---|---|
| `_better` 的比较方式 | 遍历共享指标，**命中即返回 True** | **帕累托支配**（全不差 + 至少一项严格更好） |
| 可比指标范围 | 只认名字含 `rmse` / `r2` | + `aic/bic/mae/coverage…`，并显式跳过方向不明的 |
| 方向判定顺序 | 先判 `LOWER` | 先判 `HIGHER`（`resid.r2_structure` 归 r2） |
| `orchestrate` 自检 | 19 项 | **24 项** |
| 官方账目 | ALL GREEN | ALL GREEN |

## 一、原规则的三个问题

```python
for k in shared:
    if "rmse" in k.lower() and v < old: return True
    if "r2" in k.lower() and v > old: return True
return False
```

1. **只认两类名字**：`aic`、`bic`、`coverage` 等共同指标一律不算。两条只共享
   `aic` 的路线永远「不可比」，先跑的那条自动成为最优 —— 而这件事没写在任何地方。
2. **矛盾时按遍历顺序先到先得**：A 的 rmse 更好、r2 更差时，谁当最优取决于
   dict 的插入顺序。同一批数据，只要字段顺序变一下，结论就变。
3. 上面两条都没有文档说明，读代码的人会以为它在做「综合比较」。

## 二、改成帕累托支配

> **所有可比指标都不差，且至少有一项严格更好**，才叫更好。

- 方向表分两类：越小越好 `rmse/mse/mae/error/aic/bic/gap`，
  越大越好 `r2/coverage/accuracy/precision/recall/score/f1/auc`；
- **方向不明的指标直接跳过**，不凭名字猜；
- 全相等不算更好（没有严格改进）。

## 三、我自己在改的过程中埋了一个坑

第一版我把 `"resid"` 放进了 `LOWER`。而 `resid.r2_structure` 同时含 `"r2"` 与
`"resid"` —— 先判 `LOWER` 就把它当成「越小越好」，**方向整个反了**，而且
`Orchestrate` 里最常用的指标名恰恰是这种带命名空间前缀的。

`resid` 是命名空间前缀，不是度量语义。修法两条：把 `resid` 从方向表里删掉；
判定顺序改成**先判 HIGHER**，让真正决定方向的 `r2` 先命中。

```
resid.r2_structure 更高 → 更好          OK
resid.r2_structure 更低 → 不算更好      OK
fit.best_rmse 更小 → 更好               OK
rmse 更好但 r2 更差 → 不算              OK
```

## 四、五条断言钉进自检

```
[PASS] resid.r2_structure 更高才算更好（方向别反）
[PASS] rmse 更好但 r2 更差 → 不算更好（不许先命中先赢）
[PASS] 全相等 → 不算更好（无严格改进）
[PASS] 只共享 aic 也能比（越大越好的词之外不再漏）
[PASS] 方向不明的指标被跳过，不凭名字猜
```

`orchestrate` 19 → 24 项；实测 `mmkit.py experiment --rounds 1` 的输出与改前一致
（三条路线本就没有共同指标），说明这次只把错序的规则换成确定的规则，
没有改变既有结论。

## 五、当前状态

```
23/23 通过，0 道有警告        （gate 22 项）
回归：ALL PASS（CORE 49 条，覆盖 46/46）
补丁：114/114   能力清单：与源码同步
ALL GREEN
```

## 复现

```powershell
$py = "C:\Users\21246\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
cd model1-arch
& $py orchestrate.py selftest          # 24 项
& $py mmkit.py experiment --rounds 1
& $py tools\verify_all.py
```

## 未做（下一轮）

1. `contract.py` 只做反射比对，没端到端跑通一条真提案。
2. 全局 `~/.dsh/AGENTS.md` 的「19 命令 / 22 道回归基线」过时（用户级配置）。
3. `orchestrate._fail_kind` 把错误分成几类，但分类判据没见过实测样本。
---

# 优化记录（第 104 轮）：契约存在，但执行入口不认它

## 总账

| 项 | 第 103 轮末 | 现在 |
|---|---|---|
| `experiment --propose-json` | **跳过契约校验** | 默认先过契约，`--no-contract` 才绕过 |
| 提案形状处理 | 单个 dict → 静默变成「0 条」 | 与 `contract` 一致，明确报错 |
| 判据点名了没报告的指标 | 判 **fail** | 判 **unknown**（查不到 ≠ 没通过） |
| `orchestrate` 自检 | 24 项 | **26 项** |
| `schema.json` | 33,181 B | 33,415 B（多一个开关） |
| 官方账目 | ALL GREEN | ALL GREEN |

## 一、端到端跑真提案，抓出两件事

我写了一份真提案（三条 `run` 路线，只换 `--x`），分别喂给两个入口：

```
$ mmkit.py contract --proposal real.json
  提案 3 条；结果：{'ok': False, ... '3 条提案只有 1 种结构 —— 其余是同构变体'}

$ mmkit.py experiment --propose-json real.json --rounds 1
  用外部提案：3 条
  R1 A run OK fail   R1 B run OK pass   R1 C run OK pass
  最优：R1 C
```

**契约说不行，执行入口照跑。** 契约成了摆设 —— 它只在自己那个子命令里生效。

顺带确认了一件好事：第 18 轮加的基线规则在真数据上真的起作用了 ——
A 的 `best_rmse=0.01102` 对 `baseline=0.0112` 被判 `fail`，C（0.00743）拿到最优。

## 二、改成默认过契约

`experiment --propose-json` 现在先跑 `contract.validate_batch`，不过就拒，
并逐条打印原因；要绕过必须显式写 `--no-contract`。

```
默认：        提案没过契约，先修它（或用 --no-contract 显式绕过）：
                整体: 3 条提案只有 1 种结构 ……    exit=2
--no-contract：用外部提案：3 条 ……                exit=0
```

形状处理也同步了（单个路线 dict → 明确报「必须是列表」，不再静默变 0 条）。

## 三、又一个「把不知道说成知道」

跑真提案时看到 A 被判 fail，理由却很奇怪：它的判据是 `n_rows_min: 1`，
而 `run` 路线只报 `fit.best_rmse` —— **判据点名的指标根本没被报告**。

原代码遇到这种情况直接 `ok = False`。但「查不到这个指标」不是「没通过」，
这与第 98 轮修的「空判据判 pass」是同一类错误的镜面。改成 `unknown`：

```
[PASS] 判据的指标没报告 → unknown（查不到 ≠ 没通过）
[PASS] 有指标明确违反时仍判 fail（不被 unknown 掩盖）
```

第二条是负向对照：明确违反的判据不能被 unknown 冲淡。

## 四、一个会让开关从清单里消失的写法

我第一版写成 `getattr(a, "no_contract", False)`。跑 `schema.py build` 之后
`--no-contract` **不在能力清单里** —— 因为 `schema` 是靠扫 `a.<名字>` 提取参数的。

改成 `a.no_contract` 后：

```
$ mmkit.py ... ; schema.json 33,181 -> 33,415 字节
experiment 的 --no-contract: {'type': 'bool', 'dest': 'no_contract', ...}
```

**规则记下**：想加一个 LLM 能看见的开关，就必须写 `a.<名字>`；
写成 `getattr` / `a.__dict__.get(...)` 之类，它会被静默漏掉。

## 五、当前状态

```
23/23 通过，0 道有警告        （gate 22 项）
回归：ALL PASS（CORE 49 条，覆盖 46/46）
补丁：114/114   能力清单：与源码同步（23 命令 / 33,415 B）
ALL GREEN
```

## 复现

```powershell
$py = "C:\Users\21246\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
cd model1-arch
& $py mmkit.py experiment --propose-json <同构提案>.json        # 期望 exit 2 + 原因
& $py mmkit.py experiment --propose-json <同构提案>.json --no-contract
& $py orchestrate.py selftest                                   # 26 项
& $py tools\verify_all.py
```

## 未做（下一轮）

1. 全局 `~/.dsh/AGENTS.md` 的「19 命令 / 22 道回归基线」过时（用户级配置）。
2. `orchestrate._fail_kind` 的错误分类没见过实测样本。
3. `rule_propose`（规则版提案）的三条路线是否也满足契约的多样性要求，没验过。
---

# 优化记录（第 105 轮）：错误分类器不认识自己产品说的话

## 总账

| 项 | 第 104 轮末 | 现在 |
|---|---|---|
| `_fail_kind` 兜底 | 「质量不达标」（范畴错误） | 「未识别故障」 |
| 词表覆盖 | 只有通用异常名 | + argparse / 插件自有措辞 / 输入缺失 |
| 真实失败识别率 | **0/3** | **3/3** |
| `orchestrate` 自检 | 26 项 | **30 项** |
| 官方账目 | ALL GREEN | ALL GREEN（已重跑确认） |

## 一、先验证「规则版提案是否合规」

上一轮担心 `rule_propose` 的三条内置路线过不了自己的契约。实测：

```
规则版路线数: 4
  A race      B run      C solve      D forecast
契约结果 ok = True
```

4 条路线 4 种方法，**合规**。这个疑虑排除。

## 二、`_fail_kind` 的兜底是范畴错误

它只在 `a.ok == False`（进程失败/非零退出/超时）时被调用 ——
也就是说它处理的**全是技术性失败**，判据没过的路线根本走不到这里。
而它兜底返回「质量不达标」：执行失败按定义不是质量结论。

改成「未识别故障」：认得出就写技术故障，认不出就老实说认不出。

## 三、更严重的是词表不认识插件自己说的话

先拿三条**真实失败**去打：

```
X 不存在的命令   → 未识别故障
Y 缺 --x        → 未识别故障
Z 数据文件找不到  → 未识别故障
```

三条全落兜底。它们吐的原文是：

```
usage: mmkit.py [-h] ... invalid choice
solve 需要 --x 和 --obj（或 --y）
找不到数据：'没有这个文件.xlsx'；用 --data 指定
```

分类器不认识自己产品的错误文本 —— 那这套分类就是摆设。补三类词：

- argparse：`usage:` / `invalid choice` / `error:` / `unrecognized`
- 插件参数错：`需要` / `缺少` / `未提供` / `必需`
- 输入缺失：`找不到数据` / `没有这个` / `不存在` / `not found` / `missing`

修完重测：合成 8 条 + 真实 3 条，**11/11 正确**；三条真实失败全部归到「技术故障」。

## 四、四条断言钉住

```
[PASS] argparse 的 usage 文本算技术故障
[PASS] 插件自己的参数错（「需要 --x」）算技术故障
[PASS] 数据缺失（「找不到数据」）算技术故障
[PASS] 认不出的错误不冒充质量结论
```

## 五、当前状态

```
23/23 通过，0 道有警告        （gate 22 项）
回归：ALL PASS（CORE 49 条，覆盖 46/46）
补丁：114/114   能力清单：与源码同步（23 命令 / 33,415 B）
ALL GREEN   exit 0
```

## 复现

```powershell
$py = "C:\Users\21246\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
cd model1-arch
& $py orchestrate.py selftest     # 30 项
& $py tools\verify_all.py         # ALL GREEN
```

## 未做（下一轮）

1. 全局 `~/.dsh/AGENTS.md` 的「19 命令 / 22 道回归基线」过时（用户级配置，一直没动）。
2. `_fail_kind` 只影响死路表的标签，不改控制流 —— 是否该让「技术故障」触发自动重试，没定。
3. `paper.py` 的正文生成逻辑仍只审过片段。
---

# 优化记录（第 106 轮）：「样本数量」这个问题量出了一个盲区 —— 定题命令看不见优化题

## 总账

| 项 | 第 105 轮末 | 现在 |
|---|---|---|
| `advise` 能报的题型 | explain / forecast / evaluate / unclear（**optimize 不可达**） | 四类 + **optimize 可达** |
| advise 的输出 | 单标签 `kind` | `kinds` 列表（`kind` 保留兼容） |
| `advise` 自检 | **没有** | 15 项（新建 `advise_selftest.py`） |
| 回归钉数 | 49 条 | **50 条**（46 → 47 个模块） |
| 官方账目 | ALL GREEN | ALL GREEN |

## 一、被问到「样本数量」，于是把每个断言的样本数都摆出来

| 我说过的结论 | 样本 | 判定 |
|---|---|---|
| 23 题 ALL GREEN | 23 道题（全量，非抽样） | 成立 |
| 46/46 模块上链 | 46 个模块（全量） | 成立 |
| 11/11 错误分类正确 | **真实只有 3 条**（另 8 条是我编的） | **只能支撑「3 条真实样本正确」** |
| 修掉的问题集中在同一病根 | 26 轮 / 118 小节，分类是我自己标的 | **主观归类，不算证据** |
| 「题型全覆盖」 | 题库 8 个题型标签，advise 只报得出 1–2 个 | **不成立** |

最后一条逼出了本轮的真问题。

## 二、题型覆盖：实测覆盖率

题库自己的 `题型.json` 是**多标签**人工标注（23/23 题都有）：

```
regression 18   optimization 7   evaluation 6   prediction 3
network 2   simulation 2   mechanism 1   multiobjective 1
```

而 `advise` 跑同一批题，**优化题一条都没报出来**（21 道判 explain、1 道 forecast）。

查代码：`advise.py` 里只有 4 个 kind 赋值 —— forecast / explain / evaluate / unclear。
**`"optimize"` 从未被赋值**，它自己文档里写着「optimize → 帕累托 → 约束求解 → 灵敏度」，
那条链永远选不中。

而且 `mmkit advise` 只收 `--data/--y/--x`，**没有目标列**，所以它连「这题要寻优」
都不知道 —— 22/23 道题都带目标列（min/max），信息就在配置里，只是没喂进去。

## 三、改法：多标签 + 让 optimize 可达

1. `advise.diagnose(..., objectives=[...])`：带目标列就**追加** `optimize`，
   并给出 solve / pareto / sens 方法链。
2. 返回 `kinds` 列表，`kind` 保留为主标签（老调用方不受影响）。
3. `mmkit advise` 把 `--min/--max` 的列名传进去。
4. 目标名是**论文显示名**（"等待时间"），数据里的真列名可能不同（"平均等待"），
   必须用 `ds.pick()` 解析 —— 直接按列名过滤会把 22 道题的目标全丢掉。

改后实测：

```
explain 21   optimize 21   forecast 1
evaluation  advise=explain/optimize | 题面=evaluation/optimization | 覆盖=optimization 缺=evaluation
multiobjective advise=regression/optimization | 题面=optimization/multiobjective/regression | 缺=multiobjective
```

**仍不覆盖**：evaluation（advise 的 evaluate 要「没有 y」）、
network / simulation / mechanism / multiobjective（advise 压根不报这四个）。
所以「题型全覆盖」这句话**今天仍然不成立**，我把差距量出来了。

## 四、自己挖的三个坑（当场发现）

1. `for _s in (a.min or "") + "," + (a.max or "")` —— **逐字符迭代**！
   一个目标名被拆成 等/待/时/间 四个「目标」，目标列表变成 4 个。
2. `ds.pick(全部目标)` 整体调用：其中一个名字匹配不到就抛 KeyError，
   已经解析成功的目标一起丢。改成逐个 pick。
3. 目标列表没去重。

## 五、另一个量出来、但**没动**的分歧

`mm.is_time_like` 与 `mm.time_cols` 对「这是不是时间轴」给不同答案：

- `is_time_like` 认「年份/月份/年度/季度/周次/期数/编号/序号」——
  在真实数据上**过度触发**：8 道题的列被判成时间轴，其中
  `等待时间`/`停留时间`/`妊娠时间`是**测量值**，
  `1950`/`2005` 是**按年份分箱的列名**（列里装的是人口），
  都不是时间轴。
- `time_cols` 只认 `time/hour/时刻/时间/时点/钟点/date/day/日期` ——
  反而**漏掉**真轴（年份/月份/年度）。

两者都不对，**不能直接合并**（合并会让 `--y 年份` 被拒，population 那道题就断了）。
区分「测量时长 / 年份分箱 / 真时间轴」需要看取值形态，不是改词表能解决的。
这轮只把分歧量清楚、记下来，**没有动判据** —— 半懂状态下改时间轴判定风险太大。

## 六、当前状态

```
23/23 通过，0 道有警告        （gate 22 项）
回归：ALL PASS（CORE 50 条，覆盖 47/47 个带自检的模块）
补丁：114/114   能力清单：与源码同步
ALL GREEN
```

## 复现

```powershell
$py = "C:\Users\21246\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
cd model1-arch
& $py advise_selftest.py                       # 15 项
& $py tools\probe_sample_size.py              # 题型覆盖对照
& $py tools\verify_all.py                      # ALL GREEN
```

## 未做（下一轮）

1. `is_time_like` vs `time_cols` 的分歧（见第五节），要按取值形态区分三类。
2. advise 报不出的四个题型：network / simulation / mechanism / multiobjective。
3. advise 判「评价」要求没有 y —— 有 y 的评价题（题库里有 6 道）判不出来。
4. 全局 `~/.dsh/AGENTS.md` 的「19 命令 / 22 道回归基线」过时（用户级配置）。
---

# 优化记录（第 107 轮）：题面也能定题型 + 逐页可读性审计

## 总账

| 项 | 第 106 轮末 | 现在 |
|---|---|---|
| advise 认得的标签 | 4 类（optimize 那轮才可达） | **7 类，与题库人工标注的标签集合完全一致** |
| 题型覆盖（23 题） | 多数只中 1 个 | **全中 14 道 / 部分 7 道** |
| `advise` 自检 | 15 项 | **20 项** |
| 逐页可读性审计 | 无 | `tools/audit_pdf_pages.py`（字号分布 + 图 DPI） |
| 官方账目 | ALL GREEN | ALL GREEN（CORE 50 条） |

## 一、题型覆盖：把题面喂给 advise

只看数据结构，network / simulation / mechanism / multiobjective 一个都认不出。
而 `mmkit` 早就有 `--problem`（题面），只是没喂给 advise。

加了题面线索（每条结论都写明出处是「--problem 题面文本」），并补词：
projection→prediction、conflict/trade-off→multiobjective。

实测（22 道可测，heat_sink 的冻结表里记的是显示标题而非文件名，跳过）：

```
advise 认出的标签集合: evaluation, multiobjective, network, optimization,
                       prediction, regression, simulation
题库人工标注的标签集合: 同上（完全一致）
题库有、advise 完全认不出的标签: 无
完全覆盖 14 道 / 部分覆盖 7 道
仍缺: evaluation×5、regression×1、network×1、prediction×1
```

## 二、逐页可读性审计（用户要求「pdf 一页页看」的可测化）

新工具 `tools/audit_pdf_pages.py` 逐页量：字符数、图数、**每张图的像素宽与等效 DPI**、
**字号分布**（多少比例的字小于 9pt）。

实测三份 PDF：

```
Plugin-Agent-Architecture.pdf   8 页  字号 6.0–…  小于 9pt 占 0.13%
out/d2026c/paper.pdf            17 页  字号 8.0–…  小于 9pt 占 0.18%
数模论文-最终版-26页.pdf         26 页  字号 8.0–…  小于 9pt 占 0.95%
```

结论：**「字不够清晰」不是字号问题**（小字只占千分之一量级）。
d2026c 的图：2013/1332/1319/1735 px 宽 → 等效 279–426 DPI，**清晰度合格**。

## 三、当前状态

```
23/23 通过，0 道有警告        （gate 22 项）
回归：ALL PASS（CORE 50 条，覆盖 47/47 个带自检的模块）
补丁：114/114   能力清单：与源码同步
advise 自检 20 项；题型标签集合 7/7 与人工标注一致
ALL GREEN
```

## 未做（下一轮）

1. 评价类仍漏 5 道：adivse 的 evaluate 要求「没有 y」，而有 y 的评价题（题库 6 道）判不出。
2. `is_time_like` 与 `time_cols` 两套时间轴判据不一致（过宽 / 过窄）。
3. 桌面上有一份 11-09 的旧模板卷（26 页、仅 2 张图）—— 提交稿需要明确唯一入口。
---

# 优化记录（第 108 轮）：赛题手册 —— 并且它当场抓出两个真 bug

背景：**等题目到手再开写**，比赛窗口 4 天。这段时间把开赛当天要用的东西做现成。

## 总账

| 项 | 第 107 轮末 | 现在 |
|---|---|---|
| `advise` 题型 | 只能从数据/题面推 | **可显式声明**（`--types`），并给出对应方法链 |
| `falsify.py counter` | **多因子直接崩** | 修好；且样本量报全 |
| 赛题操作手册 | 无 | `问题到手时的操作手册.md`（9 步，全部实测可跑） |
| 手册自检 | — | `tools/verify_runbook.py`，已进回归链 |
| 回归钉数 | 50 条 | **51 条** |
| 官方账目 | ALL GREEN | ALL GREEN |

## 一、`advise` 加 `--types`：题型由人声明，插件给方法链

插件是**能力层**，不是预言机。LLM 读完题面最清楚题型，所以提供覆盖接口：

```
& mmkit.py advise --data X --y Y --x A,B --min M --types network,mechanism
定题结果：**关系与解释、网络与流、机理建模**
4. mmkit.py graph --op flow --edges <边> --nodes <节点>   # 最大流/最小割
5. mmkit.py graph --op tsp --edges <边>
```

每个声明的题型都会附带**对应的方法链**，不是只贴标签。
（名字用 `--types` 而非 `--kind`：`--kind` 已被 `plot --kind` 占用，
argparse 直接报 conflicting option string。）

## 二、手册验证当场抓出两个真 bug

写完手册后写 `tools/verify_runbook.py` 逐条执行 —— 第 7 条就红了：

```
[FAIL] 7 主动证伪：滑窗找反例  exit=1
KeyError: "没有数值列 '宽度,深高'；有 ['样本编号','针肋宽度比',...]"
```

**bug 1：`falsify.py counter` 把逗号串当成一个列名。**
开赛当天第一条反例命令就崩。改成按逗号拆、逐个因子跑，
并改用 `ds.pick`（能认显示名「宽度」→ 真列「针肋宽度比」），与 hints/race 口径一致。

**bug 2：样本量报错。** 原来打印「样本 5」，而数据有 84 行 ——
`r['n']` 是 **x 的不同取值数（分组数）**，不是行数。
这正是「样本量」类毛病，评委直接看得见。改成三个数都打：

```
原始 84 行；x 有 5 个不同取值，其中 5 组参与检验；违反区段 0 段
```

## 三、手册：9 步，全部实测

`问题到手时的操作手册.md`：定题 → hints → race → 主动证伪 → lanes →
出结构稿 → 逐段重写 → 画图（图有 DPI 硬要求）→ 逐项复核 → 逐页看 PDF → 交稿前复核。

每条命令都过 `tools/verify_runbook.py`（实测 9/9 OK），并且**这条检查进了回归链**：
手册写错一条，账目就红 —— 不会等到开赛当天才发现。

## 四、当前状态

```
23/23 通过，0 道有警告        （gate 22 项）
回归：ALL PASS（CORE 51 条，覆盖 48/48 个带自检的模块）
补丁：114/114   能力清单：与源码同步
advise 自检 24 项；赛题手册 9/9 可跑
ALL GREEN
```

## 未做（下一轮）

1. `is_time_like` 与 `time_cols` 两套时间轴判据仍不一致（过宽 / 过窄）。
2. 评价类仍漏 5 道（`--types evaluation` 可以人工补上，但自动判定还不行）。
3. 手册里 `mmkit.py run` 那一步产出的模板正文，改写工作量大 ——
   可以做「段落改写助手」：把 skeleton 的段落清单直接接到 overrides 上。
---

# 优化记录（第 109 轮）：统一时间轴判据 + 写出最终论文

## 总账

| 项 | 第 108 轮末 | 现在 |
|---|---|---|
| 时间轴判据 | 两套（is_time_like 过宽 / time_cols 过窄） | **一套：名字像 + 取值像索引** |
| 标识列 | 被并进「时间轴」，提示语说错话 | 拆出 `id` 类型，措辞分开 |
| `mm.py` 自检 | **没有**（最底层的计算内核零自检） | 12 项（新建 `mm_selftest.py`） |
| 最终论文 | 8 页架构稿 | **11 页，9 张图 + 3 张表**（`out/final/`） |
| 回归钉数 | 51 | 52 |
| 官方账目 | ALL GREEN | ALL GREEN |

## 一、时间轴判据合并（并现场发现我改坏过一次）

旧状态：`is_time_like` 只看名字（「等待时间」「1950」都算时间轴，过度触发 8 列）；
`time_cols` 只认少数词（「年份/月份/年度/季度」全漏）。

新判据 `_looks_like_axis`：名字像时间 **且** 取值像索引
（几乎每行一个不同值 + 等距整数 / Excel 时间序号 / 循环重复）。

实测 23 题：误报全部消失，且**没有任何 y 被判成时间轴**（这是让改动可以上线的关键检查）。

中途我漏掉了「循环时间轴」这一条，`tests/advise_smoke.py` 立刻红：
A 题的 TIME 列（07:00/09:00 逐日重复）不再被判成时间轴 → `--y TIME` 又能跑通。
补回时又踩第二个坑：循环判据不能只看「不同值少」，否则「1950」那种高基数分箱列
（列名像年份、列里装人口）也会被当成循环轴。两个条件缺一不可。

## 二、`mm.py` 补上自检（12 项）

计算内核被引用最多、却一条自检都没有。新 `mm_selftest.py` 覆盖：
年份/月份→时间轴、等待时间→不是轴、年份分箱列→不是轴、标识列→单独归类、
`non_response_cols` 类型标签、`pick` 语义、`suspect_leak` 分类。

## 三、最终论文（11 页，9 图 3 表）

`out/final/paper.tex` → `paper.pdf`（340,171 B，11 页），另存桌面
`插件构建-最终论文-11页.pdf`。

结构：抽象 → 问题 → 系统四层 → **六类缺陷的分类学**（本文重心）→ 审计改变了什么 →
两个溯源口径 → 题型覆盖 → 语料 → 逐题实例 → 局限 → 相关 → 结论 → 复现附录。

图（全部从 `out/final/data.json` 生成，不手填）：
架构 / 流水线 / gate 两层 / 两个溯源口径 / 题型覆盖 / 缺陷分类 / 自检覆盖推进 /
页数-图数 / 证据链。

表：六类缺陷（含出现轮次）/ 22 项检查（英文说明由我写，状态现场取）/ 23 题语料。

## 四、写论文时抓出的四个自己的错

1. **摘要写「128 recorded rounds」** —— 实测 29 轮。定了要改：这类假数字正是本文批的东西。
2. 图 4 原标题「Every number is traced」—— 实测 gate 口径 94.1–100%、verify 口径 78–96.7%，
   改成两口径并列，并说明差距来自结构性整数。
3. 图 5 我原写「15/22 全中」，但图里 offer 明显**过度报 optimization（21 vs 6）**，
   图注改成「过度与不足是同一个错的两面」。
4. 图数测量错了两次：第一次数目录文件（22–24，每图两格式）、第二次数 PDF 内嵌 image
   （0–4，矢量图不算），第三次数 `\begin{figure}`（11–12）才对。
   —— 这件事本身写进了论文第 8 节。

## 五、当前状态

```
23/23 通过，0 道有警告        （gate 22 项）
回归：ALL PASS（CORE 52 条，覆盖 48/48 个带自检的模块）
补丁：114/114   能力清单：与源码同步
论文：11 页 / 9 图 / 3 表 / 340,171 B
ALL GREEN
```

## 未做（下一轮）

1. 评价类自动判定仍漏 5 道（`--types evaluation` 可人工补）。
2. 论文里的工作实例只写了一个题；可扩成两三个对比（成功/失败各一）。
3. 桌面上仍有 11-09 的旧模板卷，提交路径需要唯一入口。
---

# 优化记录（第 110–112 轮）：把「五件事」与「分板块红队」做进插件

用户的要求：**1 分析题的思路 / 2 解题方法与技巧 / 3 论证 / 4 自己错在哪怎么改（含论证）/ 5 落地产线**，
以及**不同板块配不同红队成员做专项检查**。不是「论文里最好有」，而是**插件强制**。

## 总账

| 项 | 第 109 轮末 | 现在 |
|---|---|---|
| gate 检查项 | 23 | **28**（+五件事四项 + redteam） |
| 新模块（带自检进回归） | — | `chapters.py`(4) `redteam.py`(7) `untraced.py`(12) |
| 未溯源剖析 | 解析截断打印（199/1293） | **全量** 1,483 / 10,233（五个类） |
| 消融 | 删全部 json，0.0% 恒真 | 只删冻结表：**94.0% → 11.5%**（非平凡） |
| 论文自身溯源 | 69.7%，退出码恒 0 | **136/136 = 100%**，退出码如实 |
| 交稿质量门 | 3 硬门失败 | **0 硬门失败，2 警告** |
| 官方账目 | ALL GREEN | ALL GREEN（23/23，0 警告） |

## 一、红队找到了 6 条致命（我先挨打，再改）

派了独立上下文的 `red-team`，20 条攻击 / 6 致命，**大部分是对的**：

1. **F1 分母被截断**：剖析只分类了 `verify.py` 打印的前 15 条（199），全量 1,293。
2. **F2 度量自己坏了**：论文两个摘要数字被自己的 `verify.py` 判无源（69.7%）；且
   `verify.py` 读 `unmatched` 键而 `trace()` 返回 `untraced` → **退出码恒 0**。
3. **F3 声称与代码不符**：论文写「N/A 不能判绿」，代码 `all(status in ("PASS","N/A"))`。
4. **F4 消融恒真**：脚本删的是**全部** `*.json`（第二条件吞掉第一条件），0.0% 是算术。
5. **F5 证伪不失败**：找到反例退 0，且 `return` 之后是不可达代码。
6. **F6 纯召回**：`full=(not set(gold)-set(ks))`，恒输出七标签的平凡基线拿 22/22 > 15/22。

## 二、按「把问题切开」修（不是补数字）

- **untraced.py**：五类（结构 139 / 配置 0 / 时间标签 207 / 表格数据 83 / **计算值 1,054**），
  分母改为 `verify.trace` 的完整集合，并断言「各类之和 = 未溯源总数」。
- **分词器三处缺陷**（`3.3342e-12`、`1970-1975`、`51,737`）+ `{,}` 千分位 + 列宽参数：
  未溯源 1,483 → 逐项消掉，论文自身到 **100%**。
- **消融重做**：只删 `冻结数字.json`，结果 94.0% → 11.5%（残留来自目录内其它产物）。

## 三、五件事 + 分板块红队（都是能失败的检查）

`chapters.py`：分析 / 方法论证 / 自我纠错 / 落地，**结构 + 正文信号词**（表注算论证、表体不算），
空文档四项目全 FAIL，断言钉死「信号只在表体里不算」。

`redteam.py`：七板七角色（decomposition / alternative / statistics / reproducibility /
confession / operations / overclaim），每角色 4 条专项探针，`redteam.json` 必须逐板答完；
**漏板 / 复用角色 / 探针未答 / finding 未关闭** 四种偷懒全判 FAIL。
本文的 28 条探针里 13 条 finding 全部关闭（来自红队那 20 条攻击的真实映射）。

**范围问题（我自己犯的）**：一开始把五件事压到 23 篇模板卷上，账本全红。
正解是**判据跟着主张走**：`declaration.json` 里 `deliverable: true` 的目录才按交稿判，
模板卷判「不适用」。同理 `stamp` 也只管交稿。

## 四、顺手统一的两处「双重真相」

- `hard_ok` 与 strict 转换各说一套 → 现在统一：硬 N/A 若不是 `na_kind=ABSENT`，strict 下直接 FAIL。
- `chk_domain` 返回不带 `na_kind` 的 N/A → 再也不会有「all_pass=False 但 hard_fail 为空」。

## 五、当前状态

```
端到端：23/23 通过，0 警告
回归：ALL PASS（CORE 55 条，含 chapters/redteam/untraced）
补丁：114/114   能力清单：与源码同步
交稿 out/final：23 页 / 20 图 / 22 引用 / 自身溯源 100% / 硬门 0 / 已盖章
ALL GREEN
```

## 未做

1. `rules_apmcm` A001、`rigor` P5 两条软警告需人看（前者查「模型建立与求解」结构，后者查需人工核对的句子）。
2. `dwts2026c` 原来**零引用**（新检查抓到），已补 1 条；文献表 3 条仍有 2 条未被引用。
3. 红队报告里的「中」级条目（如图注口径、图未引用）只处理了主要几条。
---

# 优化记录（第 118 轮）：把自己查出的缺陷逐个修掉

用户指令：**反复排查 → 确立方案 → 优化机制**，把已提到和新查出的问题全部优化掉。

## 一、方案（依依赖排序）

A 口径统一 → B 删重复分词器 → C 五件事加反糊弄判据 → D 文献绑定 bug
→ E 生成器登记写出的数 → F anchor 虚荣比值 → G 版面检查

已完成 **A/B/C/D/F**；**E/G 未做**（原因见末节）。

## 二、逐项：改了什么、证据是什么

### A 口径统一（声称 vs 行为）
- 缺陷：`AGENTS.md` 写「警告 0 才算完」，`all_pass` 只看硬门 —— 实测 3 条警告下仍报「通过」。
- 改：`all_pass = hard_ok and not warns`；`--lenient` 放行草稿；报告首行解释阻断原因。
- 范围：警告阻断只对 `deliverable` 生效（模板卷是草稿，警告照报不判死）。
- 证据：`质量门：通过（硬门失败 0，警告 0，未适用 5）`——这是警告开始阻断后**第一次**零警告通过。

### B 删掉重复分词器
- 缺陷：`verify.py` 与 `freeze.check_paper` 各一套抽取，曾给出 17.1% vs 100% 的矛盾判决。
- 改：`check_paper` 复用 `verify.extract_numbers`，只过滤「带小数」。
- 证据：`freeze: traced 37/37`（旧口径 33/40）。

### C 五件事加反糊弄判据
- 缺陷：原来只数信号词，我自己写的堆词样本就能过。
- 改：每项加结构判据 —— 分析要有 ≥3 行分类表 + 点名 2 类；方法要有「替代方案」列的表；
  纠错要 ≥2 个案例且每个含数字或 `\ref`；落地要有运行方式表；正文 ≥45 词。
- 证据：新增自检 `堆词但没有表 → FAIL`；真论文四项全 PASS 且**带结构证据**
  （表 7 行 / 替代表 45 行 / 7 个案例 / 部署表 16 行）。

### D 文献绑定 bug
- 缺陷：DOI 已核验能解析，`check` 仍报未绑定。
- 根因三处：① 我把 DOI 插在标题后，解析器把 DOI 当标题；② 正则 `r"\\emph\\{"` 匹配
  `\\emph\`，`cand_b` 恒空；③ `$p$` 这类数学把标题 token 切碎。
- 改：解析前剥离标识符与 `doi:` 残壳；`_norm` 去数学与命令；子集判定 + 前缀词容错。
- 证据：**绑定 19 → 24/25**；`QuickCheck` 不再误绑到 `MuCheck`（sim 0.30）；
  专著用 `bib_exempt.json` 显式豁免并给理由。

### F anchor 不再报虚荣比值
- 缺陷：干净论文上「0.0%」的分母是零问题，什么都不证明。
- 改：无可改处时直接说「压缩比无意义」。

## 三、附带发现并修掉的

- `biblio` 支持**显式豁免**（专著/技术报告无 DOI，必须给理由，名字精确匹配）。
- `rigor` P5 两处 "obvious/obviously" → 改成精确表述，rigor PASS。
- `A001` 缺「求解」痕迹 → 补一句**真实**的方法陈述（用构造而非搜索求解）。
- `numbers` 认「输入表里的观测值」（E 类）：6 道题因此回绿 1 道、另 5 道降幅明显。
- `chapters` 跟 `\input{}` 引入的表；`_prose_only` 先归一空白（折行会让信号词数不到）。

## 四、仍未解决（真信号，不是噪音）

1. **5 篇模板卷 `numbers` 红**：`nflis` 15.3%、`age_struct` 34.2%、`multiobjective`、
   `icm2006c`、`pop_panel`。原因是**模板会印出它无法归属的数** —— 正是 E 项那笔债。
2. **E 未做**：`paper.py` 不登记它写出的数。修它要改生成器（让模板只印能归属的数），
   不能靠「把论文里的数全冻进去」（那等于让溯源自我证明）。
3. **G 未做**：版面从未检查（浮动体碰撞、表溢出）。`figures` 8.0/10 是标签启发式。
4. `redteam` 仍是自证（七板七角色由我填）；`chapters` 的结构判据比词面强，但仍可被
   「造一张 3 行空表」满足。
5. 两处核心实验仍是单编码者（97.5% 分类一致率、六类缺陷分类）。

## 五、当前状态

```
交稿 out/final：27 页 / 20 图 / 16 表 / 引用 19 / 文献 25（24 条绑定外部记录）
自身数字溯源 155/155 = 100.0%；质量门 通过（硬门失败 0，警告 0）
种子缺陷检出 30/30；分类器一致率 97.5%
账本：18/23 通过（5 项为真信号），回归 ALL PASS，补丁 114/114，能力清单同步
```
---

# 第 120 轮：借 purge 的攻击目录，打我自己的门

用户提问：purge 的红队攻防可否借鉴。**可以，但要借它的方法而不是它的目的。**

purge 是什么：打**自己宿主**的补丁套件，87 条，分类是提示词/代码/工具三层，
每条有 applied / skipped 状态，带 `purge_audit` 审计流水与 `revert`。
它的目的很明确：**让宿主的护栏闭嘴**（跳过审批、放宽沙箱、关掉重复提醒）。

所以：
- **不能借它的目的** —— 我的插件价值恰恰在于「红要真红」；借它的目标会直接
  抵消我这一轮修的东西（警告阻断、N/A 不算绿）。
- **能借它的方法** —— 那 87 条本质上是一份**攻击目录**。反过来问一句：
  「同样的手法，能不能让**我的**门安静？」

## 实测：三条攻击，三条全得手

| 攻击 | 手法 | 结果（修之前） |
|---|---|---|
| A1 空稿 | 只给一个导言区，`numbers` 怎么判 | **通过**（"0/0 可溯源 0.0%"） |
| A2 自我冻结 | 拿论文自己的数字生成冻结表 | **通过**（4/4 = 100%） |
| A3 只留文献 | 只写 1 条 bibitem，记录里写 `uncited: []` | **通过**（"全部绑定且被引用"） |

共同根因：**护栏相信递给它的文件**，不核对文件与论文是否一致。
这正是 purge 那套「让守卫别说话」的通用手法 —— 我自己身上也有。

## 修完

- A1：数字个数本身必须 ≥ must（原来 `>= min(must, n)`，n=0 恒真）。
- A2：冻结表必须写 `generated_from`（生成它的脚本，且文件真实存在），
  条目必须带来源 `path`；`self/空` 一律不算。
- A3：`biblio` 自己从 paper.tex 数 bibitem 与 `\cite`，与 `lit_bound.json` 对账，
  对不上判 FAIL。
- 再打一次：**0/3 漏**。

## 附带挖出两个记账漏洞

1. **软门 FAIL 既不算硬失败也不算警告** —— 报告能同时说「通过（警告 0）」
   和列出一条 `[FAIL]`。现已计入。
2. **我自己的 ≥8 字符证据规则否掉了 4 条合法标记**（`P42` 3 字、
   `滑动窗口` 4 字、`0.2146` 6 字、`uncited` 7 字）→ redteam 误报 FAIL。
   下限降到 3；真正的防线是「文件存在 + 逐字命中」。

## redteam 的自证问题（第 119 轮）

原来 13 条 finding 只要写个 `note` 就算数 —— 谁写都能写。
现在每条 finding 必须带 `where`（文件）+ `evidence`（该文件里逐字存在的标记），
gate 亲自 grep；附件脚本在写入前先验证，验证不过不写。
于是「编一条 finding」必须先让那段代码真的存在。

chapters 同步加了两条反糊弄：
- 表不能是空壳（每行 ≥2 个非空单元格且有内容）
- 表既没有数字证据、也没有单元格原文进入正文 → 判空壳表
（第一版用「60% 词汇重合」太粗，真表的词本来就不必在正文重复 —— 真论文的
部署表被它误判成 37%，改成二选一后正常）

## 状态

```
交稿：27 页 / 20 图 / 16 表 / 引用 19 / 文献 25（24 条绑定外部记录）
质量门：通过（硬门失败 0，警告 0，未适用 5）
自攻：3 条攻击全部挡住（0/3 漏）
账本：18/23（5 项真信号），回归 ALL PASS，补丁 114/114
```

# 第 122 轮：E（生成器登记写出的数）—— 从补丁走到判据

> 交接文件第 121 轮把 E 的根因写成「模板会印出它无法归属的数，paper.py 不登记
> 写出了什么」。这句话只对了一半。本轮先取证、再动手；红队（第二编码者，
> fresh context、不看我探针）独立复现了同一批数字，并指出交接文件覆盖度
> 只有 35.6%，最大的一条（判据 bug，60.2%）被漏掉了。

## 一、根因：4 条，不是 1 条

在 `gate.chk_numbers` 的真实口径下（只算带小数的 token），5 篇红题合计
152 个未溯源，拆分如下（红队独立复现，与我的探针逐项对齐）：

| # | 根因 | 占比 | 性质 |
|---|---|---|---|
| ① | `freeze._decimals` 把 `5.924e+04` 的书写精度算成 7 位小数（`len("924e+04")`），容差 5e-8 | 106/152 = 70% | **判据 bug**：值早就冻在 `eda.per_col[*]` 里，判据不认 |
| ② | `ctx` 与 `rep` 是两本账，paper 印的派生量没进冻结表 | 40/152 | 架构缺口 |
| ③ | `paper.py` 渲染时才第一次出现的派生量（`205.5` 比值、`58.2481` 穿零点） | 2/152 | 生成器真身 |
| ④ | `kb/cards/M002.json` 把方法常数写成数字 `$1.96/\sqrt{n-k-1}$` | 5/152 | 源头把符号写成数值 |

## 二、改了什么

**架构级（不是补丁）**

| 改动 | 文件 | 为什么算架构 |
|---|---|---|
| 精度换算合成一份：`verify._written_decimals` 为唯一实现，`freeze._decimals` 委托它 | `verify.py` `freeze.py` | 消掉「同一概念两处实现」。改前同一份产物 gate 报 PASS 116/116、verify 报 88.0% |
| 整数未纳入判定显式上报（`n_int_not_judged` → gate 结论行） | `freeze.py` `gate.py` | 把隐式边界变成声明过的边界。不把整数纳入判决（行号 1009 会制造假阳性：实测 4 道题会因此变红，全是前沿表 Design 列） |
| 去掉 `abs(v) < 1e6` 的静默豁免 | `freeze.py` | 删掉一条静默通道。实测零代价：`+24969352.7%` 经 ×100 分支正确匹配 `q5_tradeoff.shift` |
| `_looks_self_proved`：自我冻结的 JSON 不进 verify 的溯源池 | `verify.py` | 堵 A2 攻击绕过 verify 门 |
| 前沿表限行 12 行 + 总数说明 | `paper.py` | nflis 原来印 400+ 行设计点；行号 >1000 被判 D_computed（608/874）。同时修版面与溯源 |
| `battle.py` 只写 `out/runs/` | `tools/battle.py` | 一条命令不该能覆盖人工交付稿 |

**补丁级（如实标注欠账）**

`rep["cond"]` / `rep["falsify"]` / `rep["q5_tradeoff"]` / `appl{i}_cross_at` /
`model_gap_pct` —— 只是把已知的四处缺口对齐。**下一处新加的 ctx 派生量仍会漏**，
因为 ctx 依然是 rep 的重算副本。

## 三、证据（都可复跑）

```powershell
& $py tools\e_verify.py          # 5 篇模板卷 100% 溯源，out/final OK，0 红题
& $py untraced.py --corpus       # D_computed 1053 → 28
& $py tests\run_all.py           # ALL PASS
& $py tools\attack_self.py       # 漏 0/3
& $py patches.py selftest        # 114/114
```

| 项 | 改前 | 改后 |
|---|---|---|
| age_struct numbers | 77/117（34.2%，红） | **118/118（100%）** |
| nflis numbers | 72/85（15.3%，红） | **87/87（100%）** |
| multiobjective numbers | 87/97（10.3%，红） | **103/103（100%）** |
| icm2006c numbers | 77/98（21.4%，红） | **112/112（100%）** |
| pop_panel numbers | 61/95（35.8%，红） | **120/120（100%）** |
| 语料 D_computed | 1053 | **28（-97.3%）** |
| 语料未溯源总数 | 1482 | **263（-82.3%）** |
| gate vs verify 分叉 | age_struct 116/116 vs 88.0% | 两者同源，不再分叉 |
| out/final | 通过 / 155-155 | 通过 / **155-155**（未退化） |

## 四、架构审计：为什么这类错会反复

写在 `ARCH-数字溯源链审计.md`。要点：

- `ctx` 31 键 / `rep` 27 键 / **只 11 个重合**；`ctx` 里 `_q4_ctx`、`_q5_ctx`、
  `_diag_ctx`、`_front_ctx`、`_spans`、`_pi_ctx`、`mm.applicability` **同参数各跑两遍**。
- 「冻结哪些数」靠 `KEY_HINTS` + `depth<=2` **猜**，不是登记。
- 冻结表 76% 的项没人引用（age_struct 24.0%、pop_panel 21.3%、icm2006c 23.0%）。
- 下一轮第一步应是 **ctx = rep 的只读视图**（删掉 6 处重复计算），
  第二步才是给表格里的数加 `emit_num`。

## 五、事故：覆盖了一份人工精修稿

全量跑 `tools/battle.py` 时，`runs.json` 里 `dwts2026c` 的 out 指向
`out/d2026c` —— 那是人工精修的交付稿，被 `mmkit run` 覆盖。

- 已从 `out/runs_backup_r4/dwts2026c/`（11/10 03:29 快照）恢复
  `paper.tex` / `paper.pdf` / `冻结数字.json` / log / aux / out；
- 第一次被覆盖的模板版留档在 `out/_backup_r122/d2026c_overwritten_20261111/`；
- `battle.py` 已加硬边界：只写 `out/runs/` 下（第一次只靠 `declaration.json`
  的 `deliverable` 字段判，而那份文件里**没有**该字段，保护形同虚设，于是又覆盖一次）。

**无法证明恢复的就是终版。** 恢复版在 `refs` 门上是红的（0 条 `\cite`），
而 `paper.before_style.tex`（11/10 00:56）也是 0 条 —— 它可能本来就是红的。

## 六、状态

```
5 篇原红题：numbers 全部 100% 可溯源（交稿/模板口径分别判，均绿）
语料：5822 个数字，未溯源 263（4.5%），D_computed 28（改前 1053）
交付物 out/final：通过（硬门失败 0，警告 0，未适用 5）/ 溯源 155-155
回归 ALL PASS（23 题）、自攻 0/3 漏、补丁 114/114
out/d2026c：已恢复 11/10 03:29 快照；refs 红（既有或我造成，未定）
```

**欠账**：ctx 与 rep 尚未合一；`emit_num` 未建；`out/d2026c` 的终版无法证明。
## 七、红队第二轮抓到的：我自己引入的假阳性

红队第一次验收挖出一条**我在修精度时新引入**的弱区：`_match_written` 的
`tol = 0.5*10**-dec + 1e-12` 里那个 `+1e-12` **绝对**地板。精度修好之前
`dec` 最大也就几位小数，地板看不出来；修好之后 `dec` 能到 18，
`0.5*10^-18 = 5e-19` 远小于 1e-12 —— 地板反而成了真容差，于是 1e-13 量级的
token 能被 `0.0` 或 `1e-17` 解释（5 篇共 9 例，`nflis 2.0839e-13 ← f=0.0` 最干净）。

**我第一次的修法是错的：直接把 `+1e-12` 删掉。** 红队第二轮（在它崩掉之前
留下的 `out/_rt_E2_tolfix.txt` 与 `out/_rt_E2_un23.txt`）抓到了后果：

```
A 合法舍入  0.78751  dec=5  f=0.787505   → 应 Y，实得 n
A 合法舍入  32.95    dec=2  f=32.945     → 应 Y，实得 n
后果：23 题未溯源 2 → 5
      heat_sink [0.78751, 0.73916] / life_exp [32.95] / dwts2026c [98.3, 78.8]
```

原因是浮点：`0.78751 - 0.787505 = 5.0000000000287557e-06`，比半格 `5e-6`
大 2.9e-17。**「恰好半格的合法舍入」被判成无源。**

正确修法是**相对余量**，不是删地板：

```python
tol = 0.5 * (10.0 ** -dec) * (1.0 + 1e-9)
```

| 组 | 例 | 删地板（错） | 相对余量（对） |
|---|---|---|---|
| A 合法舍入 | `0.78751 ← 0.787505` | 判红（假阳性） | 通过 |
| A 合法舍入 | `32.95 ← 32.945` | 判红（假阳性） | 通过 |
| B 地板假通过 | `2.0839e-13 ← 0.0` | 通过（假阴性） | 判红 |

修完：A 组 4/4 通过、B 组 4/4 判红，23 题未溯源回到 **2**（只剩 dwts2026c
人工稿的 `98.3` / `78.8`，既有缺陷）。

**这条的教训**：加任何绝对量到相对量上之前，先问「另一项的量级范围是多少」。
`+1e-12` 在 dec 只有几位时是「吸收浮点误差」，在 dec 能到 18 时是「判据失效」——
**同一个常数，量级变了，语义就反了**。

（另：这次纠错不是我自己发现的，是红队的探针抓到的。记录在此，归因如实。）