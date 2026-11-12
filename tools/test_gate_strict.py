"""gate.py 的护栏自检：断言「检查没跑成」不被当成通过，且检查器本身不能退化。


三个断言：
  A. 类型化：_is_failed_na 只认 na_kind，不看 detail 文案。
     故意让 detail 含 "Error" 字样但 kind=absent → 必须判「不是失败」；
     detail 完全干净但 kind=failed → 必须判「是失败」。
  B. 端到端：造一个会让 leakage 检查抛异常的数据，默认跑必须 FAIL，
     --lenient 跑必须回到 N/A 且硬门放行。
  C. 旧调用点兼容：没带 na_kind 的 N/A 仍按文本兜底判定。

跑法：python tools/test_gate_strict.py
退出码 0 = 三条全过。
"""
import re
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import gate  # noqa: E402

PY = sys.executable
FAIL = []


def check(name, cond, detail=""):
    tag = "PASS" if cond else "FAIL"
    print("  [%s] %s%s" % (tag, name, ("  <- " + detail) if (detail and not cond) else ""))
    if not cond:
        FAIL.append(name)


def part_a():
    print("A. 类型化判定不看文案")
    # 文案含 Error，但语义是「本题没有这一项」→ 不是失败
    c1 = dict(id="x", tier="hard", status="N/A", na_kind="absent",
              detail="KeyError: 本题不含该结构")
    check("absent 即使文案含异常词也不算失败", gate._is_failed_na(c1) is False)
    # 文案干净，语义是「检查没跑成」→ 是失败
    c2 = dict(id="x", tier="hard", status="N/A", na_kind="failed", detail="没读成")
    check("failed 文案干净也算失败", gate._is_failed_na(c2) is True)


def part_c():
    print("C. 老调用点兼容（无 na_kind）")
    c3 = dict(id="x", tier="hard", status="N/A", detail="KeyError: 'placement'")
    check("无 na_kind 时文本兜底认出崩溃", gate._is_failed_na(c3) is True)
    c4 = dict(id="x", tier="hard", status="N/A", detail="没有 paper.tex")
    check("无 na_kind 时文本兜底不误判", gate._is_failed_na(c4) is False)


def _fixture(root):
    """造一个真会抛异常的目录：冻结数字.json 是坏 JSON。

    为什么不用 leakage：它在这份样例上返回的是合法 N/A（「冻结表里没记 y」），
    属于「本题没有这一项」，本来就该算通过。要证明的是「检查没跑成」这一类，
    必须让某个检查真的抛。
    """
    d = os.path.join(root, "case")
    os.makedirs(d, exist_ok=True)
    io.open(os.path.join(d, "paper.tex"), "w", encoding="utf-8").write(
        "\\documentclass{article}\\begin{document}hello\\end{document}\n")
    io.open(os.path.join(d, "paper.log"), "w", encoding="utf-8").write(
        "Output written on paper.pdf (3 pages, 1000 bytes).\n")
    io.open(os.path.join(d, "paper.pdf"), "wb").write(b"%PDF-1.4\n%%EOF\n")
    csv = os.path.join(d, "data.csv")
    io.open(csv, "w", encoding="utf-8").write("name,label\na,foo\nb,bar\n")
    # 坏 JSON：json.load 必抛 JSONDecodeError
    io.open(os.path.join(d, "冻结数字.json"), "w", encoding="utf-8").write("{not json")
    return d, csv


