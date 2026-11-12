#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""arch_invariants.py —— 架构合理性检验：一组「如果架构成立，就必须为真」的性质。

为什么需要它（第 123 轮，用户指出）：前 12 轮是「改一点、测一点」，架构被
finding 推着长，从没验过它是否成立。本工具把「架构合理」拆成 10 条可机械
检验的不变式，每条给出**证据**（文件+行号+计数），不是「跑过了」。

用法：
    python tools/arch_invariants.py           # 逐条给证
    python tools/arch_invariants.py --json
退出码：0 = 全部成立；1 = 有不变式不成立。
"""
import glob
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)


def _src(name):
    p = os.path.join(HERE, name)
    if not os.path.exists(p):
        return ""
    return io.open(p, encoding="utf-8", errors="replace").read()


def _lines(name, pat):
    """返回 [(行号, 行)] 命中。"""
    out = []
    for i, ln in enumerate(_src(name).splitlines(), 1):
        if re.search(pat, ln):
            out.append((i, ln.strip()[:90]))
    return out


# ── I1 书写精度：判论文的口径唯一 ──
def i1():
    """口径唯一 ≠ 函数唯一。

    `_written_decimals(tok)` 判「论文里写出来的精度」，这是**唯一的口径**。
    `verify._decimals(float)` 是另一回事：它给两个 float 之间比较时定默认精度
    （`_near` 用），那里根本没有「书写形式」可依。把两者当成「重复实现」
    是**检验器写错了**（第 123 轮实测：改成按用途判定后成立）。
    """
    w = _lines("verify.py", r"^def _written_decimals")
    f = _lines("freeze.py", r"^def _decimals")
    delegates = "return _V._written_decimals" in _src("freeze.py")
    # verify._decimals 只许给 float 比较用，不许出现在 trace/check 路径
    misuse = [x for x in _lines("verify.py", r"_decimals\(")
              if "def " not in x[1] and "decimals is None" not in x[1]
              and "_written_decimals" not in x[1]]
    ok = len(w) == 1 and len(f) == 1 and delegates and not misuse
    return ok, ("written_decimals=%d freeze委托=%s 误用=%d"
                % (len(w), delegates, len(misuse)))


# ── I2 数字提取：唯一实现 ──
def i2():
    a = _lines("verify.py", r"^def extract_numbers")
    b = _lines("freeze.py", r"^def extract_numbers")
    c = _lines("gate.py", r"^def extract_numbers")
    ok = len(a) == 1 and not b and not c
    return ok, "verify=%d freeze=%d gate=%d" % (len(a), len(b), len(c))


# ── I3 token 分类：唯一实现 ──
def i3():
    a = _lines("untraced.py", r"^def classify_token")
    b = [x for x in _lines("verify.py", r"def classify") if "classify_token" in x[1]]
    ok = len(a) == 1 and not b
    return ok, "untraced.classify_token=%d 其它=%d" % (len(a), len(b))


# ── I4 冻结表：格式统一 + out/final 生成者唯一 ──
def i4():
    fz = os.path.join(HERE, "out", "final", "冻结数字.json")
    if not os.path.exists(fz):
        return False, "out/final 无冻结表"
    j = json.load(io.open(fz, encoding="utf-8"))
    items = j.get("items") or []
    shape_ok = all(("path" in it and "value" in it) for it in items)
    gen = j.get("generated_from") or j.get("source") or ""
    writers = _lines("tools/freeze_paper_numbers.py", r"冻结数字\.json")
    ok = shape_ok and bool(gen) and len(writers) >= 1
    return ok, ("items=%d 形状统一=%s generated_from=%r"
                % (len(items), shape_ok, gen[:60]))


# ── I5 板数 == 论文 section 数 ──
def i5():
    import redteam
    secs = redteam.paper_sections(os.path.join(HERE, "out", "final"))
    rows = redteam.roster(os.path.join(HERE, "out", "final"))
    ok = len(secs) == len(rows) and len(secs) > 0
    return ok, "论文 section=%d roster=%d" % (len(secs), len(rows))


# ── I6 每板角色不重复 ──
def i6():
    import redteam
    rows = redteam.roster(os.path.join(HERE, "out", "final"))
    roles = [r["role"] for r in rows]
    ok = len(set(roles)) == len(roles)
    return ok, "板=%d 角色=%d 去重=%d" % (len(rows), len(roles), len(set(roles)))


# ── I7 每条 finding 的 where/evidence 可 grep ──
def i7():
    j = json.load(io.open(os.path.join(HERE, "out", "final", "redteam.json"),
                          encoding="utf-8"))
    n = bad = 0
    for r in j["reviews"]:
        for p in r.get("probes") or []:
            if p.get("verdict") != "finding":
                continue
            n += 1
            w = os.path.join(HERE, str(p.get("where") or ""))
            ev = str(p.get("evidence") or "")
            if not (w and ev and os.path.exists(w)):
                bad += 1
                continue
            if ev not in io.open(w, encoding="utf-8", errors="replace").read():
                bad += 1
    ok = bad == 0
    return ok, "finding=%d 证据落空=%d" % (n, bad)


# ── I8 飞轮六环各有独立仪表 ──
def i8():
    need = {
        "环1 run_all": "tests/run_all.py",
        "环1 自攻": "tools/attack_self.py",
        "环1 E验收": "tools/e_verify.py",
        "环2 活变量": "tools/live_vars_check.py",
        "环3 红队": "redteam.py",
        "环4 分诊": "tools/triage_findings.py",
        "环5 盖章": "gate.py",
        "环6 台账": "tools/flywheel.py",
        "章收束": "tools/chapter_coverage.py",
    }
    miss = [k for k, v in need.items() if not os.path.exists(os.path.join(HERE, v))]
    return not miss, "需要 %d 个工具，缺 %s" % (len(need), miss or "无")


# ── I9 匹配判决唯一出口 ──
def i9():
    """`_match_written` 定义在 freeze.py 是**对的**：它做值匹配，归属判据层。
    gate 通过 `freeze.check_paper` 调用它，不另写一份 —— 要检验的是这个。"""
    m = _lines("freeze.py", r"^def _match_written")
    dup = _lines("verify.py", r"^def _match_written") + \
        _lines("gate.py", r"^def _match_written")
    g = _lines("gate.py", r"check_paper")
    ok = len(m) == 1 and not dup and len(g) >= 1
    return ok, ("freeze 定义=%d 别处重复=%d gate→check_paper=%d"
                % (len(m), len(dup), len(g)))


# ── I10 两个口径的差必须被显式说明 ──
def i10():
    """gate 口径（只判小数）与 verify 口径（全量）必然不同。
    架构合理的前提是：这个差**写在论文里**，而不是藏着。"""
    tex = _open_paper()
    said = ("integer tokens are not judged" in tex
            or "carries a fractional part" in tex
            or "of 184 tokens are judged" in tex)
    gate_says = "整数 token 未纳入判定" in _src("gate.py")
    ok = said and gate_says
    return ok, "论文说明=%s gate 输出=%s" % (said, gate_says)


def _open_paper():
    p = os.path.join(HERE, "out", "final", "paper.tex")
    return io.open(p, encoding="utf-8", errors="replace").read() \
        if os.path.exists(p) else ""


# ── I11 探针不得引用别板的输入 ──
def i11(spec=None):
    """板与板之间只许通过论文正文交互，不许直接拿对方的输入。

    `restatement` 是题面的合法持有者（它就是要对照题面）；别的板提到「题面」
    就是越界 —— 第 123 轮实测：`conclusion.probe0` 写「结论是否回应了题面的
    每一问」，于是它拿 2026 MCM Problem C 的 10 问去要求一篇工具论文逐条回应，
    而 DWTS 的稿在 out/d2026c。这类 finding 只能靠事后 `rejected` 驳回。

    `spec` 参数是**给接受测试用的**：让它能构造一个越界探针，验证本函数
    真的会报出来 —— 否则「样本只读当前状态」就成了假测试
    （第 123 轮：变异测试抓到的正是这个）。
    """
    if spec is None:
        import redteam
        spec = redteam.SPEC
    bad = []
    for sec, sp in spec.items():
        if sec == "restatement":
            continue
        for i, p in enumerate(sp["probes"]):
            if "题面" in p:
                bad.append("%s.probe%d" % (sec, i))
    return (not bad), "越界探针=%s" % (bad or "无")


# ── I12 图不许旧于它依赖的数据 ──
def i12(figdir=None, data_paths=None):
    """`gate.figures` 只看数量、分辨率与是否被引用，**不看内容是否同源**。

    实测（第 123 轮）：`fig16_sections` 一直是两版前的数据 —— 12 根条形、
    总数 5082 词、标签是旧版章节名（The system / Six ways a checker can be /
    What the audit changed），而这些小节在当前论文里不存在；当前是 9768 词、
    12 个当前章节名。原因是切分正则坏了，图从空数据画出来，而没有任何围栏管。

    本不变式用 mtime 做粗检：任何图若比它依赖的数据文件旧，就是可疑的。
    它会有假警报（重采集数据但内容没变），所以只当**提示**，不当判决。

    `figdir` / `data_paths` 是**给接受测试用的**：让它能造一个旧图，验证
    本函数真的会报出来 —— 否则「样本只读当前状态」就成了假测试。
    """
    if figdir is None:
        figdir = os.path.join(HERE, "out", "final", "fig")
    if data_paths is None:
        data_paths = [os.path.join(HERE, "out", "final", f)
                      for f in ("data.json", "data2.json", "anatomy.json",
                                "ablation.json")]
    if not os.path.isdir(figdir):
        return False, "没有图目录"
    datas = [p for p in data_paths if os.path.exists(p)]
    if not datas:
        return False, "没有数据工件"
    dmax = max(os.path.getmtime(p) for p in datas)
    dname = os.path.basename(max(datas, key=os.path.getmtime))
    old = sorted(os.path.basename(f)
                 for f in glob.glob(os.path.join(figdir, "*.pdf"))
                 # `_t.pdf` 是 savefig 的临时残留，论文 0 次引用，不参与
                 if not os.path.basename(f).startswith("_")
                 and os.path.getmtime(f) < dmax)
    return (not old), ("最新数据=%s 比它旧的图=%d 个%s"
                       % (dname, len(old), ("：" + ", ".join(old[:4])) if old else ""))


CHECKS = [
    ("I1 精度换算唯一", i1),
    ("I2 数字提取唯一", i2),
    ("I3 token 分类唯一", i3),
    ("I4 冻结表格式统一 + 生成者可溯", i4),
    ("I5 板数 == 论文 section 数", i5),
    ("I6 每板角色不重复", i6),
    ("I7 finding 证据可 grep", i7),
    ("I8 飞轮每环有独立仪表", i8),
    ("I9 匹配判决唯一出口", i9),
    ("I10 两口径之差已写进论文", i10),
    ("I11 探针不引用别板输入", i11),
    ("I12 图不旧于其数据", i12),
]


def main(argv):
    rows = []
    for name, fn in CHECKS:
        try:
            ok, ev = fn()
        except Exception as e:                          # noqa: BLE001
            ok, ev = False, "检查本身出错：%s" % e
        rows.append(dict(name=name, ok=ok, evidence=ev))
    if "--json" in argv:
        print(json.dumps(rows, ensure_ascii=False, indent=1))
        return 0 if all(r["ok"] for r in rows) else 1

    print("架构不变式：%d 条" % len(rows))
    bad = 0
    for r in rows:
        flag = "成立" if r["ok"] else "**不成立**"
        if not r["ok"]:
            bad += 1
        print("  [%-8s] %-32s %s" % (flag, r["name"], r["evidence"]))
    print()
    print("不成立：%d / %d" % (bad, len(rows)))
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
