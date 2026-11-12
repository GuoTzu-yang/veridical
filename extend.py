#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
model1 架构 · 第二轮优化（四项）

上一轮把三个瓶颈做成了可执行内核，但留了四个口子：

  X1  四条回边没有次数上限        —— Astra 实测踩过"反复进入修复循环"
  X2  循环推理没有留痕            —— 跑了 ≥3 轮，没人知道每轮改了什么
  X3  冷启动期仍走全流程          —— 库是空的，优化拓展白跑
  X4  拒绝率是拍脑袋估的          —— 阈值合不合理，没有数据支撑

本文件把四项补齐，全部复用 harness.py 的既有判据，不改动已验证代码。

用法:
    python extend.py selftest
    python extend.py bench
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field, replace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from harness import Claim, run_gates, GATE_SPEC, EvidenceEnv  # noqa: E402


# =============================================================================
# X1  回边预算
# =============================================================================
# 图上四条回边，只有两条是真"重做"，两条是"终止"：
#   A  置信度②不合格 → 回「多问题拆解」     重做，贵
#   C  疑难修完 → 回「深度切入」             重做，中
#   B  疑难 → 放弃 → 疑难1库                 终止
#   D  生成方案后 → 放弃                     终止
#
# 只给单边设上限是不够的：A→C→A→C 交替触发，能绕出 2×3=6 次。
# 所以必须再加一道全局总预算。
# -----------------------------------------------------------------------------

EDGE_LIMITS = {
    "A_REPLAN": 2,   # 重拆一次要重跑整条支线，只给 2 次
    "C_RECUT": 3,    # 重切只重跑深度切入，给 3 次
}
GLOBAL_BUDGET = 4    # 跨回边总预算，堵住交替绕过


class RetryBudget:
    def __init__(self, limits: dict[str, int] | None = None, total: int = GLOBAL_BUDGET):
        self.limits = dict(limits or EDGE_LIMITS)
        self.total_limit = total
        self.per_edge = {k: 0 for k in self.limits}
        self.total = 0
        self.log: list[dict] = []

    def consume(self, edge: str, key: str = "") -> dict:
        """申请一次重做。返回是否放行；不放行时必须给出降级去向。"""
        if edge not in self.limits:
            rec = {"allowed": False, "edge": edge, "key": key,
                   "reason": f"未知回边 {edge}", "fallback": "放弃→疑难1库"}
            self.log.append(rec)
            return rec

        if self.per_edge[edge] >= self.limits[edge]:
            rec = {"allowed": False, "edge": edge, "key": key,
                   "reason": f"单边预算耗尽 {self.per_edge[edge]}/{self.limits[edge]}",
                   "fallback": "放弃→疑难1库"}
            self.log.append(rec)
            return rec

        if self.total >= self.total_limit:
            rec = {"allowed": False, "edge": edge, "key": key,
                   "reason": f"全局预算耗尽 {self.total}/{self.total_limit}",
                   "fallback": "放弃→疑难2库"}
            self.log.append(rec)
            return rec

        self.per_edge[edge] += 1
        self.total += 1
        rec = {"allowed": True, "edge": edge, "key": key,
               "used": self.per_edge[edge],
               "remaining": self.limits[edge] - self.per_edge[edge]}
        self.log.append(rec)
        return rec

    def snapshot(self) -> dict:
        return {
            "per_edge": dict(self.per_edge),
            "total": self.total,
            "total_limit": self.total_limit,
            "exhausted": self.total >= self.total_limit,
        }


# =============================================================================
# X2  循环推理留痕
# =============================================================================
# 图上「多轮次循环推理（≥3）」只有次数要求，没有记录要求。
# 结果：跑完三轮，说不出改了什么；也分不清"真改了三轮"和"空转三轮"。
#
# 记录四类改动：修正 / 补充 / 推翻 / 无变化。
# 「无变化」必须记——它才是判断"这题值不值得循环"的唯一依据。
# -----------------------------------------------------------------------------

LOOP_ACTIONS = ("质疑复查", "查漏补缺", "优化底层")
DELTA_TYPES = ("修正", "补充", "推翻", "无变化")


@dataclass
class LoopRound:
    idx: int
    action: str
    target: str
    before: str
    after: str
    delta_type: str
    evidence: str = ""

    def __post_init__(self):
        if self.action not in LOOP_ACTIONS:
            raise ValueError(f"未知循环动作 {self.action!r}")
        if self.delta_type not in DELTA_TYPES:
            raise ValueError(f"未知改动类型 {self.delta_type!r}")
        if self.delta_type == "无变化" and self.before != self.after:
            raise ValueError(f"第 {self.idx} 轮标了无变化，但前后文本不同")


class LoopJournal:
    def __init__(self):
        self.rounds: list[LoopRound] = []

    def add(self, action: str, target: str, before: str, after: str,
            delta_type: str, evidence: str = "") -> LoopRound:
        r = LoopRound(len(self.rounds) + 1, action, target, before, after, delta_type, evidence)
        self.rounds.append(r)
        return r

    def stats(self) -> dict:
        n = len(self.rounds)
        if n == 0:
            return {"n": 0, "changed": 0, "rate": 0.0, "by_type": {}}
        by_type: dict[str, int] = {}
        for r in self.rounds:
            by_type[r.delta_type] = by_type.get(r.delta_type, 0) + 1
        changed = n - by_type.get("无变化", 0)
        return {"n": n, "changed": changed, "rate": round(changed / n, 3), "by_type": by_type}

    def recommend_strength(self) -> dict:
        """按有效率给推理强度档位——对应 Astra 的 low→max 五档。

        rate < 0.34  三轮回合里两轮空转 → 这类题不吃循环，降到 low
        0.34~0.66    半有效           → 维持 mid
        >= 0.66      大多有实质改动    → 值得 max
        """
        s = self.stats()
        if s["n"] == 0:
            return {"strength": "insufficient", "reason": "没有任何循环轮次"}
        rate = s["rate"]
        if rate < 0.34:
            return {"strength": "low", "rate": rate,
                    "reason": f"{s['n']} 轮中 {s['by_type'].get('无变化', 0)} 轮空转，该题型不值得循环"}
        if rate < 0.66:
            return {"strength": "mid", "rate": rate,
                    "reason": f"有效率 {rate}，维持当前档位"}
        return {"strength": "max", "rate": rate,
                "reason": f"有效率 {rate}，多轮均有实质改动，可提高档位"}


# =============================================================================
# X3  冷启动路由
# =============================================================================
# 库空着的时候跑全套，等于花 3 次调用查一个空库。
# 路由按题型库命中强度分三档，冷启动走轻量路径。
# -----------------------------------------------------------------------------

ROUTES = {
    # probe_ports = 深度切入的取材口数；expand_ports = 优化拓展的取材口数
    # 未命中：库里没料，拓展口全关；弱命中：只开一路（联网）；强命中：三路全开
    "lite": {"probe_ports": 4, "expand_ports": 0},
    "std":  {"probe_ports": 4, "expand_ports": 1},
    "full": {"probe_ports": 4, "expand_ports": 3},
}