def part_b():
    print("B. 端到端：崩溃的检查在默认下 FAIL，--lenient 下 N/A")
    root = tempfile.mkdtemp(prefix="gateNA_")
    target = "numbers"          # 坏 JSON 会让它抛异常
    try:
        d, csv = _fixture(root)
        # 进程内：默认 strict=True
        r_strict = gate.run_all(d, data=csv, strict=True)
        lk = [c for c in r_strict["checks"] if c["id"] == target][0]
        check("默认 %s 状态为 FAIL（不再假绿）" % target,
              lk["status"] == "FAIL", "实际 %s / %s" % (lk["status"], lk["detail"][:60]))
        check("失败项带 na_kind=failed", lk.get("na_kind") == "failed",
              "实际 %r" % (lk.get("na_kind"),))
        # 进程内：lenient
        r_len = gate.run_all(d, data=csv, strict=False)
        lk2 = [c for c in r_len["checks"] if c["id"] == target][0]
        check("lenient %s 回到 N/A" % target,
              lk2["status"] == "N/A", "实际 %s / %s" % (lk2["status"], lk2["detail"][:60]))
        # CLI 默认也是 strict
        p = subprocess.run([PY, os.path.join(HERE, "gate.py"), d, "--data", csv, "--json"],
                           capture_output=True, text=True, encoding="utf-8", cwd=HERE)
        ok_cli = False
        try:
            j = json.loads(p.stdout[p.stdout.index("{"):])
            lk3 = [c for c in j["checks"] if c["id"] == target][0]
            ok_cli = lk3["status"] == "FAIL"
        except Exception as e:
            print("     CLI 解析失败: %s" % e)
        check("CLI 不带参数时也是 FAIL", ok_cli)
        # --lenient 恢复
        p2 = subprocess.run([PY, os.path.join(HERE, "gate.py"), d, "--data", csv,
                             "--json", "--lenient"],
                            capture_output=True, text=True, encoding="utf-8", cwd=HERE)
        ok_cli2 = False
        try:
            j2 = json.loads(p2.stdout[p2.stdout.index("{"):])
            lk4 = [c for c in j2["checks"] if c["id"] == target][0]
            ok_cli2 = lk4["status"] == "N/A"
        except Exception as e:
            print("     CLI --lenient 解析失败: %s" % e)
        check("CLI --lenient 回到 N/A", ok_cli2)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def part_d():
    print("D. 数据表定位不再串题")
    # 同名题：直接按 out/data/<题名>.xlsx
    p, why = gate._resolve_data("out/runs/evaluation")
    check("按题名定位", bool(p) and os.path.basename(p) == "evaluation.xlsx",
          "%s | %s" % (p, why))
    # 异名题：目录 out/d2026c 属 dwts2026c，靠反查
    p2, why2 = gate._resolve_data("out/d2026c")
    check("按产物目录反查", bool(p2) and os.path.basename(p2) == "dwts2026c.xlsx",
          "%s | %s" % (p2, why2))
    # 不存在的题：必须给出原因，且不能返回别的题的表
    p3, why3 = gate._resolve_data("out/runs/__no_such_problem__")
    check("未知题返回空且带原因", (p3 == "") and bool(why3), "%r | %r" % (p3, why3))
    # 关键回归：绝不能回退到「工作区里随便一个 xlsx」
    bad = []
    for nm in ("evaluation", "prediction", "network", "queueing"):
        pp, _ = gate._resolve_data("out/runs/" + nm)
        if os.path.basename(pp or "") not in (nm + ".xlsx", nm + ".csv"):
            bad.append((nm, pp))
    check("四道题各拿自己的表", not bad, str(bad))


def _build_tex(root, abstract_paras):
    """在 root 里造一份能编译的最小论文，返回目录名。"""
    d = os.path.join(root, "case")
    os.makedirs(d, exist_ok=True)
    body = "\n\n".join(abstract_paras)
    tex = (
        "\\documentclass[11pt]{article}\n"
        "\\usepackage[a4paper,margin=2.5cm]{geometry}\n"
        "\\title{Template check}\n\\author{}\n\\date{}\n"
        "\\begin{document}\n\\maketitle\n"
        "\\begin{abstract}\n" + body + "\n"
        "\\noindent\\textbf{Keywords:} a; b; c\n\\end{abstract}\n"
        "\\section{Introduction}\n" + ("body text. " * 400) + "\n"
        "\\end{document}\n")
    io.open(os.path.join(d, "paper.tex"), "w", encoding="utf-8").write(tex)
    return d


