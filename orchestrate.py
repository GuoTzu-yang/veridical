#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
orchestrate.py —— 编排循环（P08，第 4 轮）

它解决什么
----------
在这之前，所有零件都是「单次」的：
    schema.py    告诉 LLM 能调什么
    contract.py  检查提案合不合规
    mmkit.py     算一次
    verify.py    查数字有没有出处
    lanes.py     验结论方向对不对
    rules.py     查论文违不违规

**没有东西把它们串成「试错」**。而试错是质量来源：
OpenAI 4000 题 → 722 篇（5.5 次/篇），Rethlas 方案 A/B/C 失败才到 D。

设计原则
--------
1. **插件不调模型**。propose / judge 是外部注入的回调。
   好处：能独立自测（mock），能换任意模型，不依赖宿主配置。
2. **预算不是 520 轮，是 5 轮**。
   按几何分布，p₀α=0.45 时 5 轮命中 95%，10 轮 99.7%，50 轮 ~100%。
   从 5 到 50 只多 5 个点，成本涨 10 倍。t* = 5。
3. **失败隔离**。失败只留一句教训进死路表，不把完整日志塞回上下文。
   这是 Archon 的教训：「自己失败的尝试会侵蚀坚持的意愿」。
4. **过思考监控**。同一路线的判定在多轮间反复变 = 结论不稳，该停。
   这是 2604.10739 的「答案振荡」信号（相关性 0.78）。

流程
----
    context = build_context()          # schema 摘要 + 数据摘要 + 死路表
    for round in 1..max_rounds:
        props   = propose(context)     # ← 外部
        valid   = contract 校验 + 不同构检查
        results = exec(valid)          # ← 调 mmkit
        verdict = judge(results)       # ← 外部
        if 收敛 / 振荡 / 预算耗尽: break
        context = 压缩(教训，不塞全文)

用法
    python orchestrate.py selftest           # 用 mock 自测
    python orchestrate.py demo --data X      # 用真实数据跑一轮骨架
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


# ══════════════════════════════════════════════════════════════════════
#  状态
# ══════════════════════════════════════════════════════════════════════
@dataclass
class Attempt:
    """一次尝试的全部记录。"""
    rnd: int
    route_id: str
    method: str
    args: dict
    ok: bool = False
    metrics: dict = field(default_factory=dict)
    error: str = ""
    elapsed_s: float = 0.0
    verdict: str = ""          # pass / fail / unknown

    def brief(self) -> str:
        m = ", ".join(f"{k}={v}" for k, v in list(self.metrics.items())[:3])
        return (f"R{self.rnd} {self.route_id} {self.method} "
                f"{'OK' if self.ok else 'FAIL'}{(' ' + m) if m else ''}")


@dataclass
class LoopState:
    """循环状态。一切都在这里，便于落盘和回放。"""
    attempts: list = field(default_factory=list)
    dead_ends: list = field(default_factory=list)   # 只存教训，不存全文
    rounds_used: int = 0
    minutes_used: float = 0.0
    best: dict = field(default_factory=dict)
    stop_reason: str = ""

    def dead_summary(self, limit: int = 8) -> list[str]:
        """给 LLM 看的死路摘要。一句话一条，绝不塞日志。"""
        return [f"{d['route_id']}: {d['lesson']}"
                for d in self.dead_ends[-limit:]]


# ══════════════════════════════════════════════════════════════════════
#  上下文构建（这是「不浪费已有零件」的地方）
# ══════════════════════════════════════════════════════════════════════
def build_context(data: str, state: LoopState, budget_min: float,
                  max_rounds: int) -> dict:
    """每一轮开头给 propose 的东西。

    刻意做成 dict（不是长文本）——让 propose 的实现方自己决定怎么序列化。
    """
    ctx = dict(
        data=data,
        round=state.rounds_used + 1,
        max_rounds=max_rounds,
        budget_min=budget_min,
        minutes_used=round(state.minutes_used, 1),
        dead_ends=state.dead_summary(),
        best_so_far=state.best.get("brief", ""),
    )
    # 挂上能力清单（摘要，不是 26KB 全文）
    try:
        import schema as _schema
        sc = _schema.build()
        ctx["commands"] = {
            name: sorted(spec.get("args") or {})
            for name, spec in sc["commands"].items()
        }
        ctx["metrics"] = sorted(sc["metrics"])
    except Exception:                               # noqa: BLE001
        ctx["commands"] = {}
        ctx["metrics"] = []
    # ── 数据摘要（关键）──
    # 不给列名，propose 只能猜；猜错就是 KeyError（实测 B 路线因此崩）。
    try:
        import mm
        ds = mm.DS(data)
        ctx["n_rows"] = ds.n_rows
        ctx["columns"] = list(ds.num_names)
        # 数值列里最后一个通常是目标，但别替它决定，只标出来
        ctx["column_note"] = ("这些是可用的数值列名；method_args 里的 "
                              "--y/--x 必须逐字用它们")
    except Exception as e:                          # noqa: BLE001
        ctx["n_rows"] = 0
        ctx["columns"] = []
        ctx["column_note"] = f"读不出数据：{type(e).__name__}"

    # 挂上硬约束（不变量里能自动查的那几条）
    try:
        import kb_loader
        ctx["invariants"] = [i["claim"] for i in
                             kb_loader.load_invariants()][:10]
    except Exception:                               # noqa: BLE001
        ctx["invariants"] = []
    return ctx


