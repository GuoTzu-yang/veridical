#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MCP 服务冒烟测试 —— 交付面的端到端验证

为什么要这个（第八十轮）：
    `mcp_server.py` 是**别人能用这套东西的唯一入口**，九个工具。
    而前面几十轮里，我反复改 `run_gates` 的行为：
        cause 规则、能力核验、前置没查成不判 pass、ask 字段……
    一次也没在 MCP 这一层验过。

    单元测试全绿而交付面坏掉，是很容易发生的：中间隔着一层序列化、
    一层参数校验、一层错误处理。

做法：
    起一个真的子进程，走真的 stdio、真的 JSON-RPC 2.0。
    不 import、不 mock——mock 会把这个测试变成"我以为它怎么工作"。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PY = sys.executable


def rpc(proc, msg_id: int, method: str, params: dict | None = None) -> dict:
    payload = {"jsonrpc": "2.0", "id": msg_id, "method": method}
    if params is not None:
        payload["params"] = params
    proc.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
    proc.stdin.flush()
    line = proc.stdout.readline()
    if not line:
        raise RuntimeError(f"{method} 没有响应（进程可能已退出）")
    return json.loads(line)


def call_tool(proc, msg_id: int, name: str, args: dict) -> dict:
    return rpc(proc, msg_id, "tools/call", {"name": name, "arguments": args})


