# -*- coding: utf-8 -*-
"""scope-auditor: emit the board deliverables (json + md) from one source of truth.

Writes ONLY:
  out/红队七板/restatement-scope-auditor.json
  out/红队七板/restatement-scope-auditor.md
Never touches paper.tex or any existing .py.
"""
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "out", "红队七板")
os.makedirs(OUT, exist_ok=True)

PAPER = "out/final/paper.tex"

rows = [
    ("T1", "交付一条能出稿并过全部检查的管线（§11.1 L1176-1178 “passes 29 checks with no warnings”；摘要 L45-47 “23/23 gate passes”）",
     "L84-L86 只有祈使句 Build a capability layer …, then measure both，没有验收条款", "未覆盖：重述从不问「算不算交付成功」"),
    ("T2", "computed 数字必须溯源到冻结产物（§11.1 L1179-L1180）",
     "Q1 L90-L92", "覆盖，但把 every number 收窄成 computed（见探针 2）"),
    ("T3", "溯源效果可归因于机制（§11.1 L1183-L1185）", "Q2 L93-L94", "覆盖"),
    ("T4", "题型识别能力（§11.1 L1186-L1188；§7.1 全节；摘要 L50-L54）",
     "无", "漏问：整条 claim 没有对应问句"),
    ("T5", "六类缺陷在验证代码里复发（§11.1 L1189-L1191；§8）", "Q3 L95-L97", "覆盖，但答案已写进问句（见探针 4）"),
    ("T6", "自检只有接线才起作用（§11.1 L1192-L1194）",
     "Q3 只隐含 “never runs / reads a stale input”，未成条目", "弱覆盖"),
    ("T7", "honest limit：工具保证数字真、不保证论证成立（摘要 L66-L68）",
     "无；Scope L108-L112 反而写了 not a report generator", "漏问，且 Scope 与能力清单冲突（见探针 2C）"),
    ("T8", "§9 deployment：把工具交给四天赛程的团队（L1001-L1005）", "无", "漏问"),
    ("T9", "§10 evaluation and extension：优势、弱点、扩展（L1119-L1130）", "无", "漏问"),
    ("T10", "§12 reproducibility, claims and disclosure：复现与 AI 使用声明（L1201-L1234）", "无", "漏问"),
]