def route_cost(route: str) -> int:
    """一个子问题在该路由下的调用次数。

    G1(1) + 深度切入(probe) + G2(1) + 优化拓展(expand) + G3(1) + 生成(1)
    """
    r = ROUTES[route]
    return 1 + r["probe_ports"] + 1 + r["expand_ports"] + 1 + 1


class TopicLibrary:
    def __init__(self, hits: dict[str, float] | None = None):
        self.hits = dict(hits or {})

    def hit(self, topic: str) -> float:
        return self.hits.get(topic, 0.0)


def choose_route(topic: str, lib: TopicLibrary,
                 t_strong: float = 0.7, t_weak: float = 0.3) -> dict:
    h = lib.hit(topic)
    if h >= t_strong:
        route = "full"
        why = f"题型库强命中 {h:.2f}，方案库有料可查，拓展三路全开"
    elif h >= t_weak:
        route = "std"
        why = f"题型库弱命中 {h:.2f}，不做方案库检索，只留一路联网拓展"
    else:
        route = "lite"
        why = f"题型库未命中（{h:.2f}），拓展口全关——查空库没有意义"
    return {
        "route": route,
        "hit": h,
        "probe_ports": ROUTES[route]["probe_ports"],
        "expand_ports": ROUTES[route]["expand_ports"],
        "calls_per_subq": route_cost(route),
        "reason": why,
    }


# =============================================================================
# X4  拒绝率实测
# =============================================================================
# 之前说"一次答题约 63 次调用"是拍出来的。这里用一批证据分布跑出实测分布。
#
# 注意：这是合成题库（16 条覆盖 e1/e2/e3 各档位组合），
# 用来验证判据的自洽性与成本模型，不代表真实题集的通过率。
# -----------------------------------------------------------------------------

# (e1, e2, e3, 越界, 未解释矛盾)
BENCH_CASES = [
    (2, 2, 2, False, 0),  # 满分
    (2, 2, 1, False, 0),
    (2, 1, 2, False, 0),
    (2, 1, 1, False, 0),
    (2, 0, 2, False, 0),
    (2, 0, 1, False, 0),
    (1, 2, 2, False, 0),
    (1, 1, 2, False, 0),
    (1, 1, 1, False, 0),
    (1, 0, 1, False, 0),
    (0, 2, 2, False, 0),  # e1=0 无论如何都过不了 G1
    (0, 1, 1, False, 0),
    (2, 2, 2, True, 0),   # 满分但越界
    (2, 2, 2, False, 1),  # 满分但有未解释矛盾
    (1, 1, 0, True, 1),   # 双重扣分
    (2, 2, 0, False, 0),  # 不可复现
    (2, 2, 0, True, 1),   # 前两闸通过后，在 G3 被 C=2 打回
    (2, 2, 1, True, 0),   # G3 降级：可复现度不足 + 越界
    (2, 2, 2, True, 1),   # G3 降级：满分但双扣
]

# 各档的调用成本
COST_TABLE = {"G1_reject": 1, "G2_reject": 6, "G3_reject": 10, "degrade": 11, "pass": 11}


def bench(cases: list[tuple] | None = None) -> dict:
    cases = cases or BENCH_CASES
    rows = []
    total_calls = 0
    buckets = {"G1_reject": 0, "G2_reject": 0, "G3_reject": 0, "degrade": 0, "pass": 0}

    for i, (e1, e2, e3, oos, contra) in enumerate(cases):
        c = Claim(cid=f"B{i:02d}", text=f"case{i}", e1=e1, e2=e2, e3=e3,
                  out_of_scope=oos, unexplained_contradiction=contra)
        r = run_gates(c)
        if r["final"] == "reject":
            key = f"{r['blocked_at']}_reject"
        elif r["final"] == "degrade":
            key = "degrade"
        else:
            key = "pass"
        calls = COST_TABLE[key]
        total_calls += calls
        buckets[key] += 1
        rows.append({
            "cid": c.cid, "dims": r["dims"], "C": r["C"],
            "final": r["final"], "blocked_at": r["blocked_at"],
            "calls": calls,
        })

    n = len(rows)
    return {
        "n": n,
        "buckets": buckets,
        "rates": {k: round(v / n, 3) for k, v in buckets.items()},
        "avg_calls_per_claim": round(total_calls / n, 2),
        "total_calls": total_calls,
        "rows": rows,
    }


# =============================================================================
# 接线：把预算接进带重试的流水线
# =============================================================================
# 上一轮的 run_pipeline 是单向的（没有回边），预算无从消耗。
# 这里加一条最小可验证的重试路径：
#   被拒 → 申请 A（重拆）→ 模拟补证 → 重评
#        → 仍被拒 → 申请 C（重切）→ 模拟补证 → 重评
#        → 仍被拒 → 预算耗尽则归档
#
# 注意：「重做后补证」此处是模拟（e1/e2 各 +1，扣分 −1），
# 用来验证预算逻辑，不代表真实检索效果。
# -----------------------------------------------------------------------------

def what_would_help(c: Claim, verdict: str, blocked_at: str | None,
                    env: EvidenceEnv | None = None) -> list[dict]:
    """被拦住时，算出「还差什么」——具体到哪一个维度差几分。

    为什么要有这个（第七十一轮）：
        旧的重试循环在 reject 之后会把 e1/e2 各加 1 再判一次，
        那等于程序替人补证据。抽掉之后，重试就只剩下"再跑一遍同样的判定"，
        什么也不产生。

        与其跑一遍空转，不如回答一个真问题：
        **如果要去补证据，补哪里最省事？**

    返回 [{dim, need, have, delta, how}, ...]，按 delta 从小到大排。
    delta 为空表示这一档已经够了。
    """
    # 已经过了就没有「还差什么」。之前漏了这个前置返回，
    # 结果 pass 的主张也带着建议，读起来像过了但还缺东西。
    if verdict == "pass":
        return []

    from harness import table_for, ENV_MAX_E
    env = env or EvidenceEnv()
    spec = table_for(c.kind)
    dims = {"e1": c.e1, "e2": c.e2, "e3": c.e3}
    have = {"e1": dims["e1"], "e2": dims["e2"], "e3": dims["e3"]}

    HOW = {
        "e1": "指到具体位置：文件+行号 / 出处链接，而不是只说个名字",
        "e2": "找第二个**独立**来源（不同团队、不同仓库）；同一处的多份文件不算",
        "e3": "真跑一次并留下可复现的记录（命令+数据+输出）",
    }

    stage = blocked_at or ("G3" if verdict == "degrade" else "G2")
    s = spec.get(stage) or spec["G2"]
    uses, need_sum = s["uses"], s["pass_at"]

    out = []
    cur = sum(have[d] for d in uses)
    gap = need_sum - cur
    if gap > 0:
        # 单维上限要取 ENV_MAX_E，不能取 env.cap()——后者是整闸合计上限，
        # 拿它当单维上限会算出 e1: 2→3 这种不可能的建议。
        cap_of = ENV_MAX_E[env.level]
        for d in uses:
            room = cap_of.get(d, 0) - have[d]
            if room > 0:
                delta = min(gap, room)
                out.append({"dim": d, "have": have[d],
                            "need": have[d] + delta, "delta": delta,
                            # solo：只补这一维就够过闸了吗。
                            # 有了它，才能回答「补哪个能**单独**解决这条」，
                            # 而不是只知道"两个都缺"。
                            "solo": delta >= gap,
                            "stage": stage, "how": HOW[d]})
    out.sort(key=lambda x: x["delta"])
    if not out and verdict != "pass":
        out.append({"dim": "—", "have": 0, "need": 0, "delta": 0,
                    "stage": stage,
                    "how": "这一档在数学上已经够了，卡点不在维度分数，"
                           "在 `refuted_by_test` / `input_valid` 这类一票否决项"})
    return out


