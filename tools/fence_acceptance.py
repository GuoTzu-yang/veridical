#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fence_acceptance.py —— 围栏接受测试：拿真缺陷样本喂给围栏，看拦不拦。

为什么需要它（第 123 轮，用户问「我们的围栏到底有用吗」）：
「有用」不能靠总结，要靠**可复现的样本**：每个样本是一次真实踩过的坑，
逐条问「哪道围栏应该拦它」，然后实际调用那道围栏。

样本来源：`out/仪表骗案.md` 与 12 轮修复实录。
每个样本声明期望：`block`（该拦住）或 `pass`（该放行，拦了就是误报）。

四类结论：
  拦住    期望 block，实际 block       —— 围栏有效
  漏检    期望 block，实际 pass        —— 围栏盲区
  误报    期望 pass，实际 block        —— 围栏太紧
  无围栏  连「该由谁拦」都没有         —— 结构性空白

用法：
    python tools/fence_acceptance.py
    python tools/fence_acceptance.py --json
退出码：0 = 无漏检无无围栏；1 = 有。
"""
import io
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

OUT = os.path.join(HERE, "out", "final")


# ────────── 样本 1-2：半格边界（freeze._match_written）──────────
def s1():
    """合法舍入 0.78751 ← 0.787505 必须放行。拦了 = 误报。"""
    import freeze
    ok = freeze._match_written(0.78751, 5, [0.787505])
    return "pass", (not ok), "freeze._match_written 放行=%s" % ok


def s2():
    """2.0839e-13 由 0.0 解释必须拦住。放行 = 漏检。"""
    import freeze
    ok = freeze._match_written(2.0839e-13, 13, [0.0])
    return "block", (not ok), "freeze._match_written 放行=%s" % ok


# ────────── 样本 3-5：活变量过时（live_vars_check）──────────
def _live_mismatch(name_key, fake_tex=None):
    """在（可伪造的）论文文本里找某个活变量的字面量，与工件比对。

    第 123 轮修：早先直接读 out/final/paper.tex 的**当前状态**，
    而那些值已经被修好了 —— 于是样本报「漏检」，实际是「样本用了已修状态」。
    接受测试必须**构造缺陷**：给一段写错值的文本，看检测逻辑能不能发现。
    """
    import re
    d = json.load(io.open(os.path.join(OUT, "data.json"), encoding="utf-8"))
    tex = fake_tex if fake_tex is not None else io.open(
        os.path.join(OUT, "paper.tex"), encoding="utf-8",
        errors="replace").read()
    if name_key == "gate_checks":
        want = d.get("n_gate_checks")
        got = [int(m) for m in re.findall(r"(\d+)\s+checks", tex)]
        return want, got
    if name_key == "selftest_modules":
        want = d.get("n_modules_with_selftest")
        got = [int(m) for m in re.findall(r"all (\d+) of \d+", tex)]
        return want, got
    if name_key == "record_rounds":
        want = d.get("n_record_rounds")
        got = [int(m) for m in re.findall(r"over (\d+) repair", tex)]
        return want, got
    return None, []


def s3():
    """给一段写「29 checks」的文本，工件是 30：必须拦住。"""
    want, got = _live_mismatch("gate_checks",
                              "every report must pass a gate of 29 checks, 12 hard.")
    bad = [g for g in got if g != want]
    return "block", bool(bad), "工件=%s 伪造文本=%s 不一致=%s" % (want, got, bad)


def s4():
    """给一段写「all 51 of 51」的文本，工件是 54：必须拦住。"""
    want, got = _live_mismatch("selftest_modules",
                              "Coverage all 51 of 51, three defects surfaced.")
    bad = [g for g in got if g != want]
    return "block", bool(bad), "工件=%s 伪造文本=%s 不一致=%s" % (want, got, bad)


def s5():
    """给一段写「over 30 repair」的文本，工件是 31：必须拦住。"""
    want, got = _live_mismatch("record_rounds",
                              "six defect classes over 30 repair rounds logged.")
    bad = [g for g in got if g != want]
    return "block", bool(bad), "工件=%s 伪造文本=%s 不一致=%s" % (want, got, bad)


# ────────── 样本 6-8：产物自身坏了（谁该拦？）──────────
def s6():
    """fig16 画的是旧章节（5082 词、旧节名），而论文是 9768。

    **必须构造缺陷 + 调真围栏**，缺一不可（第 123 轮，变异测试抓的）：
      · 只读当前状态 → 围栏改坏也照样「拦住」，假测试
      · 复制围栏逻辑 → 测的是副本，真围栏改坏不受影响，也是假测试
    这里造一个「图比数据旧」的临时场景，喂给 `arch_invariants.i12`。
    """
    import tempfile
    import arch_invariants as ai
    td = tempfile.mkdtemp(prefix="fence_i12_")
    figp = os.path.join(td, "stale.pdf")
    io.open(figp, "wb").write(b"%PDF-1.4\n")
    datap = os.path.join(td, "data.json")
    io.open(datap, "w", encoding="utf-8", newline="\n").write("{}")
    t = os.path.getmtime(figp) + 10          # 数据比图新 10 秒
    os.utime(datap, (t, t))
    ok, ev = ai.i12(figdir=td, data_paths=[datap])
    return "block", (not ok), "构造旧图后 i12 报出：%s" % ev


def s7():
    """`sections` 切分坏了 → sections=[]，而图还在画。

    第 123 轮修：早先读当前 data2（已被修成 12），所以报「漏检」是假警报。
    正确的样本是「问采集脚本有没有断言拦空 sections」，这是静态事实。
    """
    src = io.open(os.path.join(HERE, "tools", "collect_paper_data2.py"),
                  encoding="utf-8", errors="replace").read()
    guards = [k for k in ("if not secs", "assert secs", "len(secs) ==",
                          "if len(secs)") if k in src]
    d = json.load(io.open(os.path.join(OUT, "data2.json"), encoding="utf-8"))
    n = len(d.get("sections") or [])
    return "block", bool(guards), \
        "采集脚本对空 sections 的断言=%s；当前 sections=%d" % (guards or "无", n)


def s8():
    """`paper_bytes` 54778 vs 实际 67176：工件与成稿不同步。

    期望 block。实际：**无围栏**。`numbers` 只判论文里的数有没有出处，
    不判「出处本身是不是当前版本」。
    """
    d = json.load(io.open(os.path.join(OUT, "data2.json"), encoding="utf-8"))
    rec = d.get("paper_bytes")
    real = os.path.getsize(os.path.join(OUT, "paper.tex"))
    return "block", (rec == real), "工件=%s 实际=%s" % (rec, real)


# ────────── 样本 9-11：redteam 自身的假绿 ──────────
def _rt_with(mutate):
    import redteam
    j = json.load(io.open(os.path.join(OUT, "redteam.json"),
                          encoding="utf-8"))
    j = mutate(json.loads(json.dumps(j)))
    td = tempfile.mkdtemp(prefix="fence_")
    # 必须带 paper.tex，否则 check 走「没有正文 → 退回 SPEC」分支
    tex = io.open(os.path.join(OUT, "paper.tex"), encoding="utf-8",
                  errors="replace").read()
    io.open(os.path.join(td, "paper.tex"), "w", encoding="utf-8",
            newline="\n").write(tex)
    io.open(os.path.join(td, "redteam.json"), "w", encoding="utf-8",
            newline="\n").write(json.dumps(j, ensure_ascii=False, indent=1))
    r = redteam.check(td)
    return r["level"], r["detail"]


def s9():
    """finding 的 evidence 在文件里找不到（编造证据）：必须拦住。"""
    def mut(j):
        for r in j["reviews"]:
            for p in r.get("probes") or []:
                if p.get("verdict") == "finding":
                    p["evidence"] = "这句话在文件里不存在 XYZ123"
                    return j
        return j
    lvl, det = _rt_with(mut)
    return "block", (lvl == "FAIL"), "%s｜%s" % (lvl, det[:60])


def s10():
    """finding 标「未处理」：必须拦住（不能当关闭）。"""
    def mut(j):
        for r in j["reviews"]:
            for p in r.get("probes") or []:
                p.pop("disposition", None)
            r["resolved"] = "未处理"
        return j
    lvl, det = _rt_with(mut)
    return "block", (lvl == "FAIL"), "%s｜%s" % (lvl, det[:60])


def s11():
    """板数 7 而论文 12 节：必须拦住。"""
    def mut(j):
        j["reviews"] = j["reviews"][:7]
        return j
    lvl, det = _rt_with(mut)
    return "block", (lvl == "FAIL"), "%s｜%s" % (lvl, det[:60])


# ────────── 样本 12：红队拿错基准（谁该拦？）─────────
def s12():
    """conclusion 板拿 DWTS 的 10 问去审工具论文。

    **构造缺陷 + 调真围栏**：给某板探针塞一句「题面」，喂给
    `arch_invariants.i11`，它必须报出越界。
    """
    import copy
    import redteam
    import arch_invariants as ai
    spec = copy.deepcopy(redteam.SPEC)
    spec["conclusion"]["probes"][0] = \
        "结论是否回应了题面的每一问（构造的越界样本）"
    ok, ev = ai.i11(spec=spec)
    return "block", (not ok), "构造越界探针后 i11 报出：%s" % ev


SAMPLES = [
    ("S1  合法舍入 0.78751←0.787505 应放行", s1),
    ("S2  地板假通过 2.0839e-13←0.0 应拦", s2),
    ("S3  活变量 29 checks vs 30", s3),
    ("S4  活变量 51 of 51 vs 54", s4),
    ("S5  活变量 30 rounds vs 31", s5),
    ("S6  fig16 画旧章节", s6),
    ("S7  sections 切分坏了", s7),
    ("S8  paper_bytes 工件过期", s8),
    ("S9  编造 evidence", s9),
    ("S10 「未处理」当关闭", s10),
    ("S11 板数 7 vs 论文 12 节", s11),
    ("S12 红队拿错基准", s12),
]


def wilson(k, n, z=1.96):
    """Wilson 95% 置信区间（小样本比正态近似稳）。

    为什么必须报区间（Holling et al., *Nequivack: Assessing Mutation Score
    Confidence*, ICSTW 2016, DOI 10.1109/ICSTW.2016.29）：
    **通过率是估计量，不是真值。** 12 个样本里拦住 11 个，点估计 91.7%，
    但 95% Wilson 区间的下界只有约 64.6% —— 换句话说「拦住 11/12」
    与「真实拦截率 65%」在统计上无法区分。

    这一条是文献给的降级，不是我自己的判断：前几轮我把 91.7% 当结论写了。
    """
    if n <= 0:
        return (0.0, 0.0)
    p = k / float(n)
    denom = 1.0 + z * z / n
    center = (p + z * z / (2.0 * n)) / denom
    half = z * ((p * (1 - p) / n + z * z / (4.0 * n * n)) ** 0.5) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def main(argv):
    rows = []
    for name, fn in SAMPLES:
        try:
            expect, blocked, ev = fn()
        except Exception as e:                          # noqa: BLE001
            expect, blocked, ev = "block", False, "样本执行出错：%s" % e
        if expect == "block" and blocked:
            verdict = "拦住"
        elif expect == "block" and not blocked:
            verdict = "漏检"
        elif expect == "pass" and not blocked:
            verdict = "放行"
        else:
            verdict = "误报"
        rows.append(dict(name=name, expect=expect, blocked=blocked,
                         verdict=verdict, evidence=ev))

    if "--json" in argv:
        print(json.dumps(rows, ensure_ascii=False, indent=1))
        return 0

    print("围栏接受测试：%d 个真缺陷样本" % len(rows))
    print()
    for r in rows:
        print("  [%-4s] %-38s %s" % (r["verdict"], r["name"][:38],
                                     r["evidence"][:72]))
    from collections import Counter
    c = Counter(r["verdict"] for r in rows)
    n = len(rows)
    k = c["拦住"] + c["放行"]          # 判定正确的样本数
    lo, hi = wilson(k, n)
    print()
    print("拦住 %d / 漏检 %d / 误报 %d / 放行 %d"
          % (c["拦住"], c["漏检"], c["误报"], c["放行"]))
    print()
    print("判定正确率：%d/%d = %.1f%%（点估计）" % (k, n, 100.0 * k / n))
    print("            Wilson 95%% 置信区间：%.1f%% – %.1f%%" % (100 * lo, 100 * hi))
    print("  （文献依据：Nequivack, ICSTW 2016 —— 通过率是估计量，")
    print("    %d 个样本的区间很宽，不能把点估计当结论）" % n)
    miss = [r["name"] for r in rows if r["verdict"] == "漏检"]
    if miss:
        print()
        print("漏检清单：")
        for m in miss:
            print("  ·", m)
    bad = c["漏检"] + c["误报"]
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