def main() -> int:
    fails = []
    CHECKED = [0]

    def check(name, cond, detail=""):
        CHECKED[0] += 1
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}"
              + (f"  — {detail}" if detail else ""))
        if not cond:
            fails.append(name)

    print("=" * 76)
    print("MCP 服务 · 端到端冒烟（真子进程 / 真 stdio / 真 JSON-RPC）")
    print("=" * 76)

    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    # 别让冒烟测试往正式账本里写：指向临时文件
    env["MODEL1_LEDGER"] = os.path.join(os.environ.get("TEMP", "."),
                                        "m1_mcp_smoke.jsonl")

    proc = subprocess.Popen([PY, os.path.join(ROOT, "mcp_server.py")],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True,
                            encoding="utf-8", env=env, cwd=ROOT)
    try:
        r = rpc(proc, 1, "initialize", {
            "protocolVersion": "2024-11-05", "capabilities": {},
            "clientInfo": {"name": "smoke", "version": "1"}})
        ok = r.get("result", {}).get("serverInfo", {}).get("name")
        check("initialize 有响应", bool(ok), str(ok))

        tools = rpc(proc, 2, "tools/list", {})
        names = [t["name"] for t in tools.get("result", {}).get("tools", [])]
        check("tools/list 返回 9 个工具", len(names) == 9, f"{len(names)}: {names[:3]}…")
        check("九个工具名齐全",
              set(names) == {
                  "model1_evaluate_claim", "model1_evaluate_task",
                  "model1_calibrate", "model1_detect_env", "model1_record",
                  "model1_resolve", "model1_ledger_stats",
                  "model1_auto_resolve", "model1_precheck"},
              str(sorted(names)))

        # 真判一条：e1=2/e2=1/e3=1 → 应当 degrade，并且带 ask
        r3 = call_tool(proc, 3, "model1_evaluate_claim", {
            "text": "冒烟：e1=2 e2=1 e3=1",
            "e1": 2, "e2": 1, "e3": 1, "kind": "world"})
        content = r3.get("result", {}).get("content") or []
        text = content[0].get("text", "") if content else ""
        check("evaluate_claim 走通", bool(text), text[:60].replace("\n", " "))
        check("判定是 degrade", "degrade" in text, text[:60].replace("\n", " "))
        check("带 cause", "info" in text or "env" in text)
        check("带「还差什么」", "还差什么" in text and "→" in text,
              [ln for ln in text.splitlines() if "差" in ln][:1])

        # 前置检查工具
        r4 = call_tool(proc, 4, "model1_precheck", {
            "domain": "file",
            "task": {"path": os.path.abspath(__file__), "op": "read"}})
        text4 = ((r4.get("result", {}).get("content") or [{}])[0].get("text", ""))
        check("precheck 走通", bool(text4), text4[:50].replace("\n", " "))
        check("precheck 认得存在的文件", "ok" in text4.lower(), text4[:50])

        # 环境探测
        r5 = call_tool(proc, 5, "model1_detect_env", {})
        text5 = ((r5.get("result", {}).get("content") or [{}])[0].get("text", ""))
        check("detect_env 走通", "档位" in text5 and "依据" in text5,
              text5[:40].replace(chr(10), " "))
        check("没给 source_root 时会说明为什么是 L1",
              "没告诉我判什么" in text5, text5[-60:].replace(chr(10), " "))

        # 账本统计
        r6 = call_tool(proc, 6, "model1_ledger_stats", {})
        text6 = ((r6.get("result", {}).get("content") or [{}])[0].get("text", ""))
        check("ledger_stats 走通", bool(text6), text6[:50].replace("\n", " "))

        # ---- 写路径：record → resolve，这是最危险的一段 ----
        # 账本被 MODEL1_LEDGER 指到临时文件，所以敢真写。
        print()
        print("  写路径（临时账本，真写真读）")

        r9 = call_tool(proc, 9, "model1_record", {
            "verdict": "degrade", "task": "冒烟·待结算样本",
            "success": None, "env_level": 3})
        t9 = ((r9.get("result", {}).get("content") or [{}])[0].get("text", ""))
        check("record 能写入 pending", "pending" in t9 or "已记" in t9,
              t9[:50].replace("\n", " "))
        import re as _re
        m = _re.search(r"(m1-[0-9a-f]{12})", t9)
        rid = m.group(1) if m else None
        check("record 返回可用的 id", bool(rid), str(rid))

        r10 = call_tool(proc, 10, "model1_ledger_stats", {})
        t10 = ((r10.get("result", {}).get("content") or [{}])[0].get("text", ""))
        check("ledger_stats 看得到刚写的那条", "1" in t10, t10[:70].replace("\n", " "))

        if rid:
            r11 = call_tool(proc, 11, "model1_resolve", {
                "id": rid, "success": True, "evidence": "冒烟回填"})
            t11 = ((r11.get("result", {}).get("content") or [{}])[0].get("text", ""))
            check("resolve 能回填", "success=True" in t11 or "已回填" in t11,
                  t11[:50].replace("\n", " "))

            # 同一条不能回填两次
            r12 = call_tool(proc, 12, "model1_resolve", {
                "id": rid, "success": False})
            j12 = json.dumps(r12, ensure_ascii=False)
            # MCP 的错是 isError:true 挂在 result 里，不是 JSON-RPC error 字段。
            # 第一版查的是小写 "error"，于是明明拒了也被判失败。
            check("重复回填被拒（不静默覆盖）",
                  '"isError": true' in j12 or '"isError":true' in j12,
                  j12[:80])

        # auto_resolve：按任务名批量
        call_tool(proc, 13, "model1_record", {
            "verdict": "degrade", "task": "冒烟·批量样本",
            "success": None, "env_level": 3})
        r14 = call_tool(proc, 14, "model1_auto_resolve", {
            "task": "冒烟·批量样本", "success": False, "evidence": "批量"})
        t14 = ((r14.get("result", {}).get("content") or [{}])[0].get("text", ""))
        check("auto_resolve 能按任务名批量回填",
              "回填" in t14 or "1" in t14, t14[:50].replace("\n", " "))

        # evaluate_task：多条组合
        r15 = call_tool(proc, 15, "model1_evaluate_task", {
            "items": [{"label": "A", "text": "甲", "e1": 2, "e2": 2, "e3": 2},
                      {"label": "B", "text": "乙", "e1": 2, "e2": 1, "e3": 1}],
            "relation": "and"})
        t15 = ((r15.get("result", {}).get("content") or [{}])[0].get("text", ""))
        check("evaluate_task 走通", bool(t15), t15[:50].replace("\n", " "))
        check("evaluate_task 给出组合成功率",
              "p" in t15.lower() or "%" in t15 or "0." in t15,
              t15[:60].replace("\n", " "))

        # calibrate
        r16 = call_tool(proc, 16, "model1_calibrate", {
            "records": [{"verdict": "pass", "success": True},
                        {"verdict": "degrade", "success": True},
                        {"verdict": "reject", "success": False}]})
        t16 = ((r16.get("result", {}).get("content") or [{}])[0].get("text", ""))
        check("calibrate 走通", bool(t16), t16[:50].replace("\n", " "))

        # 错误路径：未知工具不该把服务弄死
        r7 = call_tool(proc, 7, "no_such_tool", {})
        check("未知工具返回错误而不是崩",
              "error" in r7 or "isError" in json.dumps(r7),
              json.dumps(r7, ensure_ascii=False)[:60])

        # 崩过之后还能继续服务
        r8 = rpc(proc, 8, "tools/list", {})
        check("出错后服务仍可用",
              len(r8.get("result", {}).get("tools", [])) == 9)
    finally:
        proc.stdin.close()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        err = proc.stderr.read()
        if err.strip():
            print("  服务 stderr（前 200 字）：", err.strip()[:200])

    print()
    print("=" * 76)
    if fails:
        print(f"FAILED: {len(fails)} 项 -> {fails}")
        return 1
    print(f"ALL PASS  （{CHECKED[0]} 项）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