# ══════════════════════════════════════════════════════════════════════
#  执行
# ══════════════════════════════════════════════════════════════════════
def _fail_kind(err) -> str:
    """给**执行失败**归个类，写进死路表的教训里。

    只在 `a.ok == False`（进程失败 / 非零退出 / 超时）时调用 ——
    也就是说这里处理的**全是技术性失败**：判据没过的路线根本走不到这里
    （质量由第 ④ 步的 verdict 判）。

    原来兜底返回「质量不达标」，那是个范畴错误：执行失败按定义不是质量结论。
    实测 `json.decoder.JSONDecodeError: Expecting value` 这类不匹配任何关键词的
    错误，就被标成「质量不达标」，读死路表的人会以为路线被判据否掉了，
    实际是它根本没跑起来（第 105 轮）。

    → 认识的关键词归「技术故障」；认不出的老实写「未识别故障」，不冒充质量结论。
    """
    e = str(err or "").lower()
    # 词表必须覆盖**这个插件自己吐出来的错误文本**，否则分类就是摆设：
    # 实测三条真实失败（不存在的命令 / 缺 --x / 数据文件找不到）原本全部落到
    # 兜底，一条都没被认出来（第 105 轮）。
    for k in ("keyerror", "typeerror", "valueerror", "argument", "参数",
              "timeout", "超时", "filenotfound", "no such file",
              "traceback", "attributeerror", "indexerror", "jsondecodeerror",
              "expecting value", "nonzero", "退出码", "returncode",
              "modulenotfound", "permissionerror", "oserror",
              # argparse / 插件自己的措辞
              "usage:", "invalid choice", "error:", "unrecognized",
              "需要", "缺少", "未提供", "必需",
              # 输入缺失
              "找不到数据", "没有这个", "不存在", "未找到", "not found",
              "missing", "required"):
        if k in e:
            return "技术故障"
    return "未识别故障"


def exec_one(route: dict, timeout_s: int = 120) -> Attempt:
    """把一条提案映射成 mmkit 命令并执行。

    这是「契约」的兑现处：提案里的 method + method_args 直接变成 argv。
    """
    t0 = time.time()
    method = str(route.get("method") or "")
    margs = route.get("method_args") or {}
    argv = [sys.executable, "mmkit.py"]
    if method and method != "run":
        argv.append(method)
    for k, v in margs.items():
        kk = str(k)
        if not kk.startswith("-"):
            kk = "--" + kk.lstrip("-")
        if isinstance(v, bool):
            if v:
                argv.append(kk)
        elif v is None or v == "":
            continue
        else:
            argv += [kk, str(v)]
    argv.append("--json")

    a = Attempt(rnd=0, route_id=str(route.get("route_id") or "?"),
                method=method, args=dict(margs))
    try:
        r = subprocess.run(argv, capture_output=True, text=True,
                           encoding="utf-8", errors="replace",
                           cwd=HERE, timeout=timeout_s)
        a.elapsed_s = round(time.time() - t0, 2)
        a.ok = r.returncode == 0
        out = (r.stdout or "").strip()
        # 尽量从输出里挖 json；挖不到就留 stderr 的第一句
        m = None
        if out.startswith("{"):
            try:
                m = json.loads(out)
            except json.JSONDecodeError:
                m = None
        if m is None:
            for line in reversed(out.splitlines()):
                if line.strip().startswith("{"):
                    try:
                        m = json.loads(line.strip())
                        break
                    except json.JSONDecodeError:
                        continue
        a.metrics = _flatten_metrics(m) if m else {}
        if not a.ok:
            a.error = ((r.stderr or out).strip().splitlines() or ["?"])[0][:120]
    except subprocess.TimeoutExpired:
        a.elapsed_s = round(time.time() - t0, 2)
        a.error = f"超时 {timeout_s}s"
    except Exception as e:                          # noqa: BLE001
        a.error = f"{type(e).__name__}: {e}"
    return a