probes = [
    {
        "probe": "重述是否逐条覆盖题面的每一问（有没有漏问）",
        "verdict": "finding",
        "note": (
            "先把前提摆明：全仓找不到本论文的外部题面，所以「覆盖题面的每一问」只能拿论文自己声明的题面条目做代理，"
            "这一点本身就是一个缺陷 —— 重述 L84 用 What we take as the task 自行定义题目，既没引用任何来源，也没说它在重述哪份东西。"
            "搜法与结果：以插件根为起点递归搜 .md/.txt/.tex/.json，排除 out/、runs/、runs_backup/、node_modules/、__pycache__、"
            "external/、fig/、build/、dist/、.git，实际扫 54 个文件；文件名提示词（题面|题目|problem|brief|requirement|要求|任务|statement）"
            "0 命中；正文提示词（Problem Statement|问题重述|题目要求|Your task|You are asked|赛题|MCM/ICM|Contest Problem）11 命中，"
            "但全是插件文档里泛指「赛题」的段落（README.md、插件速查.md、赛前检查清单.md、交接.md 等），没有一份是本题 brief。"
            "再查 out/final 内部：只有 meta_eval.json 出现 problem statement，是工时条目里「读题」这一项，不是题面。"
            "论文正文也从不点名题面（we were asked|the problem asks|the brief|assignment|competition problem|prompt asks 六个表述 0 命中）。"
            "在代理题面下做一一对照（表见 md）：10 条题面条目里重述只接住 4 条 —— T2 覆盖但收窄、T3 覆盖、T5 覆盖但答案前置、T6 弱覆盖；"
            "T1/T4/T7/T8/T9/T10 六条无对应问句。最硬的漏问是题型识别：§7.1 为它单开一节（L680）、§11.1 把 Problem types can be recognised "
            "列为六条 claim 之一（L1186）、摘要 L50-L54 把它当主结果（Type detection, which could not emit … before），而重述三问 L90/L93/L95 没一句问它。"
            "另一处是 honest limit（摘要 L66-L68）：工具保证数字真、不保证论证成立，在 Scope（L108-L112）完全没有落位。"
            "结构上还有一件事：本板 96 行里 56 行是 L114-L169 的 Relation to prior work（50 行非空），重述正文只剩 L75-L113 的 33 行非空 —— "
            "板名是「重述题面」，过半篇幅是文献综述。"
        ),
        "tried": (
            "逐行读完 L75-L170 全部 96 行并做结构普查（\\paragraph 9 个、\\item 3 条、\\subsection 1 个、\\cite 15 条、\\ref 仅 1 条指向 sec:growth、"
            "数字 token 1 个）；把 12 个 \\section 的段起点（L75/171/223/255/279/477/677/864/1001/1119/1149/1201）与三问逐一对表；"
            "读 §7.1 L677-L716 与 §11.1 声明表 L1166-L1199，确认题型识别与出稿交付都是显式 claim；"
            "用 tools/rtB_restatement_probe1.py 在插件根跑两轮递归搜索（外部题面 54 个文件、文件名 0 命中、正文命中逐条打印路径）；"
            "用 tools/rtB_restatement_probe4.py 搜 out/final/*.json 里提到 problem statement 的文件；"
            "另用 Select-String 查 we were asked/the brief/assignment 等六个表述，0 命中。"
        ),
        "where": PAPER,
        "evidence": "Problem types can be recognised",
    },
    {
        "probe": "有没有在重述里悄悄放宽或收紧约束",
        "verdict": "finding",
        "note": (
            "两个方向都动了，两处都没标注「这是改动」。"
            "(A) 收紧：L100-L102 把判据写成全称命题 —— a claim may stand only if it can be traced to something computed and has survived an attempt to break it。"
            "可同一篇论文 §11.1 的声明表表头就是 Not supported:（L1174），逐条写明自己哪条没经受住攻击：L1183-L1185 的 Tracing is attributable to the mechanism "
            "一栏写 No controlled comparison with and without the tool; no independent rater；L1189-L1191 写 The classification is our own reading; no inter-rater agreement；"
            "L1192-L1194 写 the defects were found by us, not by an independent audit。重述设的闸比正文交付的高，且没有任何一节回头对账，"
            "读者会把全篇当已过闸。"
            "(B) 放宽：L90-L92 把通行要求 every number must be traceable 直接判为 not actionable，改成只有 computed 一类必须溯源 —— 标准被收窄，"
            "却写成分析结论，而支撑它的四类分解要到 §2（L175 才出现 four kinds）才出现，标准的变更发生在证据之前。"
            "(C) 能力边界写错：L110 It is not a report generator 与 schema.json 冲突 —— run 的 desc 是「一条龙：读数据到出 PDF 全自动」，"
            "skeleton 的 desc 是「出稿骨架：--from-tex 从已生成的 tex 里列出可被 LLM 重写的段落」，gate 的 pdf 是硬门（gate.py L266：没有 paper.pdf，只有 tex 不算出稿）。"
            "真实区别是「自动模式不替你做建模决定」，不是「不出稿」；重述把一条方法论劝告写成了能力边界。"
            "(D) L104-L106 的 fails closed 也比实现强：§8 Case 3（L913-L924）自述修复前 N/A 被当作通过，修复后仍保留 genuine absence (declared) stays N/A —— "
            "「跑不起来的检查」仍可能停在 N/A，不是一律判失败。"
        ),
        "tried": (
            "把 L75-L170 里每句带约束语气的句子单独摘出来（L90-L92、L100-L106、L108-L112），逐句拿可机读事实源去撞："
            "schema.json 的 23 条命令 desc（重点 run/skeleton/hints/plot）、gate.py 的 HARD 标记与 chk_compile/chk_pdf/chk_numbers 主体（L249-L312）、"
            "out/final/gate-report.json 的 30 项检查状态、以及 §11.1 的 Not supported 列（L1174-L1194）；"
            "再用 tools/rtB_restatement_probe2.py 逐段打印原文与命中位置，确认取值不跨行。"
        ),
        "where": PAPER,
        "evidence": "has survived an attempt to break it",
    },
    {
        "probe": "题面给的常数/量纲是否原样搬来并标了出处",
        "verdict": "finding",
        "note": (
            "题面这一侧先给结论：不存在外部题面，所以没有「题面给的常数」可搬；量纲这一半不适用 —— 本板 96 行里没有任何物理单位或量纲符号"
            "（\\mathrm/\\si/\\SI/kg/kW/MPa/N\\cdot 等 0 命中）。但板上确实有一个常数且没出处：L81 的 $R^2=0.94$。"
            "用项目自己的分词器 verify.extract_numbers 扫 L75-L170，只抽出 1 个 token，就是它（written_decimals=2）。"
            "把它撞 out/final/冻结数字.json（715 条；source 写 out/final · 论文自身的测量工件，generated_from=tools/freeze_paper_numbers.py）："
            "精确等于 0.94 的条目 0 条，落在 [0.93,0.95] 的 0 条，全表连 r2 字样都没有。"
            "可 verify.trace 用 gate 真实加载的池（verify.load_outputs('out/final') = 14 份文档 / 2669 个数）跑本板，结果 ok=True、1/1 = 100% 通过。"
            "原因在 verify.py L208-L210 的 for scale in (100.0, 0.01) 百分比换算分支：0.94 被折成 94.0，命中三个百分比字段 —— "
            "data.problems[0].num_pct=94.0（items[17]）、data.problems[10].num_pct=93.9（items[157]）、ablation[0].with_table=94.0（items[630]）。"
            "于是一个假想的 R² 由「某题 93.9–94.1% 的溯源率」背书，量纲与语义都不对，判据却给满分。"
            "这正是本文 L80-L82 自己写的病（asked where $R^2=0.94$ came from, the honest answer is often the model produced it），"
            "也是 §8 Case 5（L945 Case 5: a number in our own abstract was invented）承诺不再犯的错。"
            "持平地说：把它当失败模式的举例是可读的，我不把「举例」本身当罪；但这句没有任何 example/hypothetical 标记，也没说这是假设值，"
            "读者会当它是语料里的测量值，而唯一能拦住它的判据（冻结表精确匹配）被 ×0.01 分支短路了。"
        ),
        "tried": (
            "用 verify.extract_numbers 扫 L75-L170（1 个 token：0.94，2 位小数）；按 _written_decimals 的精度撞 冻结数字.json 的 716 个数值叶子"
            "（0.94 精确 0 命中、[0.93,0.95] 0 命中、含 r2 的条目 0 条）；再用 verify.collect_output_numbers(verify.load_outputs('out/final')) "
            "平铺 2669 个数，复刻 _near 的 scale 分支算出命中集合（93.9/94.0/94.1）；最后把命中值回填到 items[17]/[157]/[630] 与 "
            "data.problems[0].num_pct、data.problems[10].num_pct、ablation[0].with_table，确认全是百分比字段。"
            "探针：tools/rtB_restatement_probe3.py、rtB_restatement_probe3b.py。"
        ),
        "where": PAPER,
        "evidence": "0.94",
    },
    {
        "probe": "重述里是否已经出现结论（把答案写进问题）",
        "verdict": "finding",
        "note": (
            "三处把答案写进了问题：一处在问句里，两处在问句外。"
            "(i) Q3（L95-L97）问 Is the checker itself trustworthy? 后面紧跟 A check that cannot fail, never runs, or reads a stale input is "
            "indistinguishable from a passing one, and we found our own code full of them —— 六类缺陷这个 §8 的结论在题面第 3 条里已经成立，"
            "Q3 不再是问题。"
            "(ii) L100-L106 把未验证结果当既成事实：机制存在、把负担放到 a program that can refuse、fails closed、a claim without a source does not compile、"
            "a check that cannot run is reported as not applicable rather than as a pass —— 这是 §5 与 §8 的答案，出现在任何测量之前。"
            "其中 does not compile 与实现不符：gate.py 的 compile 是 LaTeX 编译检查（L249 chk_compile 扫 paper.log 的错误），numbers 是另一条硬门（L284 起），"
            "数字没出处只让 numbers 判 FAIL，不会让论文编译不过；fails closed 又被本文 Case 3（L913-L924）自己否掉一半。"
            "(iii) L108-L112 的 Scope 用过去时写已交付物（the rule we kept returning to）并列了 8 个能力族 —— 这是 §7 的答案。"
            "后果可核：读者在第 1 节就能读到 §2/§5/§7/§8/§11 的结论；本板三问全部以陈述句收尾，96 行里没有一句是「待答」。"
        ),
        "tried": (
            "把本板每句按时态与模态过一遍（正则 we found|fails closed|does not compile|we introduce|we assume|kept returning to|"
            "we make the spread|is reported as not applicable，命中处逐条打印并取上下文 60 字），再把每个疑似结论句拿去后文找证据所在节"
            "（§2 L175、§5 L315、§7 L677、§8 L864-L1000、§11 L1166），确认证据都排在结论之后；"
            "另读 gate.py 的 chk_compile（L249-L256）与 numbers 硬门（L284-L312）核对 does not compile 的语义，读 §8 Case 3（L913-L924）核对 fails closed。"
        ),
        "where": PAPER,
        "evidence": "found our own code full of them",
    },
]

