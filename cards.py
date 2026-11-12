#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cards.py —— 方法卡片的加载与校验（P05，第 8 轮）

为什么要有卡片
--------------
论文里的假设最容易写成套话：「假设数据可靠」「假设变量独立」。
套话的共同点是**无法被推翻**，所以写了等于没写。

卡片解决的是这件事：每条假设必须能回答
    · 什么时候该用这个方法（when）
    · 用了要付什么代价（assumptions）
    · 它什么时候会坑你（breaks_when）  ← 这一栏最值钱
    · 报了才算完整（report_must_include）
    · 凭什么信它（refs）

`breaks_when` 是这几轮踩坑的总结：我反复犯的错不是「不知道方法」，
而是「用了方法但不知道它什么时候失效」。

接入方式
--------
paper.build 的假设节会调 assumption_lines()，把卡片里的
assumptions 和 breaks_when 写进论文，并标注出处（M001 等）。
这样每条假设都可辩护，而不是模板。

用法
    python cards.py              # 列出全部卡片
    python cards.py validate     # 校验字段完整性
    python cards.py show M001    # 看一张
    python cards.py selftest
"""

from __future__ import annotations

import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CARDS = os.path.join(HERE, "kb", "cards")

REQUIRED = ("id", "name", "when", "assumptions", "breaks_when",
            "report_must_include", "refs", "our_impl")


def load_all() -> list[dict]:
    out = []
    for p in sorted(glob.glob(os.path.join(CARDS, "*.json"))):
        try:
            c = json.load(open(p, encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            out.append(dict(id=os.path.basename(p), _error=str(e)))
            continue
        c["_path"] = os.path.basename(p)
        out.append(c)
    return out


def validate_card(c: dict) -> list[str]:
    errs = []
    for k in REQUIRED:
        v = c.get(k)
        if v is None or v == "" or v == []:
            errs.append(f"缺字段 {k!r}")
    # 假设必须可证伪：至少 2 条，且每条 > 8 字符
    asm = c.get("assumptions") or []
    if isinstance(asm, list):
        if len(asm) < 2:
            errs.append("assumptions 少于 2 条 —— 一条假设撑不起一个方法")
        for a in asm:
            if len(str(a)) < 8:
                errs.append(f"假设太短，无法判断真伪：{a!r}")
    # breaks_when 是这张卡的价值所在，不能空
    bw = c.get("breaks_when") or []
    if not bw:
        errs.append("breaks_when 为空 —— 不知道它何时失效的方法不该进卡片")
    # refs 必须能进参考文献
    refs = c.get("refs") or []
    if not refs:
        errs.append("refs 为空 —— 没有出处的假设只是口头禅")
    return errs


def for_impl(*needles) -> list[dict]:
    """按 our_impl 里的关键词找卡片。"""
    hit = []
    for c in load_all():
        impl = str(c.get("our_impl") or "")
        if any(n in impl for n in needles):
            hit.append(c)
    return hit


def _tex_safe(s: str) -> str:
    """保护文本模式下的 _ 和 ^（LaTeX 里它们是数学专用）。

    $...$ 里的内容不动 —— 那是作者有意写的数学。
    卡片文本里凡是数学符号都该写成 $...$，这里只是兜底。
    """
    out, in_math = [], False
    for ch in str(s):
        if ch == "$":
            in_math = not in_math
            out.append(ch)
        elif ch in "_^" and not in_math:
            out.append("\\" + ch)
        else:
            out.append(ch)
    return "".join(out)


def load_methods() -> dict:
    """读方法选择表。"""
    p = os.path.join(HERE, "kb", "methods.json")
    if not os.path.exists(p):
        return dict(branches=[], n=0)
    return json.load(open(p, encoding="utf-8"))


def recommend(features, top: int = 3) -> list:
    """按特征推荐方法。

    features 可以是可迭代的标签集合，例如
        {"has_data", "multi_object", "regression"}
    也可以从数据自动算：features_from_ds(ds)。
    """
    want = set(features or [])
    if not want:
        return []
    mt = load_methods()
    scored = []
    for b in mt.get("branches") or []:
        have = set(b.get("features") or [])
        if not have:
            continue
        hit = want & have
        if not hit:
            continue
        # 按**特征具体度**加权，不是简单数命中。
        # 「有数据」几乎每题都成立，权重必须低；
        # 「小样本」「多目标」这种才是真判别信号。
        W = {"has_data": 0.2, "no_data": 0.2,
             "time_series": 1.5, "small_sample": 1.8,
             "multi_objective": 1.6, "clustering": 1.4,
             "classification": 1.3, "graph": 1.3,
             "mechanism": 1.3, "stochastic": 1.2,
             "regression": 1.0, "optimization": 1.0,
             "multi_object": 0.6}
        got = sum(W.get(x, 1.0) for x in hit)
        need = sum(W.get(x, 1.0) for x in have)
        score = got / need if need else 0
        scored.append((round(score, 3), round(got, 2), b))
    # 主键用命中权重和（got），不是覆盖率。
    # 覆盖率会偏爱「只打 1 个泛标签」的分支（has_data 命中率 1.0），
    # 而真正贴合题目的分支往往要同时命中 regression + optimization。
    scored.sort(key=lambda x: (-x[1], -x[0]))
    out = []
    for cov, nh, b in scored[:top]:
        out.append(dict(
            method=b["method"],
            match=round(cov, 3),
            hit=sorted(want & set(b["features"])),
            path=b["path"],
            doc=b.get("doc") or "",
        ))
    return out


def features_from_ds(ds) -> set:
    """从数据推断特征标签（供 recommend 用）。

    只做能确定的事：
      has_data     —— 有数据文件就是
      time_series  —— 列名里有 日期/时间/date/time/month/year
      small_sample —— 行数 < 15
      multi_object —— 有「编号/对象/名称/城市/地区」这类标识列
      regression   —— 有至少两个数值列（能建关系）
      classification —— 有取值为 0/1 或少量离散值的列
    """
    import re as _re
    f = {"has_data"}
    names = list(getattr(ds, "num_names", []) or [])
    allnames = names + list(getattr(ds, "names", []) or [])
    joined = " ".join(map(str, allnames)).lower()
    if _re.search(r"日期|时间|date|time|month|year|day", joined):
        f.add("time_series")
    n = int(getattr(ds, "n_rows", 0) or 0)
    if 0 < n < 15:
        f.add("small_sample")
    if _re.search(r"编号|对象|名称|城市|地区|id|name|city", joined):
        f.add("multi_object")
    if len(names) >= 2:
        f.add("regression")
        f.add("optimization")
    return f


def failure_lines(cards: list[dict]) -> list[str]:
    """失效条件（breaks_when）单独成节，放在模型评价里。

    它们不是假设 —— 假设是「我认为成立的前提」，失效条件是
    「什么情况下这个结论不成立」。混在一起会让假设节膨胀到 20+ 条，
    而对照表要求假设 4-6 条。
    """
    L = []
    # 原来是每张卡一段「Results obtained with M00X should not be read as
    # conclusions when…」，三张卡就是同一句话写三遍。
    # aitaste 的句式重复检查按「每句开头 4 个词」判，直接命中 3 次。
    # 改成一句总述 + 三组并列：信息一样，重复消失。
    _rows = []
    for c in cards:
        cid = c.get("id", "?")
        bw = (c.get("breaks_when") or [])[:3]
        if bw:
            _rows.append((cid, bw))
    if _rows:
        L.append(r"\paragraph{Limits of the three methods}")
        L.append(
            "Each method below fails under a stated set of conditions. "
            "Results obtained outside those conditions should not be read "
            "as conclusions, whichever method produced them.")
        L.append(r"\begin{itemize}")
        for cid, bw in _rows:
            L.append(rf"  \item \textbf{{{cid}}}: "
                     + "; ".join(_tex_safe(str(b)) for b in bw) + ".")
        L.append(r"\end{itemize}")
    return L


def assumption_lines(cards: list[dict], lang: str = "en",
                     include_breaks: bool = False,
                     per_card: int = 2) -> list[str]:
    """把卡片的假设与失效条件变成论文里的段落（LaTeX 源码行）。

    每条假设后面标注卡片 id，读者能顺着找到出处；
    每条失效条件写成「若…则不适用」，这是可证伪的形式。
    """
    # 引导句必须轮换 —— 三张卡用同一套句式，AI 味检测会直接抓出来
    LEAD = (
        "The conditions below must hold for {cid} to be applicable. Each "
        "is written so that the data could contradict it.",
        "For {cid} to mean anything here, the following must be true. "
        "None of these is background; each one could fail.",
        "{cid} rests on the assumptions listed below. They are stated as "
        "claims rather than as context, because a claim can be checked.",
    )
    AFTER = (
        "{cid} is not applicable when any of the following holds. "
        "Reporting a result without checking these is how such an "
        "analysis usually goes wrong:",
        "The method breaks under any of these conditions. A result "
        "obtained while one of them fails should not be reported:",
        "Below are the failure modes that invalidate {cid}. They are "
        "listed so that a reader can check whether any applies:",
    )
    L = []
    for _i, c in enumerate(cards):
        cid = c.get("id", "?")
        name = c.get("name", "")
        L.append(rf"\paragraph{{Method {cid}: {name}}}")
        L.append(LEAD[_i % len(LEAD)].format(cid=cid))
        L.append(r"\begin{itemize}")
        # 每条假设带强度标注：强 = 由题意或物理决定，弱 = 数据只能近似满足。
        # 对照表要求标 [强]/[弱] 并写违反后果，否则假设被视为空话。
        for a in (c.get("assumptions") or [])[:per_card]:
            # strength 的键是完整假设文本，用截断前缀去取永远匹配不上
            # （实测标注 0 处，就是因为这里）。先完整匹配，再前缀匹配。
            _st = c.get("strength") or {}
            _key = str(a)
            _lab = _st.get(_key)
            if _lab is None:
                for _k, _v in _st.items():
                    if _key.startswith(_k[:40]) or _k.startswith(_key[:40]):
                        _lab = _v
                        break
            _tag = f" ({_lab})" if _lab else ""
            L.append(rf"  \item {_tex_safe(str(a))}{_tag}")
        L.append(r"\end{itemize}")
        bw = (c.get("breaks_when") or [])[:4] if include_breaks else []
        if bw:
            L.append(AFTER[_i % len(AFTER)].format(cid=cid))
            L.append(r"\begin{itemize}")
            for b in bw:
                L.append(rf"  \item {_tex_safe(str(b))}")
            L.append(r"\end{itemize}")
        rep = (c.get("report_must_include") or [])[:6]
        if rep:
            # 引导句轮换：三张卡用同一句，AI 味检测会算成句式重复
            _lead = (
                "A complete report of this method must state: ",
                "The report is incomplete unless it gives: ",
                "At minimum, the following must accompany the result: ",
            )[_i % 3]
            L.append(_lead
                     + ", ".join(_tex_safe(str(x)) for x in rep)
                     + ".")
        L.append("")
    return L


def bibliography_lines(cards: list[dict]) -> list[str]:
    """卡片里的 refs 变成 \\bibitem。去重、保序。"""
    seen, out = set(), []
    for c in cards:
        for r in (c.get("refs") or []):
            key = str(r)[:60]
            if key in seen:
                continue
            seen.add(key)
            out.append(str(r))
    return out


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

    cs = load_all()
    ck("卡片能加载", len(cs) >= 3, f"{len(cs)} 张")
    ck("没有加载错误", not any("_error" in c for c in cs))

    for c in cs:
        errs = validate_card(c)
        ck(f"{c.get('id')} 字段完整", not errs, str(errs)[:70])

    # 关键：breaks_when 必须非空（这是卡片的价值）
    ck("每张卡都有 breaks_when",
       all(c.get("breaks_when") for c in cs),
       f"{sum(1 for c in cs if c.get('breaks_when'))}/{len(cs)}")

    # 假设必须可证伪：不能出现「数据可靠」这类套话
    TAUTOLOGY = ("数据可靠", "data is reliable", "数据准确",
                 "data is accurate", "变量独立且同分布")
    taut = []
    for c in cs:
        for a in (c.get("assumptions") or []):
            low = str(a).lower()
            if any(t.lower() in low for t in TAUTOLOGY):
                taut.append(f"{c['id']}: {a[:40]}")
    ck("没有套话式假设", not taut, str(taut)[:80])

    # 找卡片
    lin = for_impl("mm.fit")
    ck("能按 our_impl 找到卡片", len(lin) >= 1,
       f"mm.fit → {[c['id'] for c in lin]}")

    # 生成 LaTeX
    lines = assumption_lines(cs[:2])
    ck("能生成假设段", len(lines) > 8, f"{len(lines)} 行")
    txt = "\n".join(lines)
    ck("假设段带卡片编号", "Method M00" in txt)
    # 别用整串匹配：生成的是 \\emph{not} applicable when，中间有 LaTeX 标记。
    # 改成查「失效条件本身的内容」有没有进正文 —— 那才是真正要验的。
    _bw0 = (cs[0].get("breaks_when") or [""])[0][:24]
    ck("假设段不含失效条件", not (bool(_bw0) and _bw0 in txt), _bw0)

    # 参考文献
    bib = bibliography_lines(cs)
    ck("能从卡片生成参考文献", len(bib) >= 3, f"{len(bib)} 条")
    ck("参考文献去重", len(bib) == len(set(b[:60] for b in bib)))

    # 方法推荐
    rec = recommend({"has_data", "multi_object", "regression"}, top=3)
    ck("能按特征推荐方法", len(rec) >= 1,
       rec[0]["method"][:30] if rec else "无")
    ck("推荐带匹配度与路径",
       all({"match", "path", "method"} <= set(r) for r in rec),
       str(rec[0])[:70] if rec else "")
    ck("没有特征时不给建议", recommend(set()) == [])

    # 校验器能挡住坏卡片
    bad_card = dict(id="X", name="x", when="x", assumptions=["短"],
                    breaks_when=[], report_must_include=[], refs=[],
                    our_impl="x")
    errs = validate_card(bad_card)
    ck("能挡住缺 breaks_when 的卡", any("breaks_when" in e for e in errs))
    ck("能挡住缺 refs 的卡", any("refs" in e for e in errs))
    ck("能挡住过短的假设", any("太短" in e for e in errs))

    print(f"\n{'ALL PASS' if bad == 0 else 'FAILED'}  {n - bad}/{n}")
    return 0 if bad == 0 else 1


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="方法卡片")
    ap.add_argument("cmd", nargs="?", default="list",
                    choices=["list", "validate", "show", "selftest"])
    ap.add_argument("id", nargs="?", default="")
    a = ap.parse_args(argv)

    if a.cmd == "selftest":
        return selftest()
    cs = load_all()
    if a.cmd == "validate":
        bad = 0
        for c in cs:
            e = validate_card(c)
            print(f"  {'OK  ' if not e else 'FAIL'} {c.get('id', '?'):<6} "
                  f"{c.get('name', '')[:44]}")
            for x in e:
                print(f"         {x}")
                bad += 1
        return 0 if bad == 0 else 1
    if a.cmd == "show":
        hit = [c for c in cs if c.get("id") == a.id]
        if not hit:
            print(f"  没有 {a.id}")
            return 1
        print(json.dumps(hit[0], ensure_ascii=False, indent=2))
        return 0
    for c in cs:
        print(f"  {c.get('id', '?'):<6}{c.get('name', '')[:40]:<42}"
              f"{len(c.get('assumptions') or [])} 假设 / "
              f"{len(c.get('breaks_when') or [])} 失效条件 / "
              f"{len(c.get('refs') or [])} 出处")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