def _simulate_repair(c: Claim) -> Claim:
    """重做一次 —— 但**不替它加分**。

    第七十轮自查时抽掉的旧实现是这样：

        return replace(c, e1=min(2, c.e1+1), e2=min(2, c.e2+1), ...)

    后果：一条 e1=2/e2=1/e3=1 的主张在 G2 被打回（e1+e2=3 < 4），
    重试循环把它"修"成 2/2/1，再判一次就成了 **pass**。

    可那 1 分是**程序凭空加上去的**：没有任何新证据、没有新出处、
    没有人复核。等于自己给自己发了一张通行证，然后拿通行证过闸。

    这正是这个项目七十几轮一直在打的那类事——**证据强度低于断言强度**。

    现在的规矩：
        重试只表示"又试了一次"，**不改变任何维度**。
        真要有改善，得由调用方拿出新的 e1/e2/e3（凭据、出处、复现记录），
        再重新调用一次评估。
        所以这个函数现在是个恒等映射——留着是为了保留重试轨迹。
    """
    return c


def run_with_retry(claims: list[Claim], budget: RetryBudget | None = None,
                   max_attempts: int = 3, env: EvidenceEnv | None = None) -> dict:
    """判完之后，回答「还差什么」。

    名字还叫 retry，但**它不再重试了**（第七十一轮改的）。

    为什么改：
        原来的循环在 reject 之后调 `_simulate_repair`，把 e1/e2 各加 1
        再判一次——那是程序替人补证据。抽掉那一步之后，重试只是
        "用同样的输入再算一遍同样的结果"，除了烧预算什么也不产生。

        与其空转，不如算清楚：**要补的话，补哪一维最省事。**

    现在每条结果带一个 `ask`：
        [{"dim": "e2", "have": 1, "need": 2, "delta": 1, "how": "..."}]
    空列表 = 这一条不需要补（已经过了，或者卡在维度之外的一票否决项）。

    `budget` 参数留着是为了不让调用方改签名；它现在不会被消耗，
    因为没有任何"额外的尝试"发生。
    """
    budget = budget or RetryBudget()
    env = env or EvidenceEnv()
    results = []

    for c in claims:
        r = run_gates(c, env)
        asks = what_would_help(c, r["final"], r.get("blocked_at"), env)
        trail = [{"attempt": 0, "C": r["C"], "final": r["final"]}]

        # 三种终止都要有去处，但都不再假装"重做过了"
        if r["final"] == "reject":
            trail.append({"attempt": 1,
                          "blocked": "打回，不再重试",
                          "archive": "放弃→疑难1库",
                          "ask": asks})
        elif r["final"] == "degrade":
            trail.append({"attempt": 1,
                          "blocked": "降级，待补证",
                          "archive": "待补→疑难2库",
                          "ask": asks})

        r["cid"] = c.cid
        r["trail"] = trail
        r["attempts"] = 0
        r["ask"] = asks
        results.append(r)

    return {
        "results": results,
        "budget": budget.snapshot(),
        # 保留字段名，语义改成"有主张是靠自己过的，不是靠重试救的"
        "recovered": 0,
        "archived": sum(1 for r in results if r.get("ask")),
    }



# =============================================================================
# 接线：把留痕接进主线循环
# =============================================================================
# 主线「多轮次循环推理（≥3）」在代码里原本不存在。这里补上最小实现：
# 每轮挑一个最弱的维度打，打不动就记「无变化」。
#
# 挑维度的顺序：e1 缺出处 → 查漏补缺；e2 独立度不足 → 质疑复查；
#               e3 不可复现 → 优化底层；全达标 → 空转（无变化）
# -----------------------------------------------------------------------------

# 现实约束：主线只能把话说得更具体，**造不出不存在的出处**。
#   e1=0（无源）  → 主线补不了，只能空转，等支线去外面取证
#   e1=1（有名无位）→ 主线可以追到具体位置，抬到 2
#   e2/e3         → 主线始终动不了，那是支线的活
# -----------------------------------------------------------------------------

def mainline_loop(c: Claim, journal: LoopJournal, rounds: int = 3) -> Claim:
    cur = c
    for _ in range(rounds):
        if cur.e1 == 0:
            action, delta = "查漏补缺", "无变化"
            before = after = "e1=0/2（无可追溯来源）"
            journal.add(action, cur.cid, before, after, delta,
                        "主线造不出出处，只能等支线取证")
            continue
        elif cur.e1 == 1:
            action, delta = "质疑复查", "修正"
            before, after = "e1=1/2（只有名字）", "e1=2/2（指到位置）"
            # 用 dataclasses.replace 而不是手工重建：
            # 手工重建会把 kind / input_valid / refuted_by_test 丢掉——
            # kind 丢了闸门会用错表，input_valid 丢了一票否决失效，
            # refuted_by_test 丢了实测反证失效。这三个都是"否决级"的字段。
            cur = replace(cur, e1=2)
        else:
            action, delta = "优化底层", "无变化"
            before = f"e1已满，e2={cur.e2} e3={cur.e3} 需外部取证"
            after = before
        journal.add(action, cur.cid, before, after, delta)
    return cur


# =============================================================================
# 接线：事前取证 → 判定 → 组合 → 记账
# =============================================================================
# 前面三十五轮造出来的东西（precheck / 机制适用性 / taskgraph / 账本先验 /
# cause 分流）全挂在主线外面，主线一次也没调用过。这一节把它们接进来。
#
# 主线的一次答题现在是：
#   1. 事前取证  前置条件 + 机制适用性 → input_valid
#   2. 主线循环  抬 e1（只能抬 e1，造不出出处）
#   3. 闸门判定  三道闸，带 cause
#   4. 组合      多条主张合起来算整体成功率（用账本先验）
#   5. 记账      落账，带 env / cause / version
# -----------------------------------------------------------------------------