resolved = (
    "未处理。四条 finding 全部是本轮新提，正文一处未改（全程只读 paper.tex 与所有 .py）。"
    "缺席可核：out/final/redteam.json 的 reviews 里 section 只有七板（analysis / method_argument / validation / results / "
    "self_correction / deployment / claims），没有 restatement；gate-report.json 的 30 项检查里也没有 restatement 这一项，"
    "所以这一板此前从未被审过。四条 finding 的关闭路径（供作者照做，不需要我改稿）："
    "① 题面侧补一行来源（哪份 brief、哪一问），并把题型识别补成第 4 问，把摘要 L66-L68 的 honest limit 搬进 Scope；"
    "或明确写清题目由本文自定（What we take as the task 不是重述）。"
    "② 全称判据改成可兑现的弱化形（例如「每条 claim 必须在 §11.1 表里同时给出 evidence 与 not supported 两栏」），"
    "把 not a report generator 改成「自动模式不替你决定建模」，把 fails closed 降级为「N/A 与 fail 分开报」。"
    "③ 给 $R^2=0.94$ 加 example 标记与假设值说明，或替换成冻结表里的真实 R²；同时让 verify 对假设值单独开口子，"
    "不要让 ×0.01 分支继续给假想数背书。"
    "④ 三问改成真问句，把 we found our own code full of them、fails closed、does not compile、8 个能力族这些结论句移出第 1 节，"
    "或标成「本文的主张，证据见 §x」。"
)