def part_e():
    print("E. abs_page 仍能抓到真溢出（不能变成假阴性）")
    import shutil as _sh
    import subprocess as _sp
    root = tempfile.mkdtemp(prefix="absPg_")
    try:
        # ① 短摘要：必须 PASS
        d1 = _build_tex(os.path.join(root, "short"),
                        ["Short abstract with a number 0.42 in it."])
        # ② 长摘要（约 2 页）：必须 FAIL
        d2 = _build_tex(os.path.join(root, "long"),
                        ["A long abstract sentence number %d that pad pads pad pads "
                         "the page until it must spill over onto the second page." % i
                         for i in range(60)])
        ok_build = True
        for d in (d1, d2):
            p = _sp.run(["pdflatex", "-interaction=nonstopmode", "-halt-on-error",
                         "paper.tex"], cwd=d, capture_output=True)
            if not os.path.exists(os.path.join(d, "paper.pdf")):
                ok_build = False
                print("     编译失败: %s" % p.stdout.decode("utf-8", "replace")[-200:])
        check("测试样例能编译", ok_build)
        if ok_build:
            r1 = gate.chk_abs_page(d1)
            check("短摘要 PASS", r1["status"] == "PASS",
                  "%s / %s" % (r1["status"], r1["detail"][:60]))
            r2 = gate.chk_abs_page(d2)
            check("长摘要被判 FAIL（判据没被改松）", r2["status"] == "FAIL",
                  "%s / %s" % (r2["status"], r2["detail"][:60]))
    finally:
        _sh.rmtree(root, ignore_errors=True)


def _mk_case(root, name, cols, frozen_y, frozen_x):
    """造一个能跑 chk_leakage 的产物目录：data.xlsx + paper.tex + 冻结数字.json。"""
    import numpy as np
    import pandas as pd
    d = os.path.join(root, name)
    os.makedirs(d, exist_ok=True)
    pd.DataFrame(cols).to_excel(os.path.join(d, "data.xlsx"), index=False)
    io.open(os.path.join(d, "paper.tex"), "w", encoding="utf-8").write(
        "\\documentclass{article}\\begin{document}x\\end{document}\n")
    io.open(os.path.join(d, "冻结数字.json"), "w", encoding="utf-8").write(
        json.dumps(dict(y=frozen_y, x=frozen_x), ensure_ascii=False))
    return d, os.path.join(d, "data.xlsx")


def part_f():
    print("F. 泄漏检查区分「时间趋势共变」与「拿响应当自变量」")
    # 名字识别
    for nm, want in (("年份", True), ("月份", True), ("1953", True),
                     ("1965-1970", True), ("pop2000", False),
                     ("消费金额", False), ("total_votes", False),
                     ("Age 45 - 49", False),
                     # 裸字包含会把这些判成时间列，而它们不是时间轴
                     ("年龄", False), ("周龄", False), ("年收入", False),
                     ("期初库存", False)):
        check("_is_time_like(%r)=%s" % (nm, want),
              gate._is_time_like(nm) is want, "实际 %r" % gate._is_time_like(nm))
    import numpy as np
    import shutil as _sh
    root = tempfile.mkdtemp(prefix="leak_")
    try:
        n = 60
        year = np.arange(1960, 1960 + n)
        # ① 时间列与响应强相关（趋势）→ 不该报泄漏
        sales = year * 3.0 + np.linspace(0, 5, n)      # 与 year 相关 ≈ 1.0
        # 价格必须**非单调**：第一版用 linspace(10,20) 也是斜坡，与销量同样
        # 相关 ≈1.0，于是被「检查所有超阈值列」判成非豁免的真泄漏 → WARN。
        # 那次失败说明新规则抓到了样例自身的缺陷，不是断言写错。
        rng = np.random.default_rng(0)
        price = 15.0 + rng.normal(0, 1.0, n)
        d1, x1 = _mk_case(root, "trend",
                          {"年份": year, "销量": sales, "价格": price},
                          "销量", ["年份", "价格"])
        r1 = gate.chk_leakage(d1, data=x1)
        check("时间趋势共变不报 WARN", r1["status"] == "PASS",
              "%s / %s" % (r1["status"], r1["detail"][:70]))
        check("说明里点出是时间列", "时间/序号列" in r1["detail"], r1["detail"][:70])
        # ② 用另一个响应当自变量 → 必须 WARN
        value = np.linspace(1, 100, n)
        spend = value * 1.005 + np.linspace(0, 1, n)
        d2, x2 = _mk_case(root, "leak",
                          {"客户价值": value, "消费金额": spend,
                           "年龄": np.linspace(20, 40, n)},
                          "客户价值", ["消费金额", "年龄"])
        r2 = gate.chk_leakage(d2, data=x2)
        check("拿响应当自变量仍报 WARN", r2["status"] == "WARN",
              "%s / %s" % (r2["status"], r2["detail"][:70]))
    finally:
        _sh.rmtree(root, ignore_errors=True)