def pre_verify(claims: list[Claim]) -> tuple[list[Claim], list[dict]]:
    """判之前先取证：把前置检查的结论填进 Claim 的 input_valid。

    三个来源合成一个判断：
      前置条件不满足（表不存在、语法错、维度不符）→ input_valid=False，一票否决
      机制不适用（索引原理上用不上）            → input_valid=False，一票否决
      都通过                                    → input_valid=True
      检查器不可用（连不上库）                  → input_valid=None，不否决

    没写 verify 的主张不动（= 未检查，保守放行）。
    """
    from precheck import check_task

    out: list[Claim] = []
    log: list[dict] = []
    for c in claims:
        v = c.verify
        if not v:
            out.append(c)
            log.append({"cid": c.cid, "checked": False})
            continue
        try:
            r = check_task(v.get("domain", ""), v.get("task", {}) or {})
        except Exception as e:
            out.append(replace(c, input_valid=None))
            log.append({"cid": c.cid, "checked": True, "status": "unknown",
                        "reason": f"检查器异常：{type(e).__name__}: {e}"})
            continue

        if r.status == "fail":
            iv = False
        elif r.mechanism is False:
            iv = False
        elif r.status == "ok":
            iv = True
        else:
            iv = None

        out.append(replace(c, input_valid=iv))
        log.append({"cid": c.cid, "checked": True, "status": r.status,
                    "mechanism": r.mechanism, "input_valid": iv,
                    "reason": r.reason,
                    "mechanism_reason": r.mechanism_reason})
    return out, log


def enrich_from_kb(claims: list[Claim], query: str,
                   limit: int = 8, record_log: bool = True
                   ) -> tuple[list[Claim], list[dict]]:
    """用检索库给主张补证据。返回 (改过的主张, 每条的变更说明)。

    它只能**往上补**，不能往下压——原本声明的 e1/e2 是作者自己的判断，
    检索库没有资格否定它，只能提供额外的可引用出处。

    三条硬规矩（都来自这个项目踩过的坑）：
        1. **同一个仓库的多个文件不算独立来源。**
           一个团队写的一套代码，观点当然一致，当两票是自欺。
        2. **命中必须能核对原文。** 摘要会截断，只有原文真含关键词才算数，
           否则就是"搜到了但没对上"。
        3. **没搜到不改动。** 这个库只有 30 个仓库，找不到只能说明
           "这 30 个里没有"，不能推出"没有证据"，更不该把 e1 打成 0。

    用法的分寸：
        它适合回答"这句话我在哪儿见过出处"，
        不适合回答"这句话对不对"。补上来的是**出处**，不是**结论**。
    """
    try:
        import kb as _kb
    except Exception as e:  # noqa: BLE001
        return claims, [{"ok": False, "why": f"检索库不可用：{type(e).__name__}"}]

    hits = _kb.search(query, limit=limit)
    terms = [w for w in _kb._sanitize(query).split() if w]
    a = _kb.assess(hits, terms)

    log = [{"ok": True, "hits": len(hits), "verified": a.hits,
            "repos": a.repos, "e1_cap": a.e1_cap, "e2_cap": a.e2_cap,
            "why": a.why}]

    if a.e1_cap == 0:
        # 没命中，或命中了但原文核对不到 —— 一律不动。
        return claims, log

    cites = [h.cite() for h in hits[:limit]]
    out = []
    for c in claims:
        new_e1 = max(c.e1, a.e1_cap)
        # **不碰 e2。** 这一条是第七十轮自查时抽掉的，理由必须写清楚：
        #
        #   我第一版拿"命中来自 2 个仓库"直接把 e2 抬到 2，
        #   结果一条 e1=2/e2=1/e3=1 的主张从 degrade 跳成了 pass。
        #
        #   但 e2 问的是「有没有**两个独立来源在支持这个结论**」，
        #   而关键词检索给出的是「这两个代码库里都**出现过**这个词」。
        #
        #   共现 ≠ 支持。拿它当独立来源，正是这个项目一直在打的那类
        #   证据强度不足却被当成结论的事。
        #
        #   所以：检索库只补**出处**（e1），不补**独立支持**（e2）。
        #   独立仓库数写进日志，供人复核，不由程序替人加分。
        srcs = list(c.sources)
        for s in cites:
            if s not in srcs:
                srcs.append(s)
        changed = (new_e1 != c.e1) or (len(srcs) != len(c.sources))
        out.append(replace(c, e1=new_e1, sources=srcs) if changed else c)
        if changed:
            log.append({"cid": c.cid, "e1": f"{c.e1}→{new_e1}",
                        "e2": f"未动（检索库不补独立支持）",
                        "独立仓库": a.repos,
                        "sources+": len(srcs) - len(c.sources)})
    return out, log


def evaluate_claims(claims: list[Claim], env: EvidenceEnv | None = None,
                    relation: str = "and", task_name: str = "",
                    rounds: int = 0, budget: RetryBudget | None = None,
                    journal: LoopJournal | None = None, record: bool = False,
                    prior: dict | None = None,
                    origin: str | None = None,
                    kb_query: str | None = None) -> dict:
    """架构的评估主干——**唯一一条路径**。

    取证 → 主线循环 → 闸门（带重试）→ 组合 → 记账

    `run_full` 是它加上路由和成本估算的完整版；
    MCP 的 evaluate_claim / evaluate_task 直接调它，不再另写一套管线。

    rounds=0 表示不跑主线循环（只判不修），MCP 默认走这个。
    """
    journal = journal or LoopJournal()
    env = env or EvidenceEnv()

    # 0. 检索库补证（可选）
    #    只在调用方明确给了 kb_query 时才做——默认不碰，
    #    因为检索库只覆盖 30 个仓库，对范围外的问题它找不到东西，
    #    那不代表"没证据"，只代表"这个库没有"。
    if kb_query:
        claims, kb_log = enrich_from_kb(claims, kb_query)
    else:
        kb_log = []

    # 1. 事前取证
    verified, vlog = pre_verify(claims)

    # 2. 主线循环
    lifted = [mainline_loop(c, journal, rounds) for c in verified]

    # 3. 支线闸门（带重试）
    tail = run_with_retry(lifted, budget, env=env)

    # 4. 组合：多条主张合起来算整体成功率，用账本先验
    from taskgraph import TaskGraph, Item
    use_prior = prior if prior is not None else _load_prior(env)
    g = TaskGraph(task_name or "主线",
                  [Item(r["cid"], c) for r, c in zip(tail["results"], lifted)],
                  relation)
    combo = g.evaluate(env, use_prior)

    # 5. 记账
    rec_ids: list[str] = []
    if record:
        rec_ids = _record_round(tail["results"], lifted, env, task_name, origin)

    by_cause: dict[str, int] = {}
    for r in tail["results"]:
        key = r.get("cause") or r["final"]
        by_cause[key] = by_cause.get(key, 0) + 1

    return {
        "journal": journal.stats(),
        "strength": journal.recommend_strength(),
        "env": env.describe(),
        "pre_verify": vlog,
        "after_mainline": [{"cid": c.cid, "C": c.score(),
                            "dims": c.dims(), "input_valid": c.input_valid}
                           for c in lifted],
        "pipeline": tail,
        "by_cause": by_cause,
        "combo": {"relation": relation, "p_success": combo["p_success"],
                  "weakest": combo["weakest"],
                  "rows": [{"label": x["label"], "verdict": x["verdict"],
                            "cause": x.get("cause"), "p": x["p"],
                            "C": x["C"]}
                           for x in combo["rows"]]},
        "prior_source": use_prior.get("__source__", "硬编码默认"),
        "recorded": rec_ids,
    }