board = {
    "section": "restatement",
    "role": "scope-auditor",
    "probes": probes,
    "resolved": resolved,
    "verdict": "revise",
}

jpath = os.path.join(OUT, "restatement-scope-auditor.json")
with open(jpath, "w", encoding="utf-8", newline="\n") as fh:
    json.dump(board, fh, ensure_ascii=False, indent=2)
    fh.write("\n")
print("wrote %s (%d bytes)" % (jpath, os.path.getsize(jpath)))

# ---------------------------------------------------------------- markdown
md = []
md.append("# restatement · scope-auditor")
md.append("")
md.append("审核对象：`out/final/paper.tex` L75-L170，`\\section{Restatement of the problem}`（96 行：L75-L113 正文 + L114-L169 `\\subsection{Relation to prior work}`）。")
md.append("角色：`scope-auditor`（本板专用，未复用）。判定：**revise**（4 条探针全部 finding）。")
md.append("")
md.append("## 0. 前提：题面在哪里")
md.append("")
md.append("全仓没有本论文的外部题面，这一点先交代清楚，因为它决定了下面那张对照表的性质。")
md.append("")
md.append("| 搜法 | 范围 | 命中 |")
md.append("|---|---|---|")
md.append("| 文件名提示词 `题面｜题目｜problem｜brief｜requirement｜要求｜任务｜statement` | 插件根，`.md/.txt/.tex/.json`，排除 `out/ runs/ runs_backup/ node_modules/ __pycache__/ external/ fig/ build/ dist/ .git`（实际扫 54 个文件） | 0 |")
md.append("| 正文提示词 `Problem Statement｜问题重述｜题目要求｜Your task｜You are asked｜赛题｜MCM/ICM｜Contest Problem` | 同上 | 11，全是插件文档里泛指「赛题」的段落（`README.md`、`插件速查.md`、`赛前检查清单.md`、`交接.md` …），无一是本题 brief |")
md.append("| `problem statement` | `out/final/*.json` | 1：`meta_eval.json` 工时条目里的「读题」环节，不是题面 |")
md.append("| `we were asked｜the problem asks｜the brief｜assignment｜competition problem｜prompt asks` | `out/final/paper.tex` | 0 |")
md.append("")
md.append("⇒ 重述 L84 用 *What we take as the task* 自行定义题目，既无来源也不说在重述哪份东西。所以「覆盖题面的每一问」只能拿**论文自己声明的条目**做代理：§11.1 六条 claim + 摘要的 honest limit + §9/§10/§12 三节交付。这是代理，不是原件。")
md.append("")
md.append("## 1. 题面条目 × 重述条目 一一对照表")
md.append("")
md.append("| # | 题面条目（来源行） | 重述里的对应条目 | 判定 |")
md.append("|---|---|---|---|")
for tid, item, mapped, verdict in rows:
    md.append("| %s | %s | %s | %s |" % (tid, item, mapped, verdict))