def part_g():
    print("G. falsify：承认语句的定位 + 列数门槛放宽")
    import shutil as _sh
    root = tempfile.mkdtemp(prefix="fsl_")
    try:
        # ① 承认语句在 Evaluation 节
        p1 = os.path.join(root, "a.tex")
        io.open(p1, "w", encoding="utf-8").write(
            "\\section{Introduction}\ntext\n\\section{Evaluation}\n"
            "The directions hold on average but fail locally.\n")
        ok, sec = gate._admission(p1)
        check("承认语句定位到 Evaluation", ok and sec == "Evaluation", "%r/%r" % (ok, sec))
        # ② 在别的节里也要能定位（不硬判必须是 Limitations）
        p2 = os.path.join(root, "b.tex")
        io.open(p2, "w", encoding="utf-8").write(
            "\\section{Introduction}\n\\section{What each claim rests on}\n"
            "We make no claim of monotonicity.\n")
        ok2, sec2 = gate._admission(p2)
        check("承认语句定位到自定义节名",
              ok2 and sec2 == "What each claim rests on", "%r/%r" % (ok2, sec2))
        # ③ 没有承认语句 → False
        p3 = os.path.join(root, "c.tex")
        io.open(p3, "w", encoding="utf-8").write(
            "\\section{Introduction}\nEverything is monotone everywhere.\n")
        ok3, _ = gate._admission(p3)
        check("没有承认语句时返回 False", ok3 is False)
        # ④ 两列数据不该再报「不足 4 个」
        import numpy as np
        import pandas as pd
        d = os.path.join(root, "two")
        os.makedirs(d, exist_ok=True)
        n = 40
        pd.DataFrame({"产量": np.linspace(1, 100, n),
                      "成本": np.linspace(10, 20, n) + np.sin(np.arange(n))}
                     ).to_excel(os.path.join(d, "data.xlsx"), index=False)
        io.open(os.path.join(d, "paper.tex"), "w", encoding="utf-8").write(
            "\\section{Evaluation}\nnothing admitted here.\n")
        io.open(os.path.join(d, "冻结数字.json"), "w", encoding="utf-8").write(
            json.dumps(dict(y="成本", x=["产量"]), ensure_ascii=False))
        r = gate.chk_falsify(d, data=os.path.join(d, "data.xlsx"))
        check("两列时不再报「数值列不足 4 个」",
              "不足 4" not in r["detail"], "%s / %s" % (r["status"], r["detail"][:70]))
        check("两列时给出可核对的结论",
              r["status"] in ("PASS", "WARN", "N/A"),
              "%s / %s" % (r["status"], r["detail"][:70]))
        # ⑤ 关键：证明 falsify **能红**。构造「整体方向显著、尾部反转、
        #    论文不承认、且没有第三列可控制」的数据 —— 必须 WARN。
        #    只测恒真的一侧，等于没测这个检查器。
        d2 = os.path.join(root, "can_fail")
        os.makedirs(d2, exist_ok=True)
        m = 40
        xv = np.arange(m, dtype=float)
        yv = np.where(xv < 30, 100 - 3 * xv, 13 + 2 * (xv - 30))
        pd.DataFrame({"驱动量": xv, "响应量": yv}).to_excel(
            os.path.join(d2, "data.xlsx"), index=False)
        io.open(os.path.join(d2, "paper.tex"), "w", encoding="utf-8").write(
            "\\section{Evaluation}\nWe claim the response falls with the driver "
            "everywhere.\n")
        io.open(os.path.join(d2, "冻结数字.json"), "w", encoding="utf-8").write(
            json.dumps(dict(y="响应量", x=["驱动量"]), ensure_ascii=False))
        r2 = gate.chk_falsify(d2, data=os.path.join(d2, "data.xlsx"))
        check("方向显著+尾部反转+未承认 → WARN", r2["status"] == "WARN",
              "%s / %s" % (r2["status"], r2["detail"][:80]))
        # 同一份数据，论文若承认了局部非单调 → 放行（断言强度匹配证据）
        io.open(os.path.join(d2, "paper.tex"), "w", encoding="utf-8").write(
            "\\section{Evaluation}\nThe direction does not hold everywhere: "
            "it fails locally in the upper tail.\n")
        r3 = gate.chk_falsify(d2, data=os.path.join(d2, "data.xlsx"))
        check("同样数据但已承认 → PASS", r3["status"] == "PASS",
              "%s / %s" % (r3["status"], r3["detail"][:80]))
    finally:
        _sh.rmtree(root, ignore_errors=True)