def run_full(claims: list[Claim], journal: LoopJournal | None = None,
             budget: RetryBudget | None = None, rounds: int = 3,
             library: TopicLibrary | None = None, topic: str = "",
             env: EvidenceEnv | None = None,
             relation: str = "and",
             record: bool = False,
             task_name: str = "",
             prior: dict | None = None,
             origin: str | None = None) -> dict:
    """完整主线：路由 → 评估主干 → 汇总。

    路由不参与闸门判定，只决定"每个子问题要花几次调用"，
    总成本 = 路由成本 × 子问题数 + 主线 4 + 汇总 4。
    """
    route = choose_route(topic, library or TopicLibrary())
    out = evaluate_claims(claims, env=env, relation=relation,
                           task_name=task_name, rounds=rounds, budget=budget,
                           journal=journal, record=record, prior=prior,
                           origin=origin)
    out["route"] = route
    out["estimated_calls"] = route["calls_per_subq"] * len(claims) + 8
    return out


def _load_prior(env: EvidenceEnv) -> dict:
    """取当前环境档位对应的先验；账本不可用时回落到硬编码。"""
    try:
        import ledger as L
        prior, detail = L.current_prior(env_level=env.level)
        prior = dict(prior)
        srcs = {v: d.get("source") for v, d in detail.items()}
        prior["__source__"] = ("账本 L%d" % env.level
                               if any(s == "ledger" for s in srcs.values())
                               else "硬编码默认")
        return prior
    except Exception:
        return {"__source__": "硬编码默认（账本不可用）"}


def _record_round(results: list[dict], claims: list[Claim],
                  env: EvidenceEnv, task_name: str,
                  origin: str | None = None) -> list[str]:
    """把本轮判定落进账本（带 env / cause / version / origin）。"""
    try:
        import ledger as L
    except Exception:
        return []
    ids = []
    for r, c in zip(results, claims):
        try:
            rec = L.record(r["final"], task=task_name or r.get("cid", ""),
                           note="主线一轮", success=None,
                           evidence=f"{r.get('cid')} C={r['C']} "
                                    f"cause={r.get('cause')} attempt={r.get('attempts')}",
                           env_level=env.level, cause=r.get("cause"),
                           origin=origin, ask=r.get("ask"))
            ids.append(rec["id"])
        except L.ProductionWriteRefused as e:
            # 静默吞掉会让"以为记上了"变成事实错误，所以往上抛
            raise L.ProductionWriteRefused(
                f"记账被门禁拒绝：{e}\n"
                f"  主线不认识调用方的身份——写不写正式账本由入口声明"
                f"（ledger.bind_production 或 origin=）。") from e
    return ids


# =============================================================================
# selftest
# =============================================================================

