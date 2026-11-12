#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
distill.py —— 把执行失败沉淀成教训，写回不变量库

为什么需要
----------
orchestrate.py 每轮失败都会往 dead_ends 里记一条，但**没人读**。
下次换个任务重跑，同样的失败会再发生一次。

这个模块做两件事：
    extract   从 dead_ends 里抽取可复用的教训（不是「这次错了」，
              而是「这类做法会错」）
    write_back  把教训写回 kb/invariants.json，供下一轮的开局读

判据
----
教训必须可复述成一个条件句：「当满足 X 时，不要做 Y，因为 Z」。
抽不出 X/Y/Z 的记录不写 —— 不可操作的教训等于没写。
"""

from __future__ import annotations

import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
KB = os.path.join(HERE, "kb", "invariants.json")

# 失败类型 → 可操作的教训模板
LESSONS = {
    "技术故障": ("当 {where} 抛出 {kind} 时，不要重试同一调用",
               "同一输入会稳定复现同一错误，换路径比重试有效"),
    "质量不达标": ("当 {where} 的指标未达阈值时，不要推进下一阶段",
                "带缺陷继续会让后续所有结论失去前提"),
    "超时": ("当 {where} 超过预算时，不要加大预算而是缩小问题",
            "超时通常说明搜索空间没剪，加钱只买更多等待"),
}


def _kind_of(rec: dict) -> str:
    """从失败记录里判定类型。"""
    txt = " ".join(str(rec.get(k) or "") for k in
                   ("status", "error", "detail", "note"))
    low = txt.lower()
    if any(w in low for w in ("timeout", "超时", "timed out")):
        return "超时"
    if any(w in low for w in ("keyerror", "typeerror", "valueerror",
                              "attributeerror", "indexerror",
                              "filenotfound", "traceback", "技术")):
        return "技术故障"
    return "质量不达标"


def extract(dead_ends) -> list:
    """把失败记录变成「条件句」形式的教训。

    抽不出 where 的记录跳过 —— 不知道在哪失败，就写不出可操作的教训。
    """
    out = []
    for rec in (dead_ends or []):
        kind = _kind_of(rec)
        where = (rec.get("lane") or rec.get("stage")
                 or rec.get("route") or rec.get("name") or "")
        if not where:
            continue
        tmpl = LESSONS.get(kind)
        if not tmpl:
            continue
        claim, why = tmpl
        sentence = claim.format(where=where, kind=kind)
        out.append(dict(
            when=kind,
            where=str(where)[:60],
            rule=sentence,
            because=why,
            source=str(rec.get("id") or rec.get("route") or "")[:40],
        ))
    # 同一 (when, where) 只留一条
    seen, uniq = set(), []
    for it in out:
        key = (it["when"], it["where"])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(it)
    return uniq


def write_back(lessons, path: str = KB) -> dict:
    """把教训合并进不变量库，返回合并统计。"""
    if not lessons:
        return dict(added=0, total=0, path=path)
    try:
        d = json.load(open(path, encoding="utf-8"))
    except Exception:                               # noqa: BLE001
        d = dict(invariants=[])
    inv = d.setdefault("invariants", [])
    have = {str(x.get("rule") or "") for x in inv if isinstance(x, dict)}
    added = 0
    for it in lessons:
        if it["rule"] in have:
            continue
        inv.append(dict(id=f"L{len(inv) + 1:03d}",
                        rule=it["rule"], because=it["because"],
                        when=it["when"], where=it["where"],
                        source=it["source"], origin="distill"))
        added += 1
    d["invariants"] = inv
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(d, fh, ensure_ascii=False, indent=2)
    return dict(added=added, total=len(inv), path=path)


def run(dead_ends, path: str = KB) -> dict:
    lessons = extract(dead_ends)
    return dict(lessons=lessons, **write_back(lessons, path))


# ══════════════════════════════════════════════════════════════════════
def selftest() -> int:
    import tempfile
    bad = 0
    n = 0

    def ck(name, cond, detail=""):
        nonlocal bad, n
        n += 1
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}"
              + (f"  — {detail}" if detail else ""))
        if not cond:
            bad += 1

    # ① 抽得出教训
    de = [dict(lane="M1", status="KeyError: 'y'"),
          dict(lane="M2", status="Timeout"),
          dict(lane="M3", status="指标未达阈值")]
    ls = extract(de)
    ck("三条记录抽三条教训", len(ls) == 3, f"{len(ls)} 条")
    ck("教训是条件句", all("当 " in x["rule"] for x in ls))
    ck("技术故障被识别", any(x["when"] == "技术故障" for x in ls))
    ck("超时被识别", any(x["when"] == "超时" for x in ls))

    # ② 没有 where 的记录跳过
    ck("缺 where 的跳过", len(extract([dict(status="KeyError")])) == 0)

    # ③ 去重
    ls2 = extract([dict(lane="M1", status="KeyError"),
                   dict(lane="M1", status="KeyError")])
    ck("同 lane 同类只留一条", len(ls2) == 1, f"{len(ls2)} 条")

    # ④ 写回
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "inv.json")
        json.dump(dict(invariants=[]), open(p, "w", encoding="utf-8"))
        r1 = write_back(ls, p)
        ck("首次写入全部新增", r1["added"] == 3, f"{r1['added']}")
        r2 = write_back(ls, p)
        ck("重复写入不叠加", r2["added"] == 0, f"{r2['added']}")
        d = json.load(open(p, encoding="utf-8"))
        ck("文件里确实有 3 条", len(d["invariants"]) == 3)

    # ⑤ 真实不变量库能读
    if os.path.exists(KB):
        try:
            json.load(open(KB, encoding="utf-8"))
            ck("真实 kb/invariants.json 可读", True)
        except Exception as e:                      # noqa: BLE001
            ck("真实 kb/invariants.json 可读", False, str(e))

    print(f"\n{'ALL PASS' if bad == 0 else 'FAILED'}  {n - bad}/{n}")
    return 0 if bad == 0 else 1


def main(argv=None) -> int:
    import sys
    a = sys.argv[1:] if argv is None else argv
    if not a or a[0] == "selftest":
        return selftest()
    # python distill.py <dead_ends.json> [不变量库路径]
    src = json.load(open(a[0], encoding="utf-8"))
    de = src if isinstance(src, list) else src.get("dead_ends") or []
    r = run(de, a[1] if len(a) > 1 else KB)
    print(f'  抽到 {len(r["lessons"])} 条教训，'
          f'新增 {r["added"]} 条，库内共 {r["total"]} 条')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