def part_h():
    print("H. paper.py 摘要词预算（超出就删段，不缩字号）")
    import paper as _paper
    # ① 纯词数：命令名去掉，但花括号里的正文必须留下
    #    Hello / world / x^2 / and / more / text = 6
    n = _paper._abs_words([r"\textbf{Hello} world $x^2$ and \emph{more} text"])
    check("_abs_words 保留花括号正文", n == 6, "实际 %d" % n)

    def _mk(npara, wpp):
        return [" ".join(["word%d" % i for i in range(wpp)]) + "\n"
                for _ in range(npara)]

    # ② 超预算 → 裁到预算内，且至少留 2 段
    body = _mk(10, 60)          # 600 词
    out = _paper._trim_abstract(body)
    w = _paper._abs_words(out)
    paras = [x for x in re.split(r"\n\s*\n", "\n".join(out)) if x.strip()]
    check("超预算被裁到预算内", w <= _paper.ABS_WORD_BUDGET, "%d 词" % w)
    check("至少保留 2 段", len(paras) >= 2, "%d 段" % len(paras))
    # ③ 已达标 → 原样返回
    small = _mk(2, 20)          # 40 词
    out2 = _paper._trim_abstract(small)
    check("未超预算不改动", _paper._abs_words(out2) == 40,
          "%d 词" % _paper._abs_words(out2))
    # ④ 只有 2 段时不许删（否则会把摘要删成一句）
    two = _mk(2, 400)           # 800 词但只有 2 段
    out3 = _paper._trim_abstract(two)
    paras3 = [x for x in re.split(r"\n\s*\n", "\n".join(out3)) if x.strip()]
    check("只有 2 段时宁可不裁", len(paras3) == 2, "%d 段" % len(paras3))