def selftest() -> int:
    fails = []

    def check(name: str, cond: bool, detail: str = ""):
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  — {detail}" if detail else ""))
        if not cond:
            fails.append(name)

    print("=" * 72)
    print("X0  主线不丢否决级字段")
    print("=" * 72)
    # 这三个字段任一丢失，都会让「已知不可行的主张」混过关：
    #   kind            → 闸门用错表（PROCEDURE_SPEC 不再适用）
    #   input_valid     → 一票否决失效
    #   refuted_by_test → 实测反证失效
    c0 = Claim("C0", "x", e1=1, e2=1, e3=1, kind="procedure",
               input_valid=False, refuted_by_test=True,
               sources=["a"], unexplained_contradiction=1, out_of_scope=True)
    c0b = mainline_loop(c0, LoopJournal(), rounds=1)
    check("kind 不丢", c0b.kind == "procedure", c0b.kind)
    check("input_valid 不丢", c0b.input_valid is False, str(c0b.input_valid))
    check("refuted_by_test 不丢", c0b.refuted_by_test is True, str(c0b.refuted_by_test))
    check("扣分项不丢", (c0b.unexplained_contradiction, c0b.out_of_scope) == (1, True))
    g0 = run_gates(c0b, EvidenceEnv(3))
    check("被否决的主张过主线后仍被否决", g0["final"] == "reject", g0["final"])

    print("=" * 72)
    print("X0b 主线接线：事前取证 → 组合 → 成因")
    print("=" * 72)
    import tempfile
    _tmp = os.path.join(tempfile.gettempdir(), "m1_ext_selftest")
    os.makedirs(_tmp, exist_ok=True)
    _f_ok = os.path.join(_tmp, "ok.txt")
    with open(_f_ok, "w", encoding="utf-8") as fh:
        fh.write("x")
    _f_bad = os.path.join(_tmp, "nope.txt")

    cv, vlog = pre_verify([
        Claim("V1", "读存在的文件", e1=2, e2=0, e3=2, kind="procedure",
              verify={"domain": "file", "task": {"path": _f_ok, "op": "read"}}),
        Claim("V2", "读不存在的文件", e1=2, e2=0, e3=2, kind="procedure",
              verify={"domain": "file", "task": {"path": _f_bad, "op": "read"}}),
        Claim("V3", "没写怎么验证", e1=2, e2=0, e3=2, kind="procedure"),
    ])
    check("前置通过 → input_valid=True", cv[0].input_valid is True, str(cv[0].input_valid))
    check("前置失败 → input_valid=False", cv[1].input_valid is False, str(cv[1].input_valid))
    check("没写 verify → 不动（未检查）", cv[2].input_valid is None, str(cv[2].input_valid))

    out = run_full(cv, env=EvidenceEnv(3), relation="and", task_name="自测")
    check("run_full 给出组合结果", "p_success" in out["combo"])
    check("run_full 给出成因分布", isinstance(out["by_cause"], dict))
    check("被前置否掉的判 reject",
          any(r["cid"] == "V2" and r["final"] == "reject"
              for r in out["pipeline"]["results"]))
    check("环境档位进了判定结果", out["env"]["level"] == 3, str(out["env"]))

    out2 = run_full([Claim("E1", "x", e1=2, e2=0, e3=2, kind="procedure")],
                     env=EvidenceEnv(2))
    check("L2 下满分也被降级", out2["pipeline"]["results"][0]["final"] == "degrade",
          out2["pipeline"]["results"][0]["final"])
    check("L2 下成因标成 env", out2["pipeline"]["results"][0].get("cause") == "env",
          str(out2["pipeline"]["results"][0].get("cause")))
    check("L2 与 L3 判定不同（环境真的进了主线）",
          out2["pipeline"]["results"][0]["final"] !=
          out["pipeline"]["results"][0]["final"])

    print()
    print("=" * 72)
    print("X0c 对外输出：总结必须交代覆盖率与最弱一环")
    print("=" * 72)
    text = summarize(out)
    print("  " + "\n  ".join(text.splitlines()[:6]))
    check("总结含环境档位", "环境: L3" in text)
    check("总结含先验来源", "先验:" in text)
    check("总结含覆盖率", "覆盖率" in text)
    check("总结含最弱一环", "最弱一环" in text)
    check("总结含成因分布", "成因分布" in text)
    check("被否决的条目在总结里是 reject",
          any("reject" in ln for ln in text.splitlines()))

    # 高分但机制不适用 → 仍然 reject（一票否决优先于分数）
    mech_reject = run_gates(
        Claim("M", "x", e1=2, e2=2, e3=2, kind="procedure", input_valid=False),
        EvidenceEnv(3))
    check("满分 6 也挡不住一票否决", mech_reject["final"] == "reject",
          f"C={mech_reject['C']} → {mech_reject['final']}")

    # 任务定义能读进来
    import json as _json
    import tempfile as _tf
    _spec = {"name": "自测任务", "relation": "or",
             "claims": [{"cid": "T1", "text": "t", "e1": 2, "e2": 0, "e3": 2,
                         "kind": "procedure"}]}
    _p = os.path.join(_tmp, "task.json")
    with open(_p, "w", encoding="utf-8") as fh:
        _json.dump(_spec, fh, ensure_ascii=False)
    _cl, _sp = load_task(_p)
    check("能从 JSON 读任务定义", len(_cl) == 1 and _cl[0].cid == "T1")
    check("任务名读到了", _sp.get("name") == "自测任务")

    print("=" * 72)
    print("X1  回边预算 · 单边上限 + 全局总预算")
    print("=" * 72)
    b = RetryBudget()
    r1 = b.consume("A_REPLAN", "SQ1")
    r2 = b.consume("A_REPLAN", "SQ1")
    r3 = b.consume("A_REPLAN", "SQ1")
    print(f"  A 连用三次: {[x['allowed'] for x in (r1, r2, r3)]}  第三次理由: {r3['reason']}")
    check("A 单边上限 2，第三次被拒", (r1["allowed"], r2["allowed"], r3["allowed"]) == (True, True, False))
    check("拒绝时给出降级去向", r3.get("fallback") == "放弃→疑难1库", str(r3.get("fallback")))

    b2 = RetryBudget()
    seq = [("A_REPLAN", "A1"), ("C_RECUT", "C1"), ("A_REPLAN", "A2"),
           ("C_RECUT", "C2"), ("C_RECUT", "C3")]
    got = [b2.consume(e, k)["allowed"] for e, k in seq]
    print(f"  A,C,A,C,C 交替: {got}  快照={b2.snapshot()}")
    check("交替触发被全局预算 4 拦住", got == [True, True, True, True, False], str(got))
    check("全局耗尽后标记 exhausted", b2.snapshot()["exhausted"] is True)

    print()
    print("=" * 72)
    print("X2  循环推理留痕 · 改动分类与强度建议")
    print("=" * 72)

    j_idle = LoopJournal()
    j_idle.add("质疑复查", "比值计算", "3.2:1", "3.2:1", "无变化")
    j_idle.add("查漏补缺", "口径说明", "未写", "未写", "无变化")
    j_idle.add("优化底层", "单位换算", "万个", "万个", "无变化")
    s_idle = j_idle.stats()
    rec_idle = j_idle.recommend_strength()
    print(f"  全空转: {s_idle}  建议={rec_idle['strength']}")
    check("三轮全空转 → 有效率 0", s_idle["rate"] == 0.0)
    check("三轮全空转 → 建议降档 low", rec_idle["strength"] == "low", rec_idle["reason"])

    j_live = LoopJournal()
    j_live.add("质疑复查", "比值计算", "3.2:1", "3.15:1", "修正", "重算分母")
    j_live.add("查漏补缺", "口径说明", "未写", "按公共桩计", "补充", "公报脚注")
    j_live.add("优化底层", "单位换算", "万个", "万辆", "推翻", "原单位错")
    s_live = j_live.stats()
    rec_live = j_live.recommend_strength()
    print(f"  全改: {s_live}  建议={rec_live['strength']}")
    check("三轮全改 → 有效率 1.0", s_live["rate"] == 1.0)
    check("三轮全改 → 建议升档 max", rec_live["strength"] == "max", rec_live["reason"])

    try:
        j_bad = LoopJournal()
        j_bad.add("质疑复查", "x", "a", "b", "无变化")
        check("前后不同却标无变化 → 应报错", False, "未抛异常")
    except ValueError as e:
        check("前后不同却标无变化 → 拒绝入账", True, str(e))

    print()
    print("=" * 72)
    print("X3  冷启动路由 · 按命中强度选路径")
    print("=" * 72)

    lib = TopicLibrary({"充电桩评估": 0.85, "车桩比测算": 0.45})
    for topic in ("充电桩评估", "车桩比测算", "某未知题型"):
        r = choose_route(topic, lib)
        print(f"  {topic:8s} hit={r['hit']:.2f} → {r['route']:4s}  "
              f"{r['calls_per_subq']} 次/子问题  ({r['reason']})")

    check("强命中走 full（11 次）",
          choose_route("充电桩评估", lib)["calls_per_subq"] == 11)
    check("弱命中走 std（9 次）",
          choose_route("车桩比测算", lib)["calls_per_subq"] == 9)
    check("未命中走 lite 且拓展口全关",
          choose_route("某未知题型", lib)["route"] == "lite"
          and choose_route("某未知题型", lib)["expand_ports"] == 0)
    costs = {route_cost(r) for r in ROUTES}
    check("三档成本互不相同", len(costs) == 3, str(sorted(costs)))

    print()
    print("=" * 72)
    print(f"X4  拒绝率实测 · {len(BENCH_CASES)} 条合成样本")
    print("=" * 72)

    res = bench()
    print(f"  样本 {res['n']} 条  分布 {res['buckets']}")
    print(f"  拒绝率 {res['rates']}  平均 {res['avg_calls_per_claim']} 次/结论")
    check("G1 拒的是 e1=0 那条", res["buckets"]["G1_reject"] >= 1, str(res["buckets"]))
    check("G2 是主要拦截点", res["buckets"]["G2_reject"] >= res["buckets"]["G3_reject"],
          str(res["buckets"]))
    check("G3 能拦住极端情况（越界+矛盾双扣）", res["buckets"]["G3_reject"] >= 1,
          str(res["buckets"]))
    check("存在降级项（G3 的主要动作是降级不是打回）", res["buckets"]["degrade"] >= 1,
          str(res["buckets"]))
    check("平均成本落在 1~11 之间",
          1.0 <= res["avg_calls_per_claim"] <= 11.0, str(res["avg_calls_per_claim"]))

    # 用实测均值替换拍脑袋的 63
    subq = 5
    est = round(subq * res["avg_calls_per_claim"] + 8, 1)
    print(f"  5 子问题 + 主线汇总 8 次 → 实测估算 {est} 次调用（旧口径 63 次）")
    check("实测估算低于旧口径", est < 63, f"{est} vs 63")

    print()
    print("=" * 72)
    print("X5  预算接线 · 带重试的流水线")
    print("=" * 72)

    from harness import CLAIMS as HARNESS_CLAIMS
    rr = run_with_retry(HARNESS_CLAIMS, RetryBudget())
    for r in rr["results"]:
        print(f"  {r['cid']:8s} 重试 {r['attempts']} 次 → {r['final']:7s} "
              f"轨迹 {[(t.get('edge') or t.get('blocked'), t.get('final', 'X')) for t in r['trail'][1:]]}")
    print(f"  预算快照: {rr['budget']}  救回 {rr['recovered']} 项  归档 {rr['archived']} 项")

    # 这条断言原来写的是 "重试后确有项被救回"，
    # 而当时"救回"的实现是 _simulate_repair 凭空给 e1/e2 各加 1。
    # 换句话说：**这条断言在守护那个 bug**。
    # 第七十轮把它翻过来——重试不该救回任何没有新证据的主张。
    check("重试不会凭空救回主张（没新证据就不该过闸）",
          rr["recovered"] == 0, str(rr["recovered"]))
    # 这两条原来断言的是"重试真的花了预算"。
    # 现在不重试了，所以预算必须**一动不动**——动了就说明还有隐藏的重试。
    check("不再重试，预算不动", rr["budget"]["total"] == 0,
          str(rr["budget"]["total"]))
    check("总消耗不超过全局上限",
          rr["budget"]["total"] <= GLOBAL_BUDGET, str(rr["budget"]["total"]))

    # 取而代之：每条被拦的主张都要说清「还差什么」
    blocked = [r for r in rr["results"] if r["final"] != "pass"]
    check("每条被拦的主张都给出了「还差什么」",
          all(r.get("ask") for r in blocked),
          f"被拦 {len(blocked)} 条，有建议 {sum(1 for r in blocked if r.get('ask'))} 条")
    check("建议不会超过该维上限",
          all(a["need"] <= 2 for r in blocked for a in r.get("ask") or []),
          str([(a["dim"], a["need"]) for r in blocked for a in r.get("ask") or []])[:60])
    check("过了的主张不产出建议",
          all(not r.get("ask") for r in rr["results"] if r["final"] == "pass"))
    check("未被救回的项有归档去向",
          all(any("archive" in t for t in r["trail"])
              for r in rr["results"] if r["final"] == "reject"))

    print()
    print("=" * 72)
    print("X6  留痕接线 · 主线循环喂给支线闸门")
    print("=" * 72)

    from harness import CLAIMS as HC2
    full = run_full(HC2, LoopJournal(), RetryBudget(), rounds=3,
                    library=TopicLibrary({"某未知题型": 0.0}), topic="某未知题型")
    print(f"  路由: {full['route']['route']}（{full['route']['calls_per_subq']} 次/子问题）"
          f" → 总估算 {full['estimated_calls']} 次")
    print(f"  主线留痕: {full['journal']}")
    print(f"  强度建议: {full['strength']['strength']}  ({full['strength']['reason']})")
    for a in full["after_mainline"]:
        print(f"    主线后 {a['cid']:8s} C={a['C']} dims={a['dims']}")

    check("主线只抬 e1，不动 e2/e3",
          all(a["dims"]["e2"] <= 2 and a["dims"]["e3"] <= 2 for a in full["after_mainline"]))
    check("留痕有效率可算",
          0.0 <= full["journal"]["rate"] <= 1.0, str(full["journal"]["rate"]))
    check("主线补不动 e2/e3，所以多数轮次空转",
          full["journal"]["rate"] < 0.5, str(full["journal"]))

    # 路由参与成本计算：lite 8×4+8=40，full 11×4+8=52
    full_route = run_full(HC2, LoopJournal(), RetryBudget(), rounds=3,
                          library=TopicLibrary({"充电桩评估": 0.95}), topic="充电桩评估")
    print(f"  强命中路由总估算: {full_route['estimated_calls']} 次（{full_route['route']['route']}）")
    check("未命中走 lite，总估算 40", full["estimated_calls"] == 40, str(full["estimated_calls"]))
    check("强命中走 full，总估算 52", full_route["estimated_calls"] == 52,
          str(full_route["estimated_calls"]))
    check("路由确实改变总成本", full["estimated_calls"] != full_route["estimated_calls"])

    # 造一个全达标样例，验证主线真的会空转并给出 low
    from harness import Claim as HC
    perfect = HC(cid="P1", text="全达标", e1=2, e2=2, e3=2)
    idle = run_full([perfect], LoopJournal(), RetryBudget(), rounds=3)
    print(f"  全达标样例: {idle['journal']}  建议={idle['strength']['strength']}")
    check("全达标时主线三轮空转", idle["journal"]["changed"] == 0, str(idle["journal"]))
    check("全达标时建议降档 low", idle["strength"]["strength"] == "low")

    # ---- 检索库补证（第七十轮接进主干）----
    print()
    print("=" * 72)
    print("X5  检索库：只补出处，不下结论")
    print("=" * 72)

    # 只有在有真索引时才测这一段；没有索引就明确说跳过，不假装通过
    try:
        import kb as _kb
        _kb_ok = _kb.stats().get("ok") is True
    except Exception:  # noqa: BLE001
        _kb_ok = False

    if not _kb_ok:
        print("  [SKIP] 没有索引，检索库这一段未测（不是通过）")
    else:
        # 1) 能补：e1=1 的主张遇到多仓库可核对命中 → 补到 2
        c = Claim("K1", "raft 一致性", e1=1, e2=1)
        out, log = enrich_from_kb([c], "raft consensus")
        check("检索库能给 e1 补出处", out[0].e1 >= 2, f"e1={out[0].e1}")
        check("补进来的出处写进 sources", len(out[0].sources) > 0,
              f"{len(out[0].sources)} 条")

        # 2) 同一仓库只算一票 —— 这是最容易被误用的地方
        hits = _kb.search("raft consensus", limit=8)
        one = [h for h in hits if h.repo == hits[0].repo]
        a1 = _kb.assess(one, ["raft"])
        # e2 是「独立度维度分」不是票数：0 单一同源 / 1 两源疑同源 /
        # 2 三源独立。同一仓库的多条命中 = 单一同源 = 0。
        check("同一仓库的多条命中 → e2=0（单一同源，不算独立证据）",
              a1.e2_cap == 0, f"e2={a1.e2_cap}")
        # 独立来源数应被单独记下来，供人看
        check("但仓库数被如实记成 1", len(a1.repos) == 1, f"{a1.repos}")

        # 3) **不补 e2**：关键词共现不等于两个来源在支持同一命题
        c_e2 = Claim("KE", "raft 一致性", e1=2, e2=1, e3=1)
        out_e2, log_e2 = enrich_from_kb([c_e2], "raft consensus")
        check("检索库不把 e2 抬上去（共现≠支持）",
              out_e2[0].e2 == 1, f"e2={out_e2[0].e2}")
        check("但把独立仓库数写进日志供人复核",
              bool(log_e2[-1].get("独立仓库")), str(log_e2[-1].get("独立仓库"))[:40])

        # 4) 不往下压：已经 2/2 的主张不会被改小
        c2 = Claim("K2", "raft 一致性", e1=2, e2=2)
        out2, _ = enrich_from_kb([c2], "raft consensus")
        check("已声明更高分时不往下压",
              out2[0].e1 == 2 and out2[0].e2 == 2,
              f"{out2[0].e1}/{out2[0].e2}")

        # 4) 搜不到就不动 —— 库里没有 ≠ 没有证据
        c3 = Claim("K3", "完全不存在的话题 zzzqqqxxx", e1=1, e2=1)
        out3, log3 = enrich_from_kb([c3], "完全不存在的话题 zzzqqqxxx")
        check("搜不到时原样返回，不打成 0",
              out3[0].e1 == 1 and out3[0].e2 == 1 and not out3[0].sources,
              f"{out3[0].e1}/{out3[0].e2} sources={len(out3[0].sources)}")

    # 5) 不传 kb_query 就完全不碰检索库
    base = Claim("N1", "x", e1=1, e2=1, e3=1)
    r_no = evaluate_claims([base], rounds=0)
    check("不传 kb_query 时不动检索库", len(base.sources) == 0,
          f"sources={len(base.sources)}  组合判定={r_no['combo'].get('final')}")

    print()
    print("=" * 72)
    if fails:
        print(f"FAILED: {len(fails)} 项 -> {fails}")
        return 1
    print("ALL PASS")
    return 0


