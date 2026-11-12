#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
model1-arch MCP server（stdio transport）

把六轮迭代出来的判定能力暴露成 MCP 工具，任何 DSH 会话都能调：
  model1_evaluate_claim   单条结论打分
  model1_evaluate_task    整题组合成功率
  model1_calibrate        用实测记录校准先验
  model1_detect_env       证据环境自动探测

协议：JSON-RPC 2.0，NDJSON（每行一条消息），MCP 2024-11-05。

手动测试：
  echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' | python mcp_server.py
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from harness import Claim, run_gates, EvidenceEnv, ENV_LEVELS, detect_env, \
    derive_e3, e3_reason, E3_SOURCE  # noqa: E402
from extend import evaluate_claims  # noqa: E402   ← 架构主干，MCP 不另写管线
from taskgraph import TaskGraph, Item, calibrate, VERDICT_PRIOR, wilson  # noqa: E402
import ledger as L  # noqa: E402

SERVER_INFO = {"name": "model1-arch", "version": "1.0.0"}
PROTOCOL = "2024-11-05"

TOOLS = [
    {
        "name": "model1_evaluate_claim",
        "description": (
            "给一条结论打分并过三道闸。返回 C 值、每道闸的判定（pass/degrade/reject）与卡点。"
            "kind: world=世界断言 / observation=观测事实 / procedure=操作规程。"
            "input_valid: 规程类专用，false 表示关键输入已失效（一票否决），null 表示未检查。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "结论内容"},
                "e1": {"type": "integer", "minimum": 0, "maximum": 2,
                       "description": "溯源度：0 无来源 / 1 有出处名 / 2 指到具体位置"},
                "e2": {"type": "integer", "minimum": 0, "maximum": 2,
                       "description": "独立度：0 单一同源 / 1 两源疑同源 / 2 三源独立或一源+复算"},
                "e3": {"type": "integer", "minimum": 0, "maximum": 2,
                       "description": "可复现度：0 不可 / 1 部分 / 2 给命令数据公式即可复现。"
                                      "若给了 e3_source，此项被覆盖"},
                "e3_source": {"type": "string",
                              "enum": sorted(E3_SOURCE.keys()),
                              "description": "证据来源，自动推导 e3（优先于 e3）："
                                             + "；".join(f"{k}={v[0]}" for k, v in E3_SOURCE.items())},
                "kind": {"type": "string", "enum": ["world", "observation", "procedure"],
                         "description": "结论类别，默认 world"},
                "input_valid": {"type": ["boolean", "null"],
                                "description": "规程类的关键输入是否有效"},
                "env_level": {"type": "integer", "minimum": 0, "maximum": 3,
                              "description": "证据环境档位，默认 3（完整）"},
                "refuted_by_test": {"type": "boolean",
                                    "description": "是否已被实测直接推翻（一票否决）"},
            },
            "required": ["text", "e1", "e2", "e3"],
        },
    },
    {
        "name": "model1_evaluate_task",
        "description": (
            "把多条结论按组合关系算成整题成功率。relation: and=全过才算成 / or=任一成功 "
            "/ weighted=加权。返回整体 p_success 与最弱一环。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "任务名"},
                "relation": {"type": "string", "enum": ["and", "or", "weighted"],
                             "description": "组合关系，默认 and"},
                "items": {
                    "type": "array",
                    "description": "条目列表，每项含 label 与 claim 字段",
                    "items": {
                        "type": "object",
                        "properties": {
                            "label": {"type": "string"},
                            "e1": {"type": "integer"}, "e2": {"type": "integer"},
                            "e3": {"type": "integer"},
                            "kind": {"type": "string"},
                            "input_valid": {"type": ["boolean", "null"]},
                            "e3_source": {"type": "string",
                                          "enum": sorted(E3_SOURCE.keys()),
                                          "description": "给了就按来源推导 e3"},
                            "weight": {"type": "number"},
                        },
                        "required": ["label", "e1", "e2", "e3"],
                    },
                },
                "env_level": {"type": "integer", "minimum": 0, "maximum": 3},
                "record": {"type": "boolean",
                           "description": "true 则自动记一条 pending 到账本，并返回 record_id"},
            },
            "required": ["name", "items"],
        },
    },
    {
        "name": "model1_calibrate",
        "description": (
            "用实测记录校准判定先验。每条记录是一次「判定 → 实际是否成功」。"
            "返回各判定的样本数、实测率、Laplace 中点、Wilson 95% 区间。"
            "样本 < 10 时点估计没有解释力，只有区间下界能用。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "records": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "verdict": {"type": "string",
                                        "enum": ["pass", "degrade", "reject"]},
                            "success": {"type": "boolean"},
                            "note": {"type": "string"},
                        },
                        "required": ["verdict", "success"],
                    },
                }
            },
            "required": ["records"],
        },
    },
    {
        "name": "model1_detect_env",
        "description": (
            "探测证据环境档位。只看硬事实：目录里有没有源码文件、有没有可执行产物、能否联网。"
            "返回 L0-L3 与依据。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "source_root": {"type": "string", "description": "源码目录绝对路径"},
                "executable": {"type": "string", "description": "可执行文件绝对路径"},
                "network": {"type": "boolean", "description": "是否能联网"},
                "wsl_distro": {"type": "string",
                               "description": "WSL 发行版名（如 Ubuntu-22.04），给了就在里面判可执行性"},
                "wsl_executable": {"type": "string",
                                   "description": "WSL 内的可执行路径（如 /usr/bin/observer）"},
            },
        },
    },
    {
        "name": "model1_record",
        "description": (
            "把一次判定记入账本。success 省略表示结果未知（pending），事后再用 "
            "model1_resolve 回填。账本是 append-only JSONL，用来攒校准样本。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "verdict": {"type": "string", "enum": ["pass", "degrade", "reject"]},
                "task": {"type": "string", "description": "这条判定属于哪个任务/条目"},
                "note": {"type": "string", "description": "备注"},
                "success": {"type": ["boolean", "null"],
                            "description": "已知结果就填，未知留空"},
                "evidence": {"type": "string", "description": "结果依据"},
            },
            "required": ["verdict", "task"],
        },
    },
    {
        "name": "model1_resolve",
        "description": "回填某条 pending 判定的实际结果。同一条只能回填一次。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "model1_record 返回的 id"},
                "success": {"type": "boolean", "description": "实际是否成功"},
                "evidence": {"type": "string", "description": "依据"},
            },
            "required": ["id", "success"],
        },
    },
    {
        "name": "model1_ledger_stats",
        "description": (
            "读账本，输出各判定的样本数、Laplace 中点与 Wilson 95% 区间。"
            "这是 calibrate 的数据来源——账本里没有样本，先验就只能靠拍。"
        ),
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "model1_auto_resolve",
        "description": (
            "按任务名批量回填：把该任务下所有 pending 记录一次性标为成功或失败。"
            "比逐条 resolve 实用——一次任务评估通常只产生一条 pending。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "task": {"type": "string", "description": "任务名（与 evaluate_task 时一致）"},
                "success": {"type": "boolean", "description": "实际是否成功"},
                "evidence": {"type": "string", "description": "依据"},
            },
            "required": ["task", "success"],
        },
    },
    {
        "name": "model1_precheck",
        "description": (
            "执行之前判断「这一步现在做得了吗」。结果直接喂给 evaluate_claim 的 input_valid。"
            "领域：file（路径/权限）、http（URL/DNS）、sql（表/列/维度，走 WSL seekdb）。"
            "新增领域只需继承 Precheck 并注册，判据代码不用改。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "domain": {"type": "string", "enum": ["file", "http", "sql"]},
                "task": {"type": "object",
                         "description": "file: {path, op}；http: {url}；sql: {sql}"},
            },
            "required": ["domain", "task"],
        },
    },
]