def part_i():
    print("I. 泄漏判定单一来源：gate 委托 mm，分类在建模入口就能算")
    import mm
    # ① 委托一致：两个入口对同一名字给出同一结论
    for nm in ("年份", "年龄", "pop2000", "total_votes", "1953"):
        check("gate 与 mm 对 %r 判定一致" % nm,
              gate._is_time_like(nm) == mm.is_time_like(nm),
              "gate=%r mm=%r" % (gate._is_time_like(nm), mm.is_time_like(nm)))
    check("滞后判据两处一致",
          gate._is_lag_pair("pop2000", "pop2005") is True
          and mm.is_lag_pair("pop2000", "pop2005") is True)
    # ② suspect_leak 三分类
    import shutil as _sh
    root = tempfile.mkdtemp(prefix="sl_")
    try:
        import numpy as np
        n = 60
        year = np.arange(1960, 1960 + n)
        y = year * 2.0 + np.linspace(0, 3, n)
        # 注意：「应当无关」的列**绝不能用 linspace 斜坡**。
        # 同一索引上的两条斜坡彼此相关 1.0，会被判成泄漏。
        # 这个陷阱在本文件里已经踩过三次（价格、年龄）。
        rng = np.random.default_rng(1)
        age = 30.0 + rng.normal(0, 5.0, n)
        d, _x = _mk_case(root, "mix",
                         {"年份": year, "pop2000": y * 0.99, "pop2005": y,
                          "消费金额": y * 1.001, "年龄": age},
                         "pop2005", ["年份", "pop2000", "消费金额", "年龄"])
        ds = mm.DS(os.path.join(d, "data.xlsx"))
        got = {c: k for c, _cc, k in mm.suspect_leak(
            ds, "pop2005", ["年份", "pop2000", "消费金额", "年龄"])}
        check("时间列归为 time", got.get("年份") == "time", str(got))
        check("同序列滞后归为 lag", got.get("pop2000") == "lag", str(got))
        check("其余高相关归为 leak", got.get("消费金额") == "leak", str(got))
        check("低相关列不进入结果", "年龄" not in got, str(got))
    finally:
        _sh.rmtree(root, ignore_errors=True)


def part_j():
    print("J. 外推判据：会穿零就必须声明适用区间（双向）")
    import shutil as _sh
    import numpy as np
    import pandas as pd
    root = tempfile.mkdtemp(prefix="ex_")
    try:
        # 构造：y 恒正，线性拟合的零点落在观测区间外一步（5 < cross <= 7.4）
        n = 30
        xv = np.linspace(1.0, 5.0, n)
        yv = 11.0 - 2.0 * xv + 0.05 * np.sin(np.arange(n))
        d = os.path.join(root, "ex")
        os.makedirs(d, exist_ok=True)
        df = pd.DataFrame({"驱动": xv, "响应": yv})
        df.to_excel(os.path.join(d, "data.xlsx"), index=False)
        io.open(os.path.join(d, "冻结数字.json"), "w", encoding="utf-8").write(
            json.dumps(dict(y="响应", x=["驱动"]), ensure_ascii=False))
        data = os.path.join(d, "data.xlsx")
        # ① 没声明 → WARN
        io.open(os.path.join(d, "paper.tex"), "w", encoding="utf-8").write(
            "\\section{Results}\nThe slope is negative and significant.\n")
        r1 = gate.chk_extrap(d, data=data)
        check("会穿零且未声明 → WARN", r1["status"] == "WARN",
              "%s / %s" % (r1["status"], r1["detail"][:60]))
        # ② 声明了 → PASS
        io.open(os.path.join(d, "paper.tex"), "w", encoding="utf-8").write(
            "\\section{Results}\nThe model should not be extrapolated "
            "outside the observed range.\n")
        r2 = gate.chk_extrap(d, data=data)
        check("会穿零但已声明 → PASS", r2["status"] == "PASS",
              "%s / %s" % (r2["status"], r2["detail"][:60]))
        # ③ 不穿零的题不受影响（改了 y 就不该报）
        df2 = pd.DataFrame({"驱动": xv, "响应": 5.0 + 0.5 * xv})
        df2.to_excel(os.path.join(d, "data.xlsx"), index=False)
        r3 = gate.chk_extrap(d, data=data)
        check("不穿零时不要求声明", r3["status"] == "PASS",
              "%s / %s" % (r3["status"], r3["detail"][:60]))
    finally:
        _sh.rmtree(root, ignore_errors=True)


def main():
    print("gate.py 护栏自检")
    part_a()
    part_c()
    part_b()
    part_d()
    part_e()
    part_f()
    part_g()
    part_h()
    part_i()
    part_j()
    print()
    if FAIL:
        print("失败 %d 项: %s" % (len(FAIL), FAIL))
        return 1
    print("全部通过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