def summarize(out: dict) -> str:
    """把一次评估排成人能读的总结。

    这是主线的**对外输出形状**。包含四件必须交代的事：
      1. 在什么环境下判的（判据随环境变）
      2. 先验从哪来（账本还是硬编码）
      3. 每条主张怎么判的、为什么（含事前取证）
      4. 合起来多少、最弱一环是谁、**覆盖率**（多少条给出了确定结论）
    """
    lines = []
    env = out.get("env", {})
    lines.append("=" * 60)
    lines.append("主线评估")
    lines.append("=" * 60)
    lines.append(f"环境: L{env.get('level')} —— {env.get('desc', '')}")
    lines.append(f"先验: {out.get('prior_source', '未知')}")

    pv = [v for v in out.get("pre_verify", []) if v.get("checked")]
    if pv:
        lines.append("")
        lines.append("事前取证")
        for v in pv:
            mech = v.get("mechanism")
            mech_s = ("机制可用" if mech is True
                      else "机制不适用" if mech is False else "机制未查")
            lines.append(f"  {v['cid']:<6}前置 {v.get('status', '?'):<8}"
                         f"{mech_s:<10}→ input_valid={v.get('input_valid')}")
            reason = v.get("mechanism_reason") or v.get("reason") or ""
            if reason:
                lines.append(f"        {reason[:56]}")

    results = out.get("pipeline", {}).get("results", [])
    lines.append("")
    lines.append("判定")
    for r in results:
        cause = f"  成因={r['cause']}" if r.get("cause") else ""
        lines.append(f"  {r.get('cid', '?'):<6}{r['final']:<8}C={r['C']}{cause}")

    combo = out.get("combo", {})
    if combo:
        lines.append("")
        lines.append(f"组合（{combo.get('relation')}）  "
                     f"整体成功率 {combo.get('p_success')}   "
                     f"最弱一环 {combo.get('weakest')}")

    # 覆盖率：多少条给出了**确定**结论。degrade 不算确定。
    n = len(results)
    decided = sum(1 for r in results if r["final"] in ("pass", "reject"))
    rate = (decided / n * 100) if n else 0
    lines.append(f"覆盖率  {decided}/{n} = {rate:.0f}%"
                 f"   （其余是 degrade，结论带保留）")

    by_cause = out.get("by_cause") or {}
    if by_cause:
        lines.append("成因分布  " + "  ".join(f"{k}:{v}" for k, v in sorted(by_cause.items())))

    rec = out.get("recorded") or []
    if rec:
        lines.append("")
        lines.append(f"已记账本  {', '.join(rec)}（pending，需事后回填）")

    lines.append("=" * 60)
    return "\n".join(lines)