def _claim_from(d: dict) -> Claim:
    # e3 优先按证据来源推导：调用方只需说"证据从哪来"，不用自己查表
    if d.get("e3_source"):
        e3 = derive_e3(d["e3_source"])
    else:
        e3 = int(d.get("e3", 0))
    return Claim(
        cid=d.get("label") or d.get("cid") or "C1",
        text=d.get("text") or d.get("label") or "",
        e1=int(d.get("e1", 0)),
        e2=int(d.get("e2", 0)),
        e3=e3,
        kind=d.get("kind", "world"),
        input_valid=d.get("input_valid", None),
        refuted_by_test=bool(d.get("refuted_by_test", False)),
    )


def call_evaluate_claim(args: dict) -> dict:
    """单条主张评估——走架构主干，不另写一套管线。"""
    env = EvidenceEnv(int(args.get("env_level", 3)))
    c = _claim_from(args)
    out = evaluate_claims([c], env=env, rounds=0,
                           task_name=c.cid,
                           prior=(dict(args["prior"]) if args.get("prior") else None),
                           origin="mcp")
    r = out["pipeline"]["results"][0]
    src = args.get("e3_source")
    e3_note = f"（来源={src}：{e3_reason(src)}）" if src else ""
    lines = [
        f"结论: {c.text}",
        f"维度: e1={c.e1} e2={c.e2} e3={c.e3}{e3_note} kind={c.kind}",
        f"C 值: {r['C']}/6",
        f"环境: L{env.level}",
        "闸门:",
    ]
    for g in r["ledger"]:
        lines.append(f"  {g['gate']}({g['label']}) 值={g['value']} 线={g['pass_at']} → {g['verdict']}")
    tail = f"最终: {r['final']}"
    if r.get("cause"):
        tail += f"（成因={r['cause']}）"
    if r.get("blocked_at"):
        tail += f"（卡在 {r['blocked_at']}）"
    lines.append(tail)
    # 「还差什么」必须传到交付面（第八十轮）。
    # 前面几轮把 ask 建出来了，但 MCP 这边没打印——
    # 造了机制不接到出口，等于没造。
    asks = r.get("ask") or []
    if asks:
        lines.append("还差什么：")
        for a in asks:
            lines.append(f"  {a['dim']} {a['have']}→{a['need']}"
                         f"（差 {a['delta']}）{a.get('how', '')}")
    elif r["final"] != "pass":
        lines.append("还差什么：（这一档已无维度缺口，卡点在一票否决项）")

    if out["pre_verify"] and out["pre_verify"][0].get("checked"):
        pv = out["pre_verify"][0]
        lines.append(f"事前取证: {pv.get('status')} → input_valid={pv.get('input_valid')}"
                     f"（{pv.get('reason', '')[:40]}）")
    return {"content": [{"type": "text", "text": "\n".join(lines)}]}


