# -*- coding: utf-8 -*-
"""rtB_assumptions_probe.py — 只读审核 out/final/paper.tex 的 Assumptions 板（L223-L254）。

四条探针：
  P1 每条假设是否可证伪（什么数据会推翻它）
  P2 有没有把结论写成假设（循环论证）
  P3 假设被违反后的后果写了吗
  P4 假设数量与检验能力是否匹配

只读文件、只打印。不修改任何东西。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAPER = ROOT / "out" / "final" / "paper.tex"
ANATOMY_TAB = ROOT / "out" / "final" / "tab_anatomy.tex"
CLASSIFIER = ROOT / "out" / "final" / "classifier_audit.json"
REDTEAM = ROOT / "out" / "final" / "redteam.json"


def read_lines(p: Path) -> list[str]:
    return p.read_text(encoding="utf-8").splitlines()


def hr(title: str) -> None:
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def section_bounds(lines: list[str], name: str) -> tuple[int, int]:
    """返回 \section{name} 的 [start, end) 行号（0-based）。"""
    start = None
    for i, ln in enumerate(lines):
        if ln.strip() == "\\section{%s}" % name:
            start = i
            break
    if start is None:
        raise SystemExit("section not found: %s" % name)
    for j in range(start + 1, len(lines)):
        if lines[j].startswith("\\section{"):
            return start, j
    return start, len(lines)


def split_items(body: list[str]) -> list[list[str]]:
    """按 \item 切分 enumerate 的条目。"""
    items, cur = [], []
    for ln in body:
        if ln.lstrip().startswith("\\item"):
            if cur:
                items.append(cur)
            cur = [ln]
        elif cur:
            cur.append(ln)
    if cur:
        items.append(cur)
    return items


def main() -> None:
    lines = read_lines(PAPER)
    s, e = section_bounds(lines, "Assumptions")
    body = [ln for ln in lines[s:e] if ln.strip() not in
            ("\\begin{enumerate}", "\\end{enumerate}")]
    items = split_items(body)

    hr("0. 定位：\\section{Assumptions} 的物理范围")
    print("paper.tex 总行数 = %d" % len(lines))
    print("Assumptions 起于第 %d 行，止于第 %d 行（0-based），条目数 = %d"
          % (s + 1, e, len(items)))
    print("前置句：")
    for ln in lines[s + 1:s + 5]:
        if ln.strip():
            print("   | " + ln)

    # ---------------- P1 / P3：逐条抽出「失败条款」 ----------------
    hr("P3. 逐条检查：是否写出「假设失败后会怎样」")
    fail_markers = ("If this", "If a", "If claims", "bounded by",
                    "different defence", "we avoid this")
    for k, it in enumerate(items, 1):
        text = " ".join(x.strip() for x in it if x.strip())
        hit = [m for m in fail_markers if m in text]
        # 抽取以 If/bounded/different 开头的子句
        clause = ""
        for m in re.finditer(r"(If [^.;]{0,90}|bounded by that\.|"
                             r"[A-Z][^.;]{0,60}needs a different defence\.)",
                             text):
            clause = m.group(1)
            break
        print("\n--- 假设 %d ---" % k)
        print("标题片段: " + it[0].strip()[:96])
        print("失败条款标记: %s" % (hit if hit else "NONE"))
        print("抽到的子句: %s" % (clause if clause else "NONE"))

    # ---------------- P1：本节引用了哪些 label，被引处的「检验」在哪 ----------------
    hr("P1. 本节引用的 label 是否存在，且被引处是否提供证伪数据")
    sec_text = "\n".join(lines[s:e])
    refs = sorted(set(re.findall(r"\\ref\{([^}]+)\}", sec_text)))
    all_labels = {}
    for i, ln in enumerate(lines):
        for m in re.finditer(r"\\label\{([^}]+)\}", ln):
            all_labels[m.group(1)] = i + 1
    for r in refs:
        print("  ref{%-16s} -> label 在第 %s 行" % (r, all_labels.get(r, "缺失")))

    # sec:result 里有没有「模型不能自验」的测量？
    # 用 label 行号定位：sec:result 的 label 在 678 行，退回上一行找 \section
    rs_lab = all_labels.get("sec:result", 678) - 1
    rs = rs_lab
    while rs > 0 and not lines[rs].lstrip().startswith("\\section{"):
        rs -= 1
    re_ = all_labels.get("sec:wrong", 865) - 1
    while re_ > 0 and not lines[re_].lstrip().startswith("\\section{"):
        re_ -= 1
    print("sec:result 物理范围 = [%d, %d) 标题 = %s" % (rs + 1, re_ + 1, lines[rs].strip()))
    sections_found = [ln.strip() for ln in lines[rs:re_] if ln.strip().startswith("\\subsection{")]
    print("\nsec:result 覆盖的 subsection（%d 个）：" % len(sections_found))
    for h in sections_found:
        print("   " + h)
    probe_kw = ["self-verif", "recompute", "fabricat", "fluent", "sanity",
                "cannot verify", "self-check"]
    hits = []
    for i in range(rs, re_):
        low = lines[i].lower()
        for kw in probe_kw:
            if kw in low:
                hits.append((i + 1, kw, lines[i].strip()[:90]))
    print("sec:result 内命中「自验/复算/编造」关键词的行数 = %d" % len(hits))
    for h in hits:
        print("   %d [%s] %s" % h)

    # 全文中真正做这项测量的位置
    print("\n全文里上述关键词出现的行（用于判断测量是否在别的节）：")
    for i, ln in enumerate(lines):
        low = ln.lower()
        if any(kw in low for kw in probe_kw):
            print("   %d | %s" % (i + 1, ln.strip()[:100]))

    # ---------------- P1/P2：four classes vs 表格实际类数 ----------------
    hr("P1/P2. 「four classes of Table」与 tab_anatomy.tex 的实际类数")
    anat = ANATOMY_TAB.read_text(encoding="utf-8")
    rows = [r for r in anat.splitlines()
            if r.strip().endswith("\\\\") and "&" in r and "midrule" not in r
            and "multicolumn" not in r]
    classes = []
    for r in rows:
        first = r.split("&")[0].replace("\\\\", "").strip()
        if first and not first.startswith("\\") and first.lower() != "class":
            classes.append(first)
    head_rows = [r for r in rows if r.split("&")[0].strip().lower() == "class"]
    print("tab_anatomy.tex 表头行 = %d，数据类 = %d，类名 = %s"
          % (len(head_rows), len(classes), classes))
    claim_line = [i + 1 for i, ln in enumerate(lines) if "four classes of Table" in ln]
    print("paper.tex 声称「four classes of Table」的行 = %s" % claim_line)
    if claim_line:
        print("   | " + lines[claim_line[0] - 1].strip())
    print("★ 类数差 = %d（表 %d 个数据类 / 假设条写 4 类）"
          % (len(classes) - 4, len(classes)))

    # 分项之和 vs 分母
    nums = re.findall(r"(\d+) \(\d+\.\d\\% of (\d+)\)", anat)
    print("各行 share 的分母: %s" % sorted(set(n[1] for n in nums)))
    print("caption 里的 untraced 数（paper.tex 189 行附近）: %s"
          % [ln.strip() for ln in lines[186:191] if "1{,}48" in ln])

    # ---------------- P2：同一对象是否又当结果又当假设 ----------------
    hr("P2. A4（形态分类）在本节 vs 正文的认知地位")
    for i, ln in enumerate(lines):
        if "residual risk" in ln:
            print("  [假设节] %d | %s" % (i + 1, ln.strip()))
        if "We measured it instead of asserting it" in ln:
            print("  [正文]   %d | %s" % (i + 1, ln.strip()))
        if "How wrong is the classifier" in ln:
            print("  [正文]   %d | %s" % (i + 1, ln.strip()))
    ca = json.loads(CLASSIFIER.read_text(encoding="utf-8"))
    print("\nclassifier_audit.json: n_untraced=%(n_untraced)s n_sample=%(n_sample)s "
          "agreement=%(agreement)s d_auto=%(d_auto)s d_excused_as_struct=%(d_excused_as_struct)s "
          "coder=%(coder)s" % ca)
    print("★ 危险方向样本量 = d_auto = %s（正文写「0 times in 138 cases」）" % ca["d_auto"])

    # ---------------- P1b：A4 的「证伪测试」是不是规则 vs 规则 ----------------
    hr("P1b. A4 的唯一测试：classifier_audit 的「人工标注」是函数还是人")
    audit_src = (ROOT / "tools" / "classifier_audit.py").read_text(encoding="utf-8")
    auto_src = (ROOT / "untraced.py").read_text(encoding="utf-8")
    what = {
        "classifier_audit.py 里 def manual_label": "def manual_label(" in audit_src,
        "classifier_audit.py 里 abs(v) <= 1000": "abs(v) <= 1000" in audit_src,
        "classifier_audit.py 里 MANUAL_HINTS": "MANUAL_HINTS" in audit_src,
        "untraced.py 里 abs(v) <= 1000": "abs(v) <= 1000" in auto_src,
        "out/final 里有没有逐条人工标签文件": sorted(
            p.name for p in (ROOT / "out" / "final").glob("*label*")),
        "classifier_audit.json 里有没有逐条标签（只有计数矩阵）":
            "matrix" in CLASSIFIER.read_text(encoding="utf-8")
            and "labels" not in CLASSIFIER.read_text(encoding="utf-8"),
    }
    for k, v in what.items():
        print("  %-52s %s" % (k, v))
    print("  ★ 结论：所谓「逐条人工判读」的标签在运行时由 manual_label() 现算，"
          "没有任何人写下并留存逐条标签。")

    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "ca_probe", str(ROOT / "tools" / "classifier_audit.py"))
        ca_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ca_mod)
        import untraced as U  # noqa: E402
        print("\n  逐 token 对照（空 data_vals、中性上下文，模拟「最可能翻车」的情形）：")
        print("  %-14s %-12s %-12s %s" % ("token", "auto", "manual", "是否同判"))
        agree = 0
        toks = ["0.218", "0.19", "3.3342e-12", "97.5", "0.2146", "45.0",
                "51", "737", "1482", "0.05", "2024"]
        for t in toks:
            a = U.classify_token(t, set())
            m = ca_mod.manual_label(t, "", set())
            agree += (a == m)
            print("  %-14s %-12s %-12s %s" % (t, a, m, "同" if a == m else "异"))
        print("  → %d/%d 同判" % (agree, len(toks)))
        print("  ★ manual_label 的 A_struct 分支要求 float(v).is_integer() 且 "
              "abs(v)<=1000，而 auto 的 A_struct 分支要求 not has_dot 且 abs(v)<=1000：")
        print("    任何带小数的计算值（0.218 / 97.5 / 3.3342e-12）在两套规则里都不可能被判成")
        print("    A_struct，所以「危险方向 0/138」是规则结构决定的，不是测量出来的。")
    except Exception as exc:                          # noqa: BLE001
        print("  导入失败，仅做文本比对: %r" % (exc,))

    # ---------------- P3/P4：A3 的失败是否「无害」 ----------------
    hr("P3/P4. A3 失败后果是否只是成本（与本节的准入规则冲突）")
    for i in range(s, e):
        if "not worth writing down" in lines[i] or "harmless" in lines[i]:
            print("  准入规则 %d | %s" % (i + 1, lines[i].strip()))
        if "redundant" in lines[i]:
            print("  A3 后果  %d | %s" % (i + 1, lines[i].strip()))

    # ---------------- P4：假设数 vs 检验能力 ----------------
    hr("P4. 每条假设的检验工具体是否存在")
    inv = {
        "A1 not self-verifying": ("sec:result 内关键词命中数", len(hits)),
        "A2 can be frozen": ("冻结/种子证据", None),
        "A3 claim is local": ("窗口搜索的多重比较说明", None),
        "A4 four classes by shape": ("classifier_audit.json agreement", ca["agreement"]),
        "A5 corpus representative": ("23 题构成表", None),
        "A6 author is the model": ("可测性", "不可测（前提）"),
    }
    freeze_art = (ROOT / "out" / "final" / "冻结数字.json").exists()
    seed_sites = 0
    for pat in ("random\\.seed\\(", "default_rng\\("):
        for py in list(ROOT.glob("*.py")) + list((ROOT / "tools").glob("*.py")):
            if py.name.startswith("rtB_assumptions"):
                continue
            try:
                seed_sites += len(re.findall(pat, py.read_text(encoding="utf-8", errors="ignore")))
            except OSError:
                pass
    print("  冻结数字.json 存在 = %s ; 代码里固定种子调用点 = %d 处" % (freeze_art, seed_sites))
    for k, (what, v) in inv.items():
        print("  %-28s 检验: %-34s 值=%s" % (k, what, v))
    print("  ★ 6 条假设中：有独立测量的 = 1 (A4) / 仅缓解措施 = 1 (A2) / "
          "有计数但无检验 = 1 (A5) / 指针悬空 = 1 (A1) / 无检验 = 1 (A3) / 不可测 = 1 (A6)")

    # ---------------- 既有 redteam 记录：author 是否审过这一板 ----------------
    hr("既有记录：out/final/redteam.json 里有没有 section==assumptions")
    rt = json.loads(REDTEAM.read_text(encoding="utf-8"))
    secs = [r.get("section") for r in rt.get("reviews", [])]
    print("已审 section = %s" % secs)
    print("★ assumptions 是否被作者审过 = %s" % ("assumptions" in secs))

    # ---------------- 计划使用的 evidence 标记是否逐字存在 ----------------
    hr("交付物 evidence 标记逐字存在性校验")
    marks = [
        (PAPER, "four classes of Table"),
        (PAPER, "show it holds for the corpus"),
        (PAPER, "We measured it instead of asserting it"),
        (PAPER, "the residual risk"),
        (PAPER, "not worth writing down"),
        (PAPER, "the windowed search would be redundant"),
        (ANATOMY_TAB, "Tabulated data"),
        (ROOT / "tools" / "classifier_audit.py", "d_excused_as_struct"),
    ]
    for p, m in marks:
        txt = p.read_text(encoding="utf-8")
        rel = p.relative_to(ROOT).as_posix()
        print("  %-28s %-40s %s" % (rel, m, "FOUND" if m in txt else "MISSING"))


if __name__ == "__main__":
    main()
