#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一回归入口：一条命令跑完架构本体 + 全部套件

在这之前，回归要手抄一长串文件名；加了新脚本就得记得补进去，
漏掉的那个就等于没测过。这个文件是**唯一**的套件清单。

用法：
  python tests/run_all.py            # 全部
  python tests/run_all.py --core     # 只跑架构本体
  python tests/run_all.py --quiet    # 只报失败

退出码：全过 0，有失败 1。
"""

from __future__ import annotations

import os
import re
import subprocess
import sys

# 一次失败不足以定罪（第七十六轮）：
#   本机回归已经三次"随机变红、重跑就绿"，红的是环境不是代码
#   （WSL 里 seekdb 被占、DNS 抖、杀毒软件扫盘）。
#   所以每条**失败**重试一次；仍然失败才算数。
#   重试过会打出来，不悄悄放过。
RETRY_ONCE = "--no-retry" not in sys.argv

# 重试记录：谁靠重试才过的，得留下痕迹。
# 「重试会掩盖真抖动」——某条如果每次都要重试，那它本身就是不稳定的，
# 不该因为"反正能过"就没人管（第七十七轮）。
RETRY_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         ".retry_log.jsonl")

TESTS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TESTS)
PY = sys.executable

# 架构本体：必须有断言、必须全过
# want 可以是 int（数 [PASS] 条数）或 str（输出里必须出现这句话）
# 断言数变了要**主动改这里**——数量下降说明有断言被删掉，不该悄悄放过
CORE = [
    ("harness.py", ["selftest"], 74),
    ("extend.py", ["selftest"], 67),
    ("ledger.py", ["guard"], 63),
    ("sargable.py", [], "准确率: 15/15"),
    ("probe.py", [], 17),
    ("capability.py", [], 20),
    ("kb.py", ["selftest"], 15),
    # 建模引擎五层：机理 / 约束优化 / 不确定性 / 外推 / 判定
    ("engine.py", ["selftest"], 28),
    # 多通道并行验证：八条通道 + veto + 跨主张一致性
    ("lanes.py", ["selftest"], 70),
    # 数据文件定位：剪枝扫描 + 磁盘缓存（曾让 run 慢 21 倍）
    ("datapath.py", [], 17),
    # 验证三件套里，原来只有 lanes 上了链 —— falsify / verify / freeze
    # 各自有独立自检却**不在验收范围内**：改坏它们，账目照样 ALL GREEN。
    # 第 94 轮补上（数字全部现场跑出来的，不是抄的）。
    ("falsify.py", ["selftest"], 16),
    ("verify.py", [], 16),
    # 第 123 轮：12 → 16。新增 4 条是「半格边界」——
    # 合法舍入必须过（0.78751←0.787505、32.95←32.945），
    # 地板假通过必须红（2.0839e-13←0.0、1e-17←0.0）。
    # 这段坑原来在 docstring 里写了 7 行、断言 0 条，删地板时冒出 5 个假阳性。
    ("freeze.py", ["selftest"], 16),
    # 出稿前的硬门与两个评分器，同样要知道自己有没有被改坏
    ("abstract.py", ["selftest"], 20),
    ("figcheck.py", ["selftest"], 11),
    ("schema.py", ["selftest"], 15),
    # 提案契约 + 试错循环：AGENTS.md 一直标着「未接进主流程」，
    # 实测两条命令都能跑（contract 会拒字段缺失的提案，experiment 能选出最优路线）。
    # 它们同样不在验收链上 —— 补进来（第 98 轮）。
    ("contract.py", ["selftest"], 7),
    ("orchestrate.py", ["selftest"], 30),
    # 计算内核 mm.py：整条流水线最底层，以前**完全没有自检**（第 109 轮补上）
    ("mm_selftest.py", [], 12),
    # 第 111/112 轮：五件事的强制检查 + 分板块红队
    ("chapters.py", ["selftest"], 5),
    # 第 123 轮：7 → 16 → 22 → 24。
    # 16：板数跟着论文走（4/12/20 节三个钉子）；
    # 22：未处理不是关闭（disposition 5 条 + 两个 FAIL 场景）；
    # 24：finding 级处置 + 「没有 disposition 一律 open」两条。
    # 都是**加**断言，原有 7 条全部保留。
    # 第 123 轮：7 → 16 → 22 → 24 → 27 → 28。
    # 27：rejected（驳回）三条；
    # 28：blocked 必须写 falsifier（一句话讲不出「什么会推翻我」就不该被豁免）。
    ("redteam.py", ["selftest"], 28),
    ("untraced.py", ["selftest"], 12),
    ("anchor.py", ["selftest"], 6),
    ("litmcp.py", ["selftest"], 7),
    ("litsearch.py", ["selftest"], 11),
    # 定题这条命令：以前**完全没有自检**（第 106 轮补上）
    ("advise_selftest.py", [], 24),
    # 赛题手册的每条命令都要真能跑（第 108 轮）。
    # 这不是装饰：手册写错一条，开赛当天就浪费半小时。
    # 用字符串形态断言「手册里的命令全部可跑」。
    ("tools/verify_runbook.py", [], "手册里的命令全部可跑"),
    # 第 123 轮：围栏自身的有效性进回归。
    # 「拦住 N/M」不算证据，只有变异测试能证明测试在测围栏而不是测自己抄的副本。
    ("tools/fence_acceptance.py", [], "拦住 11 / 漏检 0 / 误报 0 / 放行 1"),
    ("tools/fence_mutation.py", [], "假测试：0 / 4"),
    ("tools/arch_invariants.py", [], "不成立：0 / 12"),
    # ── 第 123 轮：两类「逃过 gate」的卫生检查进链 ──
    # 1) paper.tex 的 CRLF / 自指量 / 缺 declaration —— 三个都是我踩过的坑，
    #    而且 gate 全都不看（它比的是采集时的数与当时的数，不看换行符）。
    #    实测构造缺陷（CRLF 5 处 + 两个自指量 + 无 declaration）全部被抓，退出码 1。
    ("tools/paper_hygiene.py", ["out/final"], "脏 0"),
    ("tools/paper_hygiene.py", ["out/d2026c"], "脏 0"),
    # 2) \code{} 里含数字的例子：tokenizer 会 blank 掉 \code 参数，numbers 门
    #    查不到。实测事故：写「编号 12 的表行、2019 年的年份」而 heat_sink
    #    根本没有年份列，gate 全绿。这个工具把盲区照亮。
    ("tools/example_audit.py", [], "查不到出处的（含数字）**：0"),
    # 第 124 轮：图的内容检查。figcheck 只看技术规格（DPI/尺寸/矢量），
    # 不打开图看里面画了什么。这个查「图内标题与 caption 说同一句话」与「孤立图」。
    ("tools/fig_visual.py", ["--selftest"], "自校通过：同一句、近句、无关句三类分得开"),
    # 第 124 轮：写后校验。PowerShell 的 heredoc 会把 `a/`t/`b 静默转成
    # BEL/TAB/BS，`> 重定向默认写 UTF-16。这个工具扫控制字符。
    ("tools/check_write.py", ["--selftest"], "自校通过：干净样本放行，TAB/BEL/零宽三类都抓住"),
    # 第 124 轮：两道建模质量门。
    # 外部评审的原话：「插件臂用可检查的等式替代了证明」——
    # 那不是说错，是说 33 道门里没有一道查这件事。门在哪，注意力就在哪。
    ("tools/quality_doors.py", ["selftest"], "自校通过：坏样本两道都拦住，好样本两道都放行"),
    # 第 123 轮：阅卷器的自校。它不是「读当前论文」，而是拿两个**构造出来的**
    # 样本（一个故意坏、一个故意好）验判据本身：
    #   坏样本必须触发否决（实测 6 项），好样本必须零扣分（实测 0）。
    # 任一条不成立 = 判据坏了，当天的阅卷结论都不能信。
    # 阅卷器 grade.py 已封存到工作区之外（它含完整题型指纹，留在这里会泄漏题目）。
    # 解封后把下面这行加回 CORE：
    #   ("tools/grade.py", ["--selftest"], "阅卷器自校通过"),
    # ── 第 100 轮：把「带 selftest 却不在链上」的模块补齐 ──
    # 46 个模块有自检，原来只有 20 个在链上。数字全部现场跑出来的。
    ("patches.py", ["selftest"], 12),
    ("gate.py", ["selftest"], 17),
    ("limit.py", ["selftest"], 10),
    ("score.py", ["selftest"], 7),
    ("review.py", ["selftest"], 17),
    ("innovation.py", ["selftest"], 8),
    ("chk_cross.py", ["selftest"], 4),
    ("rules.py", ["selftest"], 8),
    ("rules_apmcm.py", ["selftest"], 4),
    ("verify_math.py", ["selftest"], 8),
    ("cite.py", ["selftest"], 7),
    ("kind.py", ["selftest"], 7),
    ("kb_loader.py", ["selftest"], 13),
    ("distill.py", ["selftest"], 10),
    ("cards.py", ["selftest"], 19),
    ("aitaste.py", ["selftest"], 12),
    ("dataprof.py", ["selftest"], 14),
    ("pipeline.py", ["selftest"], 7),
    ("plot_mpl.py", ["selftest"], 15),
    ("q4.py", ["selftest"], 13),
    # ── 第 102 轮：把 tools/ 下带 selftest 的 7 个也钉上 ──
    # 它们都打 [PASS] 行、汇总只有 "ALL PASS" 没有 n/n，所以按行数钉。
    # 合计耗时约 1.1 秒，不影响验收时长。
    ("tools/dp.py", ["selftest"], 27),
    ("tools/fit_params.py", ["selftest"], 5),
    ("tools/mip.py", ["selftest"], 13),
    ("tools/net_metrics.py", ["selftest"], 14),
    ("tools/queueing.py", ["selftest"], 16),
    ("tools/stat_tests.py", ["selftest"], 13),
    ("tools/topsis.py", ["selftest"], 5),
    # 图论：Dijkstra / Kruskal / 最大流 / TSP，都拿已知答案对过
    ("graph.py", [], 24),
    # 插件统一入口：算 → 验 → 报告 + 机理 + 预测 + 评价 + 聚类 + 绘图
    ("mmkit.py", ["selftest"], 79),
    # 账本自相矛盾必须让回归变红——这三类 bug 我都靠人眼查过，
    # 工具能查的就不该再靠人
    ("ledger.py", ["audit"], "没有自相矛盾的记录"),
    # 重跑核对：带规格的样本必须对得上当前世界
    ("ledger.py", ["replay"], "全部对得上"),
]

# 对外入口的冒烟测试：必须有输出、必须含关键字段
ENTRY = [
    ("extend.py", ["judge", os.path.join(TESTS, "task_index_demo.json")],
     # 文案在实现里是「机制未查」（更准确：不是不适用，是没查）。
     # 原来这里写「机制不适用」，实现改了测试没跟上，入口检查就一直红。
     ["覆盖率", "最弱一环", "机制未查"]),
]

# 套件：能跑通即可（退出码 0）
SUITE = [
    ("smoke_entry.py", []),
    # 投喂真题：13 条对 APMCM 2026 数据的确定性断言
    ("feed_qb.py", []),
    ("feed_qb2021.py", []),
    ("feed_qb_more.py", []),
    ("collect_l2_real.py", []),
    ("toctou_probe.py", []),
    ("collect_explain.py", []),
    ("case_apmcm_b.py", []),
    # 数模插件：mm.py 是库（mm_smoke 钉计算），mmkit.py 是唯一入口
    # solve_mm_smoke / craft_smoke 已合并进 mmkit_smoke ——
    # 同一件事三条命令，改一处漏两处（这是踩过的）。
    ("mm_smoke.py", []),
    # AHP 与 GM(1,1)：拿教科书里有已知答案的例子对过
    ("methods_smoke.py", []),
    # 灰色关联度 / 模糊综合评价：拿能手算的数字对过
    ("eval_smoke.py", []),
    # 读数据：CSV 支持 / 丢行提示 / 低基数不判异常 / 表头识别
    ("ds_smoke.py", []),
    # 偏相关的显著性：临界值随 n 变，显著 ≠ 重要
    ("stats_smoke.py", []),
    # 变换稳健性：R² 必须报，结论对尺度敏感要抓出来
    ("robust_smoke.py", []),
    # LaTeX 论文：转义 / 术语 / 结构 / 匿名 / lint 能抓真错
    ("paper_smoke.py", []),
    # 解题质量：用 A 题真实附件验时间列 / 准常数列 / 日期可信性
    ("solving_smoke.py", []),
    # 多源读取：12 文件 / 90 sheet / .xls 合并行数与实战记录对齐
    ("multisrc_smoke.py", []),
    # 定题：三题型判对 + 时间列脏值检测
    ("advise_smoke.py", []),
    # 领域层：假设按学科走，公式含无量纲数
    ("domain_smoke.py", []),
    ("mmkit_smoke.py", []),
    ("mcp_smoke.py", []),
    # 10 个领域的公式各自单独编译：只包最小 document，每个 1-2 秒。
    # 完整跑 mmkit --compile 太慢，但公式能不能渲染是最根本的问题
    # （\bigl\|、cases、\mathcal、\tfrac 这些都是易错构造）。
    ("domain_compile.py", []),
    # probe 匹配的精确性：ward/dual 不能被 towards/residual 命中，
    # 词干 probe 又要能匹配 feasible/diagnostics。两个方向都测。
    ("probe_precision.py", []),
    # 核心代码不得跨题借路径，也不得依赖当前工作目录 ——
    # 这个病发作过三次（44/54/55 轮），每次都是静默丢内容。
    ("portability.py", []),
    # 多语言：CJK 总闸只能在英文模式生效。
    # 第 57 轮它把 --lang zh 的中文标题替成 variable。
    ("i18n_gate.py", []),
    # 流水线级（慢）：5 个领域各完整跑一次 --compile，约 3-5 分钟。
    # 默认 SKIP，MM_SLOW=1 开启。与 domain_compile 的分工见该文件头。
    ("domain_pipeline.py", []),
    ("case_1440.py", []),
    ("case_train.py", []),
    ("survey_19.py", []),
    ("self_score.py", []),
    ("arch_score.py", []),
    ("arch_score_after.py", []),
    ("calibrate_procedure.py", []),
    ("case_l3_estacc.py", []),
    ("evaluate_model.py", []),
    ("probe_sargable.py", []),
    ("case_l3_live.py", ["--dry-run"]),
    ("case_l3_limits.py", ["--dry-run"]),
    ("case_l3_more.py", ["--dry-run"]),
    ("case_l3_optimize.py", ["--dry-run"]),
    ("case_l3_explain.py", ["--dry-run"]),
    ("case_unknown.py", ["--dry-run"]),
    ("predict_check.py", ["--dry-run"]),
    ("collect_io.py", ["--dry-run"]),
    ("collect_env.py", ["--dry-run"]),
    ("collect_mechanism.py", ["--dry-run"]),
    ("collect_v2.py", ["--batch", "a", "--dry-run"]),
    ("collect_v2.py", ["--batch", "b", "--dry-run"]),
    ("collect_degrade.py", ["--batch", "a", "--dry-run"]),
    ("collect_degrade.py", ["--batch", "b", "--dry-run"]),
    ("collect_degrade.py", ["--batch", "c", "--dry-run"]),
]


def _why(out: str) -> str:
    """从失败输出里取一条能追查的理由。

    只记 passed 布尔的话，事后只能知道"当时坏过"，无法知道"为什么坏" ——
    实测第 29 轮查 extend.py / kb.py 时，只能确认现在好了，查不出
    昨天 18:24 那次为什么失败。
    """
    lines = [x.strip() for x in str(out).splitlines() if x.strip()]
    for ln in lines:
        if any(k in ln for k in ("FAIL", "Error", "error:", "Traceback",
                                 "assert")):
            return ln[:120]
    return (lines[-1][:120] if lines else "")


def _log_retry(script: str, passed: bool, reason: str = "") -> None:
    import json
    import time
    try:
        rec = {"ts": int(time.time()), "script": script, "passed": passed}
        if reason:
            rec["reason"] = reason
        with open(RETRY_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        # 只加不减会一直长（第 102 轮）：这个文件跨运行累积，
        # 攒几百条以后「最近 6 次」的窗口反而被更早的记录挤掉。
        # 超过上限就保留最后 KEEP 条，重写一次。
        KEEP = 400
        with open(RETRY_LOG, encoding="utf-8") as f:
            rows = [x for x in f.read().splitlines() if x.strip()]
        if len(rows) > KEEP:
            tmp = RETRY_LOG + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                f.write("\n".join(rows[-KEEP:]) + "\n")
            os.replace(tmp, RETRY_LOG)
    except OSError:
        pass          # 记不上不影响回归本身


def retry_summary(limit: int = 6) -> list[tuple[str, int, int]]:
    """最近 limit 次运行里，每个脚本被重试的次数与其中通过的次数。

    一个脚本如果反复出现在这里，说明它的失败是偶发的——
    那它自己就不稳，不该被"重试机制"藏起来。
    """
    import json
    if not os.path.exists(RETRY_LOG):
        return []
    rows = []
    for line in open(RETRY_LOG, encoding="utf-8"):
        line = line.strip()
        if line:
            try:
                rows.append(json.loads(line))
            except ValueError:
                continue
    if not rows:
        return []
    # 只算近期窗口内的重试。日志是 append-only，不清的话一次临时
    # 失败会永久显示「不稳」——实测昨天 18:24 的 4 条失败记录，
    # 13 小时后仍在报，而两个脚本当时跑 selftest 都是通过的。
    _WINDOW = 12 * 3600
    import time as _t
    _now = _t.time()
    rows = [r for r in rows if _now - r.get("ts", 0) < _WINDOW]
    if not rows:
        return []
    # 取最近 limit 次运行：按时间戳分簇
    stamps = sorted({r["ts"] for r in rows}, reverse=True)[:limit]
    recent = [r for r in rows if r["ts"] in stamps]
    agg: dict[str, list[int]] = {}
    reasons: dict[str, str] = {}
    for r in recent:
        a = agg.setdefault(r["script"], [0, 0])
        a[0] += 1
        a[1] += 1 if r.get("passed") else 0
        # 留最近一条失败理由，供报告显示
        if r.get("reason"):
            reasons[r["script"]] = r["reason"]
    out = []
    for k, v in agg.items():
        out.append((k, v[0], v[1], reasons.get(k, "")))
    return sorted(out, key=lambda x: -x[1])


def run_retry(script: str, args: list[str], cwd: str,
              judge) -> tuple[int, str, bool]:
    """跑一次；不达标就再跑一次。返回 (退出码, 输出, 是否重试过)。

    为什么（第七十六轮）：
        本机回归已经三次"随机变红、重跑就绿"——红的是环境不是代码
        （WSL 里 seekdb 被占、DNS 抖、杀毒扫盘）。
        一条查询偶发失败不该把整套判死；但真漂移会连着失败两次。

        重试过会在结果里标出来，不悄悄放过。
    """
    code, out = run(script, args, cwd)
    if judge(code, out) or not RETRY_ONCE:
        return code, out, False
    code2, out2 = run(script, args, cwd)
    # 失败时记下**第一次**的失败理由：重试成功了，第一次为什么红仍然
    # 值得留痕（那正是"这个脚本不稳"的证据）。
    _log_retry(script, judge(code2, out2), _why(out))
    return code2, out2, True


def run(script: str, args: list[str], cwd: str) -> tuple[int, str]:
    # 子进程强制 UTF-8。本机控制台是 GBK，脚本里一打印 ✓ / … 就抛
    # UnicodeEncodeError，回归会莫名其妙全红 —— 而红的是调用者的终端，
    # 不是被检验的代码（第六十九轮踩的）。
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    p = subprocess.run([PY, os.path.join(cwd, script)] + args,
                       capture_output=True, cwd=cwd, timeout=600, env=env)
    out = (p.stdout or b"").decode("utf-8", "replace") + \
          (p.stderr or b"").decode("utf-8", "replace")
    return p.returncode, out


def main() -> int:
    core_only = "--core" in sys.argv
    quiet = "--quiet" in sys.argv
    fails = []

    print("=" * 74)
    print("架构本体")
    print("=" * 74)
    # 第 80 轮：试过在回归期间给 WSL 起常驻进程，想让实例不自动退出。
    # 实测**做不到**，代码已撤，结论记在这里免得下次再试：
    #   · WSL2 实例在最后一个命令后约 20~25 秒终止
    #   · `nohup setsid ... &` 起的后台进程会被带走
    #   · 连 `systemd-run --unit=... sleep infinity`（单元确为 active）
    #     也拦不住回收 —— 回收看的是"有没有 wsl.exe 会话"，不是服务状态
    # 真要消除冷启动，只能改用户级 %UserProfile%\.wslconfig 的
    # vmIdleTimeout，那会影响这台机器上所有项目，不属于本仓库能单方面决定的。
    def _count(out: str) -> int:
        """数断言条数。

        三种情况都要认（第 100/101 轮）：
          · 末尾有 `ALL PASS  n/n` → 用 n（模块**自报**的断言数，最稳定）
          · 否则数 `[PASS]` 行（harness / lanes / gate 这些逐条打点的）
          · 都没有 → 0

        为什么优先自报：`verify_math.py` 会打印 20 条 `[PASS]`，但其中 12 条是
        `report()` 打印的**数据对拍行**，不是自检断言；它自报 8/8 才是真数。
        按 `[PASS]` 行数钉会把演示输出也算进去，数据一变钉数就漂。
        """
        m = re.search(r"(?:ALL PASS|FAILED)\s+(\d+)/(\d+)", out)
        if m:
            return int(m.group(2))
        return out.count("[PASS]")

    for script, args, want in CORE:
        def _judge(code, out, want=want):
            if isinstance(want, str):
                return code == 0 and want in out
            return code == 0 and _count(out) == want

        code, out, retried = run_retry(script, args, ROOT, _judge)
        if isinstance(want, str):
            ok = code == 0 and want in out
            shown = want
        else:
            got = _count(out)
            ok = code == 0 and got == want
            shown = f"{got}/{want} 断言"
        if not quiet or not ok:
            print(f"  {'OK  ' if ok else 'FAIL'} {script:<18} {shown}"
                  + ("  (重试过一次)" if retried else "")
                  + ("" if ok else f"  (退出码 {code})"))
        if not ok:
            fails.append(f"{script} {shown}")
            if not quiet:
                for line in out.splitlines():
                    if "FAIL" in line:
                        print("       " + line.strip())

    if not core_only:
        print()
        print("=" * 74)
        print(f"对外入口（{len(ENTRY)} 个）")
        print("=" * 74)
        for script, args, must in ENTRY:
            code, out = run(script, args, ROOT)
            missing = [m for m in must if m not in out]
            ok = code == 0 and not missing
            if not quiet or not ok:
                print(f"  {'OK  ' if ok else 'FAIL'} {script:<18}"
                      + ("" if ok else f"  缺 {missing}"))
            if not ok:
                fails.append(f"{script} 入口缺 {missing}")

        print()
        print("=" * 74)
        print(f"回归套件（{len(SUITE)} 个）")
        print("=" * 74)
        for script, args in SUITE:
            code, out = run(script, args, TESTS)
            ok = code == 0
            if not quiet or not ok:
                tag = " ".join(args) if args else ""
                print(f"  {'OK  ' if ok else 'FAIL'} {script:<22}{tag}")
            if not ok:
                fails.append(f"{script} {args}")
                if not quiet:
                    for line in out.splitlines()[-6:]:
                        print("       " + line.strip())

    # 重试情况必须露出来：靠重试才过的东西，是它自己不稳，不是"没事"。
    rs = retry_summary()
    chronic = [r for r in rs if r[1] >= 2]
    if rs:
        print()
        print("=" * 74)
        print("重试情况（最近 6 次运行）")
        print("=" * 74)
        for row in rs:
            script, n, ok = row[0], row[1], row[2]
            why = row[3] if len(row) > 3 else ""
            flag = "  ← 反复重试，本身不稳" if n >= 2 else ""
            # 强调是**历史**：这是跨运行的追加日志，不是本次结论。
            # 实测一次钉数写错留下「重试 1 次，其中通过 0 次」，
            # 而底部明明写着 ALL PASS —— 两句话看起来互相矛盾（第 101 轮）。
            print(f"  {script:<24} 历史上重试 {n} 次（通过 {ok} 次，"
                  f"非本次结论）{flag}")
            if why:
                print(f"      最近一次失败：{why}")
        if chronic:
            print()
            print(f"  **有 {len(chronic)} 项在多次运行里反复重试** —— "
                  f"它们不该靠重试过关，该查为什么不稳")

    print()
    print("=" * 74)
    if fails:
        print(f"FAILED: {len(fails)} 项")
        for f in fails:
            print("  -", f)
    else:
        print("ALL PASS")
    print("=" * 74)
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(main())