def _flatten_metrics(m) -> dict:
    """从 mmkit 的 json 输出里抠出判据要用的数。"""
    out = {}

    def walk(o, prefix=""):
        if isinstance(o, dict):
            for k, v in o.items():
                walk(v, f"{prefix}{k}.")
        elif isinstance(o, (int, float)) and not isinstance(o, bool):
            out[prefix.rstrip(".")] = o

    walk(m)
    # 只留判据可能用到的那些，别把整个 json 塞进上下文
    keep = ("cv_rmse", "r2", "front", "bp", "coverage", "n_rows",
            "rmse", "aic")
    return {k: v for k, v in out.items()
            if any(x in k.lower() for x in keep)}


# ══════════════════════════════════════════════════════════════════════
#  判据（外部判 vs 内置兜底）
# ══════════════════════════════════════════════════════════════════════
def _pick_metric(metrics: dict, needle: str):
    """在扁平化后的 metrics 里按子串找第一个数值。找不到返回 None。"""
    for k, v in (metrics or {}).items():
        if needle in str(k).lower():
            try:
                return float(v)
            except (TypeError, ValueError):
                continue
    return None


def default_judge(results: list, rounds_history: list) -> dict:
    """兜底判据：按提案自带的 success_criteria 检查。

    外部 judge 没提供时用它。它不是「好」的判据，只是「不比没有强」——
    真正的判据应该由外部（人 / 另一个 agent）给，或者由
    lanes.py 的方向验证来给。这一条写在这里，是为了让缺口可见。
    """
    out = {}
    for r, a in results:
        crit = (r.get("success_criteria") or {})
        if not a.ok:
            out[a.route_id] = "fail"
            continue
        # 没有判据时**不许判 pass**（第 98 轮）。
        # 原来 crit 为空 → 下面的循环一次都不跑 → ok 恒为 True →
        # 每条路线都「达标」。实测 `mmkit.py experiment --rounds 1` 打印
        # 「第 1 轮达标且是最优」，而实际上什么也没检查。
        #
        # 内建一条不含人为阈值的判据：交叉验证误差要打得过均值基线
        # （仓库的老规矩：打不过 baseline_rmse 等于没建模）。
        # 拿不到这两个数就判 unknown —— 不确定就说不确定，不冒充通过。
        if not crit:
            _best = _pick_metric(a.metrics, "best_rmse")
            _base = _pick_metric(a.metrics, "baseline_rmse")
            if _best is None or _base is None or _base <= 0:
                out[a.route_id] = "unknown"
            else:
                out[a.route_id] = "pass" if _best < _base else "fail"
            continue
        ok = True
        _missing = []
        for name, target in crit.items():
            # "cv_rmse_max" → 核心词 "rmse"（不是 "cv_rmse"）
            # 因为 mmkit 输出的 key 是 fit.best_rmse，不含 cv_ 前缀。
            # 用后缀当核心词，再做包含匹配。
            key = str(name)
            core = key
            for suf in ("_max", "_min"):
                if core.endswith(suf):
                    core = core[:-len(suf)]
            # 拆词，取最有辨识度的一截
            parts = [p for p in core.split("_") if p]
            cand = [p for p in parts
                    if p in ("rmse", "r2", "front", "bp", "coverage",
                             "n_rows", "aic")]
            core = cand[0] if cand else (parts[-1] if parts else core)
            val = None
            for k, v in a.metrics.items():
                if core in k.lower():
                    val = v
                    break
            if val is None:
                # 判据点名了一个这条路线**没有报告**的指标（第 104 轮）。
                # 原来直接判 fail —— 但「查不到」不是「没通过」，那又是一次
                # 把不知道说成知道。实测 A 写了 n_rows_min=1，而 run 路线只
                # 报 fit.best_rmse，于是它被判 fail，理由却是自己没输出 n_rows。
                # 记下来，最后判 unknown。
                _missing.append(str(name))
                continue
            try:
                tgt = float(target)
            except (TypeError, ValueError):
                continue
            if name.endswith("_max") and val > tgt:
                ok = False
            elif name.endswith("_min") and val < tgt:
                ok = False
        # 声明的判据之外，再压一条仓库自己的规矩（第 98 轮）：
        # 交叉验证误差打不过均值基线，等于没建模。
        #
        # 为什么必须加：内建提案的判据是故意写成恒真的
        # （cv_rmse_max: 1e9 / n_rows_min: 1，注释说「只表达算出了有效数值」），
        # 于是任何路线都「达标」，而输出写的是「达标且是最优」—— 读起来像质量结论。
        # 只要同时拿到 best_rmse 与 baseline_rmse，就要求 best < baseline；
        # 拿不到就不额外施加条件（不是所有路线都拟合模型）。
        if ok:
            _best = _pick_metric(a.metrics, "best_rmse")
            _base = _pick_metric(a.metrics, "baseline_rmse")
            if _best is not None and _base is not None and _base > 0:
                ok = _best < _base
        if not ok:
            out[a.route_id] = "fail"
        elif _missing:
            # 判据里点名的指标没被这条路线报告 → 无法判定，判 unknown。
            # 不判 pass（没验证过），也不判 fail（没证伪）。
            out[a.route_id] = "unknown"
        else:
            out[a.route_id] = "pass"
    return out


