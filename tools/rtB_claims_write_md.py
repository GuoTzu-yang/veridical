# -*- coding: utf-8 -*-
import io, os
root = r"C:\Users\21246\Documents\deepseek-harness\default-workspace\model1-arch"
out = os.path.join(root, "out", "红队七板")
md = u"""# claims 板 · 独立审核（overclaim-auditor）

- 板：`claims`　正文范围：`out/final/paper.tex` L1201-L1358（`\\section{Reproducibility, claims and disclosure}`），
  连带审其直接支撑物：相邻的声明表 `tab:claims`（L1166-L1199）与两张图的图注（L1256-L1271）。
- 只读。没有改 `paper.tex`、没有改任何 `.py` 源码。探针在 `tools/rtB_claims_*.py`，只读文件、只打印。
- 结论：**4 条探针全部 finding，verdict = revise**。四条都落在作者自评判 pass 的三条探针上（见末节对比）。

## 一、声明 / 证据 / 未支撑（三列表）

| # | 声明 | 证据（我核到的那件东西） | 未支撑（论文写了没 / 我核到什么） |
|---|---|---|---|
| 1 | 流水线能产出一份通过 29 项检查、零警告的报告（表 L1176） | `data.json` `n_gate_checks=29`（`n_gate_hard=12` + `n_gate_soft=17`）；`gate-report.json` `all_pass=true`、`hard_fail=[]`；23/23 题在台账里 | **写了**：「One corpus；checks were designed alongside the reports they judge」 |
| 2 | 计算出来的数可追到冻结工件（表 L1179） | 每题两个口径（`data.json` 每题 `num_pct` 与 `gate_num_pct`） | **写了**：「Structural integers are untraced by construction；读者分不清哪些整数是算出来的」 |
| 3 | 溯源可归因于机制（表 L1183） | 五题消融（`ablation.json` 5 条） | **写了**：「无对照、无独立评分者」 |
| 4 | 题型可识别（表 L1186） | `data.json.type_coverage` 22 条，`full=true` 计 15 条；7/7 标签 | **写了**：「过度报告 optimization；泛化未测」 |
| 5 | 六类缺陷在验证代码里复发（表 L1189） | `n_record_rounds=30`；`record_bytes=132523` B（≈129.4 kB） | **写了**「分类是我们自己的读法；无评分者间一致性」，**没写「一个项目」**——而第 6 行写了「One project」，同表内不一致 |
| 6 | 自测只有接进流程时才有用（表 L1192） | `n_modules_with_selftest=51`；51/51 | **写了**：「One project；缺陷是我们发现的，不是独立审计」 |
| 7 | 本文每个计数由一个采集脚本产出、写单一 JSON；每张图只从那件工件画出来（L1205-L1207） | 无。清单自己列了两个采集脚本 | **未写**。实测 `out/final/data.json` 与 `out/final/data2.json` 两件并存；四张结构图按 L1245-L1247 自己承认不是数据图，与「from nothing else」冲突 |
| 8 | 本文每个数字 token 都对着冻结表解过，验证器报零未溯源（L1229） | 冻结表存在（`冻结数字.json`，715 条） | **未写**。冻结表全文 0 次点名、六步复现清单 0 步生成它（详见探针 1） |
| 9 | 本文每个数字都由脚本或 gate 产出，没有一个是手打进正文的（L1241） | 冻结表 + gate 判决 | **未写**。`0.2146` 的唯一出处是 `tools/freeze_paper_numbers.py:111` 里手打的常数（详见探针 3） |
| 10 | 每张图都由上面的脚本从测量工件画出，除四张结构图外没有一张是示意（L1244-L1247） | 20 张 `\\includegraphics` | **未写**。`fig16_sections` 的数据源是空列表，脚本遇到空表直接 return（详见探针 2） |

第 1-6 行（表内六条）三列齐全，这部分作者的 pass 站得住；第 7-10 行（正文里的全称句）三列只有一列。

## 二、逐探针证据

### 探针 1 ｜每条主张是否都有证据指针 —— finding

查过：`paper.tex` L1166-L1272 逐行；声明表 6 行拆成三列逐格看；六步复现清单的脚本名与 `tools/` 目录对账；
UTF-8 全仓扫 `冻结数字` / `freeze_paper_numbers` 的引用点共 156 处；`verify_all.py` 全文与 `gate.py` 的 `chk_numbers`。

关键数：

- `paper.tex` 里 `冻结数字` 出现 **0** 次、`freeze_paper_numbers` 出现 **0** 次，而 `frozen table` 出现 8 次——L1229 拿它当唯一支撑物，却不给读者一个能打开的名字。
- 六步清单（L1210-L1224）抽出的脚本：`collect_paper_data.py`、`collect_paper_data2.py`、`anatomy_tokens.py`、
  `make_final_figs.py`、`verify_all.py`、`gate.py`。**没有一步生成冻结表**。
- `tools/verify_all.py` 全文不含冻结表字样；`gate.py:286` 在缺表时把 `numbers` 判 **N/A**（原文：
  「没有 冻结数字.json（先跑 run）」）。照本节清单复现，`numbers` 这一门会退化成 N/A——而那正是论文在
  部署一节里禁止的「把 N/A 当通过」。
- 同一段的自相矛盾：L1205-L1206 写「one collection script … a single JSON artifact」，L1214 立刻列出第二个采集脚本，
  `out/final` 下 `data.json`（13648 B）与 `data2.json`（30976 B）并存。
- `fig:densitynum`（L1259-L1261）的图注把自己 `\\ref` 到自身，还夹带 `fig:sections` 的图注句
  （「Figure~\\ref{fig:sections} shows the same balance for this paper.」）——指针指向自己，不是指向证据。

`where` = `out/final/paper.tex`　`evidence` = `frozen table`

### 探针 2 ｜每条主张是否写明「哪里没支撑」 —— finding

查过：按全称量词正则扫 L1201-L1271 得 8 个全称句（L1203、1205、1206、1207、1217、1229、1241、1244），
逐个取 ±4 行邻域查 `Not supported` / `limitation` / `weak` / `cannot` 等字样；图注 L1256-L1263 与 `data2.json` 对账；
读 `make_final_figs2.py` 的 `fig16_sections`；比对三件文件的 mtime。

关键数：

- 8 个全称句，邻域内**没有一处**局限字样（0/8）。
- `data2.json["sections"]` = `[]`（len 0），而 `fig16_sections` 的图注（L1268-L1270）断言
  「the balance is deliberate: the mechanism and its validation carry most of the length」。
- `make_final_figs2.py:154-156`：`S = D2["sections"]` 后紧接 `if not S: return` —— 空表直接跳过重画。
- `fig16_sections.pdf` mtime **2026-11-10 22:02:29**，`paper.tex` mtime **2026-11-11 01:34:26**：
  这张图描述的是 3.5 小时前的稿子，而图注说的是「this paper」。

`where` = `tools/make_final_figs2.py`　`evidence` = `if not S`

### 探针 3 ｜有没有把「未见反例」写成「已证明」 —— finding

查过：在 root 下 `import freeze, verify`，对成稿复跑 `freeze.check_paper(paper.tex, 冻结数字.json)` 并打印全部返回字段；
把 37 个被判 token 逐个用 `freeze._match_written` 反查命中的冻结项路径；读 `freeze.py:182-309` 的判决代码；
读 `freeze_paper_numbers.py` 的 `derived` 段确认哪些值是脚本里写死的。

原文的判决（复跑逐字）：

```
ok = True
n_numbers = 37
n_traced = 37
untraced_ratio = 0.0
n_int_not_judged = 147
n_from_data = 0
```

- 被判的是 **37** 个带小数 token；**147** 个整数 token 被跳过（`freeze.py:209`：`toks = [t for t, _line in _all if "." in t]`）。
  全体数字 token ≈ **184**，「每个数字都被核过」实际覆盖 **20.1%**。23 题、29 检查、51 of 51、1,027 行、129 kB
  这些最像测量的整数，全在免检那一侧。
- 「命中」是一条 715 值袋子匹配（原值、×100、÷100、按书写精度取整），不是出处匹配：
  `0.0` 命中 **229** 条（等于没有证据也能过），`100.0` 命中 75 条，`0.12` 命中 24 条；
  `0.2146` 只命中 **1** 条——`derived.r_crit_84`，而它是 `tools/freeze_paper_numbers.py:111` 手打的常数。
- 于是 L1229 的 `no untraced token at all` 是「检查器在它愿意看的 20% 里没报反例」，被写成了「全部已证」。

`where` = `tools/freeze_paper_numbers.py`　`evidence` = `derived.r_crit_84`

### 探针 4 ｜有没有主张超出语料范围而没说明边界 —— finding

查过：比对 `paper.tex` / `data.json` / `data2.json` / `fig16_sections.pdf` 的大小与 mtime；
`data2.paper_bytes` 与成稿实际字节数对账；L1201-L1255 逐句按 `corpus` / `one author` / `different object` /
`outside` / `generalise` 抓边界声明；核对 L1251-L1253 的摘要绑定覆盖到哪一层。

关键数：

- `paper.tex` **65235 B**，写于 **11-11 01:34**；`data2.json` 写于 **11-10 22:05**，其中 `paper_bytes = 54778`——差 **10.5 kB**。
- `fig16_sections.pdf` 写于 **11-10 22:02**。
- 边界声明只到语料层（L1128-L1134「一个语料、一个作者、一种日志口径」；表第 1、6 行的「One corpus」「One project」）；
  **版本/对象层没有一句**。而 L1251-L1253 明确给 gate 判决做了摘要绑定
  （「stored with the digests of the files it judged, so a reader can check whether the verdict and the paper are the same object」）——
  同一把尺子没有用到 `data.json` / `data2.json` / 图上，于是 L1205「reads the repository state」把旧版工件与成稿当成了同一个状态。

`where` = `out/final/data2.json`　`evidence` = `paper_bytes`

## 三、与作者自评（`out/final/redteam.json`，section == claims）逐探针对比

| 探针 | 作者 | 本轮 | 差别 |
|---|---|---|---|
| 每条主张是否都有证据指针 | pass（「claims 表六行都指到章节/图」「未发现悬空声明」） | finding | 表内六行确实齐；漏的是表外 L1229 的冻结表——没点名、不在复现清单、缺表时 gate 判 N/A |
| 每条主张是否写明「哪里没支撑」 | pass（「第三列 Not supported」） | finding | 第三列只覆盖表内六行；正文 8 个全称句 0 处局限字样，`fig16_sections` 图注的主张背后是空工件 |
| 有没有把「未见反例」写成「已证明」 | finding（针对分类器召回 agreement=97.5） | finding | 同一探针，不同对象：本轮抓的是论文对**自己数字**的「零未溯源」=37/184，且 0.2146 的出处是手打常数 |
| 有没有主张超出语料范围而没说明边界 | pass（「局限一节明确一个语料、一个作者、一种日志口径」） | finding | 语料层写了；版本层没写——采集工件早于成稿 3.5 小时、`paper_bytes` 差 10.5 kB |

作者这一板从未审过「论文对自己数字的溯源」这件事，而这正是本文全篇主张的兑现处。

## 四、复现方式（只读）

```powershell
$env:PYTHONIOENCODING="utf-8"; $env:PYTHONUTF8="1"
$root = "C:\\Users\\21246\\Documents\\deepseek-harness\\default-workspace\\model1-arch"
$py  = "C:\\Users\\21246\\.dsh\\dsh-runtimes\\dsh-primary-runtime\\dependencies\\python\\python.exe"
Push-Location $root
& $py tools\\rtB_claims_p1_pointers.py          # 指针：表六行 / 六步清单 / 冻结表点名
& $py tools\\rtB_claims_p1b_who_builds_frozen.py # 谁生成冻结表（全仓 UTF-8 扫）
& $py tools\\rtB_claims_p2_unsupported.py        # 8 个全称句 / fig16 空工件 / mtime
& $py tools\\rtB_claims_p3_nonfalsify.py         # 复跑 check_paper：37 判 / 147 免检 / 手打常数
& $py tools\\rtB_claims_p4_scope.py              # 工件 vs 成稿的大小与时间
& $py tools\\rtB_claims_p0_evidence_check.py     # 交付里每个 evidence 标记逐字存在
```

## 五、边界与未做项（这一节也是给我自己的）

- 只审了 claims 板。`out/红队七板/` 下其他板的报告**没有读**，其他板的结论不出现在这里。
- 没有改 `paper.tex`、没有改任何 `.py`；没有跑 `gate.py --stamp`（会写文件），只读它的既有产物 `gate-report.json`。
- 探针 4 用到的 mtime 是文件系统现状，能证明「工件早于成稿」，不能证明「内容一定不一致」；
  能证明内容不一致的是 `paper_bytes=54778` vs 成稿 65235 B 这一个数。
- `fig14_density` 的图注缺陷（自己 `\\ref` 自己、夹带 `fig:sections` 的句子）在本板范围内记录，但它的归属更像图表板的问题；
  我没有去改，也没有把它单列为一条 finding，只写在探针 1 的证据里。
- 本节 L1234-L1254 的 AI 披露四条，我只核了「数字由脚本产出」这一条（探针 3）；「分类是判断而非测量」那一条按声明表
  第 5 行的自述算已披露，没有独立复核判断质量。
"""
p = os.path.join(out, "claims-overclaim-auditor.md")
io.open(p, "w", encoding="utf-8", newline="\n").write(md)
print("wrote", p, os.path.getsize(p), "bytes")
# 结构自检：三列表存在、四个 finding 小节存在、无表格断行
t = io.open(p, encoding="utf-8").read()
print("has 声明/证据/未支撑 header:", u"| # | 声明 | 证据（我核到的那件东西） | 未支撑（论文写了没 / 我核到什么） |" in t)
for k in ("探针 1", "探针 2", "探针 3", "探针 4"):
    print(" section", k, ":", k in t)
bad = [i for i, ln in enumerate(t.splitlines(), 1) if ln.strip().startswith("|") and ln.count("|") != 5]
print("rows with wrong pipe count (expect 5 for 4-col table):", bad[:10], "n=", len(bad))