def call_evaluate_task(args: dict) -> dict:
    """多条主张组合评估——同样走架构主干。"""
    env = EvidenceEnv(int(args.get("env_level", 3)))
    claims = [_claim_from(it) for it in args.get("items", [])]
    labels = [it.get("label", f"item{i}")
              for i, it in enumerate(args.get("items", []))]

    prior = dict(args["prior"]) if args.get("prior") else None
    if prior is not None:
        prior["__source__"] = "调用方指定"
    out = evaluate_claims(claims, env=env,
                           relation=args.get("relation", "and"),
                           task_name=args.get("name", "task"),
                           rounds=0, record=bool(args.get("record")),
                           prior=prior, origin="mcp")
    rows = out["combo"]["rows"]
    lines = [f"任务: {args.get('name', 'task')}（{out['combo']['relation']}）",
             f"先验来源: {out['prior_source']}", "条目:"]
    for row in rows:
        cause = f"  cause={row['cause']}" if row.get("cause") else ""
        lines.append(f"  {row['label']:<14} {row['verdict']:<8} p={row['p']}  "
                     f"C={row['C']}{cause}")
    lines.append(f"整体成功率: {out['combo']['p_success']}")
    lines.append(f"最弱一环: {out['combo']['weakest']}")

    if out["pre_verify"]:
        checked = [v for v in out["pre_verify"] if v.get("checked")]
        if checked:
            lines.append("事前取证:")
            for v in checked:
                mech = f" 机制={v['mechanism']}" if v.get("mechanism") is not None else ""
                lines.append(f"  {v['cid']}: {v.get('status')}{mech} → "
                             f"input_valid={v.get('input_valid')}  {v.get('reason', '')[:40]}")

    if out["recorded"]:
        lines.append("")
        lines.append(f"已记入账本 {', '.join(out['recorded'])}（pending，L{env.level}）")
        lines.append(f"做完后调用 model1_auto_resolve(task=\"{args.get('name', 'task')}\", "
                     f"success=true/false) 回填")

    return {"content": [{"type": "text", "text": "\n".join(lines)}]}