# ══════════════════════════════════════════════════════════════════════
#  主循环
# ══════════════════════════════════════════════════════════════════════
def run_loop(data: str, propose, judge=None, max_rounds: int = 5,
             routes_per_round: int = 3, budget_min: float = 45.0,
             max_minutes_per_round: float = 10.0) -> LoopState:
    """提案 → 执行 → 判断 → 下一轮。

    propose(ctx) -> list[proposal]
    judge(results, history) -> {route_id: "pass"/"fail"/"unknown"}
    """
    import contract

    st = LoopState()
    judge = judge or default_judge
    cmds, argn = contract.reflect_cmds()
    best_verdicts: list = []

    for rnd in range(1, max_rounds + 1):
        st.rounds_used = rnd
        ctx = build_context(data, st, budget_min, max_rounds)

        # ── ① 提案 ──
        try:
            props = propose(ctx) or []
        except Exception as e:                      # noqa: BLE001
            st.stop_reason = f"propose 异常：{type(e).__name__}: {e}"
            break
        props = list(props)[:routes_per_round]
        if not props:
            st.stop_reason = "提案为空"
            break

        # ── ② 校验（不浪费已有零件：直接用 contract）──
        batch = contract.validate_batch(props, cmds, argn)
        good = []
        for p in props:
            rid = str(p.get("route_id") or "?")
            errs = (batch["per_route_errors"] or {}).get(rid)
            if errs:
                st.dead_ends.append(dict(
                    route_id=rid, round=rnd,
                    lesson=f"提案不合规：{errs[0][:60]}"))
                continue
            good.append(p)
        if batch["batch_errors"]:
            st.dead_ends.append(dict(
                route_id="*", round=rnd,
                lesson=f"整批不合规：{batch['batch_errors'][0][:70]}"))
        if not good:
            continue

        # ── ③ 执行 ──
        results = []
        for p in good:
            a = exec_one(p)
            a.rnd = rnd
            st.attempts.append(a)
            st.minutes_used += a.elapsed_s / 60.0
            results.append((p, a))
            if not a.ok:
                # 执行失败 ≠ 质量不达标（借 mcmp 的区分）。
                # KeyError / 参数错 是**技术故障**，该重试或修参数；
                # RMSE 不达标才是路线问题，该换路线。
                # 原来两类都塞进死路表，导致「路线被误杀」。
                a.fail_kind = _fail_kind(a.error)
                st.dead_ends.append(dict(
                    route_id=a.route_id, round=rnd,
                    kind=a.fail_kind,
                    lesson=(f"[{a.fail_kind}] {a.method}："
                            f"{a.error[:56]}")))

        # ── ④ 判断 ──
        try:
            verdicts = judge(results, st.attempts) or {}
        except Exception as e:                      # noqa: BLE001
            st.stop_reason = f"judge 异常：{type(e).__name__}: {e}"
            break
        for p, a in results:
            a.verdict = str(verdicts.get(a.route_id) or "unknown")
            if a.verdict == "fail" and a.ok:
                st.dead_ends.append(dict(
                    route_id=a.route_id, round=rnd,
                    lesson=f"未达判据（{a.metrics or '无指标'}）"))

        # ── ⑤ 收敛 / 振荡 / 预算 ──
        passed = [a for _, a in results if a.verdict == "pass"]
        for a in passed:
            if not st.best or _better(a, st.best):
                st.best = dict(route_id=a.route_id, brief=a.brief(),
                               metrics=a.metrics, round=rnd)

        best_verdicts.append(
            max((a.verdict for _, a in results),
                key=lambda v: {"pass": 2, "unknown": 1, "fail": 0}[v]
                if v in ("pass", "fail", "unknown") else 0))

        # 停止不能看「有一条达标」——实测 C 的判据 n_rows_min=1
        # 几乎必然通过，一轮就把循环停了，等于没探索。
        # 要求：达标的那条必须是**当前最优**（按 _better 比较），
        # 否则只能算「低标准通过」，不进结论。
        if passed:
            strong = [a for a in passed if not st.best
                      or _better(a, st.best) or st.best["route_id"] == a.route_id]
            weak = [a for a in passed if a not in strong]
            if strong:
                # 措辞要准（第 99 轮）：这里只说明「过了判据且是当前最优」，
                # 不说明「质量好」。内建提案的判据本来就可能很松
                # （cv_rmse_max: 1e9），所以不能写成「达标」——
                # 那读起来像质量结论，而它只是一次筛选。
                st.stop_reason = (
                    f"第 {rnd} 轮有路线过判据且为当前最优"
                    f"（{', '.join(a.route_id for a in strong)}）；"
                    f"判据来自提案，不代表质量结论")
                break
            if weak:
                st.dead_ends.append(dict(
                    route_id=",".join(a.route_id for a in weak),
                    round=rnd,
                    lesson="判据过松（过判据但不是最优），继续探索"))
        if _oscillating(best_verdicts):
            st.stop_reason = ("结论在多轮间反复变 —— 过思考信号，停止"
                              "（2604.10739：答案振荡与负翻转相关 0.78）")
            break
        if st.minutes_used >= budget_min:
            st.stop_reason = f"预算耗尽（{st.minutes_used:.1f} / {budget_min} min）"
            break

    if not st.stop_reason:
        st.stop_reason = f"跑满 {max_rounds} 轮，没有路线过判据"
    return st


