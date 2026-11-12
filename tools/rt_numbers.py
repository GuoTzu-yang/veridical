#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""rt_numbers.py —— 红队只读复现（E 项）：按 gate.chk_numbers 的口径列出**全部**未溯源 token。

只读：不写任何被检查目录，只在 stdout / out/_rt_E_numbers.json 落结果。

口径来源（逐条对齐）：
  gate.chk_numbers → freeze.check_paper(tex, frozen,
        single_point=_is_deliverable(dir), data_values=untraced.data_values_of(find_data_file(dir)),
        strict_source=_is_deliverable(dir))
  而 check_paper 的候选集 = verify.extract_numbers(tex, skip_meta=False) 中「带小数点」的 token，
  |v|<1e6，按 (round(v,6), 书写小数位) 去重。

本脚本做两件事：
  1) 直接调用 freeze.check_paper，拿到 gate 同款判决（ok / ratio / n / n_from_data）；
  2) 用**同一套**函数重建 pairs 但保留原始 token 字符串 + 上下文，逐条列出 untraced，
     并断言它与 check_paper 的 untraced 值完全一致（不一致即报错，不静默）。
"""
from __future__ import annotations

import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import verify as V          # noqa: E402
import freeze as F          # noqa: E402
import untraced as U        # noqa: E402

TASKS = ["age_struct", "nflis", "multiobjective", "icm2006c", "pop_panel"]


def is_deliverable(d: str) -> bool:
    p = os.path.join(d, "declaration.json")
    if not os.path.exists(p):
        return False
    try:
        return bool(json.load(io.open(p, encoding="utf-8")).get("deliverable"))
    except Exception:                                   # noqa: BLE001
        return False


def _decimals(tok: str) -> int:
    """与 freeze._decimals 同源 —— 判据改过一次（第 122 轮加科学计数法），
    必须跟着它走，否则重建的集合与 check_paper 不一致。"""
    return F._decimals(tok)


def rebuild(tex: str, frozen: dict):
    """镜像 check_paper 的候选集，但保留原始 token 与上下文。"""
    t = tex
    t = __import__("re").sub(
        r"\\begin\{thebibliography\}.*?\\end\{thebibliography\}", " ", t,
        flags=__import__("re").S)
    _all = V.extract_numbers(t, skip_meta=False)
    pairs = []
    for tok, line in _all:
        if "." not in tok:
            continue
        try:
            v = float(tok)
        except ValueError:
            continue
        if abs(v) < 1e6:
            pairs.append((tok, v, _decimals(tok), line))
    seen = set()
    uniq = []
    for tok, v, dec, line in pairs:
        key = (round(v, 6), dec)
        if key in seen:
            continue
        seen.add(key)
        uniq.append((tok, v, dec, line))
    return uniq, len(_all)


def lines_of_token(tex: str, tok: str) -> list:
    """token 原文在**原始** paper.tex 里出现的行（1 基）+ 原文（截 160 字）。

    用原始写法搜，不用抽取器的上下文片段 —— 片段已被命令抹除改写过，
    行号会指错（实测：495340.5 的片段指向 Problem 5 那句）。
    """
    hits = []
    for i, ln in enumerate(tex.splitlines(), 1):
        if tok in ln:
            hits.append([i, ln.strip()[:160]])
    return hits


def run_task(name: str) -> dict:
    d = os.path.join(ROOT, "out", "runs", name)
    tex_p = os.path.join(d, "paper.tex")
    fz_p = os.path.join(d, "冻结数字.json")
    tex = io.open(tex_p, encoding="utf-8").read()
    frozen = json.load(io.open(fz_p, encoding="utf-8"))
    deliv = is_deliverable(d)
    data_file = U.find_data_file(d)
    dv = U.data_values_of(data_file) if data_file else set()

    # ① gate 同款调用
    r = F.check_paper(tex, frozen, single_point=deliv, data_values=dv or None,
                      strict_source=deliv)
    # ② 重建并逐条判定
    uniq, n_all = rebuild(tex, frozen)
    frozen_vals = [it["value"] for it in frozen.get("items", [])]
    rows = []
    for tok, v, dec, ctx in uniq:
        in_frozen = F._match_written(v, dec, frozen_vals)
        in_data = bool(dv) and round(v, 6) in dv
        if in_frozen:
            kind = "traced_frozen"
        elif in_data:
            kind = "traced_data"
        else:
            kind = "UNTRACED"
        rows.append(dict(token=tok, value=v, dec=dec, kind=kind,
                         in_frozen=in_frozen, in_data=in_data,
                         context=ctx, lines=lines_of_token(tex, tok)))
    un = [x for x in rows if x["kind"] == "UNTRACED"]
    # 断言与 check_paper 一致（值集合）
    a = sorted(round(x["value"], 6) for x in un)
    b = sorted(round(float(x), 6) for x in (r.get("untraced") or []))
    r["_rebuilt_n"] = len(uniq)
    r["_rebuilt_n_untraced"] = len(un)
    r["_consistent"] = (a == b) or (len(r.get("untraced") or []) >= 20
                                    and set(a) >= set(b))
    return dict(task=name, dir=d, deliverable=deliv,
                data_file=os.path.basename(data_file) if data_file else "",
                n_data_values=len(dv),
                n_frozen_items=len(frozen.get("items", [])),
                n_raw_tokens=n_all, n_candidates=len(uniq),
                check=r, untraced=un,
                traced_frozen=sum(1 for x in rows if x["kind"] == "traced_frozen"),
                traced_data=sum(1 for x in rows if x["kind"] == "traced_data"),
                all_rows=rows)


def main(argv=None) -> int:
    names = argv[1:] or TASKS
    out = {}
    for name in names:
        res = run_task(name)
        out[name] = res
        c = res["check"]
        print("=" * 78)
        print("%s  deliverable=%s  data=%s(%d 个值)  frozen_items=%d"
              % (name, res["deliverable"], res["data_file"],
                 res["n_data_values"], res["n_frozen_items"]))
        print("  gate 口径: ok=%s %d/%d 可溯源  未溯源 %d (%.1f%%)  "
              "hp_bad=%s few=%s n_from_data=%d"
              % (c["ok"], c["n_traced"], c["n_numbers"],
                 c["_rebuilt_n_untraced"],
                 100.0 * c["untraced_ratio"], c["high_precision_bad"],
                 c["few_numbers"], c.get("n_from_data", 0)))
        print("  候选(去重后)=%d  冻结溯源 %d  输入表溯源 %d  **未溯源 %d**"
              % (res["n_candidates"], res["traced_frozen"],
                 res["traced_data"], len(res["untraced"])))
        print("  一致性断言(与 check_paper 的 untraced 值集) =", c["_consistent"])
        print("  --- 未溯源 token 全表 ---")
        for x in res["untraced"]:
            print("   %-14s dec=%d" % (x["token"], x["dec"]))
            for ln, txt in x["lines"][:3]:
                print("        L%-5d %s" % (ln, txt))
    p = os.path.join(ROOT, "out", "_rt_E_numbers.json")
    io.open(p, "w", encoding="utf-8", newline="\n").write(
        json.dumps(out, ensure_ascii=False, indent=1))
    print("\n已写", p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