def call_calibrate(args: dict) -> dict:
    """优先用传入的 records；不传则读账本。账本才是样本的归宿。"""
    recs = [(x["verdict"], bool(x["success"]), x.get("note", ""))
            for x in args.get("records", [])]
    source = "传入记录"

    if not recs:
        s = L.stats()
        recs = []
        for e in L.entries():
            if e.get("success") is not None:
                recs.append((e["verdict"], bool(e["success"]), e.get("task", "")))
        source = f"账本 {os.path.basename(L.LEDGER)}（{len(recs)} 条已结算）"

    if not recs:
        return {"content": [{"type": "text",
                             "text": "没有任何可用样本。先 model1_record 记判定，"
                                     "再 model1_auto_resolve 回填结果。"}]}

    cal = calibrate(recs)
    lines = [f"数据源: {source}", "",
             "判定   样本  成功  实测率  Laplace  Wilson95%"]
    for v in ("pass", "degrade", "reject"):
        c = cal.get(v)
        if c:
            lines.append(f"{v:<7}{c['n']:>4}{c['success']:>6}{str(c['raw_rate']):>8}"
                         f"{c['laplace']:>9}   [{c['wilson_lo']}, {c['wilson_hi']}]")
        else:
            lines.append(f"{v:<7}{0:>4}{0:>6}{'-':>8}{'-':>9}   -")
    lines.append("")
    lines.append("样本 < 10 时，点估计无解释力；只有 Wilson 下界能拿去决策。")
    return {"content": [{"type": "text", "text": "\n".join(lines)}]}


def call_detect_env(args: dict) -> dict:
    env, why = detect_env(
        source_root=args.get("source_root"),
        executable=args.get("executable"),
        network=bool(args.get("network", True)),
        wsl_distro=args.get("wsl_distro"),
        wsl_executable=args.get("wsl_executable"),
    )
    txt = (f"档位: L{env.level} —— {ENV_LEVELS[env.level]}\n"
           f"依据: {why['reason']}\n"
           f"各维上限: {env.describe()['caps']}")
    # 不传 source_root / executable 时必然是 L1，这得说清楚：
    # 「我不知道你要判什么」和「这个环境很弱」是两件事。
    if not args.get("source_root") and not args.get("executable"):
        txt += ("\n注意: 没给 source_root / executable，所以只能按「只看得见路径」算 L1。\n"
                "      这不代表环境差，只代表**没告诉我判什么**。\n"
                "      判某个目录请传 source_root，判产物请传 executable。")
    return {"content": [{"type": "text", "text": txt}]}


def call_record(args: dict) -> dict:
    rec = L.record(
        verdict=args["verdict"],
        task=args.get("task", ""),
        note=args.get("note", ""),
        success=args.get("success", None),
        evidence=args.get("evidence", ""),
        env_level=args.get("env_level", None),
    )
    state = "已结算" if rec["success"] is not None else "pending"
    env = f"L{rec['env_level']}" if rec.get("env_level") is not None else "未标环境"
    return {"content": [{"type": "text",
                         "text": f"已记入 {rec['id']}（{state}，{env}）\n{json.dumps(rec, ensure_ascii=False)}"}]}


def call_resolve(args: dict) -> dict:
    ev = L.resolve(args["id"], bool(args["success"]), args.get("evidence", ""))
    return {"content": [{"type": "text",
                         "text": f"已回填 {ev['id']} success={ev['success']}\n{json.dumps(ev, ensure_ascii=False)}"}]}


def call_ledger_stats(args: dict) -> dict:
    from harness import MODEL_VERSION
    env_f = args.get("env_level", None)
    # 默认按当前判据版本统计——跟 evaluate_task 同一个口径
    ver_f = args.get("version", MODEL_VERSION)

    s = L.stats(env_f, ver_f)
    dist = "  ".join(f"{k}:{v}" for k, v in sorted(s["by_env"].items())) or "-"
    vdist = "  ".join(f"{k}:{v}" for k, v in sorted(s["by_version"].items())) or "-"
    odist = "  ".join(f"{k}:{v}" for k, v in sorted(s.get("by_origin", {}).items())) or "-"
    lines = [f"过滤: {s['filter']}    总数 {s['total']} / 已结算 {s['resolved']} / 待结算 {s['pending']}",
             f"账本: {os.path.basename(L.LEDGER)}",
             f"环境分布: {dist}    版本分布: {vdist}",
             f"来源分布: {odist}",
             "", "判定   样本  成功  Laplace  Wilson95%"]
    for v in ("pass", "degrade", "reject"):
        c = s["calibration"].get(v)
        if c:
            lines.append(f"{v:<7}{c['n']:>4}{c['success']:>6}{c['laplace']:>9}"
                         f"   [{c['wilson_lo']}, {c['wilson_hi']}]")
        else:
            lines.append(f"{v:<7}{0:>4}{0:>6}{'-':>9}   -")

    # 关键对照：同环境下全部版本有多少条，让"新判据样本不够"这件事无法被忽略
    s_all = L.stats(env_f, None)
    if s_all["total"] != s["total"]:
        lines.append("")
        lines.append(f"对照：同环境下全部版本共 {s_all['total']} 条"
                     f"（当前判据 v{ver_f} 只占 {s['total']} 条）")
        lines.append("  旧版本样本不该决定新判据的先验——样本不够就用硬编码，不借旧数据装点。")

    if s["pending"]:
        lines.append(f"\n有 {s['pending']} 条待结算——用 model1_auto_resolve 或 model1_resolve 回填。")
    return {"content": [{"type": "text", "text": "\n".join(lines)}]}