def _better(a: Attempt, best: dict) -> bool:
    """比较两条尝试谁更好：**帕累托支配**，不是「先命中先赢」。

    只在双方都有的指标上比（不同量纲不能比大小 —— 第一版「新指标名就算更好」
    让只有 n_rows=84 的诊断路线把 rmse=0.0074 的建模路线挤成第二）。

    第 103 轮改了两处：

    ① 方向表不再只认 rmse / r2。原来越界词之外的共同指标（aic、coverage…）
       一律不算，于是两条只共享 aic 的路线永远「不可比」，先跑的自动成为最优。
    ② 不再「命中即返回 True」。原来遍历共享指标，撞上一个更好的就判更好 ——
       A 的 rmse 更好、r2 更差时，结论取决于 dict 的遍历顺序。
       改成帕累托支配：**所有可比指标都不差，且至少一项严格更好**。

    方向不明的指标直接跳过（不知道越小越好还是越大越好，就不拿它比），
    这一条写在这里，免得以后有人凭名字猜方向。
    """
    cur = best.get("metrics") or {}
    # 越小越好 / 越大越好。
    # 注意：这里只能放**度量语义**，不能放命名空间前缀。
    # 第一版我把 "resid" 放进 LOWER，而 `resid.r2_structure` 同时含 "r2" 与
    # "resid" —— 按 LOWER 先判就把它当成「越小越好」，方向整个反了。
    LOWER = ("rmse", "mse", "mae", "error", "aic", "bic", "gap")
    HIGHER = ("r2", "coverage", "accuracy", "precision", "recall",
              "score", "f1", "auc")

    def _dir(k):
        low = k.lower()
        # 先判 HIGHER：`resid.r2_structure` 这类带命名空间的名字里，
        # 真正决定方向的是 "r2"，不是前缀。
        if any(t in low for t in HIGHER):
            return +1
        if any(t in low for t in LOWER):
            return -1
        return 0

    worse = False
    strictly = False
    for k in set(a.metrics) & set(cur):
        d = _dir(k)
        if not d:
            continue                      # 方向不明，不参与比较
        try:
            v, old = float(a.metrics[k]), float(cur[k])
        except (TypeError, ValueError):
            continue
        if d < 0:
            if v > old:
                worse = True
            elif v < old:
                strictly = True
        else:
            if v < old:
                worse = True
            elif v > old:
                strictly = True
    return strictly and not worse


def _oscillating(seq: list, window: int = 3) -> bool:
    """判定序列在窗口内反复变 = 振荡。

    判据：窗口内出现 ≥2 种判定就算不稳。
    **不要**加「首尾必须不同」——fail → pass → fail 首尾相同，
    但中间变了，那恰恰是振荡的典型形状（放弃对的、又回到错的）。
    第一版就是因为这个条件漏判了。
    """
    if len(seq) < window:
        return False
    tail = seq[-window:]
    return len(set(tail)) >= 2