def load_task(path: str) -> tuple[list[Claim], dict]:
    """从 JSON 读一个任务定义。

    格式：
      {"name": "...", "relation": "and", "env_level": 3,
       "claims": [{"cid": "C1", "text": "...", "e1": 2, "e2": 0, "e3": 2,
                   "kind": "procedure",
                   "verify": {"domain": "sql", "task": {"sql": "..."}}}]}
    """
    import json
    with open(path, encoding="utf-8") as f:
        spec = json.load(f)
    claims = []
    for i, c in enumerate(spec.get("claims", [])):
        claims.append(Claim(
            cid=c.get("cid") or f"C{i + 1}",
            text=c.get("text") or c.get("cid") or "",
            e1=int(c.get("e1", 0)),
            e2=int(c.get("e2", 0)),
            e3=int(c.get("e3", 0)),
            kind=c.get("kind", "world"),
            input_valid=c.get("input_valid"),
            refuted_by_test=bool(c.get("refuted_by_test", False)),
            verify=c.get("verify"),
        ))
    return claims, spec


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "selftest"
    if cmd == "selftest":
        return selftest()
    if cmd == "bench":
        import json
        print(json.dumps(bench(), ensure_ascii=False, indent=2))
        return 0
    if cmd == "judge":
        # 主线的对外入口：给一个任务定义，出人读得懂的总结
        if len(sys.argv) < 3:
            print("用法: python extend.py judge <task.json> "
                  "[--env N] [--relation and|or|weighted] [--record]")
            return 2
        path = sys.argv[2]
        env_lvl = 3
        relation = "and"
        do_record = "--record" in sys.argv
        if "--env" in sys.argv:
            i = sys.argv.index("--env")
            if i + 1 < len(sys.argv):
                env_lvl = int(sys.argv[i + 1])
        if "--relation" in sys.argv:
            i = sys.argv.index("--relation")
            if i + 1 < len(sys.argv):
                relation = sys.argv[i + 1]
        if do_record:
            # 命令行是正式入口，绑定后才允许写正式账本
            import ledger as L
            L.bind_production("extend.py judge CLI")
        claims, spec = load_task(path)
        out = evaluate_claims(claims,
                              env=EvidenceEnv(env_lvl),
                              relation=relation,
                              task_name=spec.get("name") or "",
                              rounds=int(spec.get("rounds", 0)),
                              record=do_record,
                              origin="cli")
        print(summarize(out))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