def call_auto_resolve(args: dict) -> dict:
    task = args["task"]
    success = bool(args["success"])
    ev = args.get("evidence", "")
    hit = [e for e in L.entries()
           if e.get("task") == task and e.get("success") is None]
    if not hit:
        return {"content": [{"type": "text",
                             "text": f"任务『{task}』下没有 pending 记录"}]}
    ids = []
    for e in hit:
        L.resolve(e["id"], success, ev)
        ids.append(e["id"])
    return {"content": [{"type": "text",
                         "text": f"已回填 {len(ids)} 条（任务『{task}』→ success={success}）\n"
                                 + "\n".join(f"  {i}" for i in ids)}]}


def call_precheck(args: dict) -> dict:
    from precheck import check_task, REGISTRY
    domain = args.get("domain", "")
    task = args.get("task", {}) or {}
    if domain not in REGISTRY:
        return {"content": [{"type": "text",
                             "text": f"未注册的领域 {domain}，可用：{sorted(REGISTRY)}"}],
                "isError": True}
    r = check_task(domain, task)
    label = {"ok": "可行", "fail": "不可行", "unknown": "没查成"}[r.status]
    iv = "True" if r.ok is True else ("False" if r.ok is False else "None")
    note = ""
    if r.status == "unknown":
        note = "\n注意：unknown ≠ fail。这是「检查器不可用」，不是「任务做不了」。"
    return {"content": [{"type": "text",
                         "text": f"{label}（{r.status}）  {r.reason}\n"
                                 f"（领域 {domain}：{REGISTRY[domain].describe()}）\n"
                                 f"→ input_valid={iv}{note}"}]}


HANDLERS = {
    "model1_evaluate_claim": call_evaluate_claim,
    "model1_evaluate_task": call_evaluate_task,
    "model1_calibrate": call_calibrate,
    "model1_detect_env": call_detect_env,
    "model1_record": call_record,
    "model1_resolve": call_resolve,
    "model1_ledger_stats": call_ledger_stats,
    "model1_auto_resolve": call_auto_resolve,
    "model1_precheck": call_precheck,
}


def handle(msg: dict) -> dict | None:
    mid = msg.get("id")
    method = msg.get("method", "")

    if method == "initialize":
        return {"jsonrpc": "2.0", "id": mid, "result": {
            "protocolVersion": PROTOCOL,
            "capabilities": {"tools": {}},
            "serverInfo": SERVER_INFO,
        }}

    if method == "notifications/initialized":
        return None

    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": mid, "result": {"tools": TOOLS}}

    if method == "tools/call":
        params = msg.get("params", {})
        name = params.get("name")
        fn = HANDLERS.get(name)
        if not fn:
            return {"jsonrpc": "2.0", "id": mid,
                    "error": {"code": -32601, "message": f"unknown tool: {name}"}}
        try:
            return {"jsonrpc": "2.0", "id": mid,
                    "result": fn(params.get("arguments", {}) or {})}
        except Exception as e:
            return {"jsonrpc": "2.0", "id": mid, "result": {
                "content": [{"type": "text", "text": f"ERROR: {type(e).__name__}: {e}"}],
                "isError": True,
            }}

    if method == "ping":
        return {"jsonrpc": "2.0", "id": mid, "result": {}}

    return {"jsonrpc": "2.0", "id": mid,
            "error": {"code": -32601, "message": f"unknown method: {method}"}}


def main() -> int:
    # MCP 是正式入口，允许写正式账本。
    # 其它脚本（测试、演示、自测）不绑定，于是默认写不进去——
    # 这样"忘记隔离"的后果是拒写，而不是悄悄污染。
    L.bind_production("MCP 服务入口")
    for raw in sys.stdin:
        raw = raw.strip()
        if not raw:
            continue
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            continue
        resp = handle(msg)
        if resp is not None:
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