# ══════════════════════════════════════════════════════════════════════
#  报告
# ══════════════════════════════════════════════════════════════════════
def report(st: LoopState) -> str:
    L = []
    L.append(f"编排结果：{st.rounds_used} 轮 / "
             f"{len(st.attempts)} 次尝试 / "
             f"{st.minutes_used:.2f} min")
    L.append(f"停止原因：{st.stop_reason}")
    L.append("")
    L.append(f"  {'轮':<4}{'路线':<8}{'方法':<12}{'结果':<8}{'判定':<8}指标")
    for a in st.attempts:
        m = ", ".join(f"{k}={v:.4g}" for k, v in list(a.metrics.items())[:2])
        L.append(f"  R{a.rnd:<3}{a.route_id[:7]:<8}{a.method[:11]:<12}"
                 f"{'OK' if a.ok else 'FAIL':<8}{a.verdict:<8}{m}")
    if st.best:
        L.append("")
        L.append(f"  最优：{st.best.get('brief', '')}")
    if st.dead_ends:
        L.append("")
        L.append(f"  死路 {len(st.dead_ends)} 条（只留教训，不留日志）：")
        for d in st.dead_ends[:6]:
            L.append(f"    R{d['round']} {d['route_id']}: {d['lesson'][:64]}")
        # 沉淀：把死路写成条件句教训，追加到 kb/invariants.json。
        # 只打印不写回的话，下次换个任务同样的失败会再发生一次。
        try:
            import distill as _ds
            _r = _ds.run(st.dead_ends)
            if _r.get("added"):
                L.append(f"    已沉淀 {_r['added']} 条教训 → "
                         f"kb/invariants.json（库内 {_r['total']} 条）")
        except Exception as _e:                     # noqa: BLE001
            L.append(f"    沉淀失败：{type(_e).__name__}")
    return "\n".join(L)