md.append("")
md.append("**计数**：10 条题面条目 → 覆盖 3（T2/T3/T5）、弱覆盖 1（T6）、无对应问句 6（T1/T4/T7/T8/T9/T10）。")
md.append("三问只接住 §2（Q1）、§6-S7（Q2）、§8（Q3）；§9 deployment、§10 evaluation、§12 reproducibility 三个交付承诺在重述里没有任何问句。")
md.append("")
md.append("## 2. 四条探针")
md.append("")
for i, pr in enumerate(probes, 1):
    md.append("### 探针 %d：%s" % (i, pr["probe"]))
    md.append("")
    md.append("- verdict：**%s**" % pr["verdict"])
    md.append("- where：`%s`" % pr["where"])
    md.append("- evidence（逐字存在）：`%s`" % pr["evidence"])
    md.append("")
    md.append("**note**")
    md.append("")
    md.append(pr["note"])
    md.append("")
    md.append("**tried**")
    md.append("")
    md.append(pr["tried"])
    md.append("")
md.append("## 3. 关键证据回放（可直接复跑）")
md.append("")
md.append("| 事实 | 命令/探针 | 结果 |")
md.append("|---|---|---|")
md.append("| 本板只有 1 个数字 token | `tools/rtB_restatement_probe3.py`（`verify.extract_numbers`） | `0.94`，2 位小数 |")
md.append("| 0.94 在冻结表里的精确命中 | 同上（716 个数值叶子） | 0 条；`[0.93,0.95]` 0 条；含 `r2` 的条目 0 条 |")
md.append("| 0.94 却通过溯源 | `tools/rtB_restatement_probe3b.py`（`verify.trace` + `verify.load_outputs('out/final')`） | `ok=True, 1/1, traced_ratio=1.0` |")
md.append("| 谁给它背书 | 同上（复刻 `verify.py` L208-L210 的 `scale in (100.0, 0.01)`） | `data.problems[0].num_pct=94.0`、`data.problems[10].num_pct=93.9`、`ablation[0].with_table=94.0` |")
md.append("| `not a report generator` 与能力清单冲突 | `tools/rtB_restatement_probe2.py`（`schema.json`） | `run`=「一条龙：读数据到出 PDF 全自动」；`skeleton`=「出稿骨架」；`gate` 的 `pdf` 是硬门 |")
md.append("| `does not compile` 是编译还是判分 | 同上（`gate.py` L249-L312） | `compile` 是 LaTeX 日志检查；`numbers` 是另一条硬门，数字没出处只判 FAIL |")
md.append("| `fails closed` 被本文自己否掉一半 | `paper.tex` L913-L924（Case 3） | 修复前 N/A 算通过；修复后 `genuine absence (declared)` 仍留 N/A |")
md.append("")
md.append("## 4. 关闭情况")
md.append("")
md.append(resolved)
md.append("")
md.append("## 5. 本轮只读声明")
md.append("")
md.append("未改 `out/final/paper.tex`，未改任何 `.py` 源码。新增文件仅为探针：")
md.append("`tools/rtB_restatement_probe1.py`、`rtB_restatement_probe2.py`、`rtB_restatement_probe3.py`、`rtB_restatement_probe3b.py`、`rtB_restatement_probe4.py`、`rtB_restatement_selfcheck.py`、`rtB_restatement_write.py`。")
md.append("未读 `out/红队七板/` 下其他板的报告。")
md.append("")

mpath = os.path.join(OUT, "restatement-scope-auditor.md")
with open(mpath, "w", encoding="utf-8", newline="\n") as fh:
    fh.write("\n".join(md))
print("wrote %s (%d bytes)" % (mpath, os.path.getsize(mpath)))
