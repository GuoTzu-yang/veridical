#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
判定账本：把每次「判定 → 实际结果」落盘

之前的 calibrate() 吃的是硬编码在源码里的 8 条 OBSERVED。
那种写法没法攒样本——每加一条都要改代码。

这个账本改成 append-only JSONL：
  1. 判定时先记 pending（success=null）
  2. 事后回填 resolve(id, success)
  3. stats() 读全账本，喂给 calibrate()

跑法：
  python ledger.py seed      # 灌入已有 8 条历史记录（幂等）
  python ledger.py stats     # 看当前校准
  python ledger.py demo      # 记一条再回填，验证往返
"""

from __future__ import annotations

import json
import os
import re
import shutil
import time
import sys
import uuid
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from taskgraph import calibrate, wilson, prior_for  # noqa: E402, F401

HERE = os.path.dirname(os.path.abspath(__file__))
# 正式账本：只有它承载真实判定，也是先验与自评的唯一依据
PRODUCTION_LEDGER = os.path.join(HERE, "ledger.jsonl")
# 允许用环境变量指向别的账本——demo / 测试不该污染正式账本
LEDGER = os.environ.get("MODEL1_LEDGER") or PRODUCTION_LEDGER
CST = timezone(timedelta(hours=8))

# ---------------------------------------------------------------------------
# 写入门禁：测试样本不许混进正式账本
# ---------------------------------------------------------------------------
# 这个坑踩过五次（结论硬编码、校准脚本参数错、demo 写正式账本、
# 去重误删、MCP 闭环测试直接写进去）。每次都要手工清理，清理本身又可能出错。
#
# 第三十七轮先试了「按任务名识别测试」，但那是拿名字猜语义——
# 和第十三轮修掉的「靠错误消息文本判断错误类型」是同一类脆弱设计：
# 真名假样本拦不住，改个名字就绕过。
#
# 第三十八轮改成**默认拒绝**：进程必须显式声明"我在产出真实证据"，
# 才允许写正式账本。忘记声明 = 写不进去，而不是悄悄写进去。
# 只看真正说明"这是测试"的词。
# "临时" / "probe" 已剔除（第四十五轮）：`写一个临时文件` 是正常任务名，
# 拿它当测试标记会误杀真样本——门禁的名字层是兜底，不能比结构性那层还凶。
TEST_MARKERS = ("测试", "test", "demo", "自测", "闭环")

_PRODUCTION_BOUND = False
_BIND_REASON = ""


class ProductionWriteRefused(RuntimeError):
    """本进程没有绑定正式账本，或样本明显是测试。"""


def bind_production(reason: str = "") -> None:
    """允许本进程写正式账本。

    只有**真正产出证据**的入口该调用它：采集脚本、MCP 服务。
    测试、演示、自测一律不绑——这样它们即使忘了设 MODEL1_LEDGER，
    也写不进正式账本。
    """
    global _PRODUCTION_BOUND, _BIND_REASON
    _PRODUCTION_BOUND = True
    _BIND_REASON = reason


def production_bound() -> bool:
    return _PRODUCTION_BOUND


def _unbind() -> None:
    """撤销绑定（自测与临时切换用）。"""
    global _PRODUCTION_BOUND, _BIND_REASON
    _PRODUCTION_BOUND = False
    _BIND_REASON = ""


def _looks_like_test(task: str) -> bool:
    low = (task or "").lower()
    return any(m.lower() in low for m in TEST_MARKERS)


def _guard_write(task: str, origin: str | None = None) -> None:
    if LEDGER != PRODUCTION_LEDGER:
        return                       # 写到临时账本，随便
    if os.environ.get("MODEL1_ALLOW_TEST_WRITE") == "1":
        return                       # 人工放行
    # 第一层：调用方自己声明是测试 → 一律拒（哪怕进程已绑定）
    if origin == "test":
        raise ProductionWriteRefused(
            f"调用方声明 origin='test'，拒绝写正式账本：task={task!r}。\n"
            f"  测试请设 MODEL1_LEDGER 指向临时文件。"
        )
    # 第二层：没声明来源，又没绑定进程 → 拒
    if origin is None and not _PRODUCTION_BOUND:
        raise ProductionWriteRefused(
            f"本进程没有绑定正式账本，拒绝写入 {task!r}。\n"
            f"  产出证据的入口应调用 ledger.bind_production('原因')，\n"
            f"  或在 record(origin=...) 里显式声明来源；\n"
            f"  测试请设 MODEL1_LEDGER 指向临时文件：\n"
            f"    set MODEL1_LEDGER=%TEMP%\\m1_test.jsonl"
        )
    # 第三层：名字明显是测试，仍然拦（防止夹带）
    if _looks_like_test(task):
        raise ProductionWriteRefused(
            f"样本名像测试：task={task!r}（绑定={_BIND_REASON or '无'}，origin={origin}）。\n"
            f"  确实要写请设 MODEL1_ALLOW_TEST_WRITE=1。"
        )


def _now() -> str:
    return datetime.now(CST).isoformat(timespec="seconds")


def _load() -> list[dict]:
    if not os.path.exists(LEDGER):
        return []
    out = []
    with open(LEDGER, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def _append(rec: dict) -> None:
    with open(LEDGER, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def record(verdict: str, task: str = "", note: str = "",
           success: bool | None = None, evidence: str = "",
           env_level: int | None = None, cause: str | None = None,
           version: int | None = None,
           conclusion_verified: bool | None = None,
           group: str | None = None,
           origin: str | None = None,
           replay: dict | None = None,
           exec_ok: bool | None = None,
           prejudged: bool = False,
           counterfactual: bool = False,
           ask: list | None = None,
           criterion_right: bool | None = None,
           conclusion_held: bool | None = None,
           conclusion_checkable: bool | None = None,
           check_why: str = "") -> dict:
    """记一条判定。success=None 表示结果未知（pending）。

    env_level 必须记：L2 下判 degrade 和 L3 下判 degrade，成功率可能完全不同。
    cause 只在 verdict=degrade 时有意义：
      env  —— 本可 pass，被环境规则降级
      info —— 证据不足，闸门自己判的降级
    两者结果能差 7 倍（第十八轮实测 4/4 vs 1/7），混算等于把两件事当一件。

    version 记判据版本，默认取当前 MODEL_VERSION。不同版本判据产出的样本
    不该在同一个池子里算概率——v1 根本没有 cause 和 input_valid 这两维。

    conclusion_verified 是第三十二轮加的：**结论是否经得起复查**。
    success 记的是「任务是否做成」，但做成 ≠ 结论对——degrade 的语义是
    「结论带保留」，用 success 衡量它必然失真（实测 degrade 成功率与 pass
    完全持平）。这一项单独记「事后复查结论是否还成立」，三态同 success。
    旧的 degrade 样本没有这一项，按「未复查」处理，不参与该口径的统计。

    group 标实验分组。阴性对照里批次 c 和批次 b 是同一批任务、同一个结论，
    只把判据调高——这两组必须能分开统计，否则控制组会污染 pass 桶的推翻率。

    origin 声明这条样本**从哪来**（collect / case / mcp / cli / test）。
    它同时干两件事：
      1. 事后审计——账本里每条都能说清是谁写的
      2. 事前拦截——origin='test' 一律拒写正式账本，哪怕进程已经绑定
         （进程级开关区分不了同一进程里的不同调用方，这才是彻底的做法）

    prejudged=True 表示**先验证、后判 pass**。这类样本的 pass 不可能错——
    它没检验判据，只是把已验证的结论记了一遍。算 pass 精确率时必须排除，
    否则 100% 是同义反复，不是实测。（第五十二轮发现自己虚高了这个数）

    counterfactual=True 表示这条样本的 success 是**反事实**的：
    「如果能验，这任务会不会成」——不是「在当前环境里成不成」。

    典型来源：	ests/collect_env.py 按 L2 限制判定、却用 L3 权限执行。
    它证明了「这次降级是不必要的」，但回答不了「degrade/env 在这一档靠不靠得住」。
    混在一起算，会得到 L2 100% / L3 0% 这种方向相反的数。

    replay 存**机器可重跑的规格**：{"domain": "file", "task": {...}}。
    没有它，账本只能查自相矛盾，查不了"这条样本测得对不对"——
    因为 task 字段只是人读的文字。
    """
    from harness import MODEL_VERSION

    if verdict not in ("pass", "degrade", "reject"):
        raise ValueError(f"未知判定 {verdict}")
    if env_level is not None and env_level not in (0, 1, 2, 3):
        raise ValueError(f"未知环境档位 {env_level}")
    if cause is not None and verdict != "degrade":
        raise ValueError(f"cause 只对 degrade 有意义，当前 verdict={verdict}")
    if cause is not None and cause not in ("env", "info"):
        raise ValueError(f"未知成因 {cause}，只能是 env / info")
    _guard_write(task, origin)
    rid = "m1-" + uuid.uuid4().hex[:12]
    rec = {
        "id": rid,
        "ts": _now(),
        "verdict": verdict,
        "cause": cause,
        "version": version if version is not None else MODEL_VERSION,
        "conclusion_verified": conclusion_verified,
        "group": group,
        "origin": origin,
        "replay": replay,
        "exec_ok": exec_ok,
        "prejudged": prejudged,
        "counterfactual": counterfactual,
        "task": task,
        "note": note,
        "success": success,
        "evidence": evidence,
        "env_level": env_level,
        # 当时缺什么（第七十二轮）。
        # 只记「不行」，复盘时学不到东西；记下「缺哪一维、差几分」，
        # 下次才知道该先补哪儿。
        "ask": ask,
        # 第八十四轮把老字段 conclusion_verified 拆成两个。
        #
        # 原来一个字段被两拨脚本用两种意思填：
        #   case_l3_*   → judged_right：判据判 degrade **判得对不对**
        #   collect_*   → held：结论最终**有没有被推翻**
        # 这两件事答案可以相反，而且混在一起会让任何基于它的指标失去意义
        # （我据此建过一个"判据准确率"，把"结论被推翻"当成了"判据判错"）。
        #
        # 现在各归各：
        #   criterion_right —— 判据判得对不对（框架当时就有可能知道答案时）
        #   conclusion_held —— 结论最终成立不成立（能被复核时）
        "criterion_right": criterion_right,
        "conclusion_held": conclusion_held,
        # 第八十六轮：把"不可复核"从一种状态拆成三种。
        #   conclusion_held 不为 None      → 复核过，结论成立/不成立可知
        #   conclusion_checkable is False  → 明确**没法**复核（附原因）
        #   两个都是 None                   → 不知道是没复核还是不能复核
        # 以前这三种混在一起，报告里只体现为"少了几条"，缺口是看不见的。
        "conclusion_checkable": conclusion_checkable,
        "check_why": check_why,
    }
    _append(rec)
    return rec


def resolve(rid: str, success: bool, evidence: str = "") -> dict:
    """回填实际结果。账本是 append-only，所以这里追加一条 resolve 事件。"""
    # 必须查**折叠后的状态**，不能查原始事件流（第八十一轮修的 bug）。
    #
    # 原来这里用的是 _load()，也就是那一串 append-only 的原始行。
    # 原始行里，一条记录被 resolve 过之后，它自己那条 `success` 仍然是 None——
    # 因为有结果的是后面那条 resolve 事件。
    # 于是 `target.get("success") is not None` 永远为 False，
    # **同一条可以被回填两次**；而 entries() 折叠时又取最后一条，
    # 后一次 True/False 会把前一次静默覆盖，账本上一点矛盾痕迹都不留。
    #
    # 现在查 entries()：折叠后的 success 只要有值，就拒绝。
    state = {r["id"]: r for r in entries()}
    target = state.get(rid)
    if target is None:
        raise KeyError(f"账本里没有 {rid}")
    if target.get("success") is not None:
        raise ValueError(f"{rid} 已有结果，不重复回填")
    ev = {
        "id": rid,
        "ts": _now(),
        "op": "resolve",
        "success": bool(success),
        "evidence": evidence,
    }
    _append(ev)
    return ev


def entries() -> list[dict]:
    """把 append-only 的事件流折叠成当前状态。"""
    rows = _load()
    state: dict[str, dict] = {}
    order: list[str] = []
    for r in rows:
        rid = r.get("id")
        if not rid:
            continue
        if r.get("op") == "resolve":
            if rid in state:
                state[rid]["success"] = r["success"]
                state[rid]["evidence"] = r.get("evidence", "")
                state[rid]["resolved_at"] = r["ts"]
        else:
            if rid not in state:
                order.append(rid)
            state[rid] = dict(r)
    return [state[i] for i in order]


def stats(env_level: int | None = None, version: int | None = None,
          group: str | None = None, exclude_control: bool = False) -> dict:
    """统计账本。

    env_level=None 统计全部；传具体档位则只看该环境的样本。
    **跨环境混算先验是错的**——L2 的 degrade 和 L3 的 degrade 不是同一种东西。

    version 同理：v1 时期的样本是在没有 cause / input_valid 两维的判据下产生的，
    和 v2 的样本混算，等于把两种判据的结果当一件事。

    group 同理：阴性对照的样本必须能和正常样本分开，否则会互相污染。

    exclude_control=True 时剔除 CONTROL_GROUPS。
    这会改变结论：自然池 pass 精确率 89%，混入对照组后只有 78%——
    **对外报的应该是自然池的数**，对照组只是实验材料。
    """
    rows = entries()
    if env_level is not None:
        rows = [r for r in rows if r.get("env_level") == env_level]
    if version is not None:
        rows = [r for r in rows if r.get("version") == version]
    if group is not None:
        rows = [r for r in rows if r.get("group") == group]
    if exclude_control:
        rows = [r for r in rows if r.get("group") not in CONTROL_GROUPS]
    # 统计基数要排除两类：
    #   对照组（故意构造，不描述分布）—— precision 早排除了，这里也要排，
    #     否则 calibration 里 pass 会比 precision 里多出几条失败样本，两个数打架。
    #   反事实样本（success 答的是另一个问题）
    resolved = [r for r in rows if r.get("success") is not None
                and not r.get("counterfactual")
                and r.get("group") not in CONTROL_GROUPS]
    pending = [r for r in rows if r.get("success") is None]
    obs = [(r["verdict"], bool(r["success"]), r.get("note", "")) for r in resolved]
    cal = calibrate(obs) if obs else {}

    # 环境分布：让"样本来自哪个环境"变成可见事实，而不是埋在 evidence 字符串里
    by_env: dict[str, int] = {}
    for r in rows:
        key = f"L{r['env_level']}" if r.get("env_level") is not None else "unknown"
        by_env[key] = by_env.get(key, 0) + 1

    # 版本分布：不同版本判据产出的样本不该混算
    by_version: dict[str, int] = {}
    for r in rows:
        key = f"v{r['version']}" if r.get("version") is not None else "v?"
        by_version[key] = by_version.get(key, 0) + 1

    # 成因分布：degrade 拆成 env / info 两桶——它们的成功率能差 7 倍
    by_cause: dict[str, int] = {}
    for r in rows:
        if r["verdict"] == "degrade":
            key = r.get("cause") or "unknown"
            by_cause[key] = by_cause.get(key, 0) + 1

    # 来源分布：谁写的这条样本。
    # origin=None 的是第四十一轮之前的老样本——那时还没有来源声明，
    # 这一栏把"有多少条说不清来源"变成可见数字，而不是假装都可信。
    by_origin: dict[str, int] = {}
    for r in rows:
        key = r.get("origin") or "未声明"
        by_origin[key] = by_origin.get(key, 0) + 1

    # 按 (判定, 成因) 分别校准
    buckets: dict[str, list[bool]] = {}
    for r in resolved:
        key = r["verdict"]
        if key == "degrade":
            key = f"degrade/{r.get('cause') or 'unknown'}"
        buckets.setdefault(key, []).append(bool(r["success"]))
    cal_by_cause = {}
    for key, oks in buckets.items():
        n = len(oks)
        succ = sum(1 for x in oks if x)
        lo, hi = wilson(succ, n)
        cal_by_cause[key] = {
            "n": n, "success": succ,
            "laplace": round((succ + 1) / (n + 2), 3),
            "wilson_lo": round(lo, 3), "wilson_hi": round(hi, 3),
        }

    # 结论复查：degrade 的正确度量（第三十二轮）
    # success 只说「任务做成」，做成 ≠ 结论对。这一项单独记「事后结论是否还成立」。
    cc: dict[str, dict] = {}
    for r in resolved:
        key = r["verdict"]
        if key == "degrade":
            key = f"degrade/{r.get('cause') or 'unknown'}"
        b = cc.setdefault(key, {"n": 0, "verified": 0, "overturned": 0, "unchecked": 0})
        b["n"] += 1
        cv = r.get("conclusion_verified")
        if cv is None:
            b["unchecked"] += 1
        elif cv:
            b["verified"] += 1
        else:
            b["overturned"] += 1

    # --- 精确率：必须把两类样本剔掉 ---
    #   1. 阴性对照组（故意构造的，不描述自然分布）
    #   2. 「先验证后判 pass」的样本——它的 pass 不可能错，
    #      混进来会把精确率抬成同义反复的 100%
    tested = [r for r in resolved
              if not r.get("prejudged") and not r.get("counterfactual")
              and r.get("group") not in CONTROL_GROUPS]
    pre = [r for r in resolved if r.get("prejudged")]
    # 反事实样本单独统计：它回答的是「如果能验会不会成」
    # 从 rows 算，不从 resolved —— resolved 已经把它们排掉了
    cf_rows = [r for r in rows if r.get("success") is not None
               and r.get("counterfactual")]
    cf = {"n": len(cf_rows),
          "success": sum(1 for r in cf_rows if r["success"]),
          "note": "success 是反事实的（如果能验会不会成），不与其他样本混算"}
    precision: dict[str, dict] = {}
    for verdict in ("pass", "reject"):
        ss = [r for r in tested if r["verdict"] == verdict]
        if ss:
            correct = sum(1 for r in ss if bool(r["success"]) == (verdict == "pass"))
            lo, hi = wilson(correct, len(ss))
            precision[verdict] = {
                "n": len(ss), "correct": correct,
                "precision": round(correct / len(ss), 3),
                "wilson_lo": round(lo, 3), "wilson_hi": round(hi, 3)}

    # ---- 判据准不准，和"这批主张碰巧有多少是真的"，是两件事 ----
    #
    # 第八十三轮才想明白的一处长期误读：
    #   calibration（成功率）  = 这批落进 degrade 的主张，**碰巧**有多少是真的
    #   criterion_accuracy     = 判据判 degrade 判得对不对
    #
    # 对**盲判**样本（qb 53 条），后者**没有定义**：
    # 框架当时确实不知道，它说"证据不足"是**正确行为**，
    # 验证后发现主张为真，那是真的，与判据准不准无关。
    #
    # 只有"已知答案还去判"的样本（case / collect 这类），
    # 才谈得上判对率 —— 它们填了 conclusion_verified。
    #
    # 把这两件事混在一个数里读，就会得出"degrade 判错率 30%"这种
    # 既不是判据的错、也不是样本的错的结论。
    _cv = [r for r in resolved if r.get("conclusion_verified") is not None]
    _cv_ok = sum(1 for r in _cv if r.get("conclusion_verified"))
    _cv_by_origin: dict[str, list[int]] = {}
    for r in _cv:
        a = _cv_by_origin.setdefault(r.get("origin") or "未声明", [0, 0])
        a[0] += 1
        a[1] += 1 if r.get("criterion_right") else 0
    criterion_accuracy = {
        "n": len(_cv),
        "correct": _cv_ok,
        "rate": round(_cv_ok / len(_cv), 3) if _cv else None,
        "by_origin": {k: {"n": v[0], "correct": v[1],
                          "rate": round(v[1] / v[0], 3) if v[0] else None}
                      for k, v in sorted(_cv_by_origin.items())},
        "note": ("只统计填了 criterion_right 的样本；"
                 "盲判样本没有这个字段，因为它们当时确实不知道，"
                 "判『不知道』不算错也不算对"),
    }

    return {
        "total": len(rows),
        "resolved": len(resolved),
        "pending": len(pending),
        "criterion_accuracy": criterion_accuracy,
        "overturn_rate": overturn_rate(env_level=env_level, version=version),
        "calibration": cal,
        "calibration_by_cause": cal_by_cause,
        "conclusion_check": cc,
        "precision": precision,
        "prejudged_excluded": len(pre),
        "counterfactual": cf,
        "by_env": by_env,
        "by_cause": by_cause,
        "by_version": by_version,
        "by_origin": by_origin,
        "filter": "/".join(
            [f"L{env_level}" if env_level is not None else "全部环境",
             f"v{version}" if version is not None else "全部版本"]
            + (["排除对照组"] if exclude_control else [])),
    }


# ---------------------------------------------------------------------------
# 账本驱动先验：样本够了就自动替换硬编码的三个数
# ---------------------------------------------------------------------------
MIN_SAMPLES = 5   # 少于这个数，样本的波动比硬编码更不可靠

# 阴性对照组：故意把同一批任务换个判法重判的重复测量。
# 它们用来**检验判据**（对照实验），不描述自然分布，
# 混进先验池会把先验拉到失真（实测 pass 从 0.917 被拉到 0.739）。
# 所以先验只用 group 不在这张表里的样本。
CONTROL_GROUPS = ("c", "d")


HISTORY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "ledger-history")


def backup(reason: str) -> str:
    """给当前账本留一份带原因的备份，返回备份路径。

    为什么做成函数（第七十六轮）：
        这轮我清样本前没备份，脚本半路断言失败，`补充·` 那 3 条
        一度是真的丢了——后来靠"脚本还能重跑"侥幸救回来。
        **侥幸不是机制。**

        现在的规矩：任何会删记录的操作，都先调这个；
        它失败就拒绝删。
    """
    os.makedirs(HISTORY_DIR, exist_ok=True)
    safe = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", reason)[:40] or "backup"
    stamp = time.strftime("%Y%m%d-%H%M%S")
    dst = os.path.join(HISTORY_DIR, f"ledger.jsonl.{stamp}.bak-{safe}")
    shutil.copy2(LEDGER, dst)
    # 备份必须能读回来，否则等于没备
    with open(dst, encoding="utf-8") as f:
        if sum(1 for _ in f) < 1:
            raise OSError(f"备份文件是空的：{dst}")
    return dst


def prune(prefixes: tuple[str, ...], apply: bool = False,
          reason: str = "prune") -> dict:
    """按任务名前缀删记录，**默认只预览**。

    先备份，备份失败就不删。删完再做一次自检：
    被删的条数必须等于预演时算出的条数，否则报错（宁可多报警）。
    """
    rows = [json.loads(l) for l in open(LEDGER, encoding="utf-8") if l.strip()]
    hit = [r for r in rows
           if any((r.get("task") or "").startswith(p) for p in prefixes)]
    keep = [r for r in rows if r not in hit]

    out = {"would_delete": len(hit), "remain": len(keep),
           "sample": [(r.get("task") or "")[:36] for r in hit[:5]],
           "backup": None, "deleted": 0}
    if not apply:
        return out

    out["backup"] = backup(f"{reason}-{'/'.join(prefixes)}")
    with open(LEDGER, "w", encoding="utf-8", newline="\n") as f:
        f.write("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in keep))

    after = [json.loads(l) for l in open(LEDGER, encoding="utf-8") if l.strip()]
    out["deleted"] = len(rows) - len(after)
    if out["deleted"] != out["would_delete"]:
        raise OSError(f"删除条数对不上：预演 {out['would_delete']}，"
                      f"实际 {out['deleted']}（备份在 {out['backup']}）")
    return out


def _print_prune(r: dict, applied: bool) -> None:
    print("=" * 72)
    print("清样本" + ("（已执行）" if applied else "（预演，未动账本）"))
    print("=" * 72)
    print(f"  命中 {r['would_delete']} 条，清完剩 {r['remain']} 条")
    for s in r["sample"]:
        print(f"    · {s}")
    if applied:
        print(f"  备份：{r['backup']}")
        print(f"  实际删除：{r['deleted']} 条（与预演一致）")
    else:
        print("  要真删加 --apply —— 删之前会自动备份")
    print("=" * 72)


def blockers(env_level: int | None = None,
             version: int | None = None) -> dict:
    """账本里被拦住的主张，最常缺哪一维。

    为什么要这个（第七十二轮）：
        单看"degrade 占 60%"，只知道结论保留得多，不知道该改什么。
        把每条记录的 `ask` 汇总起来，才看得出**系统性的短板在哪儿**——
        是缺出处（e1）、缺独立来源（e2），还是缺复现（e3）。

        这直接决定下一步该造什么工具：
        如果 70% 卡在 e3，那该做的是"能真跑"的验证器；
        如果卡在 e2，那该做的是"找第二来源"，检索库正好干这个。
    """
    from harness import MODEL_VERSION

    ver = MODEL_VERSION if version is None else version
    rows = [r for r in entries() if r.get("op") != "resolve"]
    if env_level is not None:
        rows = [r for r in rows if r.get("env_level") == env_level]
    rows = [r for r in rows if r.get("version") == ver]

    with_ask = [r for r in rows if r.get("ask")]
    per_dim: dict[str, int] = {}
    solo: dict[str, int] = {}
    for r in with_ask:
        seen = set()
        for a in r["ask"]:
            d = a.get("dim")
            if d and d not in seen:      # 一条样本里同一维只算一次
                seen.add(d)
                per_dim[d] = per_dim.get(d, 0) + 1
                if a.get("solo"):
                    solo[d] = solo.get(d, 0) + 1

    # 同构样本不算多次观测（第七十四轮）。
    # 10 条样本如果缺口组合完全一样，那只是**同一次观测**重复了 10 遍，
    # 拿它的计数去比大小，等于把 1 票说成 10 票——就是 e2 那条规矩
    # （同一仓库的多个文件不算独立来源）用在统计自己身上。
    sigs: dict[tuple, int] = {}
    for r in with_ask:
        key = tuple(sorted({a.get("dim") for a in r["ask"] if a.get("dim")}))
        sigs[key] = sigs.get(key, 0) + 1
    distinct = len(sigs)

    total = len(per_dim and with_ask or with_ask) or 0
    ranked = sorted(per_dim.items(), key=lambda kv: -kv[1])
    # 并列必须如实说成并列。
    # 上一版只取 ranked[0][0]，e2 和 e3 都是 10 次时它会随便报一个"最常缺 e2"——
    # 这等于用一个平局编出一个结论。
    # 排名要按「不同缺口组合」算，不能按条数算。
    # 否则 10 条同构样本会把某一维抬到 10 分，而它其实只是 1 次观测。
    sig_dim: dict[str, int] = {}
    for key in sigs:
        for d in key:
            if d and d != "—":
                sig_dim[d] = sig_dim.get(d, 0) + 1
    ranked_sig = sorted(sig_dim.items(), key=lambda kv: (-kv[1], kv[0]))
    _max = ranked_sig[0][1] if ranked_sig else 0
    tops = [k for k, v in ranked_sig if v == _max] if ranked_sig else []
    return {
        "rows": len(rows),
        "with_ask": len(with_ask),
        "coverage": round(len(with_ask) / len(rows), 3) if rows else 0.0,
        "per_dim": dict(ranked),
        "solo": solo,
        "per_dim_sig": dict(ranked_sig),
        "distinct_signatures": distinct,
        "signatures": {"+".join(k) or "—": v for k, v in
                       sorted(sigs.items(), key=lambda kv: -kv[1])},
        "effective_n": distinct,
        "tops": tops,
        "top": tops[0] if len(tops) == 1 else None,
        "note": ("只有记了 ask 的样本能统计；老样本没这个字段"
                 if len(with_ask) < len(rows) else "全部样本都带建议"),
    }


def duplicate_resolves() -> list[dict]:
    """查有没有样本被回填过不止一次。

    为什么留着这个检查（第八十二轮）：
        第八十一轮修掉的那个 bug —— resolve() 查的是原始事件流，不是折叠状态，
        所以同一条能被回填两次，后一次静默覆盖前一次。
        修完之后**应该永远查不到**。

        但"修完之后查不到"和"从来没发生过"是两件事：
        这个检查的意义是，如果哪天代码又退回去，它会在审计里冒出来。

    返回 [{id, times, values, conflict}, ...]。conflict=True 表示两次结果互相矛盾。
    """
    rows = [r for r in _load() if r.get("op") == "resolve"]
    seen: dict[str, list] = {}
    for r in rows:
        rid = r.get("id")
        if rid:
            seen.setdefault(rid, []).append(r.get("success"))
    out = []
    for rid, vals in seen.items():
        if len(vals) > 1:
            out.append({"id": rid, "times": len(vals), "values": vals,
                        "conflict": len(set(bool(v) for v in vals)) > 1})
    return out


def criterion_accuracy(env_level: int | None = None,
                       version: int | None = None) -> dict:
    """判据准不准（只对"已知答案还去判"的样本有意义）。

    与 calibration 的区别：
        calibration      —— 这批主张碰巧有多少是真的
        criterion_accuracy —— 判据判得对不对

    盲判样本（qb 那 53 条）没有 conclusion_verified，因为它们当时
    确实不知道；说"证据不足"是**正确行为**，不该算成对或错。
    """
    from harness import MODEL_VERSION
    ver = MODEL_VERSION if version is None else version
    rows = [r for r in entries() if r.get("op") != "resolve"]
    if env_level is not None:
        rows = [r for r in rows if r.get("env_level") == env_level]
    rows = [r for r in rows if r.get("version") == ver
            and r.get("success") is not None
            and r.get("group") not in CONTROL_GROUPS
            and not r.get("prejudged")
            and not r.get("counterfactual")]
    cv = [r for r in rows if r.get("criterion_right") is not None]
    ok = sum(1 for r in cv if r.get("criterion_right"))
    by: dict[str, list[int]] = {}
    for r in cv:
        a = by.setdefault(r.get("origin") or "未声明", [0, 0])
        a[0] += 1
        a[1] += 1 if r.get("criterion_right") else 0
    return {"n": len(cv), "correct": ok,
            "rate": round(ok / len(cv), 3) if cv else None,
            "by_origin": {k: {"n": v[0], "correct": v[1],
                              "rate": round(v[1] / v[0], 3) if v[0] else None}
                          for k, v in sorted(by.items())},
            "note": "只统计填了 criterion_right 的样本；盲判样本不在内"}


def overturn_rate(env_level: int | None = None,
                  version: int | None = None) -> dict:
    """degrade 之后被**实测推翻**的比例 —— 这才是 degrade 该管的量。

    与 criterion_accuracy 的分工：
        criterion_right —— 判据判得对不对（框架当时就有可能知道答案时）
        overturn_rate   —— 结论最后被推翻了多少（能被复核时）

    推翻率越低，说明"判成保留"的那批里结论越经得起站。
    对盲判样本尤其重要：它们当时说"证据不足"，
    验证后一半以上真被推翻的话，说明那些证据其实拿得到。
    """
    from harness import MODEL_VERSION
    ver = MODEL_VERSION if version is None else version
    rows = [r for r in entries() if r.get("op") != "resolve"]
    if env_level is not None:
        rows = [r for r in rows if r.get("env_level") == env_level]
    rows = [r for r in rows if r.get("version") == ver
            and r.get("success") is not None
            and r.get("group") not in CONTROL_GROUPS
            and not r.get("prejudged")
            and not r.get("counterfactual")]
    deg = [r for r in rows if r["verdict"] == "degrade"]
    ck = [r for r in deg if r.get("conclusion_held") is not None]
    held = sum(1 for r in ck if r.get("conclusion_held"))
    by: dict[str, list[int]] = {}
    for r in ck:
        a = by.setdefault(r.get("origin") or "未声明", [0, 0])
        a[0] += 1
        a[1] += 1 if r.get("conclusion_held") else 0
    # 不可复核的那几条，说清楚是"没法"还是"没做"
    no_ck = [r for r in deg if r.get("conclusion_held") is None]
    cannot = [r for r in no_ck if r.get("conclusion_checkable") is False]
    unknown = [r for r in no_ck if r.get("conclusion_checkable") is None]
    why: dict[str, int] = {}
    for r in cannot:
        k = (r.get("check_why") or "未说明原因")[:40]
        why[k] = why.get(k, 0) + 1

    return {
        "degrade": len(deg),
        "checkable": len(ck),
        "held": held,
        "overturned": len(ck) - held,
        "cannot_check": len(cannot),
        "unknown_check": len(unknown),
        "cannot_by_reason": dict(sorted(why.items(), key=lambda kv: -kv[1])),
        "rate": round((len(ck) - held) / len(ck), 3) if ck else None,
        "by_origin": {k: {"n": v[0], "held": v[1],
                          "overturn_rate": round((v[0] - v[1]) / v[0], 3) if v[0] else None}
                      for k, v in sorted(by.items())},
        "note": "只统计能复核的 degrade；判据准不准请看 criterion_accuracy",
    }


def coverage(env_level: int | None = None,
             version: int | None = None) -> dict:
    """两段覆盖率：一次判完多少有结论，复核之后又能多出多少。

    为什么不能只报一个"覆盖率"（第六十五轮）：
        之前报的覆盖率 = (pass + reject) / 全部 = 72%。
        但 degrade 里 **59/76 条带可复核规格** —— 跑一遍就有结论了。

        把"暂时没结论"和"永远没结论"混成一个数，会低估这套东西能干什么，
        也会让「再补样本」这个方向看起来比实际更划算。

    两个数：
        first_pass   —— 一次判完就给出确定结论的比例
        after_verify —— 把带规格的 degrade 复核掉之后的比例
    """
    from probe import replayable
    from harness import MODEL_VERSION

    ver = MODEL_VERSION if version is None else version
    rows = [r for r in entries() if r.get("op") != "resolve"]
    if env_level is not None:
        rows = [r for r in rows if r.get("env_level") == env_level]
    rows = [r for r in rows if r.get("version") == ver
            and r.get("success") is not None
            and r.get("group") not in CONTROL_GROUPS
            and not r.get("prejudged")
            and not r.get("counterfactual")]

    total = len(rows)
    determinate = [r for r in rows if r["verdict"] in ("pass", "reject")]
    degrade = [r for r in rows if r["verdict"] == "degrade"]

    verifiable, stuck = [], []
    for r in degrade:
        spec = r.get("replay")
        if spec and replayable(spec.get("domain"), spec.get("task") or {}):
            verifiable.append(r)
        else:
            stuck.append(r)

    after = len(determinate) + len(verifiable)
    return {
        "total": total,
        "determinate": len(determinate),
        "degrade": len(degrade),
        "verifiable": len(verifiable),
        "stuck": len(stuck),
        "first_pass": round(len(determinate) / total, 3) if total else 0.0,
        "after_verify": round(after / total, 3) if total else 0.0,
        "stuck_examples": [(r.get("task") or "")[:36] for r in stuck[:5]],
    }


def pooling_check(env_level: int | None = None, version: int | None = None,
                  by: str = "origin") -> dict:
    """同一档位下按来源拆开，检查**能不能合并成一个先验**。

    存在的理由（第五十三轮发现）：
        degrade/info 一个桶里，
          case     1/7  = 14%
          collect 11/18 = 61%
          qb      20/28 = 71%
        先验把它压成 0.481——**这个数不代表任何一类样本**。

    判据：各组 Wilson 95% 区间**两两有交集**才算可合并。
    有任意两组区间不重叠，就说明它们不是同一个分布的样本，
    合并出来的数不能用来预测任何一组。

    这不是"更精确的先验"，是**别拿平均数冒充结论**。
    """
    from harness import MODEL_VERSION

    rows = [r for r in entries() if r.get("op") != "resolve"]
    if env_level is not None:
        rows = [r for r in rows if r.get("env_level") == env_level]
    ver = MODEL_VERSION if version is None else version
    rows = [r for r in rows if r.get("version") == ver]
    rows = [r for r in rows if r.get("success") is not None
            and r.get("group") not in CONTROL_GROUPS
            and not r.get("prejudged")
            and not r.get("counterfactual")]

    groups: dict[tuple[str, str], list[bool]] = {}
    for r in rows:
        k = r["verdict"]
        if k == "degrade":
            k = f"degrade/{r.get('cause') or 'unknown'}"
        sub = r.get(by) or "未声明"
        groups.setdefault((k, sub), []).append(bool(r["success"]))

    out: dict[str, dict] = {}
    for verdict in sorted({k for k, _ in groups}):
        subs = {s: v for (k, s), v in groups.items() if k == verdict}
        detail = {}
        for s, oks in sorted(subs.items()):
            n = len(oks)
            succ = sum(1 for x in oks if x)
            lo, hi = wilson(succ, n)
            detail[s] = {"n": n, "success": succ,
                         "rate": round(succ / n, 3) if n else 0.0,
                         "wilson_lo": round(lo, 3), "wilson_hi": round(hi, 3)}

        keys = list(detail)
        disjoint = []
        for i in range(len(keys)):
            for j in range(i + 1, len(keys)):
                a, b = detail[keys[i]], detail[keys[j]]
                if a["wilson_hi"] < b["wilson_lo"] or b["wilson_hi"] < a["wilson_lo"]:
                    disjoint.append((keys[i], keys[j]))

        n_all = sum(d["n"] for d in detail.values())
        succ_all = sum(d["success"] for d in detail.values())
        out[verdict] = {
            "groups": detail,
            "pooled": round(succ_all / n_all, 3) if n_all else 0.0,
            "poolable": not disjoint,
            "disjoint_pairs": disjoint,
        }
    return {"by": by, "env_level": env_level, "version": ver, "verdicts": out}


def _print_blockers(b: dict) -> None:
    print("=" * 72)
    print("瓶颈定位 · 被拦住的主张最常缺哪一维")
    print("=" * 72)
    if not b["rows"]:
        print("  没有记录")
        return
    print(f"  记录 {b['rows']} 条，其中带建议的 {b['with_ask']} 条"
          f"（{b['coverage']*100:.0f}%）")
    if not b["per_dim"]:
        print("  没有可统计的建议")
    else:
        HOW = {
            "e1": "指到具体位置（文件+行号 / 出处链接）",
            "e2": "找第二个独立来源（不同团队、不同仓库）",
            "e3": "真跑一次并留下可复现记录",
        }
        for dim, n in b["per_dim"].items():
            bar = "#" * min(40, n)
            print(f"    {dim}  {n:>4}  {bar}  {HOW.get(dim, '')}")
        print()
        # 单独补哪一维就够 —— 比"哪维出现得多"更接近能行动的东西
        solo = b.get("solo") or {}
        if solo:
            print()
            print("  单独补这一维就能过闸的条数：")
            for d, n in sorted(solo.items(), key=lambda kv: -kv[1]):
                print(f"    {d}  {n:>4} 条")

        # 同构样本不算多次观测
        n_ask, n_sig = b["with_ask"], b.get("distinct_signatures", b["with_ask"])
        if n_ask and n_sig < n_ask:
            print()
            print(f"  **同构提醒**：{n_ask} 条建议只有 {n_sig} 种不同缺口组合，"
                  f"有效样本量按 {n_sig} 算")
            for sig, cnt in (b.get("signatures") or {}).items():
                print(f"     {sig:<12} {cnt} 条")
            print("     同一组合重复多次只算一票——"
                  "这是 e2 那条规矩用在统计自己身上")

        ps = b.get("per_dim_sig") or {}
        if ps:
            print()
            print("  按不同缺口组合计数（才是排名依据）：")
            for d, n in ps.items():
                print(f"    {d}  {n:>4} 种组合")

        tops = b.get("tops") or []
        eff = b.get("effective_n", b["with_ask"])
        if eff <= 1:
            # 只有一种缺口组合时，任何"哪维更多"的说法都是同一次观测在自我重复。
            print(f"  **有效样本量不足**：只有 {eff} 种缺口组合，分不出先后")
            print("  这不是并列，是还没有第二个独立观测")
        elif len(tops) == 1:
            print(f"  最常缺：{tops[0]} —— 下一步该优先造「{HOW.get(tops[0], '')}」的工具")
        elif len(tops) > 1:
            print(f"  并列最常缺：{'、'.join(tops)}"
                  f"（各 {max(b['per_dim'].values())} 次）")
            print("  **平局不下结论** —— 样本再多一点才能分出先后")
        else:
            print("  没有可统计的建议")
    print(f"  说明：{b['note']}")
    print("=" * 72)


def _print_pooling(res: dict) -> int:
    tag = f"L{res['env_level']}" if res["env_level"] is not None else "全部环境"
    print("=" * 74)
    print(f"先验可合并性检查 · {tag} · v{res['version']} · 按 {res['by']} 拆")
    print("=" * 74)
    bad = 0
    for verdict, d in res["verdicts"].items():
        mark = "可合并" if d["poolable"] else "**不可合并**"
        print(f"\n  {verdict}   合并值 {d['pooled']:.3f}   {mark}")
        for s, g in d["groups"].items():
            print(f"    {s:<12} {g['success']}/{g['n']} = {g['rate']*100:5.1f}%"
                  f"   Wilson[{g['wilson_lo']}, {g['wilson_hi']}]")
        if not d["poolable"]:
            bad += 1
            for a, b in d["disjoint_pairs"]:
                print(f"    ✗ {a} 与 {b} 的区间不重叠——不是同一个分布")
    print()
    print("=" * 74)
    if bad:
        print(f"{bad} 个桶不能合并。合并值只能当「全体平均」，不能预测任何一组。")
    else:
        print("各桶内部各组区间都有交集，合并是合理的。")
    print("=" * 74)
    return 0 if not bad else 1


def current_prior(base: dict[str, float] | None = None,
                  env_level: int | None = None,
                  version: int | None = None) -> tuple[dict, dict]:
    """从账本算当前先验。

    返回 (prior, detail)。detail 说明每个桶是"账本来的"还是"沿用硬编码"。

    样本 < MIN_SAMPLES 的桶不覆盖——4 个样本算出来的 0.833 比拍出来的 0.65
    更不可信，因为它的 Wilson 区间宽到 [0.51, 1.0]。

    env_level 非空时只采信该环境下的样本：跨环境混算会把 L2 的宽松当成人人都宽松。

    version **默认取当前 MODEL_VERSION**，不取全部。v1 的样本是在没有 cause /
    derive_e3 / 三态 input_valid 的判据下产生的，用它们决定 v2 的先验，
    等于拿旧尺子的刻度去量新尺子。传 version=None 显式表示"要混算"。

    key 可能是 "degrade/env"、"degrade/info" 这样的复合键——第十九轮实测这两者
    差 4 倍（0.833 vs 0.222），按 verdict 混算得到的中间值没有物理意义。
    取值用 prior_for()，它会先查复合键再回落到 verdict。
    """
    from taskgraph import VERDICT_PRIOR as DEFAULT
    from harness import MODEL_VERSION

    v = MODEL_VERSION if version is None else version
    prior = dict(base or DEFAULT)
    # 先验只用自然样本：排除阴性对照组（重复测量，不描述分布）
    rows = [r for r in entries()
            if (env_level is None or r.get("env_level") == env_level)
            and r.get("version") == v
            and r.get("group") not in CONTROL_GROUPS
            and not r.get("counterfactual")]
    resolved = [r for r in rows if r.get("success") is not None]
    obs = [(r["verdict"], bool(r["success"]), r.get("note", "")) for r in resolved]
    s = {"calibration": calibrate(obs) if obs else {}}
    buckets: dict[str, list[bool]] = {}
    for r in resolved:
        key = r["verdict"]
        if key == "degrade":
            key = f"degrade/{r.get('cause') or 'unknown'}"
        buckets.setdefault(key, []).append(bool(r["success"]))
    s["calibration_by_cause"] = {}
    for key, oks in buckets.items():
        nn = len(oks)
        sc = sum(1 for x in oks if x)
        lo, hi = wilson(sc, nn)
        s["calibration_by_cause"][key] = {
            "n": nn, "success": sc, "laplace": round((sc + 1) / (nn + 2), 3),
            "wilson_lo": round(lo, 3), "wilson_hi": round(hi, 3)}
    detail = {}

    # 先查每个桶能不能合并。不可合并的桶不覆盖先验——
    # 拿三种不同分布的平均数去预测其中任何一组，比沿用默认值更糟。
    # （第五十三轮实测：degrade/info 里 case 14% vs qb 71%，区间不重叠）
    try:
        pool = pooling_check(env_level=env_level, version=v)
        poolable = {k: d["poolable"] for k, d in pool["verdicts"].items()}
    except Exception:  # noqa: BLE001
        poolable = {}

    # 再按复合键（带 cause）填
    for key, c in s.get("calibration_by_cause", {}).items():
        if key in poolable and not poolable[key]:
            # 混合桶：先验直接回落到默认值，别让 prior_for 拿到平均数
            prior[key] = DEFAULT.get(key.split("/")[0])
            detail[key] = {"source": "default(mixed)", "n": c["n"], "version": v,
                           "value": prior[key],
                           "default": DEFAULT.get(key.split("/")[0]),
                           "why": "各组区间不重叠，合并值不预测任何一组"}
            continue
        if c["n"] >= MIN_SAMPLES:
            prior[key] = c["laplace"]
            detail[key] = {"source": "ledger", "n": c["n"], "version": v,
                           "value": c["laplace"], "default": DEFAULT.get(key.split("/")[0])}
        else:
            detail[key] = {"source": "default", "n": c["n"], "version": v,
                           "value": DEFAULT.get(key.split("/")[0]),
                           "default": DEFAULT.get(key.split("/")[0])}

    # 再补 verdict 级（没有 cause 拆分的桶）
    for name in ("pass", "degrade", "reject"):
        # 只要有一个 cause 子桶是混合的，verdict 级也是混合的——
        # 把混合子桶再平均一次，得不到更可靠的东西。
        subs_mixed = [k for k, d in detail.items()
                      if k.startswith(name + "/") and d.get("source") == "default(mixed)"]
        if subs_mixed:
            prior[name] = DEFAULT.get(name)
            detail.setdefault(name, {
                "source": "default(mixed)", "n": 0, "version": v,
                "value": prior[name], "default": DEFAULT.get(name),
                "why": f"子桶 {subs_mixed} 已不可合并"})
            continue
        if any(k.startswith(name + "/") and detail.get(k, {}).get("source") == "ledger"
               for k in detail):
            continue
        if name in poolable and not poolable[name]:
            detail.setdefault(name, {"source": "default(mixed)", "n": 0, "version": v,
                                     "value": prior.get(name), "default": DEFAULT.get(name),
                                     "why": "各组区间不重叠"})
            continue
        c = s["calibration"].get(name)
        if c and c["n"] >= MIN_SAMPLES:
            prior[name] = c["laplace"]
            detail[name] = {"source": "ledger", "n": c["n"], "version": v,
                            "value": c["laplace"], "default": DEFAULT.get(name)}
        else:
            detail.setdefault(name, {"source": "default", "n": (c["n"] if c else 0),
                                     "version": v,
                                     "value": prior.get(name), "default": DEFAULT.get(name)})
    return prior, detail


# prior_for 定义在 taskgraph（那边不吃 ledger，避免循环 import）


# ---------------------------------------------------------------------------
# seed：把之前硬编码的 8 条历史记录灌进来（幂等）
# 全部产自 L2 环境——本地无可执行实例、无 GitHub 账号，只能读到源码
# ---------------------------------------------------------------------------
SEED = [
    ("degrade", "case_train T1 部署UUID", True,  "2026-11-06 提测 30.000", 2),
    ("degrade", "case_train T2 Fork",     True,  "2026-11-06 提测 30.000", 2),
    ("degrade", "case_train T3 PR",       True,  "2026-11-06 提测 30.000", 2),
    ("degrade", "calib S1 真UUID",        True,  "calibrate_procedure.py", 2),
    ("reject",  "calib S2 伪UUID",        False, "calibrate_procedure.py", 2),
    ("reject",  "calib S3 格式错",        False, "calibrate_procedure.py", 2),
    ("reject",  "calib S4 空值",          False, "calibrate_procedure.py", 2),
    ("reject",  "calib S5 已认领",        False, "calibrate_procedure.py", 2),
]


def seed() -> int:
    existing = {(r["verdict"], r["task"]) for r in entries()}
    added = 0
    for verdict, task, ok, ev, env in SEED:
        if (verdict, task) in existing:
            continue
        record(verdict, task=task, success=ok, evidence=ev, env_level=env)
        added += 1
    return added


def guard_selftest() -> int:
    """验证写入门禁：测试样本不许进正式账本。"""
    global LEDGER
    import tempfile

    fails = []

    def check(name, cond, detail=""):
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  — {detail}" if detail else ""))
        if not cond:
            fails.append(name)

    saved_ledger = LEDGER
    saved_allow = os.environ.pop("MODEL1_ALLOW_TEST_WRITE", None)
    print("=" * 72)
    print("GUARD  正式账本默认拒绝写入")
    print("=" * 72)
    print(f"  正式账本: {os.path.basename(PRODUCTION_LEDGER)}")
    print(f"  当前账本: {os.path.basename(LEDGER)}")

    try:
        # 第一层：没绑定 → 一律拒写（哪怕名字看起来正常）
        LEDGER = PRODUCTION_LEDGER
        _unbind()
        for nm in ("v2收集·真名样本", "闭环测试_X"):
            try:
                record("pass", task=nm, success=True, env_level=3)
                refused = False
            except ProductionWriteRefused:
                refused = True
            check(f"未绑定 → 拒绝 {nm!r}", refused)

        # 第二层：绑定了，但名字明显像测试 → 仍拒
        bind_production("自测")
        for nm in ("闭环测试_X", "自测样本", "demo run", "test case"):
            try:
                record("pass", task=nm, success=True, env_level=3)
                refused = False
            except ProductionWriteRefused:
                refused = True
            check(f"已绑定但名像测试 → 拒绝 {nm!r}", refused)

        # 正常任务名不该被误杀（"临时" 是常见词，不是测试标记）
        for nm in ("file收集·F4 写一个临时文件", "http收集·H1 访问 github.com"):
            LEDGER = os.path.join(tempfile.gettempdir(), "m1_guard_ok.jsonl")
            if os.path.exists(LEDGER):
                os.remove(LEDGER)
            try:
                record("pass", task=nm, success=True, env_level=3)
                okname = True
            except Exception:
                okname = False
            check(f"正常任务名不被误杀 {nm[:18]!r}", okname)
        LEDGER = PRODUCTION_LEDGER

        # 第三层：绑定了、名字正常，但调用方声明 origin='test' → 拒
        # （进程级开关区分不了同进程内的调用方，这一条才是彻底的）
        try:
            record("pass", task="v2收集·真名", success=True, env_level=3,
                   origin="test")
            refused = False
        except ProductionWriteRefused:
            refused = True
        check("已绑定但 origin='test' → 拒绝", refused)

        # 第四层：没绑定，但 origin 显式声明为真实来源 → 放行
        _unbind()
        LEDGER = os.path.join(tempfile.gettempdir(), "m1_guard_selftest.jsonl")
        if os.path.exists(LEDGER):
            os.remove(LEDGER)
        try:
            rec = record("pass", task="v2收集·A2", success=True, env_level=3,
                         origin="collect")
            ok_origin = rec.get("origin") == "collect"
        except Exception:
            ok_origin = False
        check("origin 声明后放行且写入记录", ok_origin)

        # 第五层：绑定 + 真名 → 放行。用临时账本验证，不污染正式账本
        LEDGER = os.path.join(tempfile.gettempdir(), "m1_guard_selftest3.jsonl")
        if os.path.exists(LEDGER):
            os.remove(LEDGER)
        try:
            record("pass", task="v2收集·A1 建表", success=True, env_level=3)
            ok_real = True
        except Exception:
            ok_real = False
        check("绑定 + 真名 → 放行（临时账本）", ok_real)

        # 第六层：临时账本下无需绑定
        _unbind()
        try:
            record("pass", task="测试名", success=True, env_level=3)
            ok_sandbox = True
        except Exception:
            ok_sandbox = False
        check("临时账本下测试名可写", ok_sandbox)

        # 第七层：来源统计要看得到
        LEDGER = os.path.join(tempfile.gettempdir(), "m1_guard_origin.jsonl")
        if os.path.exists(LEDGER):
            os.remove(LEDGER)
        record("pass", task="v2收集·S1", success=True, env_level=3, origin="collect")
        record("pass", task="预测·S2", success=True, env_level=3, origin="case")
        record("pass", task="无来源", success=True, env_level=3)
        bo = stats(env_level=3, group=None).get("by_origin", {})
        check("来源分布统计到三种",
              bo.get("collect") == 1 and bo.get("case") == 1
              and bo.get("未声明") == 1, str(bo))

        # 第八层：审计必须真能抓到 bug。
        # 没测过的检测器等于没有——注入五类问题，逐条验证它报出来。
        LEDGER = os.path.join(tempfile.gettempdir(), "m1_audit_selftest.jsonl")
        if os.path.exists(LEDGER):
            os.remove(LEDGER)
        _inject = [
            # 1. cause 越界：非 degrade 带 cause
            {"id": "a1", "verdict": "pass", "cause": "info", "version": 2,
             "task": "越界样本", "success": True, "env_level": 3,
             "origin": "collect", "group": None},
            # 2. v2 的 degrade 缺 cause
            {"id": "a2", "verdict": "degrade", "cause": None, "version": 2,
             "task": "缺 cause 样本", "success": True, "env_level": 3,
             "origin": "collect", "group": None},
            # 3. reject 却成功
            {"id": "a3", "verdict": "reject", "cause": None, "version": 2,
             "task": "reject 却成功", "success": True, "env_level": 3,
             "origin": "collect", "group": None},
            # 4. pass 却失败
            {"id": "a4", "verdict": "pass", "cause": None, "version": 2,
             "task": "pass 却失败", "success": False, "env_level": 3,
             "origin": "collect", "group": None},
            # 5. 缺 origin
            {"id": "a5", "verdict": "pass", "cause": None, "version": 2,
             "task": "缺来源", "success": True, "env_level": 3,
             "origin": None, "group": None},
        ]
        for rec in _inject:
            full = {"ts": _now(), "note": "", "evidence": "",
                    "conclusion_verified": None}
            full.update(rec)
            _append(full)

        ar = audit(env_level=3, version=2)
        joined = "\n".join(ar["errors"] + ar["warnings"])
        check("审计抓到 cause 越界", "cause 越界" in joined)
        check("审计抓到 degrade 缺 cause", "缺 cause" in joined)
        check("审计抓到 reject 却成功", "reject 却成功" in joined)
        check("审计抓到 pass 却失败", "pass 却失败" in joined)
        check("审计抓到缺 origin", "缺 origin" in joined)
        check("审计把矛盾算作错误而非警告", len(ar["errors"]) >= 2, str(len(ar["errors"])))

        # 第九层：重跑核对必须真能发现漂移。
        # 「一致」不算证据——把世界改掉，它必须报出来。
        LEDGER = os.path.join(tempfile.gettempdir(), "m1_replay_selftest.jsonl")
        if os.path.exists(LEDGER):
            os.remove(LEDGER)
        _victim = os.path.join(tempfile.gettempdir(), "m1_replay_victim.txt")
        with open(_victim, "w", encoding="utf-8") as fh:
            fh.write("x")
        record("pass", task="可重跑样本", success=True, env_level=3,
               origin="collect", exec_ok=True,
               replay={"domain": "file", "task": {"path": _victim, "op": "read"}})
        r1 = replay(env_level=3)
        check("样本仍在 → 重跑一致", len(r1["ok"]) == 1 and not r1["drift"],
              f"ok={len(r1['ok'])} drift={len(r1['drift'])}")

        os.remove(_victim)          # 把世界改掉
        r2 = replay(env_level=3)
        check("文件被删 → 重跑报漂移", len(r2["drift"]) == 1,
              f"drift={len(r2['drift'])}")
        check("漂移记录里记账与重跑都留着",
              bool(r2["drift"]) and r2["drift"][0]["was"] is True
              and r2["drift"][0]["now"] is False,
              str(r2["drift"][0] if r2["drift"] else None))

        # 没有规格的样本要如实报「查不了」，不能当成"一致"
        _append({"id": "nospec", "ts": _now(), "verdict": "pass", "cause": None,
                 "version": 2, "conclusion_verified": None, "group": None,
                 "origin": "collect", "replay": None, "task": "无规格样本",
                 "note": "", "success": True, "evidence": "", "env_level": 3})
        r3 = replay(env_level=3)
        check("无规格样本计入「查不了」而不是「一致」",
              len(r3["no_spec"]) == 1 and len(r3["drift"]) == 1,
              f"no_spec={len(r3['no_spec'])}")

        # 第十层：混合桶不能拿平均数当先验
        LEDGER = os.path.join(tempfile.gettempdir(), "m1_pool_selftest.jsonl")
        if os.path.exists(LEDGER):
            os.remove(LEDGER)
        # a 组：0/8 成功；b 组：8/8 成功 —— 区间必然不重叠
        for i in range(8):
            record("degrade", task=f"混合a{i}", success=False, env_level=3,
                   cause="info", origin="collect")
        for i in range(8):
            record("degrade", task=f"混合b{i}", success=True, env_level=3,
                   cause="info", origin="qb")
        pc = pooling_check(env_level=3)
        di = pc["verdicts"].get("degrade/info", {})
        check("两组差异大 → 判为不可合并", di.get("poolable") is False, str(di.get("poolable")))
        check("不可合并时列出冲突的组", bool(di.get("disjoint_pairs")),
              str(di.get("disjoint_pairs")))

        pr, dt = current_prior(env_level=3)
        check("混合桶的先验回落到默认值，不用平均数",
              dt.get("degrade/info", {}).get("source") == "default(mixed)",
              str(dt.get("degrade/info", {}).get("source")))
        check("回落值等于默认值而不是 0.5",
              abs(pr.get("degrade/info", 0) - 0.65) < 1e-6,
              str(pr.get("degrade/info")))

        # 第十一层：反事实样本不能混进先验和精确率
        LEDGER = os.path.join(tempfile.gettempdir(), "m1_cf_selftest.jsonl")
        if os.path.exists(LEDGER):
            os.remove(LEDGER)
        # 4 条真样本成功 + 4 条反事实样本失败 —— 混算会把成功率拉到 50%
        for i in range(6):
            record("degrade", task=f"真样本{i}", success=True, env_level=3,
                   cause="info", origin="collect")
        for i in range(4):
            record("degrade", task=f"反事实{i}", success=False, env_level=3,
                   cause="info", origin="collect", counterfactual=True)
        from harness import MODEL_VERSION as _MVg
        st = stats(env_level=3, version=_MVg)
        check("反事实样本被单独统计", st.get("counterfactual", {}).get("n") == 4,
              str(st.get("counterfactual")))
        d_info = st["calibration_by_cause"].get("degrade/info", {})
        check("反事实样本不混进 degrade/info 的分母",
              d_info.get("n") == 6 and d_info.get("success") == 6,
              f"n={d_info.get('n')} succ={d_info.get('success')}")
        pcf, dcf = current_prior(env_level=3)
        check("反事实样本不影响先验",
              abs(dcf.get("degrade/info", {}).get("value", 0) - 0.875) < 1e-2,
              str(dcf.get("degrade/info", {}).get("value")))
    finally:
        LEDGER = saved_ledger
        _unbind()
        if saved_allow is not None:
            os.environ["MODEL1_ALLOW_TEST_WRITE"] = saved_allow

    print()
    print("=" * 72)
    print(f"{'ALL PASS' if not fails else 'FAILED: ' + str(fails)}")
    print("=" * 72)
    # ---- 建议能落账、能汇总（第七十二轮）----
    # 这一段要真写记录，所以先切到临时账本并绑定——
    # 前面几段可能已经把 LEDGER 还原成正式库且解绑了。
    _tmpf = os.path.join(tempfile.gettempdir(), "m1_guard_ask.jsonl")
    if os.path.exists(_tmpf):
        os.remove(_tmpf)
    LEDGER = _tmpf
    bind_production("门禁自测·建议字段")

    _ask = [{"dim": "e2", "have": 1, "need": 2, "delta": 1, "how": "找第二个独立来源"},
            {"dim": "e2", "have": 1, "need": 2, "delta": 1, "how": "重复项，应被去重"}]
    _r1 = record("degrade", task="门禁·带建议样本", success=None, env_level=3,
                 cause="info", ask=_ask)
    check("ask 能落账并读回", bool(_r1.get("ask")) and len(_r1["ask"]) == 2,
          str(len(_r1.get("ask") or [])))

    _r2 = record("degrade", task="门禁·无建议样本", success=None, env_level=3,
                 cause="info")
    check("不传 ask 时字段为空", _r2.get("ask") is None, str(_r2.get("ask")))

    _b = blockers(env_level=3)
    # 临时库里写了 2 条，只有 1 条带建议 → with_ask 必须是 1，不是 2
    check("blockers 只统计带建议的样本",
          _b["with_ask"] == 1 and _b["rows"] == 2,
          f"with_ask={_b['with_ask']} rows={_b['rows']}")
    check("同一条样本里同一维只算一次", _b["per_dim"].get("e2", 0) >= 1,
          str(_b["per_dim"]))

    # ---- 平局必须如实说成平局（第七十三轮）----
    # 上一版只取 ranked[0][0]，e2/e3 都是 N 次时会随便报一个"最常缺 e2"——
    # 那等于用一个平局编出一个结论。
    for f in (_tmpf,):
        if os.path.exists(f):
            os.remove(f)
    LEDGER = _tmpf
    bind_production("门禁自测·平局")
    record("degrade", task="平局甲", success=None, env_level=3, cause="info",
           ask=[{"dim": "e2"}, {"dim": "e3"}])
    record("degrade", task="平局乙", success=None, env_level=3, cause="info",
           ask=[{"dim": "e2"}, {"dim": "e3"}])
    _bt = blockers(env_level=3)
    check("平局时不给单一结论",
          _bt["top"] is None and sorted(_bt["tops"]) == ["e2", "e3"],
          f"top={_bt['top']} tops={_bt['tops']}")

    if os.path.exists(_tmpf):
        os.remove(_tmpf)
    LEDGER = _tmpf
    bind_production("门禁自测·不平时")
    record("degrade", task="不平甲", success=None, env_level=3, cause="info",
           ask=[{"dim": "e3"}])
    record("degrade", task="不平乙", success=None, env_level=3, cause="info",
           ask=[{"dim": "e3"}, {"dim": "e1"}])
    _bn = blockers(env_level=3)
    check("不平时给出唯一结论",
          _bn["top"] == "e3" and len(_bn["tops"]) == 1,
          f"top={_bn['top']} tops={_bn['tops']}")

    # ---- 同构样本不算多次观测（第七十四轮）----
    if os.path.exists(_tmpf):
        os.remove(_tmpf)
    LEDGER = _tmpf
    bind_production("门禁自测·同构")
    record("degrade", task="同构甲", success=None, env_level=3, cause="info",
           ask=[{"dim": "e2"}, {"dim": "e3"}])
    record("degrade", task="同构乙", success=None, env_level=3, cause="info",
           ask=[{"dim": "e2"}, {"dim": "e3"}])
    _bs = blockers(env_level=3)
    check("同一缺口组合重复多次只算一组",
          _bs["with_ask"] == 2 and _bs["distinct_signatures"] == 1,
          f"with_ask={_bs['with_ask']} distinct={_bs['distinct_signatures']}")

    record("degrade", task="同构丙", success=None, env_level=3, cause="info",
           ask=[{"dim": "e1"}])
    _bs2 = blockers(env_level=3)
    check("出现第二种组合后有效样本量变 2",
          _bs2["distinct_signatures"] == 2,
          str(_bs2["distinct_signatures"]))

    # ---- 排名按组合数，不按条数（第七十五轮）----
    # 造 4 条同构（只要 e2）+ 1 条（只要 e3）：
    #   按条数 e2=4 > e3=1，会报"最常缺 e2"
    #   按组合 e2=1 = e3=1，应当如实说平局
    if os.path.exists(_tmpf):
        os.remove(_tmpf)
    LEDGER = _tmpf
    bind_production("门禁自测·按组合排名")
    for i in range(4):
        record("degrade", task=f"同构e2_{i}", success=None, env_level=3,
               cause="info", ask=[{"dim": "e2", "delta": 1}])
    record("degrade", task="单条e3", success=None, env_level=3,
           cause="info", ask=[{"dim": "e3", "delta": 1}])
    _br = blockers(env_level=3)
    check("条数上 e2 明显更多",
          _br["per_dim"]["e2"] == 4 and _br["per_dim"]["e3"] == 1,
          str(_br["per_dim"]))
    check("排名按缺口组合数，不按条数（平局就说平局）",
          sorted(_br["tops"]) == ["e2", "e3"],
          f"tops={_br['tops']} per_dim_sig={_br.get('per_dim_sig')}")

    # ---- 删样本前必须备份（第七十六轮）----
    if os.path.exists(_tmpf):
        os.remove(_tmpf)
    LEDGER = _tmpf
    bind_production("门禁自测·删除前备份")
    for i in range(3):
        record("degrade", task=f"待删_{i}", success=None, env_level=3, cause="info")
    record("degrade", task="保留_0", success=None, env_level=3, cause="info")

    _pv = prune(("待删_",), apply=False)
    check("prune 默认只预演，不动账本",
          _pv["would_delete"] == 3 and _pv["deleted"] == 0
          and os.path.getsize(_tmpf) > 0,
          f"would={_pv['would_delete']} deleted={_pv['deleted']}")
    _n_before = sum(1 for _ in open(_tmpf, encoding="utf-8"))

    _ap = prune(("待删_",), apply=True, reason="门禁")
    check("prune 真删前先备份", bool(_ap["backup"]) and os.path.exists(_ap["backup"]),
          str(_ap["backup"]))
    check("备份文件非空且行数与删除前一致",
          sum(1 for _ in open(_ap["backup"], encoding="utf-8")) == _n_before,
          f"备份 {sum(1 for _ in open(_ap['backup'], encoding='utf-8'))} 行 / 删前 {_n_before} 行")
    check("删除条数与预演一致",
          _ap["deleted"] == _ap["would_delete"] == 3,
          f"deleted={_ap['deleted']} would={_ap['would_delete']}")
    _left = [json.loads(l) for l in open(_tmpf, encoding="utf-8") if l.strip()]
    check("没删错东西", len(_left) == 1
          and (_left[0].get("task") or "").startswith("保留_"),
          str([r.get("task") for r in _left]))

    # ---- 同一条不能回填两次（第八十一轮）----
    # 原来 resolve() 查的是 _load()（原始事件流），而原始记录行自己的
    # success 永远是 None（有结果的是后面那条 resolve 事件）。
    # 于是第二条 resolve 被静默接受，entries() 折叠时又取最后一条，
    # 前一次的结果被无声覆盖——账本上一点矛盾痕迹都不留。
    if os.path.exists(_tmpf):
        os.remove(_tmpf)
    LEDGER = _tmpf
    bind_production("门禁自测·重复回填")
    _rr = record("degrade", task="重复回填甲", success=None, env_level=3,
                 cause="info")
    resolve(_rr["id"], True, "第一次")
    _threw = False
    try:
        resolve(_rr["id"], False, "第二次")
    except ValueError:
        _threw = True
    check("同一条不能回填两次", _threw, f"id={_rr['id']}")

    _st = {r["id"]: r for r in entries()}
    check("折叠状态保留第一次的结果",
          _st[_rr["id"]]["success"] is True,
          str(_st[_rr["id"]].get("success")))

    # ---- 检测器本身要被验证（第八十二轮）----
    # 「修完之后查不到」和「检测器根本不会查」是两件事。
    # 所以这里直接绕过 resolve()，用 _append 伪造一条重复回填，
    # 确认 duplicate_resolves() 能抓到。
    _append({"id": _rr["id"], "ts": _now(), "op": "resolve",
             "success": False, "evidence": "伪造的第二次"})
    _dup = duplicate_resolves()
    _hit = next((d for d in _dup if d["id"] == _rr["id"]), None)
    check("检测器能抓到伪造的重复回填",
          _hit is not None and _hit["times"] == 2,
          str(_hit))
    check("能识别两次结果互相矛盾",
          _hit is not None and _hit["conflict"] is True,
          str(_hit))

    # ---- 判据准确率 ≠ 主张成功率（第八十三轮）----
    # calibration 问的是"这批主张碰巧有多少真的"；
    # criterion_accuracy 问的是"判据判得对不对"。
    # 盲判样本当时确实不知道，说"不知道"是**正确行为**，
    # 它们不进判据准确率的分母。
    if os.path.exists(_tmpf):
        os.remove(_tmpf)
    LEDGER = _tmpf
    bind_production("门禁自测·判据准确率")
    _a1 = record("degrade", task="已知答案且判对", success=True, env_level=3,
                 cause="info", criterion_right=True)
    _a2 = record("degrade", task="已知答案且判错", success=False, env_level=3,
                 cause="info", criterion_right=False)
    _a3 = record("degrade", task="盲判不知道", success=True, env_level=3,
                 cause="info")

    _ca = criterion_accuracy(env_level=3)
    check("判据准确率只算填了 criterion_right 的",
          _ca["n"] == 2, str(_ca))
    check("判据准确率算对了 1/2",
          _ca["correct"] == 1 and _ca["rate"] == 0.5,
          f"{_ca['correct']}/{_ca['n']} rate={_ca['rate']}")
    check("盲判样本不进判据准确率",
          _a3["id"] not in [r["id"] for r in entries()
                            if r.get("criterion_right") is not None],
          _a3["id"])

    # ---- 推翻率：degrade 之后被实测推翻的比例（第八十四轮）----
    _b1 = record("degrade", task="可复核且成立", success=True, env_level=3,
                 cause="info", conclusion_held=True)
    _b2 = record("degrade", task="可复核但被推翻", success=False, env_level=3,
                 cause="info", conclusion_held=False)
    _ov = overturn_rate(env_level=3)
    check("推翻率只统计能复核的 degrade",
          _ov["checkable"] == 2, str(_ov))
    check("推翻率算对了 1/2",
          _ov["overturned"] == 1 and _ov["rate"] == 0.5,
          f"{_ov['overturned']}/{_ov['checkable']} rate={_ov['rate']}")
    check("判据准确率不把 conclusion_held 当成判据对错",
          _b1["id"] not in [r["id"] for r in entries()
                            if r.get("criterion_right") is not None],
          _b1["id"])

    # ---- 推翻率只认"结论成立"语义（第八十五轮）----
    # 迁移时踩过的坑：盲判样本的 success 是在后面的 resolve 事件里，
    # 在**原始行**上找 success 只会找到 None —— 会以为"一条都没迁到"。
    # 必须用折叠后的状态。
    _ov_before = overturn_rate(env_level=3)
    _c1 = record("degrade", task="真题·样例 成立", success=True, env_level=3,
                 cause="info", conclusion_held=True)
    _c2 = record("degrade", task="真题·样例 被推翻", success=False, env_level=3,
                 cause="info", conclusion_held=False)
    _c3 = record("degrade", task="意图类样例 达成", success=True, env_level=3,
                 cause="info")      # success 语义是意图达成，不算结论成立
    _ov2 = overturn_rate(env_level=3)
    check("推翻率只认结论成立语义（意图达成的不算）",
          _c3["id"] not in [r["id"] for r in entries()
                            if r.get("conclusion_held") is not None],
          _c3["id"])
    check("成立与被推翻各记一条（看增量，不看绝对值）",
          _ov2["checkable"] - _ov_before["checkable"] == 2
          and _ov2["overturned"] - _ov_before["overturned"] == 1,
          f"可复核 {_ov_before['checkable']}->{_ov2['checkable']}，"
          f"推翻 {_ov_before['overturned']}->{_ov2['overturned']}")

    # 折叠后的状态才是可用的：resolve 之后才拿得到结论
    _d1 = record("degrade", task="待结算样例", success=None, env_level=3,
                 cause="info")
    check("pending 样本不算进推翻率",
          _d1["id"] not in [r["id"] for r in entries()
                            if r.get("success") is not None],
          _d1["id"])

    # ---- 不可复核的三类分得开（第八十六轮）----
    # 复核过 / 明确没法复核（附原因）/ 不知道能不能复核
    _e1 = record("degrade", task="复核过且成立", success=True, env_level=3,
                 cause="info", conclusion_held=True)
    _e2 = record("degrade", task="没法复核", success=False, env_level=3,
                 cause="info", conclusion_checkable=False,
                 check_why="环境给不了")
    _e3 = record("degrade", task="不知能否复核", success=False, env_level=3,
                 cause="info")
    _ov3 = overturn_rate(env_level=3)
    _e1_in = [r for r in entries() if r.get("id") == _e1["id"]][0]
    _e2_in = [r for r in entries() if r.get("id") == _e2["id"]][0]
    _e3_in = [r for r in entries() if r.get("id") == _e3["id"]][0]
    check("明确没法复核的，不进推翻率分母",
          _e2_in.get("conclusion_held") is None
          and _ov3["cannot_check"] >= 1,
          f"cannot_check={_ov3['cannot_check']}")
    check("没法复核的原因被记下来",
          _e2_in.get("check_why") == "环境给不了",
          str(_e2_in.get("check_why")))
    check("不知道能否复核的，两头都不算",
          _e3_in.get("conclusion_held") is None
          and _e3_in.get("conclusion_checkable") is None
          and _ov3["unknown_check"] >= 1,
          f"unknown_check={_ov3['unknown_check']}")
    check("三类互不重叠：复核过的不会同时被算成没法复核",
          _e1_in.get("conclusion_held") is not None
          and _e1_in.get("conclusion_checkable") is None,
          str(_e1_in.get("conclusion_held")))

    # calibration 与 criterion_accuracy 必须是两个数
    from harness import MODEL_VERSION as _MVc
    _st = stats(3, _MVc)
    check("stats 里两件事是分开的字段",
          "criterion_accuracy" in _st
          and "calibration" in _st
          and "overturn_rate" in _st,
          str(list(_st.keys())))

    LEDGER = saved_ledger
    _unbind()

    # 还原现场，别把后面可能的验证带偏
    LEDGER = saved_ledger
    _unbind()

    return 0 if not fails else 1


def audit(env_level: int | None = None, version: int | None = None) -> dict:
    """账本一致性审计。

    存在的理由：第三十六到三十八轮，我靠手工翻账本查出三类语义 bug——
      · success 被记成「判据判得对不对」（三个脚本，共 17 条样本失真）
      · degrade 漏传 cause（5 个脚本，9 条样本掉进 unknown 桶）
      · 阴性对照混进自然池，把 pass 精确率从 89% 拉到 78%
    每一类都是**同一份账本里的自相矛盾**，本该由工具发现。

    这个函数把那些检查写死，以后改脚本不用再靠人眼。
    返回 {"errors": [...], "warnings": [...], "infos": [...], "checked": n}
    """
    from harness import MODEL_VERSION

    rows = [r for r in entries() if r.get("op") != "resolve"]
    if env_level is not None:
        rows = [r for r in rows if r.get("env_level") == env_level]
    if version is not None:
        rows = [r for r in rows if r.get("version") == version]

    errors: list[str] = []
    warnings: list[str] = []
    infos: list[str] = []

    # 判 pass 却失败的样本单独攒着，按比率汇总报警。
    # 逐条列出来只是噪音——盲判本来就有错误率，重要的是比率有多大。
    pass_false: list[dict] = []
    reject_true: list[dict] = []

    seen: dict[str, int] = {}

    for r in rows:
        tid = r.get("id") or "?"
        task = (r.get("task") or "")[:40]
        v = r.get("version")
        verdict = r.get("verdict")

        seen[tid] = seen.get(tid, 0) + 1
        if seen[tid] == 2:
            errors.append(f"[重复] {tid} 被记录了不止一次")

        # --- 自相矛盾（必然是 bug）---
        if r.get("cause") and verdict != "degrade":
            errors.append(f"[cause 越界] {tid} verdict={verdict} 却带 cause={r['cause']}")

        if v == MODEL_VERSION and verdict == "degrade" and not r.get("cause"):
            errors.append(f"[缺 cause] {tid} v{v} 判 degrade 但没有 cause"
                          f"（应记 env 或 info）: {task}")

        # --- 统计会失真（多半是语义用错）---
        # 跳过阴性对照组：那批样本是**故意构造**的，pass 却失败是设计预期。
        if r.get("group") in CONTROL_GROUPS:
            continue

        if verdict == "pass" and r.get("success") is False:
            # 不逐条报警——盲判必然有错误率，逐条列只会变成噪音。
            # 汇总在下面按比率报。
            pass_false.append(r)
        if verdict == "reject" and r.get("success") is True:
            reject_true.append(r)

        if v == MODEL_VERSION and not r.get("origin"):
            warnings.append(f"[缺 origin] {tid} 没有来源声明，说不清是谁写的: {task}")

        if r.get("success") is None and v == MODEL_VERSION:
            infos.append(f"[未结算] {tid} 还是 pending: {task}")

    # --- 判错的比率：这是校准，不是 bug ---
    # 判 pass 却失败 = 假阳性。盲判必然有，重要的是**有多少**。
    n_pass = sum(1 for r in rows if r.get("success") is not None
                 and r["verdict"] == "pass"
                 and r.get("group") not in CONTROL_GROUPS)
    if pass_false:
        rate = len(pass_false) / n_pass if n_pass else 0.0
        warnings.append(
            f"[pass 假阳性] {len(pass_false)}/{n_pass} = {rate*100:.0f}% "
            f"判了 pass 但结论不成立。判之前不知道答案的样本有这个错误率是正常的，"
            f"但要知道它有多大。例：{(pass_false[0].get('task') or '')[:36]}")
    if reject_true:
        warnings.append(
            f"[reject 却成功] {len(reject_true)} 条判 reject 但 success=True，"
            f"要么任务其实做成了，要么 success 记错了东西")

    # --- 重复测量：同一任务在同一「版本+环境」下有多条 ---
    # env_level 必须进 key：同一个任务在 L3 和 L2 下各判一次是**有意为之**，
    # 那是跨环境对照，不是重复记账。
    key_count: dict[tuple, int] = {}
    for r in rows:
        k = (r.get("task") or "", r.get("version"), r.get("env_level"))
        key_count[k] = key_count.get(k, 0) + 1
    dup = [(k, c) for k, c in key_count.items() if c > 1]
    if dup:
        warnings.append(f"[重复测量] {len(dup)} 组「任务+版本+环境」有多条记录"
                        f"（重测会产生，需确认不是重复记账）")

    # --- 样本量提醒 ---
    # 剔除两类：阴性对照组、先验证后判的样本。
    # 后者不检验判据，只把已验证的结论记一遍，算进去会虚高样本量。
    resolved = [r for r in rows if r.get("success") is not None
                and r.get("group") not in CONTROL_GROUPS
                and not r.get("prejudged")
                and not r.get("counterfactual")]
    skipped = sum(1 for r in rows if r.get("success") is not None
                  and (r.get("group") in CONTROL_GROUPS or r.get("prejudged")
                       or r.get("counterfactual")))
    cf_n = sum(1 for r in rows if r.get("success") is not None
               and r.get("counterfactual"))
    if skipped:
        infos.append(f"[已剔除] {skipped} 条样本不进样本量统计"
                     f"（对照组 / 先验证后判 / 反事实，它们答的不是同一个问题）")
    if cf_n:
        infos.append(f"[反事实] {cf_n} 条的 success 说的是「如果能验会不会成」，"
                     f"不是「在当前环境成不成」——单独看，别和上面混")
    buckets: dict[str, list[bool]] = {}
    for r in resolved:
        k = r["verdict"]
        if k == "degrade":
            k = f"degrade/{r.get('cause') or 'unknown'}"
        buckets.setdefault(k, []).append(bool(r["success"]))
    for k, oks in sorted(buckets.items()):
        n = len(oks)
        if n >= 60:
            continue
        succ = sum(1 for x in oks if x)
        lo, hi = wilson(succ, n)
        # 方向要对：
        #   pass / degrade 关心「成功率会不会比看到的低」→ 看下界
        #   reject 关心「成功率会不会比看到的低」→ 看上界（上界低才说明判得准）
        if k == "reject":
            infos.append(f"[样本量] {k}: n={n}，成功率上界 {hi:.2f}"
                         f"（要压到 0.1 以下才算 reject 判得准）")
        else:
            infos.append(f"[样本量] {k}: n={n}，成功率下界 {lo:.2f}"
                         f"（下界要到 0.9 以上才敢报精确率）")

    # --- 先验可合并性：混合桶不能拿平均数当结论 ---
    # **必须按环境档分别查**：L2 和 L3 的 degrade/env 是两个问题
    # （L2 是「如果能验会不会成」，L3 是「环境真给不了」），
    # 跨档合并后再判可合并性，等于先犯一次错再去检查它。
    try:
        levels = sorted({r.get("env_level") for r in rows
                         if r.get("env_level") is not None})
        for lv in (levels or [env_level]):
            pool = pooling_check(env_level=lv, version=version)
            for verdict, d in pool["verdicts"].items():
                if not d["poolable"]:
                    rates = "  ".join(f"{s} {g['rate']*100:.0f}%"
                                      for s, g in d["groups"].items())
                    warnings.append(
                        f"[先验不可合并] L{lv} {verdict}：各组 {rates}，区间不重叠。"
                        f"合并值 {d['pooled']:.2f} 不预测任何一组，先验已回落到默认")
    except Exception as e:  # noqa: BLE001
        infos.append(f"[先验可合并性] 查不了：{type(e).__name__}: {e}")

    # --- 判据准不准（与"主张碰巧真不真"分开）---
    try:
        _ca = criterion_accuracy(env_level=env_level, version=version)
        if _ca["n"]:
            _by = "，".join(f"{k} {v['correct']}/{v['n']}"
                           for k, v in _ca["by_origin"].items())
            infos.append(
                f"[判据准确率] {_ca['correct']}/{_ca['n']} = "
                f"{_ca['rate']*100:.1f}%（按 origin：{_by}）")
            infos.append(
                f"[判据准确率] 只统计填了 criterion_right 的样本；"
                f"盲判样本不在内——它们当时确实不知道")
    except Exception as e:  # noqa: BLE001
        infos.append(f"[判据准确率] 算不了：{type(e).__name__}: {e}")

    # --- degrade 推翻率：结论最后被推翻了多少 ---
    try:
        _ov = overturn_rate(env_level=env_level, version=version)
        if _ov["checkable"]:
            _by = "，".join(f"{k} {v['n'] - v['held']}/{v['n']}"
                           for k, v in _ov["by_origin"].items())
            infos.append(
                f"[推翻率] 可复核的 degrade {_ov['checkable']} 条里，"
                f"被实测推翻 {_ov['overturned']} 条 = {_ov['rate']*100:.1f}%"
                f"（按 origin：{_by}）")
            if _ov["cannot_check"] or _ov["unknown_check"]:
                _why = "；".join(f"{k}×{v}"
                                 for k, v in _ov["cannot_by_reason"].items())
                infos.append(
                    f"[推翻率] 另有 {_ov['cannot_check']} 条**没法**复核"
                    f"{'（' + _why + '）' if _why else ''}，"
                    f"{_ov['unknown_check']} 条**不知道**能不能复核")
    except Exception as e:  # noqa: BLE001
        infos.append(f"[推翻率] 算不了：{type(e).__name__}: {e}")

    # --- 重复回填：修过的 bug 会不会回来 ---
    try:
        _dup = duplicate_resolves()
        if _dup:
            _conf = sum(1 for d in _dup if d["conflict"])
            errors.append(f"[重复回填] {len(_dup)} 个样本被回填多次，"
                          f"其中 {_conf} 个结果互相矛盾："
                          + "; ".join(f"{d['id']}×{d['times']}={d['values']}"
                                      for d in _dup[:3]))
    except Exception as e:  # noqa: BLE001
        infos.append(f"[重复回填] 查不了：{type(e).__name__}: {e}")

    # --- 瓶颈定位：被拦住的主张最常缺哪一维 ---
    try:
        _bl = blockers(env_level=env_level, version=version)
        if _bl["per_dim"]:
            _eff = _bl.get('effective_n', _bl['with_ask'])
            if _eff <= 1:
                infos.append(
                    f"[瓶颈] 带建议的 {_bl['with_ask']}/{_bl['rows']} 条，"
                    f"但只有 {_eff} 种缺口组合 → **分不出先后**"
                    f"（分布 {_bl['per_dim']}）")
            else:
                infos.append(
                    f"[瓶颈] 带建议的 {_bl['with_ask']}/{_bl['rows']} 条、"
                    f"{_eff} 种组合，最常缺 "
                    f"{'、'.join(_bl.get('tops') or []) or '无法判定'}"
                    f"（分布 {_bl['per_dim']}）")
        elif _bl["rows"]:
            infos.append(f"[瓶颈] {_bl['rows']} 条记录里还没有带建议的，"
                         f"无法定位短板（老样本没有 ask 字段）")
    except Exception as e:  # noqa: BLE001
        infos.append(f"[瓶颈] 算不了：{type(e).__name__}: {e}")

    # --- 两段覆盖率：别把「暂时没结论」和「永远没结论」混成一个数 ---
    try:
        for lv in (levels or [env_level]):
            cv = coverage(env_level=lv, version=version)
            if not cv["total"]:
                continue
            infos.append(
                f"[覆盖率] L{lv} 一次判完 {cv['first_pass'] * 100:.0f}%"
                f"（{cv['determinate']}/{cv['total']}），"
                f"复核之后 {cv['after_verify'] * 100:.0f}%"
                f"（degrade {cv['degrade']} 条中 {cv['verifiable']} 条可复核、"
                f"{cv['stuck']} 条永远没结论）")
    except Exception as e:  # noqa: BLE001
        infos.append(f"[覆盖率] 算不了：{type(e).__name__}: {e}")

    return {"errors": errors, "warnings": warnings, "infos": infos,
            "checked": len(rows)}


def _print_audit(res: dict) -> int:
    print("=" * 72)
    print("账本审计")
    print("=" * 72)
    print(f"  检查 {res['checked']} 条记录")
    print()
    for label, items, mark in (("错误", res["errors"], "✗"),
                               ("警告", res["warnings"], "!"),
                               ("提示", res["infos"], "·")):
        print(f"{label}: {len(items)} 项")
        for it in items[:20]:
            print(f"  {mark} {it}")
        if len(items) > 20:
            print(f"    … 另有 {len(items) - 20} 项")
        print()
    ok = not res["errors"]
    print("=" * 72)
    print("没有自相矛盾的记录" if ok else f"有 {len(res['errors'])} 处自相矛盾，必须修")
    print("=" * 72)
    return 0 if ok else 1


def _looks_unavailable(why: str) -> bool:
    """这次核对是「对不上」，还是「根本没跑成」？

    为什么要分（第六十八轮）：
        回归里跑 replay 时，如果 seekdb 正被别的脚本占着，
        EXPLAIN 会取不到计划，do_exec 返回 False。
        replay 就把它记成"漂移"——可样本本身没变，是环境当时不可用。

        两种情况混在一起，会让回归**随机变红**。
        「没跑成」应该和「查不了」一样处理：跳过，不判对错。
    """
    keys = ("起不来", "取不到", "调用失败", "NODB", "连接",
            "不可用", "timeout", "超时")
    up = why or ""
    return any(k in up for k in keys)


# 重跑核对时 http 的超时窗口（秒）。活探测不受影响，仍用 12 秒。
REPLAY_HTTP_TIMEOUT = 5


def replay(env_level: int | None = None, version: int | None = None,
           limit: int | None = None) -> dict:
    """重跑样本，核对记账的 outcome 现在还成不成立。

    这是审计查不到的那一层：审计只能查账本**自相矛盾**，
    查不了"这条样本当初测得对不对"。要查后者，只能按规格重跑一遍。

    三类结果：
      ok        重跑结果与记账一致
      drift     重跑结果与记账不一致（要么当初记错，要么世界变了）
      no_spec   样本没有可重跑规格（老样本 / sql 域），如实报告，不猜

    **drift 不等于当初记错**。文件被删、网络变了、URL 失效都会造成 drift。
    它只说明"这条样本对不上当前世界"，需要人看一眼。
    """
    from probe import check_kind, do_exec_many, replayable

    rows = [r for r in entries() if r.get("op") != "resolve"]
    if env_level is not None:
        rows = [r for r in rows if r.get("env_level") == env_level]
    if version is not None:
        rows = [r for r in rows if r.get("version") == version]
    if limit:
        rows = rows[:limit]

    ok, drift, no_spec, unavailable = [], [], [], []

    # 先筛出可重跑的，**按域分组批量跑**：
    # sql 每跑一条都要起一次 WSL（含等 seekdb），单条调用慢到没法接受。
    runnable: list[tuple[dict, dict]] = []
    for r in rows:
        spec = r.get("replay")
        if not spec or not replayable(spec.get("domain"), spec.get("task") or {}):
            no_spec.append(r)
            continue
        # 比什么取决于这个域返回的是哪个问题的答案（见 probe.CHECK_KIND）：
        #   execution 域（file/http/sql）→ 比 exec_ok（操作跑通没有）
        #   assertion 域（data）       → 比 success（断言真假 = 主张真假）
        if check_kind(spec.get("domain")) == "assertion":
            if r.get("success") is None:
                no_spec.append(r)
                continue
        elif r.get("exec_ok") is None:
            no_spec.append(r)
            continue
        runnable.append((r, spec))

    by_domain: dict[str, list[tuple[dict, dict]]] = {}
    for r, spec in runnable:
        by_domain.setdefault(spec["domain"], []).append((r, spec))

    for domain, group in by_domain.items():
        # 去重执行：同一个 task 重跑几次，结果必然一样。
        # 第 80 轮实测：http 域 12 条样本里有 **6 条是逐字相同的 task**
        # （github.com / example.com / .invalid / ftp:// / not-a-url 各两次），
        # 白白跑了两遍 —— 单这一项就吃掉 38 秒。
        #
        # 注意去重的粒度是 **task**，不是整条记录：
        # 两条记录可能 task 相同但当初记的 success 不同，
        # 重跑后各自跟自己的记录比 —— 比的是「当初记的对不对」，
        # 不是「两条记录该不该一样」。
        keys: list[str] = []
        uniq_tasks: list[dict] = []
        key_to_idx: dict[str, int] = {}
        for _r, spec in group:
            task = dict(spec["task"])
            if domain == "http":
                # 重跑核对用更短的窗口（第 80 轮）。
                # 依据是实测：6 个 URL 里有 3 个各自跑满 12 秒超时
                # （github.com 不可达、ftp:// 的 handler 直接挂死）。
                # 而 replay 判的是**漂移**（结论变没变），
                # 超时归入"环境不可用"、不算漂移 ——
                # 所以窗口变短**不会削弱漂移检测**，只是少等一会儿。
                # 活探测仍走默认 12 秒，网络余量不打折。
                task.setdefault("timeout", REPLAY_HTTP_TIMEOUT)
            try:
                key = json.dumps(task, sort_keys=True,
                                 ensure_ascii=False, default=str)
            except (TypeError, ValueError):
                key = repr(task)
            keys.append(key)
            if key not in key_to_idx:
                key_to_idx[key] = len(uniq_tasks)
                uniq_tasks.append(task)
        outs = do_exec_many(domain, uniq_tasks)
        for i, (r, spec) in enumerate(group):
            got, why = outs[key_to_idx[keys[i]]]
            if check_kind(domain) == "assertion":
                was = r.get("success")
            else:
                was = r.get("exec_ok")
            rec = {"id": r.get("id"), "task": (r.get("task") or "")[:44],
                   "was": was, "now": got, "why": why[:50], "domain": domain}
            # 核对没跑成 ≠ 核对不符。前者不算漂移，否则回归会随机变红。
            if _looks_unavailable(why):
                unavailable.append(rec)
            elif bool(got) == bool(was):
                ok.append(rec)
            else:
                drift.append(rec)

    return {"ok": ok, "drift": drift, "no_spec": no_spec,
            "unavailable": unavailable, "checked": len(rows)}


def _print_replay(res: dict) -> int:
    print("=" * 72)
    print("样本重跑核对")
    print("=" * 72)
    un = res.get("unavailable") or []
    print(f"  检查 {res['checked']} 条：一致 {len(res['ok'])}  "
          f"对不上 {len(res['drift'])}  无规格/待结算 {len(res['no_spec'])}"
          + (f"  环境不可用跳过 {len(un)}" if un else ""))
    if res["ok"]:
        seen: dict[str, int] = {}
        for r in res["ok"]:
            k = r.get("domain") or "?"
            seen[k] = seen.get(k, 0) + 1
        print("  一致的按域： " + "  ".join(f"{k}:{v}" for k, v in sorted(seen.items())))
    print()
    if res["drift"]:
        print("对不上的（不一定是记错，也可能世界变了）：")
        for d in res["drift"]:
            print(f"  ✗ {d['task']}")
            print(f"     记账={d['was']}  重跑={d['now']}  {d['why']}")
        print()
    if res["no_spec"]:
        print(f"查不了的 {len(res['no_spec'])} 条（没有可重跑规格）：")
        seen = {}
        for r in res["no_spec"]:
            k = (r.get("origin") or "未声明")
            seen[k] = seen.get(k, 0) + 1
        for k, n in sorted(seen.items()):
            print(f"  · origin={k}: {n} 条")
        print()
    print("=" * 72)
    print("全部对得上" if not res["drift"] else f"有 {len(res['drift'])} 条对不上")
    print("=" * 72)
    return 0 if not res["drift"] else 1


def resolve_blind(env_level: int | None = None,
                  version: int | None = None) -> dict:
    """把**盲判**挂起的样本按规格验证掉。

    为什么要有这个流程：

    第五十二轮发现自己虚高了精确率——qb 那批是「先跑断言拿到真假，再记 pass」，
    **判的时候就知道答案了，pass 不可能错**，算进去是同义反复。

    真检验的顺序必须是：
        第一轮：只看题目和数据结构 → 判 pass/degrade/reject → 记 success=None（挂起）
        第二轮：跑规格验证 → resolve(id, success=实际) → 这才检验了判据

    这个函数就是第二轮。它只碰挂起样本，不动已结算的。
    """
    from probe import do_exec_many, replayable

    rows = [r for r in entries() if r.get("op") != "resolve"]
    if env_level is not None:
        rows = [r for r in rows if r.get("env_level") == env_level]
    if version is not None:
        rows = [r for r in rows if r.get("version") == version]

    pending = [r for r in rows if r.get("success") is None]
    done, skipped = [], []

    usable = []
    for r in pending:
        spec = r.get("replay")
        if not spec or not replayable(spec.get("domain"), spec.get("task") or {}):
            skipped.append({"id": r.get("id"),
                            "task": (r.get("task") or "")[:44],
                            "why": "没有可重跑规格"})
            continue
        usable.append((r, spec))

    by_domain: dict[str, list] = {}
    for r, spec in usable:
        by_domain.setdefault(spec["domain"], []).append((r, spec))

    for domain, group in by_domain.items():
        outs = do_exec_many(domain, [spec["task"] for _r, spec in group])
        for (r, _spec), (got, why) in zip(group, outs):
            ev = f"盲判验证（{domain}）：{why[:60]}"
            resolve(r["id"], bool(got), ev)
            done.append({"id": r["id"],
                         "task": (r.get("task") or "")[:44],
                         "verdict": r["verdict"], "success": bool(got),
                         "why": why[:50]})

    return {"resolved": done, "skipped": skipped,
            "checked": len(rows), "pending_before": len(pending)}


def _print_resolve_blind(res: dict) -> int:
    print("=" * 74)
    print("盲判验证 · 挂起的判定按规格结算")
    print("=" * 74)
    print(f"  检查 {res['checked']} 条：挂起 {res['pending_before']} 条，"
          f"结算 {len(res['resolved'])} 条，跳过 {len(res['skipped'])} 条")
    print()
    if res["resolved"]:
        from collections import Counter
        c = Counter(f"{d['verdict']}/{'成立' if d['success'] else '不成立'}"
                    for d in res["resolved"])
        print("  结算结果：")
        for k, n in sorted(c.items()):
            print(f"    {k}: {n}")
        print()
        print("  **这才是对判据的检验**——判的时候还不知道答案。")
        print()
    if res["skipped"]:
        print(f"  跳过 {len(res['skipped'])} 条（没有可重跑规格，验不了）：")
        for s in res["skipped"][:6]:
            print(f"    · {s['task']}")
        if len(res["skipped"]) > 6:
            print(f"    … 另有 {len(res['skipped']) - 6} 条")
        print()
    print("=" * 74)
    return 0


def main() -> int:
    global LEDGER
    cmd = sys.argv[1] if len(sys.argv) > 1 else "stats"

    if cmd == "backup":
        why = sys.argv[2] if len(sys.argv) > 2 else "手工备份"
        print("已备份：", backup(why))
        return 0

    if cmd == "prune":
        pres = [a for a in sys.argv[2:] if not a.startswith("--")]
        if not pres:
            print("用法: ledger.py prune 前缀1 [前缀2 ...] [--apply]")
            print("      默认只预演；--apply 才真删，删前自动备份")
            return 2
        apply = "--apply" in sys.argv
        r = prune(tuple(pres), apply=apply, reason="cli")
        _print_prune(r, apply)
        return 0

    if cmd == "blockers":
        from harness import MODEL_VERSION as _MVb
        lvl = None
        ver = _MVb
        for a in sys.argv[2:]:
            if a.isdigit():
                lvl = int(a)
            elif a == "all":
                ver = None
        return _print_blockers(blockers(env_level=lvl, version=ver))

    if cmd == "guard":
        return guard_selftest()

    if cmd == "audit":
        # 支持 `python ledger.py audit 3` 只看 L3；`audit all` 看全部版本
        from harness import MODEL_VERSION as _MV
        lvl = None
        ver = _MV
        for a in sys.argv[2:]:
            if a.isdigit():
                lvl = int(a)
            elif a == "all":
                ver = None
        return _print_audit(audit(env_level=lvl, version=ver))

    if cmd == "resolve-blind":
        from harness import MODEL_VERSION as _MV3
        lvl = None
        ver = _MV3
        for a in sys.argv[2:]:
            if a.isdigit():
                lvl = int(a)
            elif a == "all":
                ver = None
        return _print_resolve_blind(resolve_blind(env_level=lvl, version=ver))

    if cmd == "replay":
        from harness import MODEL_VERSION as _MV2
        lvl = None
        ver = _MV2
        for a in sys.argv[2:]:
            if a.isdigit():
                lvl = int(a)
            elif a == "all":
                ver = None
        return _print_replay(replay(env_level=lvl, version=ver))

    if cmd == "seed":
        n = seed()
        print(f"seed: 新增 {n} 条，账本 {len(entries())} 条")

    if cmd == "demo":
        # demo 是演示，不该写正式账本——自动切到临时文件
        import tempfile
        if LEDGER == PRODUCTION_LEDGER:
            LEDGER = os.path.join(tempfile.gettempdir(), "m1_demo.jsonl")
            if os.path.exists(LEDGER):
                os.remove(LEDGER)
            print(f"demo 自动改用临时账本: {LEDGER}")
        rec = record("degrade", task="demo 任务", note="演示 pending")
        print(f"记入 pending: {rec['id']}")
        resolve(rec["id"], True, "演示回填")
        print("已回填 success=True")
        print(f"账本 {len(entries())} 条，其中 pending {stats()['pending']} 条")
        return 0

    # 支持 `python ledger.py stats 2` 只看 L2
    env_filter = None
    if cmd.isdigit():
        env_filter = int(cmd)
    elif len(sys.argv) > 2 and sys.argv[2].isdigit():
        env_filter = int(sys.argv[2])

    s = stats(env_filter)
    print("=" * 60)
    print("判定账本")
    print("=" * 60)
    print(f"  文件: {os.path.basename(LEDGER)}")
    print(f"  过滤: {s['filter']}")
    print(f"  总数 {s['total']} / 已结算 {s['resolved']} / 待结算 {s['pending']}")
    if s["by_env"]:
        dist = "  ".join(f"{k}:{v}" for k, v in sorted(s["by_env"].items()))
        print(f"  环境分布: {dist}")
    if s.get("by_origin"):
        dist = "  ".join(f"{k}:{v}" for k, v in sorted(s["by_origin"].items()))
        print(f"  来源分布: {dist}")
        if s["by_origin"].get("未声明"):
            print(f"            ↑ {s['by_origin']['未声明']} 条没有 origin 声明"
                  f"（第四十一轮之前的老样本），说不清是谁写的")
    print()
    if not s["calibration"]:
        print("  还没有已结算记录。先跑 `python ledger.py seed`。")
        return 0
    print(f"  {'判定':<10}{'样本':>5}{'成功':>5}{'Laplace':>9}{'Wilson95%':>16}")
    print("  " + "-" * 45)
    for v in ("pass", "degrade", "reject"):
        c = s["calibration"].get(v)
        if c:
            print(f"  {v:<10}{c['n']:>5}{c['success']:>5}"
                  f"{c['laplace']:>9}   [{c['wilson_lo']}, {c['wilson_hi']}]")
        else:
            print(f"  {v:<10}{0:>5}{0:>5}{'-':>9}   -")
    print()
    if not s["calibration"].get("pass"):
        print("  pass 桶为空 = 还没有任何一条结论判过 pass 并被验证。")
        print("  注意：L2 环境下按规则 pass 一律降为 degrade，")
        print("        所以在 L3 之前，pass 桶注定是空的——这不是判据问题。")
    print("  跨环境混算先验是错的：`python ledger.py stats <档位>` 单看一层。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