# ══════════════════════════════════════════════════════════════════════
#  自测（用 mock，不需要真实数据）
# ══════════════════════════════════════════════════════════════════════
def selftest() -> int:
    bad = 0
    n = 0

    def ck(name, cond, detail=""):
        nonlocal bad, n
        n += 1
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}"
              + (f"  — {detail}" if detail else ""))
        if not cond:
            bad += 1

    # ── 上下文 ──
    ctx = build_context("x.csv", LoopState(), 45.0, 5)
    ck("上下文含能力清单", bool(ctx.get("commands")),
       f"{len(ctx['commands'])} 个命令")
    ck("上下文含指标名", bool(ctx.get("metrics")),
       str(ctx["metrics"][:3]))
    ck("上下文含不变量", bool(ctx.get("invariants")),
       f"{len(ctx.get('invariants') or [])} 条")
    ck("上下文有轮次信息", ctx["round"] == 1)

    # ── 指标扁平化 ──
    fm = _flatten_metrics({"fit": {"cv_rmse": 0.0074, "r2": 0.59},
                           "junk": "字符串不该进"})
    ck("扁平化只留判据用的数", "fit.cv_rmse" in fm and len(fm) == 2, str(fm))

    # ── 振荡检测 ──
    ck("平稳定序列不报振荡", not _oscillating(["pass", "pass", "pass"]))
    ck("反复变报振荡", _oscillating(["fail", "pass", "fail"]))
    ck("不足窗口不报振荡", not _oscillating(["fail", "pass"]))

    # ── 主循环：提案全不合规 → 全进死路，不执行 ──
    def bad_propose(ctx):
        return [dict(route_id="A", title="t", method="不存在的命令",
                     method_args={}, success_criteria={},
                     falsifiable_assumption="若无关则 r≈0")]

    st = run_loop("x.csv", bad_propose, max_rounds=2)
    ck("非法提案被挡住", len(st.attempts) == 0, f"{len(st.attempts)} 次执行")
    ck("非法提案进死路表", any("不合规" in d["lesson"]
                          for d in st.dead_ends),
       str([d["lesson"][:30] for d in st.dead_ends[:2]]))

    # ── 主循环：合法提案 + 达标 → 第一轮就停 ──
    calls = {"n": 0}

    def good_propose(ctx):
        calls["n"] += 1
        # 必须 3 条且不同构 —— check_diversity 会挡住「三个变体冒充三条路线」
        return [
            dict(route_id="A", title="t1", method="selftest",
                 method_args={},
                 success_criteria={"n_rows_min": 1},
                 falsifiable_assumption="若无关则 r≈0"),
            dict(route_id="B", title="t2", method="advise",
                 method_args={},
                 success_criteria={"n_rows_min": 1},
                 falsifiable_assumption="若题型判错则链路失败"),
            dict(route_id="C", title="t3", method="hints",
                 method_args={},
                 success_criteria={"n_rows_min": 1},
                 falsifiable_assumption="若无建议则无事可做"),
        ]

    st2 = run_loop("x.csv", good_propose, max_rounds=3)
    ck("合法提案被执行", len(st2.attempts) >= 1, f"{len(st2.attempts)} 次")
    ck("最多跑 max_rounds 轮", st2.rounds_used <= 3)
    ck("有停止原因", bool(st2.stop_reason), st2.stop_reason[:50])

    # ── 死路摘要不塞全文 ──
    st3 = LoopState(dead_ends=[
        dict(route_id="A", round=1, lesson="x" * 200)])
    ds = st3.dead_summary()
    ck("死路摘要只留教训字段", ds and "A:" in ds[0] and len(ds[0]) < 260)

    # ── 空提案 → 停 ──
    st4 = run_loop("x.csv", lambda c: [], max_rounds=3)
    ck("空提案立即停", st4.rounds_used == 1 and "空" in st4.stop_reason,
       st4.stop_reason)

    # ── 判据不许恒真（第 98 轮）──
    # 内建提案故意用 cv_rmse_max=1e9 这种恒真判据（「只表达算出了有效数值」），
    # 于是每条路线都 pass。这里钉住两条：空判据不许 pass；
    # 打得过均值基线才算 pass。
    def _att(rid, metrics, crit=None):
        r = dict(route_id=rid, success_criteria=crit or {})
        a = Attempt(rnd=0, route_id=rid, method="run", args={})
        a.ok = True
        a.metrics = dict(metrics)
        return r, a

    r_a, a_a = _att("A", dict(fit_best_rmse=0.5, fit_baseline_rmse=1.0))
    ck("空判据但优于基线 → pass",
       default_judge([(r_a, a_a)], [])["A"] == "pass")
    r_b, a_b = _att("B", dict(fit_best_rmse=2.0, fit_baseline_rmse=1.0))
    ck("空判据且劣于基线 → fail",
       default_judge([(r_b, a_b)], [])["B"] == "fail")
    r_c, a_c = _att("C", {})
    ck("空判据且无指标 → unknown（不冒充通过）",
       default_judge([(r_c, a_c)], [])["C"] == "unknown")
    # 声明了恒真判据，但劣于基线 → 仍要 fail（声明判据不能豁免基线）
    r_d, a_d = _att("D", dict(fit_best_rmse=9.0, fit_baseline_rmse=1.0),
                    {"cv_rmse_max": 1e9})
    ck("恒真判据 + 劣于基线 → fail",
       default_judge([(r_d, a_d)], [])["D"] == "fail")

    # ── 比较规则：帕累托支配，不是「先命中先赢」（第 103 轮）──
    class _A:
        def __init__(self, m):
            self.metrics = m

    def _b(m, best):
        return _better(_A(m), {"metrics": best})

    ck("resid.r2_structure 更高才算更好（方向别反）",
       _b({"resid.r2_structure": 0.8}, {"resid.r2_structure": 0.3})
       and not _b({"resid.r2_structure": 0.2},
                  {"resid.r2_structure": 0.8}))
    ck("rmse 更好但 r2 更差 → 不算更好（不许先命中先赢）",
       not _b({"fit.best_rmse": 0.01, "resid.r2_structure": 0.2},
              {"fit.best_rmse": 0.02, "resid.r2_structure": 0.9}))
    ck("全相等 → 不算更好（无严格改进）",
       not _b({"fit.best_rmse": 0.01}, {"fit.best_rmse": 0.01}))
    ck("只共享 aic 也能比（越大越好的词之外不再漏）",
       _b({"aic": 10}, {"aic": 20}))
    ck("方向不明的指标被跳过，不凭名字猜",
       not _b({"神秘指标": 1}, {"神秘指标": 99}))

    # ── 判据点名了没报告的指标 → unknown，不是 fail（第 104 轮）──
    r_e, a_e = _att("E", dict(fit_best_rmse=0.5, fit_baseline_rmse=1.0),
                    {"n_rows_min": 1})
    ck("判据的指标没报告 → unknown（查不到 ≠ 没通过）",
       default_judge([(r_e, a_e)], [])["E"] == "unknown")
    # 明确违反的判据仍然判 fail，不能被 unknown 掩盖
    r_f, a_f = _att("F", dict(fit_best_rmse=9.0, fit_baseline_rmse=1.0),
                    {"n_rows_min": 1, "cv_rmse_max": 0.1})
    ck("有指标明确违反时仍判 fail（不被 unknown 掩盖）",
       default_judge([(r_f, a_f)], [])["F"] == "fail")

    # ── 执行失败的分类：词表要认识插件自己的措辞（第 105 轮）──
    ck("argparse 的 usage 文本算技术故障",
       _fail_kind("usage: mmkit.py [-h] ... invalid choice") == "技术故障")
    ck("插件自己的参数错（「需要 --x」）算技术故障",
       _fail_kind("solve 需要 --x 和 --obj（或 --y）") == "技术故障")
    ck("数据缺失（「找不到数据」）算技术故障",
       _fail_kind("找不到数据：'x.xlsx'；用 --data 指定") == "技术故障")
    ck("认不出的错误不冒充质量结论", _fail_kind("什么也没说") == "未识别故障")

    print(f"\n{'ALL PASS' if bad == 0 else 'FAILED'}  {n - bad}/{n}")
    return 0 if bad == 0 else 1


