#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""grade.py —— 阅卷器（只判形式与硬约束，判不了对错）。

**保密约束**：本文件只写「判据」，不复述题面。题面不进任何会被别的会话读到的文件，
也不派任何 subagent —— 派了就等于把题泄露给另一个会话。

设计原则：**只做机器能做的**。
  · 能机械判的：某个约束在不在、某个错误假设有没有出现、格式齐不齐
  · 判不了的：模型对不对、推导错没错、结论合不合理 —— 这些列成清单交给人

用法：
    python tools/grade.py out/d2026d            # 待评目录
    python tools/grade.py out/d2026d --json
退出码：0 = 无「一票否决」级缺陷；1 = 有。

一票否决级（按评分标准，命中则该问得分上限被压死）：
  · 没有需量电费 / P_max 线性化   → 问题 1 ≤ 10
  · SOC 越界或充放电不同时互斥     → 问题 1 ≤ 10
  · 问题 2 只做蒙特卡洛/随机规划   → 问题 2 ≤ 15
  · 假设「无限带宽 / 训练可任意平移」→ 数据与假设项直接扣 10
"""
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _tex(d):
    # 认 paper.tex 与 main.tex 两种命名（不同模板惯例不一样）。
    # 也允许 d 指到上层目录，自动下沉一层的 paper/ 或 tex/。
    for name in ("paper.tex", "main.tex"):
        for sub in ("", "paper", "tex"):
            p = os.path.join(d, sub, name) if sub else os.path.join(d, name)
            if os.path.exists(p):
                return io.open(p, encoding="utf-8", errors="replace").read()
    return None


def _has(t, *pats):
    return any(re.search(p, t, re.I) for p in pats)


def _count(t, *pats):
    return sum(len(re.findall(p, t, re.I)) for p in pats)


def _bad_bandwidth(t):
    """有没有「无限带宽 / 任意平移」的错误假设 —— **排除否定式**。

    实测踩到：好论文写 `We do not assume unlimited bandwidth.`，
    朴素正则命中 `unlimited bandwidth` 就判「命中错误假设」，把对的判成错的。
    所以按句切，句内有关键词时再看有没有否定词。
    """
    KEY = r"无限带宽|unlimited\s+bandwidth|任意平移|不受带宽.{0,10}限制"
    NEG = (r"(do|does|did|is|are|was|were)\s+not|not\s+assume|no\s+longer"
           r"|never|without|cannot|can't|没有|不使用|不假设|不存在|并非|拒绝"
           # 第 123 轮补：批判「错误假设」时常用这些词，它们同样是否定语境。
           # 实测漏掉：「这从物理上杜绝了…伪假设」「若采用…伪假设，该解不可执行」。
           r"|杜绝|伪假设|不可执行|不成立|避免|摒弃|而非|警惕")
    for sent in re.split(r"[.;。；\n]", t):
        if re.search(KEY, sent, re.I) and not re.search(NEG, sent, re.I):
            return True
    return False


# ── 每项：(id, 名称, 判据函数, 缺了扣多少, 是否一票否决) ──
def checks(t):
    out = []

    def add(i, name, ok, why, penalty, veto=False):
        out.append(dict(id=i, name=name, ok=bool(ok), why=why,
                        penalty=0 if ok else penalty, veto=veto and not ok))

    # ============ 数据甄别与假设合理性（10） ============
    add("A1", "两部制电价：需量/容量电费被建模",
        _has(t, r"需量", r"capacity\s+charge", r"demand\s+charge",
             r"两部制", r"P_?\{?\\?(max|peak)"),
        "目标函数里必须出现需量电费项，否则没有理解这类高需量负荷的盈利模式", 8, veto=True)
    add("A2", "需量费用的线性化（Big-M 或等价）",
        _has(t, r"big[-\s]?m", r"大\s*\$?\s*[Mm]", r"\\text\{big-?M\}",
             r"辅助变量.{0,30}(峰值|peak)"),
        "只写「最大值」不算线性化：需要辅助变量 + 二元变量 + 大 M", 5)
    add("A3", "储能成本口径：EPC + 运维（不是只算电池单价）",
        _has(t, r"EPC", r"运维", r"O\s*&\s*M", r"全生命周期"),
        "成本口径少一项，等年值就偏低，规划结论不可信", 4)
    add("A4", "推理负荷被当作**不可平移**",
        _has(t, r"推理.{0,20}(不可|不能).{0,10}(平移|中斷|中断)",
             r"SLA", r"刚性", r"inference.{0,20}(not|non)[-\s]?(shift|defer)"),
        "把推理当柔性负荷是可平移假设的翻版", 0)          # 单独在 A5 判罚
    add("A5", "**没有**「无限带宽 / 训练任意平移」的错误假设",
        not _bad_bandwidth(t),
        "命中即按评分标准扣满 10 分（这一条是防雷区，不是加分项）", 10, veto=True)

    # ============ 问题 1（25） ============
    add("B1", "带宽约束 B_limit 进入模型（不只是文字提一句）",
        _has(t, r"B_?\{?\\?(limit|max)", r"带宽.{0,12}(约束|上限)",
             r"bandwidth.{0,15}(constraint|limit)"),
        "训练任务的时间-空间耦合必须写成硬约束", 7)
    add("B2", "SOC 上下限（10%–90%）",
        _has(t, r"SOC", r"荷电状态", r"state\s+of\s+charge"),
        "没有 SOC 约束就没有储能模型", 5, veto=True)
    add("B3", "充放电互斥（0-1 变量，不能同时充放）",
        _has(t, r"互斥", r"mutual(ly)?\s+exclusiv",
             r"(充|放).{0,10}同时",
             r"u_?\^?\{?(ch|dis)"),
        "缺互斥约束 = 允许同时充放 = 凭空造能，是最常见的建模漏洞", 5, veto=True)
    add("B4", "功率平衡约束",
        _has(t, r"功率平衡", r"power\s+balance", r"能量平衡"),
        "缺这一条，任何调度都「可行」", 4)
    add("B5", "目标函数含：等年值投资 + 电量电费 + 需量电费 − 售电收益",
        _has(t, r"等年值", r"annuali[sz]ed?", r"售电", r"上网"),
        "四项缺一项，比较基准就不同", 4)

    # ============ 问题 2（30） ============
    add("C1", "Wasserstein 距离 / 模糊集（Ambiguity Set）",
        _has(t, r"Wasserstein", r"模糊集", r"ambiguity\s+set",
             r"1-Wasserstein"),
        "没有模糊集就不是 DRO", 10, veto=True)
    add("C2", "**没有**只做蒙特卡洛 / 场景法就宣称鲁棒",
        not (not _has(t, r"Wasserstein", r"模糊集", r"ambiguity\s+set")
             and _has(t, r"蒙特卡洛", r"Monte\s*Carlo", r"场景(法|生成)",
                      r"scenario\s+(generation|reduction)")),
        "只做场景法按评分标准 ≤ 15 分", 15, veto=True)
    add("C3", "对偶转化，或明确说明用求解器实现",
        _has(t, r"对偶", r"dual", r"Gurobi", r"Cplex", r"YALMIP", r"SOCP", r"SDP"),
        "DRO 不写对偶就直接说「求解」，等于跳过了最难的一步", 10)
    add("C4", "半径–成本–风险的敏感性分析（帕累托前沿）",
        _has(t, r"帕累托", r"Pareto", r"前沿", r"半径.{0,12}(成本|风险)"),
        "这一项是 DRO 的「深化」得分点", 10)

    # ============ 问题 3（25） ============
    add("D1", "Arrhenius / 半经验电化学衰减模型",
        _has(t, r"Arrhenius", r"阿伦尼乌斯", r"半经验", r"衰减"),
        "只写「电池容量线性衰减」等于没做这一问", 8)
    add("D2", "分段线性化（Piecewise Linearization）",
        _has(t, r"分段线性", r"piecewise", r"\\text\{PWL\}", r"SOS2"),
        "非线性项不线性化，MINLP 求解结论不可复现", 7)
    add("D3", "孤岛恢复时间服从对数正态并被抽样/建模",
        _has(t, r"对数正态", r"lognormal", r"log-normal"),
        "题面给的是分布，不是常数", 5)
    add("D4", "训练挂起/回滚 与 储能保供推理 的协同策略",
        _has(t, r"挂起", r"回滚", r"checkpoint", r"检查点"),
        "这一问考的是「算力侧动作」与「电力侧动作」的耦合", 5)
    add("D5", "P2P 互济 + 算力迁移的组合，且有量化对比",
        _has(t, r"P2P", r"点对点", r"互济", r"peer[-\s]?to[-\s]?peer"),
        "只定性说「有好处」不够，要有量化对比", 5)

    # ============ 学术规范（10） ============
    add("E1", "公式是 LaTeX 环境（不是截图/纯文本）",
        _count(t, r"\\begin\{(equation|align|gather)") >= 5,
        "公式少于 5 个环境，通常意味着模型没写成数学语言", 3)
    add("E2", "有变量/符号说明表",
        _has(t, r"\\begin\{table\}", r"符号", r"notation", r"变量说明"),
        "变量定义不清是最高频的失分点", 2)
    add("E3", "摘要含**量化**结论（不是「本文建立了模型」）",
        _has(t, r"\d+(\.\d+)?\s*\\?%", r"降低.{0,8}\d", r"较基准"),
        "摘要没有数字，评审看不到你算出了什么", 3)
    add("E4", "有伪代码或算法流程",
        _has(t, r"\\begin\{(algorithm|algorithmic)", r"伪代码", r"pseudocode"),
        "MINLP/DRO 的求解流程不写算法，复现性存疑", 2)
    return out


BAD_SAMPLE = r"""\documentclass{article}
\begin{document}
\begin{abstract}We build a model.\end{abstract}
\section{Model}
We assume unlimited bandwidth, so training jobs move anywhere.
We use Monte Carlo scenario generation to be robust.
\end{document}
"""

GOOD_SAMPLE = r"""\documentclass{article}
\begin{document}
\begin{abstract}Cost drops 12.4\% against the baseline.\end{abstract}
\section{Assumptions}
Two-part tariff with demand charge on P_{max}. EPC plus O\&M annualised.
Inference is not shiftable (SLA 99.99\%). We do not assume unlimited bandwidth.
\section{Model}
\begin{equation}\min C\end{equation}
\begin{equation}P_{max}\ge P_t\end{equation}
\begin{equation}SOC_{min}\le SOC_t\le SOC_{max}\end{equation}
\begin{equation}u^{ch}_t+u^{dis}_t\le 1\end{equation}
\begin{equation}B_{limit}\ge f_{ij,t}\end{equation}
Power balance holds. The demand charge is linearised by \textbf{Big-M}.
\section{Notation}\begin{table}\begin{tabular}{ll}SOC & state of charge\end{tabular}\end{table}
\section{DRO}
Wasserstein ball and ambiguity set; dual reformulation to an SOCP solved with Gurobi.
Radius-cost-risk Pareto front.
\section{Islanding}
Arrhenius semi-empirical degradation with piecewise linearisation and SOS2.
Recovery time is lognormal. Training suspended at checkpoint.
P2P sharing plus task migration, compared quantitatively.
\begin{algorithm}\caption{flow}\end{algorithm}
\end{document}
"""


def cmd_selftest():
    """阅卷器自校：拿两个构造出来的样本验它自己。

    不能「读当前状态」当验证 —— 必须构造缺陷。坏样本必须触发否决，
    好样本必须零扣分。任一条不成立 = 判据坏了，今天的阅卷结论都不能信。
    """
    res = []
    for name, body, want_veto in (("坏样本", BAD_SAMPLE, True),
                                  ("好样本", GOOD_SAMPLE, False)):
        rows = checks(body)
        veto = [r for r in rows if r["veto"]]
        pen = sum(r["penalty"] for r in rows)
        ok = (bool(veto) == want_veto)
        res.append((name, ok))
        print("  [%s] %s → 否决 %d 项，参考扣分 %d（期望%s否决）"
              % ("PASS" if ok else "**FAIL**", name, len(veto), pen,
                 "" if want_veto else "无"))
    bad = [r for r in res if not r[1]]
    print()
    if bad:
        print("**阅卷器自校失败**：%s —— 判据坏了，先修再阅卷" % bad[0][0])
        return 1
    print("阅卷器自校通过：坏样本抓得住，好样本不误报。可以开始阅卷。")
    return 0


def main(argv):
    if "--selftest" in argv:
        return cmd_selftest()
    d = argv[1] if len(argv) > 1 and not argv[1].startswith("-") else None
    if not d:
        print(__doc__)
        return 2
    t = _tex(d)
    if t is None:
        print("没有 %s/paper.tex" % d)
        return 2
    rows = checks(t)
    veto = [r for r in rows if r["veto"]]
    total_pen = sum(r["penalty"] for r in rows)

    if "--json" in argv:
        print(json.dumps(dict(dir=d, rows=rows, veto=[r["id"] for r in veto],
                              penalty=total_pen), ensure_ascii=False, indent=1))
        return 0 if not veto else 1

    print("阅卷：%s" % d)
    print("（机器只判「在不在」，判不了「对不对」—— 后者见下面的清单）")
    print()
    for r in rows:
        tag = "有" if r["ok"] else ("**否决**" if r["veto"] else "缺")
        print("  [%-6s] %-4s %s" % (tag, r["id"], r["name"]))
        if not r["ok"]:
            print("           %s  → 参考扣分 %d" % (r["why"], r["penalty"]))
    print()
    print("合计参考扣分：%d / 100" % total_pen)
    if veto:
        print("**一票否决级缺陷**：%s" % ", ".join(x["id"] for x in veto))
        print("  按评分标准，对应的问得分上限被压死，不是按扣分算。")
    print()
    print("机器判不了的（留给阅卷人）：")
    print("  1. 目标函数与约束的**推导**对不对（尤其 DRO 的对偶）")
    print("  2. 求解器设置、收敛性、是否真的求出全局最优")
    print("  3. 敏感性分析的**结论**是否支撑「鲁棒成本」的说法")
    print("  4. 孤岛场景里「关键算力存活」的定义是否自洽")
    print("  5. 有无**未声明的假设**（最危险的一类）")
    return 0 if not veto else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