def rule_propose(ctx: dict) -> list:
    """规则版 propose：不需要 LLM 也能跑起来。

    demo 里那个 _propose 把 --y/--x 硬编码成 demo 数据的列名，
    换个数据集就 KeyError；而且只提 1 条，过不了
    「至少 3 条」的批量校验（实测 5 轮全 FAIL）。

    这一版从 ctx["columns"] 读真实列名，按能力清单生成三条互不相同的
    路线：赛马 / 基线出稿 / 优化。LLM 想接管时，写 --propose-json
    给出自己的提案即可，本函数不参与。
    """
    cols = [str(c) for c in (ctx.get("columns") or [])]
    data = ctx.get("data") or ""
    cmds = ctx.get("commands") or {}
    # 调用方（比如手工构造 ctx 的测试）可能没带能力清单；
    # 这里自己补一份，免得整条 propose 静默返回 0 条。
    if not cmds:
        try:
            import schema as _sc
            cmds = _sc.build()["commands"]
        except Exception:                       # noqa: BLE001
            cmds = {}
    # 列名同理：没带就从数据里读
    if not cols and data:
        try:
            import mm as _mm
            cols = list(_mm.DS(data).num_names)
        except Exception:                       # noqa: BLE001
            cols = []
    if len(cols) < 2 or not data:
        return []

    # 目标列：默认最后一个数值列；解释变量取前面几个
    y = cols[-1]
    xs = cols[:-1][:3]
    xj = ",".join(xs)
    x2 = ",".join(xs[:2]) if len(xs) >= 2 else xj

    out = []

    if "race" in cmds:
        out.append(dict(
            route_id="A", title="模型赛马",
            method="race",
            method_args={"--data": data, "--y": y, "--x": xj, "--json": True},
            success_criteria={"cv_rmse_max": 1e9},
            falsifiable_assumption="若二次型相对线性型没有可测改进，"
                                   "则响应关系在本样本上是线性的"))

    if "run" in cmds:
        out.append(dict(
            route_id="B", title="基线出稿",
            method="run",
            method_args={"--data": data, "--y": y, "--x": xj,
                         "--json": True, "--no-gate": True},
            # 判据只表达「算出了有效数值」，不表达「质量好不好」——
            # 质量由循环里的最优比较决定。_flatten_metrics 只拍平数值
            # 字段，n_rows 提不出来，所以判据必须落在 rmse 上。
            success_criteria={"cv_rmse_max": 1e9},
            falsifiable_assumption="若残差检验显示漏设曲率，"
                                   "则基线模型形式不足"))

    if "solve" in cmds and len(xs) >= 2:
        out.append(dict(
            route_id="C", title="约束优化",
            method="solve",
            method_args={"--data": data, "--y": y, "--x": x2,
                         "--maximize": True, "--json": True},
            success_criteria={"cv_rmse_max": 1e9},
            falsifiable_assumption="若最优解落在可行域内部，"
                                   "则约束没有绑定，问题退化为无约束"))

    if "forecast" in cmds and len(cols) >= 2:
        out.append(dict(
            route_id="D", title="时间外推",
            method="forecast",
            method_args={"--data": data, "--t": cols[0], "--y": y,
                         "--horizon": 5, "--json": True},
            success_criteria={"cv_rmse_max": 1e9},
            falsifiable_assumption="若外推误差随步长单调增大且不收敛，"
                                   "则该序列不可预测"))

    return out


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="编排循环")
    ap.add_argument("cmd", nargs="?", default="selftest",
                    choices=["selftest", "demo"])
    ap.add_argument("--data", default="")
    ap.add_argument("--rounds", type=int, default=5)
    ap.add_argument("--budget", type=float, default=45.0)
    a = ap.parse_args(argv)

    if a.cmd == "selftest":
        return selftest()

    # demo：用固定提案跑一轮骨架，验证「映射成命令」这条路是通的
    if not a.data:
        print("  demo 需要 --data")
        return 2
    data = a.data

    def _propose(ctx):
        return [dict(route_id="A", title="单因子回归",
                     method="run",
                     method_args={"--data": data, "--y": "剂量",
                                  "--x": "草甘膦"},
                     success_criteria={"n_rows_min": 1},
                     falsifiable_assumption="若两列无关则 R² 接近 0")]

    st = run_loop(data, _propose, max_rounds=a.rounds,
                  budget_min=a.budget)
    print(report(st))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
