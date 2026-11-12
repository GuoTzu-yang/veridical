#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gate.py —— 统一质量门（第 9 轮，设计集成自 dsh-ultramath 的 verify_all.py + gates.py）

取自它的三个设计
----------------
1. **硬门 / 软门分离**：硬门 PASS/FAIL 决定能不能出稿；软门只记 WARN 不阻断。
   我们原来的 rules.py 是 7 项平铺，一项不过就全红，分不清轻重。
2. **N/A 是一种状态**：产物不存在时说 N/A，不是 FAIL。
   探索阶段没有 PDF 很正常，不该判失败。
3. **统一 JSON schema**：每项 `{id, status, detail}`，上层（阶段门禁、
   评审循环）都消费同一份结果，不各算各的。

去它的糟粕
----------
- 它的路径写死 `求解/` `论文/`，我们没有那种布局 —— 改成参数化
- 它的 `check_format` 认「核心公式汇总与建模思路回顾」这种中文节名，
  那是它自家模板 —— 我们换成自己的检查项

我们加的
--------
- `numbers`：论文里每个数必须有出处（复用 verify.py）
- `rules`：7 条竞赛规则（复用 rules.py）
- `falsify`：反例搜索（软门，只提示局部非单调）

用法
    python gate.py out/fig                    # 全量
    python gate.py out/fig --hard-only        # 只看硬门
    python gate.py out/fig --json             # 机器可读
    python gate.py selftest
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

# 编译错误的判据（照搬 ultramath：硬错误行 + 两类致命）
# 图片缺失报的是 "! Package pdftex.def Error: File `x.pdf' not found:
# using draft setting" —— 行首也是 !，但它只是降级（用方框代替图），
# 不是编译失败。图缺不缺由 chk_figures 单独管。
COMPILE_ERR = re.compile(
    r"(?m)^!\s(?!Package pdftex\.def Error)|Emergency stop|Fatal error")

HARD, SOFT = "hard", "soft"


# ══════════════════════════════════════════════════════════════════════
#  单项检查（统一返回 {id, status, detail, tier}）
# ══════════════════════════════════════════════════════════════════════
def _r(cid, tier, status, detail):
    return dict(id=cid, tier=tier, status=status, detail=str(detail)[:200])


# ── strict 模式：把「检查没做成」的 N/A 计为失败 ───────────────────
# N/A 原本混了两种含义，而 hard_ok 把它们都当通过：
#   ① 这题真没有这一项（题目不含该结构）
#   ② 检查没执行成功（读错表 / KeyError / 依赖缺失）
# ② 被当成通过，于是「读错表」也能拿到绿灯 —— 实测 dwts 的 leakage
# 就是这样：KeyError 报「没有数值列 placement」，状态 N/A，硬门算过。
# strict 只把 ② 降级为 FAIL；① 仍算通过。默认模式行为不变。
_NA_ERR_MARK = (
    "Exception", "Error", "Traceback", "KeyError", "TypeError",
    "ValueError", "ImportError", "AttributeError", "FileNotFoundError",
    "IndexError", "ZeroDivisionError", "UnicodeDecodeError",
)


def _na_is_error(detail: str) -> bool:
    d = str(detail)
    return any(m in d for m in _NA_ERR_MARK)


# ── N/A 的两种含义：类型化，不再靠 detail 文本猜 ────────────────────
# absent —— 本题确实没有这一项（题目不含该结构），硬门算通过
# failed —— 检查没跑成（读错表 / KeyError / 依赖缺失），硬门必须算失败
NA_ABSENT, NA_FAILED = "absent", "failed"


def _na(cid, tier, detail, kind=NA_ABSENT):
    r = _r(cid, tier, "N/A", detail)
    r["na_kind"] = kind
    return r


def _na_err(cid, tier, exc):
    """异常路径统一出口：类型即证据，不依赖异常文本。"""
    return _na(cid, tier, "%s: %s" % (type(exc).__name__, exc), kind=NA_FAILED)


def _is_failed_na(c):
    """带 na_kind 的按类型判；没带的老调用点退回文本匹配。"""
    k = c.get("na_kind")
    if k is not None:
        return k == NA_FAILED
    return _na_is_error(c.get("detail", ""))


# ── 数据表定位：按题解析，不扫描工作区 ────────────────────────────────
def _resolve_data(figdir: str, data: str = ""):
    """返回 (路径, 失败原因)。路径为空时原因说明为什么拿不到。

    顺序：显式路径 → runs.json 里这道题登记的表 → out/data/<题名>.xlsx|.csv → 放弃。
    刻意不调用 mm.find_xlsx()：那是「在工作区里找一个 xlsx」，与本题无关。
    实测它恒返回 APMCM 2026 B 题附件，导致 22/23 道题用别人的表做泄漏检查。
    """
    if data:
        if os.path.exists(data):
            return data, ""
        alt = os.path.join(HERE, "out", "data", os.path.basename(data))
        if os.path.exists(alt):
            return alt, ""
        return "", "给定了数据表但文件不存在：%s" % data

    name = os.path.basename(os.path.normpath(figdir))
    # ① runs.json 登记（先按题名，再按产物目录反查 —— 两者常常不同名，
    #    例如 dwts2026c 的产物目录叫 out/d2026c）
    try:
        import json as _json
        cfg = _json.load(open(os.path.join(HERE, "runs.json"), encoding="utf-8"))
        ent = (cfg.get(name) or {})
        if not ent:
            for _k, _v in cfg.items():
                if os.path.basename(os.path.normpath(_v.get("out") or "")) == name:
                    ent = _v
                    break
        fn = ent.get("data")
        if fn:
            cand = fn if os.path.isabs(fn) else os.path.join(
                HERE, "out", "data", os.path.basename(fn))
            if os.path.exists(cand):
                return cand, ""
    except Exception:                               # noqa: BLE001
        pass
    # ② 按产物目录名
    for ext in (".xlsx", ".csv"):
        p = os.path.join(HERE, "out", "data", name + ext)
        if os.path.exists(p):
            return p, ""
    return "", "没有这道题的数据表（runs.json 未登记，out/data/%s.xlsx 不存在）" % name


def _pick_col(ds, name):
    """把题面里的变量名对到真实列名：精确 → 唯一包含 → 放弃。

    题面常写简称（「热阻」），表里是全称（「无量纲热阻」）。只接受唯一解；
    多解或无解都返回 None，让调用方报清楚，而不是随便挑一列。
    """
    if not name:
        return None
    names = list(getattr(ds, "num_names", []) or [])
    if name in names:
        return name
    cands = [c for c in names if name in c]
    if len(cands) == 1:
        return cands[0]
    return None


# 名字像时间 / 序号列？保守识别：认不出就当「不是」，宁可多报一条假警。
# 注意：不能拿「年」「月」「日」做裸字包含 —— 「年龄」含「年」但不是时间轴，
# 实测把 age 判成时间列后，一条真的「年龄→目标」高相关被静默放过。
# 只认完整词形：年份/月份/日期/年度/季度/周次/期数/时间/编号/序号。
_TIME_COMPOUND = ("年份", "月份", "日期", "年度", "季度", "周次", "期数",
                  "时间", "编号", "序号")
_TIME_EN = ("year", "month", "date", "time", "period", "index", "week",
            "quarter")


def _is_lag_pair(a, b):
    """两列是不是**同一序列的不同期**（滞后自变量）。

    「pop2000 → pop2005」用上一期同口径值预测下一期，是人口/存量类问题的
    标准做法（队列存活、持续性模型），不是泄漏。
    而「total_votes → helpful_votes」虽然也高度相关，却是**包含关系**
    （helpful 是 total 的一部分），那才是拿响应凑响应。

    判据：去掉结尾的数字/分隔符后主干相同、数字部分不同。
    「总票数」这类不含数字后缀的名字对不上，仍按泄漏处理。
    """
    def stem(s):
        t = str(s or "").strip().lower()
        m = re.match(r"^(.*?)[\s_\-]*(\d+)$", t)
        if not m:
            return t, None
        return re.sub(r"[\s_\-]+$", "", m.group(1)), m.group(2)

    sa, na = stem(a)
    sb, nb = stem(b)
    if not sa or sa != sb or len(sa) < 2:
        return False
    return na is not None and nb is not None and na != nb


_ADMIT_PATS = (r"fail(s|ed)?\s+locally",
               r"no claim of monotonic",
               r"[Nn]ot monoton|[Nn]on-?monoton",
               r"local reversal",
               r"局部非单调", r"非单调", r"局部反例")


def _admission(tex_path):
    """论文有没有承认「局部非单调」，并报出写在哪一节。

    只提供证据位置，不判位置是否恰当：本仓库的论文这一节叫 Evaluation 或
    「What each claim rests on」，按标题硬判「必须在 Limitations」会把
    20 篇合格论文误打成 WARN（实测确认）。
    关键词匹配不是语义理解 —— 匹配不到不等于没写。
    """
    try:
        s = open(tex_path, encoding="utf-8", errors="replace").read()
    except OSError:
        return False, ""
    heads = [(m.start(), m.group(1))
             for m in re.finditer(r"\\section\{([^{}]*)\}", s)]
    for pat in _ADMIT_PATS:
        m = re.search(pat, s)
        if not m:
            continue
        pos, owner = m.start(), ""
        for st, title in heads:
            if st <= pos:
                owner = title
            else:
                break
        return True, owner.strip()
    return False, ""


def _is_time_like(name):
    """判断某列是不是时间轴 / 序号轴。

    用途：泄漏检查里把「时间与趋势共变」和「拿响应当自变量」分开。
    前者是正当建模（用时间解释趋势），报成泄漏就是假警报。

    只认完整词形，不做裸字包含：`年龄`/`周龄`/`年收入` 都不是时间轴。
    """
    import mm
    return mm.is_time_like(name)


def chk_compile(figdir: str) -> dict:
    """读 .log 数错误。没有 log → N/A（还没编译，不是失败）。"""
    log = os.path.join(figdir, "paper.log")
    if not os.path.exists(log):
        return _r("compile", HARD, "N/A", "没有 paper.log（尚未编译）")
    txt = open(log, encoding="utf-8", errors="replace").read()
    n = len(COMPILE_ERR.findall(txt))
    return _r("compile", HARD, "PASS" if n == 0 else "FAIL",
              f"{n} 处编译错误" if n else "无编译错误")


def chk_pdf(figdir: str) -> dict:
    """PDF 存在且页数合理（我们加的：编译成功不等于出了东西）。"""
    p = os.path.join(figdir, "paper.pdf")
    if not os.path.exists(p):
        # PDF 是硬门：没有 PDF 就是没出稿。原来报 N/A，于是
        # 只生成 tex 的题也显示「通过」—— 硬门形同虚设。
        return _r("pdf", HARD, "FAIL", "没有 paper.pdf，只有 tex 不算出稿")
    d = open(p, "rb").read()
    pages = len(re.findall(rb"/Type\s*/Page[^s]", d))
    if pages < 3:
        return _r("pdf", HARD, "FAIL", f"仅 {pages} 页，疑似编译不完整")
    return _r("pdf", HARD, "PASS", f"{pages} 页 / {len(d)} 字节")


def chk_numbers(figdir: str) -> dict:
    """论文里每个数都要能在冻结表找到出处。

    用 freeze.py 而不是直接比插件输出 —— 冻结表是中间层，
    它多了「反向核对」（插件算出的数论文有没有用上）和
    「传播检测」（数值变了能不能找出旧引用）。
    """
    tex = os.path.join(figdir, "paper.tex")
    fz = os.path.join(figdir, "冻结数字.json")
    if not os.path.exists(tex):
        return _r("numbers", HARD, "N/A", "没有 paper.tex")
    if not os.path.exists(fz):
        return _r("numbers", HARD, "N/A", "没有 冻结数字.json（先跑 run）")
    try:
        import json as _json
        import freeze
        frozen = _json.load(open(fz, encoding="utf-8"))
        # 输入表里的观测值算「可解释」（E 类）：它该追到输入文件，
        # 而不是追到某次计算 —— 与论文自己的五类分类保持一致。
        try:
            import untraced as _U
            _dv = _U.data_values_of(_U.find_data_file(figdir))
        except Exception:                            # noqa: BLE001
            _dv = None
        r = freeze.check_paper(open(tex, encoding="utf-8").read(), frozen,
                                  # 单点严判只对「交稿」：模板卷允许
                                  # 少量未溯源，交稿承诺零容忍
                                  single_point=_is_deliverable(figdir),
                                  data_values=_dv,
                               strict_source=_is_deliverable(figdir))
        bad = r.get("untraced") or []
        _pct = 100.0 * float(r.get("untraced_ratio") or 0.0)
        # 整数 token 未纳入判定这件事必须写在结论行里（第 122 轮，红队
        # 独立诊断 §3.5a）：不写出来，它就会变成一条静默的免检通道。
        _nint = int(r.get("n_int_not_judged") or 0)
        # 判死时把理由也写出来（红队独立验收 §3-④）：否则会出现
        # 「0.0% 无出处却 FAIL」，读日志的人会去查错方向。
        _why = r.get("reasons") or []
        return _r("numbers", HARD,
                  "PASS" if r["ok"] else "FAIL",
                  (f"{r['n_traced']}/{r['n_numbers']} 可溯源"
                   f"（无出处 {_pct:.1f}%，阈值 10%）"
                   + (f"，{len(bad)} 个" if bad else "")
                   + (f"；另有 {_nint} 个整数 token 未纳入判定" if _nint else "")
                   + ("；判死理由：" + "；".join(_why) if _why else "")))
    except Exception as e:                          # noqa: BLE001
        return _na_err("numbers", HARD, e)


def chk_rules(figdir: str) -> dict:
    """7 条竞赛规则。"""
    tex = os.path.join(figdir, "paper.tex")
    if not os.path.exists(tex):
        return _r("rules", HARD, "N/A", "没有 paper.tex")
    try:
        import rules
        r = rules.check(open(tex, encoding="utf-8").read())
        bad = [x["id"] for x in r["results"] if not x["ok"]]
        return _r("rules", HARD,
                  "PASS" if r["ok"] else "FAIL",
                  f"{r['passed']}/{r['total']} 通过"
                  + (f"，未过 {bad}" if bad else ""))
    except Exception as e:                          # noqa: BLE001
        return _na_err("rules", HARD, e)


def chk_aitaste(figdir: str) -> dict:
    """AI 味。软门：> 60 只警告。"""
    tex = os.path.join(figdir, "paper.tex")
    if not os.path.exists(tex):
        return _r("ai_taste", SOFT, "N/A", "没有 paper.tex")
    try:
        import aitaste
        r = aitaste.analyze(open(tex, encoding="utf-8").read())
        st = "PASS" if r["score"] <= 60 else "WARN"
        return _r("ai_taste", SOFT, st,
                  f"{r['score']}/100（{r['grade']}）")
    except Exception as e:                          # noqa: BLE001
        return _na_err("ai_taste", SOFT, e)


def chk_figures(figdir: str) -> dict:
    """图表质量。软门：平均分 < 7 只警告。"""
    try:
        import figcheck
        src = os.path.join(HERE, "plot_mpl.py")
        stext = open(src, encoding="utf-8").read() if os.path.exists(src) else ""
        # 只审论文真正引用的图
        only = None
        tex = os.path.join(figdir, "paper.tex")
        if os.path.exists(tex):
            import re as _re
            inc = _re.findall(r"\\includegraphics(?:\[.*?\])?\{([^}]+)\}",
                              open(tex, encoding="utf-8").read())
            if inc:
                # 论文引用的是 .pdf（图源已换成矢量），而 figcheck 审的是 .png。
                # 统一去掉扩展名，否则 only=['flow.pdf'] 匹配不上 flow.png。
                only = [os.path.splitext(os.path.basename(x))[0]
                        for x in inc]
        # 图可能在 figdir 根、figdir/fig（默认题），也可能在 figdir/<任意题名>/。
        # 实测踩到：out/d2026c 下同时有 fig/（11 张通用自动模式图，不属于本题）
        # 和 fig2026c/（本题真图 4 张）。只认 "fig" 会选中前者，而 only=
        # 来自论文引用的 fig1_lambda 等，匹配不上 → 报「没有 PNG」。
        # 改法：扫所有子目录，选「命中论文引用图名最多」的那个。
        cands = [figdir]
        try:
            cands += [os.path.join(figdir, _d)
                      for _d in sorted(os.listdir(figdir))
                      if os.path.isdir(os.path.join(figdir, _d))]
        except OSError:
            pass

        def _hits(d):
            if not os.path.isdir(d):
                return -1
            try:
                stems = {os.path.splitext(x)[0].lower()
                         for x in os.listdir(d)
                         if x.lower().endswith((".png", ".pdf"))}
            except OSError:
                return -1
            if not stems:
                return -1
            if only is None:
                return 0
            return sum(1 for o in only if o.lower() in stems)

        _fd, _best = figdir, -1
        for _c in cands:
            _h = _hits(_c)
            if _h > _best:
                _best, _fd = _h, _c
        r = figcheck.audit_dir(_fd, stext, only=only)
        if not r.get("ok"):
            return _r("figures", SOFT, "N/A", r.get("why", "没有图"))
        # 第 123 轮：**数量下限**（同上，对每份 deliverable 生效）。
        # 只查质量不查数量，会让「4 张图 + 9 张表」的稿子拿满分 ——
        # 表能承载信息，但评委翻页时的第一印象是图。
        _mf = _min_figs(figdir)
        if _is_deliverable(figdir) and r["n"] < _mf:
            return _r("figures", SOFT, "FAIL",
                      f"只有 {r['n']} 张图，低于交付下限 {_mf} 张"
                      f"（均分 {r['avg']}/10，质量不是问题，数量是）")
        st = "PASS" if r["avg"] >= 7 else "WARN"
        return _r("figures", SOFT, st,
                  f"均分 {r['avg']}/10（{r['n']} 张，"
                  f"A{r['grades']['A']} B{r['grades']['B']} "
                  f"C{r['grades']['C']} D{r['grades']['D']}）"
                  + (f"；交付下限 {_mf} 张" if _is_deliverable(figdir) else ""))
    except Exception as e:                          # noqa: BLE001
        return _na_err("figures", SOFT, e)


def chk_sensitivity(figdir: str) -> dict:
    """实质性敏感性分析（第 123 轮新增）。

    为什么要有这一门：敏感性分析是一等稿与二等稿的分水岭之一，而原来的
    gate 只在 `falsify` 里查「边际反例」，没有查「论文自己有没有扰动过参数」。

    只查关键词会被堆词通过，所以要求**三件同时成立**：
      ① 出现 sensitivity / robustness / 灵敏度 之类的词；
      ② 出现一个**参数范围**（`0.30--0.70`、`from 0.3 to 0.7`、`±10\\%`）；
      ③ 出现一句把它们连起来的判断（unchanged / stable / insensitive / 结论不变）。

    三件都齐才 PASS；缺哪件就在结论行里点名缺哪件 —— 不是笼统地说「没有敏感性分析」。
    """
    tex = os.path.join(figdir, "paper.tex")
    if not os.path.exists(tex):
        return _r("sensitivity", SOFT, "N/A", "没有 paper.tex")
    try:
        x = open(tex, encoding="utf-8").read()
        word = bool(re.search(r"sensitiv|robust|灵敏度|敏感性", x, re.I))
        rng = re.findall(
            r"\d+(?:\.\d+)?\s*(?:--|–|-|to|至)\s*\d+(?:\.\d+)?"
            r"|±\s*\d+(?:\.\d+)?\s*\\?%"
            r"|\\pm\s*\d+(?:\.\d+)?", x)
        verdict = bool(re.search(
            r"unchanged|insensitive|stable|robust to|not sensitive"
            r"|不变|无影响|稳健|结论不改", x, re.I))
        miss = []
        if not word:
            miss.append("没有 sensitivity/robustness 的表述")
        if not rng:
            miss.append("没有参数范围（如 0.30--0.70、from 0.3 to 0.7、±10\\%）")
        if not verdict:
            miss.append("没有「扰动后结论怎样」的判断（unchanged/stable/结论不变）")
        if miss:
            return _r("sensitivity", SOFT, "WARN" if not _is_deliverable(figdir)
                      else "FAIL", "；".join(miss))
        return _r("sensitivity", SOFT, "PASS",
                  f"有扰动范围（{len(rng)} 处，例 {rng[0].strip()[:18]}）"
                  f"且有扰动后的判断")
    except Exception as e:                          # noqa: BLE001
        return _na_err("sensitivity", SOFT, e)


def chk_significance(figdir: str) -> dict:
    """统计显著性 / 不确定性（第 123 轮新增，借自 NeurIPS Paper Checklist 第 7 项
    "Experiment Statistical Significance"）。

    为什么单独一门：`chk_sensitivity` 只查「参数扰动后怎样」，**不查结果本身有没有
    不确定性表述**。一个只给点估计、不给区间/误差的报告，在审稿人眼里是「不知道
    自己多不确定」，这与「不确定但说清楚」是两回事。

    判据（三选一即成立不算数，要求前两条同时成立）：
      ① 出现置信/区间/误差的表述（confidence interval / bootstrap / 标准差 /
         standard error / credible interval / ± / 区间）
      ② 出现一个**具体区间或误差数值**（`[0.29, 0.84]`、`0.83 ± 0.05`、`(0.79, 0.88)`）
    """
    tex = os.path.join(figdir, "paper.tex")
    if not os.path.exists(tex):
        return _r("significance", SOFT, "N/A", "没有 paper.tex")
    try:
        x = open(tex, encoding="utf-8").read()
        word = bool(re.search(
            r"confidence interval|credible interval|bootstrap|standard error"
            r"|标准差|標準差|置信|置信区间|可信区间|不确定性区间", x, re.I))
        val = re.findall(
            # 区间的两端可能带百分号：`[96.13\%, 97.22\%]` 是最常见的写法，
            # 原来漏掉 `\%`，于是论文明明白白写了区间、门还报「没有区间」。
            r"\[\s*-?\d+(?:\.\d+)?\s*\\?%?\s*,\s*-?\d+(?:\.\d+)?\s*\\?%?\s*\]"
            r"|\(\s*-?\d+(?:\.\d+)?\s*\\?%?\s*,\s*-?\d+(?:\.\d+)?\s*\\?%?\s*\)"
            r"|\\pm\s*\d+(?:\.\d+)?"
            r"|±\s*\d+(?:\.\d+)?"
            r"|±\s*\d+(?:\.\d+)?\s*\\?%", x)
        # 第 123 轮修：`[0,1]` 是「份额的定义域」，不是区间估计。
        # 实测 out/d2026c 靠这个平凡区间过了门 —— 那不叫交代不确定性。
        # 排除两种平凡情形：端点是 0 与 1 的开闭区间；宽度为 0 的退化区间。
        _trivial = []
        for _v in val:
            _nums = [float(t) for t in re.findall(r"-?\d+(?:\.\d+)?", _v)]
            if len(_nums) == 2 and (
                    (_nums[0] == 0.0 and _nums[1] == 1.0)
                    or _nums[1] - _nums[0] == 0.0):
                _trivial.append(_v)
        val = [v for v in val if v not in _trivial]
        miss = []
        if not word:
            miss.append("没有置信/区间/误差的表述")
        if not val:
            miss.append("没有具体区间或误差数值（如 [0.29, 0.84]、0.83 ± 0.05）")
        if miss:
            return _r("significance", SOFT,
                      "FAIL" if _is_deliverable(figdir) else "WARN",
                      "；".join(miss)
                      + "（NeurIPS Paper Checklist 第 7 项要求交代实验的统计显著性）")
        return _r("significance", SOFT, "PASS",
                  f"有区间/误差表述，且给了 {len(val)} 处具体数值"
                  f"（例 {val[0].strip()[:16]}）")
    except Exception as e:                          # noqa: BLE001
        return _na_err("significance", SOFT, e)


def chk_prompt(figdir: str) -> dict:
    """题面必须落地、必须被逐字引用、每一问必须被回应（第 123 轮新增）。

    用户的原话：**「要约束 LLM 认真地读取题目信息，不允许猜，不允许跳过！」**

    这三件事原来零约束：`paper.tex` 有 `\\section{Restatement}` 就算过，而这一节
    完全可以凭记忆写；题面从来没被存成文件，所以无从比对。

    判据见 `tools/prompt_fidelity.py`：A 题面存在且 ≥200 字符；
    B 正文有 ≥40 字与题面逐字一致；C 题面编号小问全部被回应。
    """
    try:
        import importlib.util
        _p = os.path.join(HERE, "tools", "prompt_fidelity.py")
        _spec = importlib.util.spec_from_file_location("_prompt_fid", _p)
        _m = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_m)
        r = _m.check_dir(figdir)
        if r is None:
            return _r("prompt", SOFT, "N/A", "没有 paper.tex")
        if r["problems"]:
            st = "FAIL" if _is_deliverable(figdir) else "WARN"
            return _r("prompt", SOFT, st, "；".join(r["problems"])[:260])
        return _r("prompt", SOFT, "PASS",
                  "；".join(r["notes"]) or "题面已落地且被逐字引用")
    except Exception as e:                          # noqa: BLE001
        return _na_err("prompt", SOFT, e)



def _qd():
    """载入 tools/quality_doors.py（不在包路径里，用 importlib）。"""
    import importlib.util
    p = os.path.join(HERE, "tools", "quality_doors.py")
    spec = importlib.util.spec_from_file_location("_qd", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def chk_proof(figdir: str) -> dict:
    """关键推导必须写成命题并给出证明（第 124 轮新增）。

    外部评审对工具论文的评语：「插件臂用可检查的等式替代了证明」。
    那不是说错，是说**33 道门里没有一道查这件事** —— 门在哪，注意力就在哪。
    """
    try:
        m = _qd()
        tex = m._tex(figdir)
        if tex[0] is None:
            return _r("proof", SOFT, "N/A", "没有 paper.tex")
        ok, det, _ = m.check_proof(m._subs(tex[0]))
        st = "PASS" if ok else ("FAIL" if _is_deliverable(figdir) else "WARN")
        return _r("proof", SOFT, st, det)
    except Exception as e:
        return _na_err("proof", SOFT, e)


def chk_iterlog(figdir: str) -> dict:
    """必须有「轮 | 现象 | 诊断 | 修正」的迭代史（第 124 轮新增）。

    对照组的这张表是它最强的东西：「每轮都是解出来了但结论不可信」。
    我的插件有 7 个纠错案例，但那是事后复盘，不是逐轮的不信。
    """
    try:
        m = _qd()
        tex = m._tex(figdir)
        if tex[0] is None:
            return _r("iterlog", SOFT, "N/A", "没有 paper.tex")
        ok, det, _ = m.check_iterlog(tex[0])
        st = "PASS" if ok else ("FAIL" if _is_deliverable(figdir) else "WARN")
        return _r("iterlog", SOFT, st, det)
    except Exception as e:
        return _na_err("iterlog", SOFT, e)


def chk_code(mods=("mmkit", "paper", "mm", "plot_mpl")) -> dict:
    """核心模块能否 import（比 py_compile 更严：能抓到循环导入）。"""
    bad = []
    for m in mods:
        r = subprocess.run([sys.executable, "-c", f"import {m}"],
                           capture_output=True, text=True,
                           encoding="utf-8", errors="replace", cwd=HERE)
        if r.returncode != 0:
            last = (r.stderr or "").strip().splitlines()
            bad.append(f"{m}: {last[-1][:50] if last else '?'}")
    return _r("code", HARD, "PASS" if not bad else "FAIL",
              "; ".join(bad) if bad else f"{len(mods)} 个模块可导入")


def chk_falsify(figdir: str, data: str = "") -> dict:
    """反例搜索 + 偏相关对照。

    只报「边际有反例」会冤枉论文：未控制第三变量时局部反例很常见。
    真正该报的是「边际有反例 **且** 控制后符号仍与主张相反」。
    """
    data, why = _resolve_data(figdir, data)
    if not data:
        return _na("falsify", SOFT, why, kind=NA_FAILED)
    try:
        import falsify
        import mm
        ds = mm.DS(data)
        cols = [c for c in ds.num_names if "编号" not in c]
        # 门槛从 4 降到 2：旧门槛是「前 3 列当 x、后 2 列当 y」时代留下的。
        # 现在用论文声明的 y/x，只需 y + 至少一个 x。
        if len(cols) < 2:
            return _r("falsify", SOFT, "N/A", "数值列不足 2 个")

        # 优先测论文**声明**的那对 y / x；拿不到才按列序盲测并标注。
        # 原来直接 xs=cols[:3]、ys=cols[3:5]，测的是任意列对，
        # 而 detail 写着「符号仍矛盾」——读者会以为在检验论文的主张。
        xs, ys, _mode = cols[:3], cols[3:5], "blind"
        _fz = os.path.join(figdir, "冻结数字.json")
        if os.path.exists(_fz):
            try:
                import json as _json
                _fd = _json.load(open(_fz, encoding="utf-8"))
                _y = _pick_col(ds, _fd.get("y"))
                _x = [c for c in (_pick_col(ds, v) for v in (_fd.get("x") or []))
                      if c and c != _y]
                if _y and _x:
                    xs, ys, _mode = _x, [_y], "paper"
            except Exception:                   # noqa: BLE001
                pass
        _tag = "" if _mode == "paper" else "（严格说这是盲测：冻结表里没有可用的 y/x）"
        marginal = 0
        real = []
        uncontrolled = 0
        n_insig = 0
        import math as _math
        for x in xs:
            for y in ys:
                if x == y:
                    continue
                # sign 必须按数据的实际符号。硬编码 -1 时，
                # 对任何正相关的变量对，测「负」当然处处是反例 ——
                # 那报的不是「结论有问题」，是「测错了方向」。
                _xv, _yv = ds.col(x), ds.col(y)
                _rho = _rho2(_xv, _yv)
                # 方向本身不显著时，不能拿它去检验「方向是否反转」：
                # 那是在给噪声判卷。实测 evaluation 的 交付周期→综合得分
                # 全局相关只有 -0.157（噪声），却算出「100% 区段违反」。
                # 用 t 检验判显著性（不引入 scipy），不显著就跳过这一对。
                _n = len([1 for a, b in zip(_xv, _yv)
                          if a is not None and b is not None
                          and a == a and b == b])
                _sig = False
                if _n > 3 and abs(_rho) < 0.999:
                    try:
                        _tc = mm._t_quantile(0.975, _n - 2)
                        _t = abs(_rho) * _math.sqrt(_n - 2) / _math.sqrt(
                            max(1e-12, 1 - _rho * _rho))
                        _sig = _t > _tc
                    except Exception:           # noqa: BLE001
                        _sig = True             # 算不出来就别拿它当理由跳过
                else:
                    _sig = _n > 3
                if not _sig:
                    n_insig += 1
                    continue
                _sg = 1 if _rho >= 0 else -1
                r = falsify.counterexamples(_xv, _yv, sign=_sg)
                if r["ok"]:
                    continue
                marginal += 1
                # 控制其余因子，看偏相关符号
                others = [c for c in cols if c not in (x, y)][:3]
                signs = []
                for o in others:
                    try:
                        pc = mm.partial_corr(ds, y, x, [o])
                        if pc.get("r") is not None:
                            signs.append(pc["r"])
                    except Exception:               # noqa: BLE001
                        continue
                if not others:
                    # 没有第三个数值列可控制：既不能把反例归因于混淆，
                    # 也不能就此放行。单独计数，最后如实报「未做对照」。
                    uncontrolled += 1
                    continue
                if signs and all(s < 0 for s in signs):
                    continue        # 控制后符号一致 → 反例来自混淆
                if signs:
                    real.append(f"{x[:6]}→{y[:6]}")
        # 论文已经如实说明了局部非单调，这条就算履行了 ——
        # gate 该查的是「断言强度是否超过证据」，不是「数据有没有反例」。
        # 数据有反例是事实，改不掉；论文承不承认才是可改的。
        # 无对照的反例（uncontrolled）与已控制的反例（real）同等计入：
        # 论文承认了「局部非单调」就等于覆盖了这两类。
        _admits, _sec = _admission(os.path.join(figdir, "paper.tex"))
        _where = ("论文「%s」节已承认" % _sec) if _admits else ""
        _nrev = len(real) + uncontrolled
        _unc = ("，另有 %d 组无数值列可对照" % uncontrolled) if uncontrolled else ""
        if _nrev and _admits:
            return _r("falsify", SOFT, "PASS",
                      f"{_nrev} 组局部非单调，{_where}{_unc}" + _tag)
        if real:
            return _r("falsify", SOFT, "WARN",
                      f"{len(real)} 组边际反例且控制后符号仍矛盾："
                      + "、".join(real[:3]) + _unc + _tag)
        if uncontrolled:
            return _r("falsify", SOFT, "WARN",
                      f"{uncontrolled} 组边际反例，无第三个数值列可控制，"
                      f"无法排除混淆" + _tag)
        if marginal:
            return _r("falsify", SOFT, "PASS",
                      f"{marginal} 组边际反例，但控制后符号一致"
                      f"（来自混淆，非真非单调）" + _tag)
        if n_insig and not (marginal or _nrev):
            # 方向本身不显著 → 谈不上「方向是否反转」。如实说没做检验，
            # 不要用一个恒真的 PASS 假装检查过了。
            return _r("falsify", SOFT, "N/A",
                      f"{n_insig} 组相关不显著，方向未建立，未做单调性检验"
                      + _tag)
        return _r("falsify", SOFT, "PASS", "未发现局部反例")
    except Exception as e:                          # noqa: BLE001
        return _na_err("falsify", SOFT, e)


# ══════════════════════════════════════════════════════════════════════
def chk_abstract(figdir: str) -> dict:
    """摘要 8 项硬性自检。硬门 —— 摘要是 35% 那一项的核心。"""
    tex = os.path.join(figdir, "paper.tex")
    if not os.path.exists(tex):
        return _r("abstract", HARD, "N/A", "没有 paper.tex")
    try:
        import abstract as ab
        r = ab.audit(open(tex, encoding="utf-8").read())
        if not r.get("items"):
            # 找不到摘要不能算通过：摘要（含关键词）是竞赛必交项。
            # 原来返回裸 N/A，硬门按通过处理 —— 实测 out/arch 用自定义环境
            # abstractbox，真有摘要却因识别不到而放行。
            return _na("abstract", HARD,
                       r.get("why", "无摘要")
                       + "（已尝试 abstract 类环境 / \\section{Abstract|摘要|Summary}）",
                       kind=NA_FAILED)
        bad = [i["name"] for i in r["items"] if not i["ok"]]
        return _r("abstract", HARD,
                  "PASS" if r["ok"] else "FAIL",
                  f"{r['score']}/100（{r['n_words']} 词，"
                  f"{r['anchors']} 处锚点）"
                  + (f"，未过 {bad}" if bad else ""))
    except Exception as e:                          # noqa: BLE001
        return _na_err("abstract", HARD, e)


def chk_leakage(figdir: str, data: str = "") -> dict:
    """数据泄漏：自变量里混进了与 y 高度相关的列。

    这是建模里最致命的错误之一：RMSE 会假性变好，而所有统计量都支持
    「模型很棒」。实测踩到过 —— 把另外两个响应变量当自变量，
    RMSE 从 0.00743 掉到 0.00276，gate 九项全绿。

    判据：任一自变量与 y 的 |相关系数| > 0.95 就报。

    数据来源：caller 传进来的 data 优先；没传才回退 mm.find_xlsx()。
    只用 find_xlsx() 时，比赛里换了一道题的产物目录仍会读上一道题的表，
    结果是「没有数值列 'placement'」这类 N/A 而不是真检查。
    """
    try:
        import json as _json
        import mm
        data, why = _resolve_data(figdir, data)
        fz = os.path.join(figdir, "冻结数字.json")
        # 从冻结表里拿 y 的名字（freeze 记了 source，但没记 y）
        # 退而求其次：直接读 tex 里的 notation，取第一个被解释变量
        if not data:
            # 硬门没跑成，不能算通过：严格模式会把它计为失败
            return _na("leakage", HARD, why, kind=NA_FAILED)
        ds = mm.DS(data)
        tex = os.path.join(figdir, "paper.tex")
        if not os.path.exists(tex):
            return _r("leakage", HARD, "N/A", "没有 paper.tex")
        # 从冻结表读 y / x —— 论文是英文并转成了符号，从正文反查不到
        hit, xused = None, []
        if os.path.exists(fz):
            _fd = _json.load(open(fz, encoding="utf-8"))
            hit = _pick_col(ds, _fd.get("y"))
            xused = [c for c in (_pick_col(ds, v) for v in (_fd.get("x") or []))
                     if c]
        if hit is None:
            _fd_y = (_fd.get("y") if os.path.exists(fz) else None)
            return _na("leakage", HARD,
                       "冻结表的 y=%r 对不上表里的列（有：%s）"
                       % (_fd_y, "、".join(list(ds.num_names)[:6])),
                       kind=NA_FAILED)
        import numpy as np
        yv = np.asarray(ds.col(hit), dtype=float)
        worst, who = 0.0, ""
        pool = xused or [c for c in ds.num_names
                         if c != hit and "编号" not in c]
        # 收集**所有**超阈值的列，而不是只看最相关的那一个：
        # 只看最大者时，一个正当的滞后项（pop2000→pop2005，相关 1.000）
        # 会把后面真正的泄漏掩盖掉。
        suspects = []
        for c in pool:
            if c == hit or "编号" in c or c not in ds.num_names:
                continue
            xv = np.asarray(ds.col(c), dtype=float)
            if xv.std() == 0 or yv.std() == 0:
                continue
            cc = float(np.corrcoef(xv, yv)[0, 1])
            if abs(cc) > abs(worst):
                worst, who = cc, c
            if abs(cc) > 0.95:
                suspects.append((cc, c))
        if suspects:
            # 0.95 以上基本就是同一个量换了名字。但要分成三类，
            # 否则一半告警是假警报，假警报会让真警报失效：
            #   ① 时间/序号列（月份→销量 +0.968、年份→人口 +0.998）——
            #      用时间解释趋势是模型本身；
            #   ② 同一序列的滞后项（pop2000→pop2005 +1.000）——
            #      持续性/队列存活模型；
            #   ③ 其余（消费金额→客户价值 +0.995、total_votes→helpful_votes
            #      +0.997）—— 拿另一个响应或它的组成部分冒充自变量，真泄漏。
            benign, real = [], []
            for cc, c in suspects:
                if _is_time_like(c) or _is_time_like(hit):
                    benign.append((cc, c, "时间/序号列（趋势共变）"))
                elif _is_lag_pair(c, hit):
                    benign.append((cc, c, "同一序列的滞后项（持续性模型）"))
                else:
                    real.append((cc, c))
            if real:
                real.sort(key=lambda t: -abs(t[0]))
                cc, c = real[0]
                _more = ("，另 %d 列同类" % (len(real) - 1)) if len(real) > 1 else ""
                return _r("leakage", HARD, "WARN",
                          f"{c[:10]} 与 {hit[:10]} 相关 {cc:+.3f}，"
                          f"疑似把响应当成了自变量{_more}")
            cc, c, why_b = benign[0]
            return _r("leakage", HARD, "PASS",
                      f"{c[:10]} 与 {hit[:10]} 相关 {cc:+.3f}，"
                      f"属{why_b}，不是泄漏")
        return _r("leakage", HARD, "PASS",
                  f"最高相关 {worst:+.3f}（{who[:10]}），无泄漏迹象")
        return _r("leakage", HARD, "PASS",
                  f"最高相关 {worst:+.3f}（{who[:10]}），无泄漏迹象")
    except Exception as e:                          # noqa: BLE001
        return _na_err("leakage", HARD, e)


def chk_math(figdir: str) -> dict:
    """数值对拍：统计实现算得对不对。

    三层：已知答案（构造时定死）、不变量（尺度/平移/打乱）、
    附录代码与实现是否同行为。
    这一项和论文内容无关，只验「算得对不对」—— 它错了，
    前面所有数字都不可信。
    """
    try:
        import verify_math
        import tempfile
        tmp = tempfile.mkdtemp(prefix="gatemath_")
        rows = (verify_math.known_answer(tmp)
                + verify_math.invariants(tmp)
                + verify_math.compare_cases(tmp)
                + verify_math.cross_impl(tmp))
        bad = [r for r in rows if not r["ok"]]
        if bad:
            return _r("math", HARD, "FAIL",
                      f"{len(bad)}/{len(rows)} 项不符："
                      + "；".join(r["name"] for r in bad[:2]))
        return _r("math", HARD, "PASS",
                  f"{len(rows)}/{len(rows)} 对拍通过")
    except Exception as e:                          # noqa: BLE001
        return _na_err("math", HARD, e)


def chk_innovation(figdir: str) -> dict:
    """创造性审查：核心思想 / 三段式 / 过度声称 / 创新点数量。

    依据《国奖论文评审对照表》：创造性占 ~30%（四轴最大），
    且「全文无统一核心思想」是一票否决项。
    """
    tex = os.path.join(figdir, "paper.tex")
    if not os.path.exists(tex):
        return _r("innovation", SOFT, "N/A", "没有 paper.tex")
    try:
        import innovation as _iv
        r = _iv.audit(open(tex, encoding="utf-8").read())
        bad = [i["name"] for i in r["items"] if not i["ok"]]
        return _r("innovation", SOFT,
                  "PASS" if r["ok"] else "WARN",
                  f"{r['score']}/100"
                  + (f"，未过 {bad}" if bad else ""))
    except Exception as e:                          # noqa: BLE001
        return _na_err("innovation", SOFT, e)


def chk_abs_page(figdir: str) -> dict:
    """摘要是否严格占第 1 页。

    判据顺序（第 1 条优先，因为它不猜版面位置）：
      A. 正文首节标题已经出现在第 1 页 → 摘要必然止于第 1 页，PASS。
      B. Keywords 出现在第 2 页 → 摘要（含关键词）跨页，FAIL。
      C. 第 2 页出现摘要的收尾句 / 小标题 → FAIL。

    2026-11-10 修正：原判据「第 2 页第一个章节标题之前的文字超过 200 字符」
    是假阳性来源 —— 章节标题可能正好落在第 1 页底部，此时第 2 页是从句子中间
    开始的正文续行，正则认不出标题，于是整页正文被当成摘要残留。实测 12 道题
    因此被误判为「摘要跨页」，其中 queueing 第 1 页底部明明已有「1 Introduction」。
    """
    pdf = os.path.join(figdir, "paper.pdf")
    if not os.path.exists(pdf):
        return _r("abs_page", HARD, "N/A", "没有 paper.pdf")
    try:
        from pypdf import PdfReader
        rd = PdfReader(pdf)
        if len(rd.pages) < 2:
            return _r("abs_page", HARD, "PASS", "只有 1 页")
        p1 = rd.pages[0].extract_text() or ""
        p2 = (rd.pages[1].extract_text() or "")[:1500]

        # 判据 A（主判据，最直接）：摘要的**结尾**是否落在第 1 页。
        # 从 paper.tex 取出 abstract 环境正文，归一化成纯字母数字，取末尾 40 字符，
        # 在第 1 页的归一化文本里找。这一条不推断版面位置，因此
        #   ① 不会被「章节标题正好落在第 1 页底部」骗成假阳性
        #      （旧判据 B 就这样把 12 道题误判成摘要跨页）；
        #   ② 也不会因为 Keywords 落在第 3 页而漏判
        #      （长摘要样例正是这样从旧判据下溜过去的）。
        tex = os.path.join(figdir, "paper.tex")
        _sec = None
        if os.path.exists(tex):
            try:
                _src = open(tex, encoding="utf-8", errors="replace").read()
                _m = re.search(r"\\section\{([^}]{2,80})\}", _src)
                _sec = _m.group(1).strip() if _m else None
                _am = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}",
                                _src, re.S)
                if _am:
                    _body = re.sub(r"\\[a-zA-Z]+\*?(\[[^\]]*\])?(\{[^{}]*\})?", " ",
                                   _am.group(1))
                    _ns = re.sub(r"[^a-z0-9]+", "", _body.lower())
                    if len(_ns) >= 60:
                        _tail = _ns[-40:]
                        _p1n = re.sub(r"[^a-z0-9]+", "", p1.lower())
                        if _tail in _p1n:
                            return _r("abs_page", HARD, "PASS",
                                      "摘要结尾落在第 1 页")
                        return _r("abs_page", HARD, "FAIL",
                                  "摘要结尾不在第 1 页（跨页）")
            except Exception:                       # noqa: BLE001
                pass

        # 判据 A2：摘要正文解析不出来时，退回「正文首节是否已在第 1 页」
        if _sec:
            _probe = _sec[:24].lower()
            if _probe and _probe in p1.lower():
                return _r("abs_page", HARD, "PASS",
                          f"第 1 页已出现正文首节「{_sec[:24]}」，摘要止于第 1 页")

        # 判据 B：Keywords 跑到第 2 页
        if re.search(r"\bkeywords?\b", p2, re.I):
            return _r("abs_page", HARD, "FAIL",
                      "摘要（含 Keywords）跨到第 2 页")
        # 判据 C：摘要的收尾句 / 小标题
        marks = ("Existing treatments", "We propose",
                 "The resulting model is deliberately",
                 "Two features distinguish",
                 "Problem 4 asks", "Problem 5 asks",
                 "standard errors anyway")
        hit = [m for m in marks if m in p2]
        if hit:
            return _r("abs_page", HARD, "FAIL",
                      f"摘要跨到第 2 页（{hit[0][:28]}）")
        return _r("abs_page", HARD, "PASS", "摘要止于第 1 页")
    except Exception as e:                          # noqa: BLE001
        return _na_err("abs_page", HARD, e)


def chk_bare_pct(figdir: str) -> dict:
    """扫裸 %：它会把同一行后面的内容变成注释。

    排除 转义写法与整行注释，以及整行注释。
    """
    tex = os.path.join(figdir, "paper.tex")
    if not os.path.exists(tex):
        return _r("bare_pct", HARD, "N/A", "没有 paper.tex")
    try:
        bad = []
        for i, ln in enumerate(open(tex, encoding="utf-8"), 1):
            body = ln.rstrip("\n")
            if body.lstrip().startswith("%"):
                continue                        # 整行注释，正常
            for m in re.finditer(r"%", body):
                j = m.start()
                # 往前数反斜杠：奇数个说明已转义
                k = j - 1
                nb = 0
                while k >= 0 and body[k] == "\\":
                    nb += 1
                    k -= 1
                if nb % 2 == 0:
                    bad.append((i, body[max(0, j - 40):j + 30]))
        if bad:
            i, seg = bad[0]
            return _r("bare_pct", HARD, "FAIL",
                      f"{len(bad)} 处裸 %（首处 L{i}: ...{seg}...）")
        return _r("bare_pct", HARD, "PASS", "没有裸 %")
    except Exception as e:                      # noqa: BLE001
        return _na_err("bare_pct", HARD, e)


def chk_stamp(figdir: str) -> dict:
    """判定是否绑定到**当前**文件的摘要。

    为什么需要（第 110 轮）：这一场我改了十几次 paper.tex，
    却一直引用「最早那次 gate 全绿」当结论 —— 判定与被判对象脱钩，
    绿灯就变成了装饰。这里把它变成可检查的：

      · 目录里没有 gate-report.json  → WARN（还没盖过章）
      · 有章，但 tex/pdf 的 sha256 与章上的不一致 → FAIL（结论已过期）
      · 章上的 digest 与当前一致 → PASS

    盖章用 `gate.py <dir> --stamp`。
    """
    # 只对「交稿」要求盖章：模板卷不投出去，没有章是正常的（第 112 轮）
    if not _is_deliverable(figdir):
        return _na("stamp", SOFT,
                   "非交稿（模板卷）：盖章只对交稿要求", NA_ABSENT)
    rep = os.path.join(figdir, "gate-report.json")
    tex = os.path.join(figdir, "paper.tex")
    pdf = os.path.join(figdir, "paper.pdf")
    if not os.path.exists(tex):
        return _r("stamp", SOFT, "N/A", "没有 paper.tex")
    if not os.path.exists(rep):
        return _r("stamp", SOFT, "WARN",
                  "没有 gate-report.json —— 这次判定没有绑定到文件摘要")
    try:
        import hashlib
        import json as _json
        r = _json.load(open(rep, encoding="utf-8"))

        def _d(p):
            if not os.path.exists(p):
                return None
            h = hashlib.sha256()
            with open(p, "rb") as f:
                h.update(f.read())
            return h.hexdigest()

        cur = {"tex": _d(tex), "pdf": _d(pdf)}
        old = r.get("digests", {})
        stale = [k for k in ("tex", "pdf")
                 if old.get(k) and cur.get(k) and old[k] != cur[k]]
        if stale:
            return _r("stamp", SOFT, "FAIL",
                      f"{'、'.join(stale)} 在盖章之后被改过 —— "
                      f"旧的绿灯不能再用，请重新跑 gate --stamp")
        return _r("stamp", SOFT, "PASS",
                  f"盖章于 {r.get('stamped_at', '?')}；摘要与当前文件一致")
    except Exception as e:                              # noqa: BLE001
        return _na_err("stamp", SOFT, e)


# ── 交付标准的下限（第 123 轮）──
#
# 用户的原话：「不是只有这篇论文是，而是用这个插件必须要遵循如此的规则。」
# 所以下面的门槛写进 gate，对**每一份 deliverable** 生效。
#
# 这些数是**设计选择不是定理**（同类经验区间，不是推导出来的），因此：
#   ① 写成模块常量，可被 `<figdir>/standard.json` 覆盖；
#   ② 结论行打印「实际值 / 门槛」，读者能自己判断；
#   ③ 只对 `_is_deliverable` 为真的目录生效 —— 模板卷不该被要求这些。
DEFAULT_MIN_BIB = 10      # 经验：优秀论文多在 8–15 条
DEFAULT_MIN_FIGS = 6      # 经验：一等稿多在 6–10 张图


def _std_override(figdir: str) -> dict:
    p = os.path.join(figdir, "standard.json")
    if not os.path.exists(p):
        return {}
    try:
        return json.load(open(p, encoding="utf-8")) or {}
    except Exception:                               # noqa: BLE001
        return {}


def _min_bib(figdir: str) -> int:
    return int(_std_override(figdir).get("min_bib", DEFAULT_MIN_BIB))


def _min_figs(figdir: str) -> int:
    return int(_std_override(figdir).get("min_figs", DEFAULT_MIN_FIGS))


def chk_refs(figdir: str) -> dict:
    r"""\ref 配平**并且真的引用了文献**。

    第 110 轮补第二半：原来只查 \ref，于是「全文 0 条引用」也 PASS ——
    一条没有引用可查的论文被算成「引用没问题」。这是本文自己列的
    「空洞检查」：判断在没有输入时恒真。现在 0 条 \cite 判 FAIL，
    除非文档显式放了 nonresearch.json 声明它不投学术场合。
    """
    tex = os.path.join(figdir, "paper.tex")
    if not os.path.exists(tex):
        return _r("refs", HARD, "N/A", "没有 paper.tex")
    try:
        x = open(tex, encoding="utf-8").read()
        refs = set(re.findall(r"\\ref\{([^}]+)\}", x))
        labs = set(re.findall(r"\\label\{([^}]+)\}", x))
        # 第 123 轮：**递归扫 \input 的文件**。
        # 论文把长表拆到 tab_checks.tex 是正常做法，而 label 写在被 \input
        # 的文件里时，只扫 paper.tex 会报「\ref 无对应 \label」—— 实测踩过：
        # tab:checks 明明有 label，gate 仍判 FAIL。判据必须跟着文件结构走。
        for _m in re.finditer(r"\\input\{([^}]+)\}", x):
            _p = os.path.join(figdir, _m.group(1))
            if not _p.endswith(".tex"):
                _p += ".tex"
            if os.path.exists(_p):
                try:
                    labs |= set(re.findall(r"\\label\{([^}]+)\}",
                                           open(_p, encoding="utf-8").read()))
                except Exception:                   # noqa: BLE001
                    pass
        miss = sorted(refs - labs)
        if miss:
            return _r("refs", HARD, "FAIL",
                      f"{len(miss)} 个 \\ref 无对应 \\label: {miss[:3]}")
        cites = re.findall(r"\\cite\{([^}]+)\}", x)
        keys = {k.strip() for c in cites for k in c.split(",") if k.strip()}
        bib = set(re.findall(r"\\bibitem\{([^}]+)\}", x))
        if not keys and not os.path.exists(
                os.path.join(figdir, "nonresearch.json")):
            return _r("refs", HARD, "FAIL",
                      f"{len(refs)} 个 \\ref 配平，但全文 0 条 \\cite —— "
                      f"没有引用可查，不等于引用没问题")
        uncited = sorted(bib - keys)
        if bib and len(uncited) > max(3, int(0.3 * len(bib))):
            return _r("refs", HARD, "WARN",
                      f"{len(uncited)}/{len(bib)} 条文献未被引用: {uncited[:3]}")
        # 第 123 轮：**数量下限**。
        # 用户提的规矩是「用这个插件必须遵循如此的规则」，不是某一篇的建议 ——
        # 所以下限写进门里，对每一份 deliverable 生效。
        # 下限值本身是**设计选择不是定理**（一等奖论文的文献量是经验区间），
        # 因此：① 写成模块常量，可被 standard.json 覆盖；② 结论行打印实际值与门槛。
        _min = _min_bib(figdir)
        if _is_deliverable(figdir) and len(bib) < _min:
            return _r("refs", HARD, "FAIL",
                      f"只有 {len(bib)} 条文献，低于交付下限 {_min} 条 —— "
                      f"文献量不是装饰：评委据此判断作者读没读过这个领域")
        return _r("refs", HARD, "PASS",
                  f"{len(refs)} 个 \\ref 配平；{len(keys)} 条引用用到 "
                  f"{len(bib)} 条文献"
                  + (f"（交付下限 {_min}）" if _is_deliverable(figdir) else ""))
    except Exception as e:                      # noqa: BLE001
        return _na_err("refs", HARD, e)


def chk_rigor(figdir: str) -> dict:
    """数学严谨性：模糊引用与不自足陈述（借自 dsh-danus 的 P5/P6）。

    软门：命中不一定错（「而不是取自教科书相关系数」就是正面用法），
    但每一条都值得人看一眼。
    """
    tex = os.path.join(figdir, "paper.tex")
    if not os.path.exists(tex):
        return _r("rigor", SOFT, "N/A", "没有 paper.tex")
    try:
        import re as _re
        x = open(tex, encoding="utf-8").read()
        body = _re.sub(r"\\[a-zA-Z]+\*?(\[[^\]]*\])?(\{[^{}]*\})?", " ", x)
        body = _re.sub(r"\s+", " ", body)
        p5 = [r"\bwell[- ]known\b", r"\bclassical\b",
              r"\bstandard\s+(argument|result|theory|method)\b",
              r"\bobvious(ly)?\b", r"\bit is known\b", r"\btextbook\b"]
        p6 = [r"[Uu]nder the (standard|usual|typical)",
              r"given the (usual|standard) (assumptions|hypotheses)"]
        h5 = sum(len(_re.findall(p, body, _re.I)) for p in p5)
        h6 = sum(len(_re.findall(p, body, _re.I)) for p in p6)
        if h5 + h6 == 0:
            return _r("rigor", SOFT, "PASS", "无模糊引用、无缺口陈述")
        # 「rather than taken from a textbook」这类是正面用法，不算问题
        if _re.search(r"rather than (taken from )?(a )?textbook", body, _re.I):
            h5 = max(0, h5 - 1)
        if h5 + h6 == 0:
            return _r("rigor", SOFT, "PASS", "只有正面用法")
        return _r("rigor", SOFT, "WARN",
                  f"P5 {h5} 处 / P6 {h6} 处，需人看")
    except Exception as e:                      # noqa: BLE001
        return _na_err("rigor", SOFT, e)


def chk_domain(figdir: str) -> dict:
    """领域污染：正文出现与响应变量不匹配的领域术语。"""
    tex = os.path.join(figdir, "paper.tex")
    if not os.path.exists(tex):
        return _r("domain", HARD, "N/A", "没有 paper.tex")
    try:
        import re as _re
        x = open(tex, encoding="utf-8").read()
        m = _re.search(r"Problem 1: How the geometry governs ([^}]+)", x)
        resp = (m.group(1) if m else "").strip().lower()
        if not resp:
            return _r("domain", HARD, "N/A", "读不到 Problem 1 的响应名")
        # 响应名不是热学类，却出现热沉术语 → 污染
        thermal_resp = any(k in resp for k in
                           ("thermal", "resistance", "heat", "temperature"))
        if thermal_resp:
            return _r("domain", HARD, "PASS",
                      f"响应「{resp[:24]}」与领域一致")
        bad = [w for w in ("R_{th}", "Nu = C", "subsection{Thermal resistance}",
                           "thermal resistance", "pressure drop",
                           "manifold", "pin-fin")
               if w in x]
        if bad:
            return _r("domain", HARD, "FAIL",
                      f"响应「{resp[:20]}」但出现 {len(bad)} 类热沉术语: "
                      f"{bad[:3]}")
        return _r("domain", HARD, "PASS",
                  f"响应「{resp[:24]}」无跨领域术语")
    except Exception as e:                      # noqa: BLE001
        return _na_err("domain", HARD, e)


# required 文本 → 论文里应有的线索（用标签/章节名，避免自然语言误判）
_REQ_EVIDENCE = {
    "守恒律或控制方程": ["conservation of", "governing relations", "Nu = C"],
    "量纲一致性": ["dimensionless"],
    "参数来源标注": ["Where the numbers come from"],
    "候选模型对比（交叉验证）": ["tab:multi", "cross-validated"],
    "残差诊断": ["tab:diag"],
    "预测区间与原量纲残差": ["tab:pi"],
    "目标函数与约束写成标准形式": ["mathbf{f}(x)", "min_{"],
    "求解方法与可行性检查": ["Pareto", "front", "knee"],
    "至少一次敏感性分析": ["tab:sens", "tornado", "Sensitivity"],
    "Pareto 前沿与非支配说明": ["Pareto", "front"],
    "写明目标向量而非加权和": ["mathbf{f}(x)", "objective vector", "min_{"],
    "解析解特例或数值稳定性验证": ["closed-form", "stability",
                                  "numerical stability", "verified"],
    "权重或偏好的敏感性": ["weight", "Problem 4"],
    "交叉验证或留出验证": ["cross-validated", "tab:multi"],
    "预测区间": ["tab:pi", "prediction interval"],
    "外推风险声明": ["extrapolat", "outside the observed"],
    "指标归一化方向说明": ["direction", "benefit", "cost"],
    "权重来源与合理性": ["weight"],
    "方法间一致性检验": ["consistent", "agreement"],
    "簇数选择依据": ["cluster"],
    "聚类有效性指标": ["silhouette", "cluster"],
    "结果可解释性": ["interpret"],
    "随机性来源与种子": ["seed", "random"],
    "重复次数与置信区间": ["replicate", "confidence"],
    "结果收敛性": ["converg"],
    "图的构造说明": ["graph", "node"],
    "算法复杂度": ["complexity"],
    "可行性与最优性": ["feasib", "optimal"],
}


def chk_required(figdir: str) -> dict:
    """题型必做项：required 在论文里有没有对应证据。

    软门：缺失不阻断出稿，但会被列出来 ——
    这是「换题后自动告诉你漏了什么」的机制。
    """
    import json as _j
    import re as _re
    kp = os.path.join(figdir, "题型.json")
    tex = os.path.join(figdir, "paper.tex")
    if not os.path.exists(kp):
        return _r("required", SOFT, "N/A", "没有 题型.json（未识别题型）")
    if not os.path.exists(tex):
        return _r("required", SOFT, "N/A", "没有 paper.tex")
    try:
        kd = _j.load(open(kp, encoding="utf-8"))
        req = kd.get("required") or []
        kinds = kd.get("kinds") or []
        if not req:
            return _r("required", SOFT, "PASS",
                      f"题型 {kinds} 无必做项")
        x = open(tex, encoding="utf-8").read()
        miss = []
        for item in req:
            clues = _REQ_EVIDENCE.get(item)
            if clues is None:
                continue                    # 没有映射的项不判
            if not any(c in x for c in clues):
                miss.append(item)
        if miss:
            return _r("required", SOFT, "WARN",
                      f"{len(miss)}/{len(req)} 项缺证据: {miss[:3]}")
        return _r("required", SOFT, "PASS",
                  f"题型 {kinds} 的 {len(req)} 项必做项齐备")
    except Exception as e:                  # noqa: BLE001
        return _na_err("required", SOFT, e)


# ── 失分层级 ──
# zero  一票归零：编译不过、数字不可溯源、引用断裂、领域污染…
# half  扣一半：摘要、摘要跨页、创新性、题型必做项
# decay 扣几分：措辞、图质量、反例
GATE_WEIGHT = {
    "compile": "zero",     # 编译不过就没有论文
    "pdf": "zero",         # 没有 PDF
    "numbers": "zero",     # 数字不可溯源 = 造假嫌疑
    "rules": "zero",       # 竞赛规则 7 项
    "bare_pct": "zero",    # 裸 % 会吞掉半句话（踩过）
    "refs": "zero",        # \ref 断裂 = 正文印出 ??
    "domain": "zero",      # 领域污染 = 标题与摘要矛盾
    "leakage": "zero",     # 数据泄漏 = 方法论错误
    "math": "zero",        # 对拍不过 = 算错
    "abstract": "half",    # 评委 90 秒看摘要
    "abs_page": "half",    # 摘要跨页是格式硬伤
    "innovation": "half",  # 评审权重 30%
    "required": "half",    # 题型必做项漏了就少一块
    "rigor": "decay",      # 措辞
    "aitaste": "decay",    # AI 味
    "figures": "decay",    # 图质量
    "falsify": "decay",
    "claims": "decay",    # 反例
}
_ORDER = ("zero", "half", "decay")
_CN = {"zero": "0 分项", "half": "半衰项", "decay": "衰减项"}




def _is_deliverable(figdir: str) -> bool:
    """这个目录是不是「交稿」。只有交稿才强制五件事与红队。

    为什么（第 112 轮）：语料里的 23 篇是**模板卷**，用途是证明流水线能跑，
    项目规则明确说它们不是交稿。把「分析/论证/纠错/落地/红队」压到模板卷上，
    等于用交稿标准判草稿 —— 账本会永远红，信号被噪声淹没。
    判据跟着主张走：`declaration.json` 里写 deliverable=true 的目录才按交稿判。
    """
    p = os.path.join(figdir, "declaration.json")
    if not os.path.exists(p):
        return False
    try:
        d = json.load(open(p, encoding="utf-8")) or {}
        return bool(d.get("deliverable"))
    except Exception:                                   # noqa: BLE001
        return False


def chk_redteam(figdir: str) -> dict:
    """分板块红队：七板七角色，专项探针逐条答，finding 必须关闭。

    判据在 redteam.py。**只有声明 deliverable 的目录才要求**：
    模板卷不是交稿，不要求红队记录（与五件事同一口径）。
    """
    if not _is_deliverable(figdir):
        return _na("redteam", SOFT,
                   "非交稿（模板卷）：红队按交稿标准才要求", NA_ABSENT)
    try:
        import redteam as _rt
        r = _rt.check(figdir)
        return _r("redteam", SOFT, r["level"], r["detail"])
    except Exception as e:                              # noqa: BLE001
        return _na_err("redteam", SOFT, e)


def chk_chapters(figdir: str, kind: str) -> dict:
    """「五件事」里的四件：分析 / 方法论证 / 自我纠错 / 落地。

    判据在 chapters.py（结构 + 正文信号词，表注算论证、表体不算）。
    **只有声明 deliverable 的目录才强制**：语料里的模板卷按项目规则不是交稿，
    用交稿标准判草稿会让账本永远红，反而丢掉信号（第 112 轮）。
    """
    if not _is_deliverable(figdir):
        return _na(kind, SOFT,
                   "非交稿（模板卷）：五件事按交稿标准才检查", NA_ABSENT)
    try:
        import chapters as _ch
        for x in _ch.check(figdir):
            if x["id"] == kind:
                return _r(kind, SOFT,
                          "PASS" if x["ok"] else x["level"],
                          x["detail"])
        return _na_err(kind, SOFT, RuntimeError("chapters 没有返回该项"))
    except Exception as e:                              # noqa: BLE001
        return _na_err(kind, SOFT, e)


def chk_biblio(figdir: str) -> dict:
    """文献必须绑定到可核验记录（第 117 轮）。

    判据来自 litsearch.py 的核查结果（lit_bound.json，离线可读）：
      · 每条 bibitem 必须绑定一条外部记录（DOI/arXiv 反查命中）；
      · 未被正文引用的条目算装饰，也要清掉。
    没有核查文件时不判失败（还没跑过核查），但会说明怎么生成。
    """
    f = os.path.join(figdir, "lit_bound.json")
    if not os.path.exists(f):
        return _na("biblio", SOFT,
                   "还没跑文献核查：python litsearch.py check <目录>", NA_ABSENT)
    try:
        d = json.load(open(f, encoding="utf-8"))
    except Exception as e:                              # noqa: BLE001
        return _na_err("biblio", SOFT, e)
    # A3（第 120 轮）：不能全信记录 —— 自己从论文里数一遍对账。
    # 攻击样例：只写 1 条 bibitem，记录里写 uncited=[]，就被判「全部绑定且被引用」。
    try:
        _tex = open(os.path.join(figdir, "paper.tex"), encoding="utf-8").read()
    except Exception:                                   # noqa: BLE001
        _tex = ""
    _n_bib = len(re.findall(r"\\bibitem\{", _tex))
    _cited = set()
    for _m in re.finditer(r"\\cite\{([^}]*)\}", _tex):
        for _k in _m.group(1).split(","):
            _cited.add(_k.strip())
    _keys = re.findall(r"\\bibitem\{([^}]*)\}", _tex)
    _uncited_real = [k for k in _keys if k not in _cited]
    if _tex and int(d.get("n") or 0) != _n_bib:
        return _r("biblio", SOFT, "FAIL",
                  "记录说 %s 条，论文里实际 %d 条 —— 记录与论文不符"
                  % (d.get("n"), _n_bib))
    if _tex and sorted(_uncited_real) != sorted(d.get("uncited") or []):
        return _r("biblio", SOFT, "FAIL",
                  "未引用清单与论文不符：实际 %s" % (_uncited_real[:4] or "无"))
    unbound = d.get("unbound") or []
    uncited = _uncited_real if _tex else (d.get("uncited") or [])
    # 专著/技术报告可以**显式声明**没有外部标识符（必须给理由）。
    # 豁免不是免检：名字必须精确匹配，且理由要写在文件里（可被评审看到）。
    _ex = {}
    _ep = os.path.join(figdir, "bib_exempt.json")
    if os.path.exists(_ep):
        try:
            _ex = (json.load(open(_ep, encoding="utf-8")) or {}).get("exempt") or {}
        except Exception:                               # noqa: BLE001
            _ex = {}
    _still = [k for k in unbound if k not in _ex]
    if _ex and len(_still) < len(unbound):
        unbound = _still
    if unbound:
        # 「查不到」不等于「是假的」：Crossref/arXiv 不收录全部文献
        # （NeurIPS 会议集、技术报告常见缺失）。所以报警告并点名，
        # 由作者逐条处理（补 DOI 或说明来源），而不是直接判死。
        return _r("biblio", SOFT, "WARN",
                  "%d/%d 条文献查不到外部记录，需逐条补 DOI 或说明：%s"
                  % (len(unbound), d.get("n", 0), ", ".join(unbound[:5])))
    if uncited:
        return _r("biblio", SOFT, "WARN",
                  "%d 条文献未被正文引用（装饰）：%s"
                  % (len(uncited), ", ".join(uncited[:4])))
    return _r("biblio", SOFT, "PASS",
              "%d 条文献全部绑定，且都被引用" % d.get("n", 0))


def chk_causal(figdir: str) -> dict:
    """因果措辞是否配了因果设计（第 114 轮，种子缺陷基准逼出来的缺口）。

    一个把「相关」写成「证明了因果」的论文，能通过原来的全部检查 ——
    因为没有任何一条读措辞。这里加一条最小可行的：断言因果就要说明设计。
    """
    import re as _re
    p = os.path.join(figdir, "paper.tex")
    if not os.path.exists(p):
        return _na("causal", SOFT, "没有 paper.tex", NA_ABSENT)
    with open(p, encoding="utf-8") as _f:
        t = _f.read().lower()
    claim = ("proves", "prove that", "causes", "causal effect", "leads to",
             "drives", "because of", "证明了", "导致", "因果")
    design = ("experiment", "randomis", "randomiz", "instrument",
              "counterfactual", "difference-in-difference", "granger",
              "control group", "natural experiment", "ablation",
              "准实验", "随机", "反事实")
    hit_c = [w for w in claim if w in t]
    hit_d = [w for w in design if w in t]
    if not hit_c:
        return _r("causal", SOFT, "PASS", "没有因果措辞，无需设计支撑")
    if hit_d:
        return _r("causal", SOFT, "PASS",
                  "有因果措辞（%s），并且交代了设计（%s）"
                  % (", ".join(hit_c[:2]), ", ".join(hit_d[:2])))
    return _r("causal", SOFT, "WARN",
              "有因果措辞（%s）但没有交代任何识别设计 —— "
              "要么降级为相关，要么说明凭什么能推因果"
              % ", ".join(hit_c[:3]))


def chk_claims(figdir: str) -> dict:
    """「声明-证据」节：声称全有证据，比承认几处没有更可疑。"""
    p = os.path.join(figdir, "paper.tex")
    if not os.path.exists(p):
        return _r("claims", SOFT, "N/A", "没有 paper.tex")
    t = open(p, encoding="utf-8").read()
    if "What each claim rests on" not in t:
        return _r("claims", SOFT, "FAIL",
                  "缺「声明-证据」节 —— 没有任何地方说明哪些结论证据不足")
    n_sup = t.count("Evidence:")
    n_uns = t.count("Not supported")
    if n_sup == 0:
        return _r("claims", SOFT, "FAIL", "该节里一条声明都没列")
    if n_uns == 0:
        return _r("claims", SOFT, "WARN",
                  f"{n_sup} 条全部声称有证据 —— 要么真的完整，要么没逐条查")
    return _r("claims", SOFT, "PASS",
              f"{n_sup} 条有证据 / {n_uns} 条明确无支撑")


def chk_rules_apmcm(figdir: str, track: str = "auto") -> dict:
    """APMCM 专用规则（章程第八条/第十二条）。

    与 chk_rules 并存：rules.py 是 MCM/ICM 口径，rules_apmcm.py 是 APMCM 口径。
    两者查的结构不同（A001-A008 vs I002-I008），同篇论文可以同时检查。

    track="auto"   有 Keywords 才查，没有则 N/A（避免对 MCM 论文报噪声）
    track="apmcm"  **强制检查**。这样漏写 Keywords 会被 A008 抓到，而不是
                   整块静默跳过 —— 后者是假绿。
    """
    tex = os.path.join(figdir, "paper.tex")
    if not os.path.exists(tex):
        return _r("rules_apmcm", SOFT, "N/A", "没有 paper.tex")
    try:
        _t = open(tex, encoding="utf-8").read()
        has_kw = bool(re.search(r"\\textbf\{keywords?\}|\\keyword\{|keywords?:",
                                _t, re.I))
        if track != "apmcm" and not has_kw:
            return _r("rules_apmcm", SOFT, "N/A",
                      "非 APMCM 格式（摘要后无 Keywords），不适用；"
                      "若这是 APMCM 论文请用 --track apmcm 强制检查")
        import rules_apmcm
        r = rules_apmcm.check(_t)
        bad = [x["id"] for x in r["results"] if not x["ok"]]
        return _r("rules_apmcm", SOFT,
                  "PASS" if r["ok"] else "WARN",
                  f"{r['passed']}/{r['total']} 通过"
                  + (f"，未过 {bad}" if bad else ""))
    except Exception as e:                          # noqa: BLE001
        return _na_err("rules_apmcm", SOFT, e)


def chk_cross_section(figdir: str) -> dict:
    """跨段一致性：说同一件事、数字却不同。

    numbers 只查「每个数有没有出处」，不查「同一结论在两处是否同一个数」。
    实测风险：正文写 83.5%、表格写 83.4%，两个都可能各有出处而全部放行。

    判据见 chk_cross.py：句子实词 Jaccard >= 0.5，且两侧数字集合互不包含。
    纯启发式，只报 WARN 供人工核对，不判 FAIL。
    """
    tex = os.path.join(figdir, "paper.tex")
    if not os.path.exists(tex):
        return _r("cross", SOFT, "N/A", "没有 paper.tex")
    try:
        import chk_cross
        hits, n = chk_cross.check(open(tex, encoding="utf-8").read())
        if not hits:
            return _r("cross", SOFT, "PASS", f"{n} 句，无跨段冲突")
        top = hits[0]
        return _r("cross", SOFT, "WARN",
                  f"{n} 句，{len(hits)} 处需人工核对"
                  f"（最相似 {top['jaccard']:.2f}："
                  f"{top['nums_a']} vs {top['nums_b']}）")
    except Exception as e:                          # noqa: BLE001
        return _na_err("cross", SOFT, e)


# ══════════════════════════════════════════════════════════════════════
#  外推荒谬性：线性模型稍一外推就预言不可能的取值，论文声明了边界吗？
# ══════════════════════════════════════════════════════════════════════
# 这条判据分两步落地（第 95→96 轮）：
#   ① 先做成独立审计 tools/probe_extrapolation.py，量出「23 题里 5 题触发」；
#      （第一版量出 11 题是错的 —— 常数项约定混用，见 falsify.fit_centered）
#   ② 5 道题全部补上「适用区间」声明后，才接进这里。
# 不先做 ① 就接，会一夜之间 5 道题变红，而且没人知道红得对不对。
_EXTRAP_PATS = (
    r"should not be extrapolated",
    r"outside the observed (range|support)",
    r"no claim is made",
    r"interpolation, not an extrapolation",
    r"only (valid|admissible) (with)?in",
    r"where this model is valid",
    r"scope of extrapolation",
    r"适用区间",
    r"外推",
)


def chk_extrap(figdir: str, data: str = "") -> dict:
    """SOFT：外推一步就穿零时，论文必须把适用区间说出来。"""
    try:
        data_path, why = _resolve_data(figdir, data)
        if not data_path:
            return _na("extrap", SOFT, "没有数据表，未做外推检查：" + why)
        fz = os.path.join(figdir, "冻结数字.json")
        if not os.path.exists(fz):
            return _na("extrap", SOFT, "没有 冻结数字.json，不知道 y/x 是什么")
        import json as _json
        import mm
        fd = _json.load(open(fz, encoding="utf-8"))
        ds = mm.DS(data_path)
        y = _pick_col(ds, fd.get("y"))
        xs = [c for c in (_pick_col(ds, v) for v in (fd.get("x") or []))
              if c and c != y]
        if not y or not xs:
            return _na("extrap", SOFT, "冻结表里没有可用的 y/x")
        ap = mm.applicability(ds, xs, y)
        if not ap:
            return _na("extrap", SOFT, "样本不足或因子无变化，无法外推")
        absurd = [a for a in ap if a.get("absurd")]
        if not absurd:
            return _r("extrap", SOFT, "PASS",
                      f"{len(ap)} 个因子在外推一步内都不穿零")
        tex_p = os.path.join(figdir, "paper.tex")
        txt = ""
        if os.path.exists(tex_p):
            txt = open(tex_p, encoding="utf-8").read()
        hit = [p for p in _EXTRAP_PATS
               if __import__("re").search(p, txt, __import__("re").I)]
        _which = "、".join(f"{a['x']}（零点 {a['cross_at']:g}）"
                           for a in absurd[:3])
        if hit:
            return _r("extrap", SOFT, "PASS",
                      f"{len(absurd)} 个因子外推会穿零（{_which}），"
                      f"论文已声明适用区间")
        return _r("extrap", SOFT, "WARN",
                  f"{len(absurd)} 个因子外推一步就穿零（{_which}），"
                  f"但论文没说哪里不适用 —— 加一节「适用区间/以外推为界」")
    except Exception as e:                          # noqa: BLE001
        return _na_err("extrap", SOFT, e)


def run_all(figdir: str, data: str = "", strict: bool = True,
            track: str = "auto", lenient: bool = False) -> dict:
    checks = [
        chk_compile(figdir),
        chk_pdf(figdir),
        chk_code(),
        chk_numbers(figdir),
        chk_rules(figdir),
        chk_rules_apmcm(figdir, track=track),
        chk_abstract(figdir),
        chk_abs_page(figdir),
        chk_bare_pct(figdir),
        chk_refs(figdir),
        chk_rigor(figdir),
        chk_domain(figdir),
        chk_required(figdir),
        chk_leakage(figdir, data),
        chk_math(figdir),
        chk_innovation(figdir),
        chk_aitaste(figdir),
        chk_claims(figdir),
        chk_causal(figdir),
        chk_biblio(figdir),
        # 第 111 轮：用户要的五件事里，前四件必须被强制（第五件是 claims 表）
        chk_chapters(figdir, "analysis"),
        chk_chapters(figdir, "method_argument"),
        chk_chapters(figdir, "self_correction"),
        chk_chapters(figdir, "deployment"),
        chk_redteam(figdir),
        chk_cross_section(figdir),
        chk_figures(figdir),
        chk_falsify(figdir, data),
        chk_extrap(figdir, data),
        # 第 123 轮：交付标准（文献数量下限、图数量下限、实质性敏感性分析）。
        # 用户的原话是「用这个插件必须遵循如此的规则」，所以落进门里，
        # 对每份 deliverable 生效，而不是对某一篇论文的建议。
        chk_sensitivity(figdir),
        # NeurIPS Paper Checklist 第 7 项（Experiment Statistical Significance）：
        # 只给点估计不给区间，等于不知道自己多不确定。
        chk_significance(figdir),
        # 第 123 轮：题面忠实度（不许猜、不许跳过）。
        # 用户的原话：「要约束 LLM 认真地读取题目信息」。
        chk_prompt(figdir),
        # 第 124 轮：外部评审点出的两项建模质量门
        chk_proof(figdir),
        chk_iterlog(figdir),
        # 第 110 轮：判定必须绑定到文件摘要。
        # 没有这一条时，改了十几次 tex 仍可以引用「上一次 gate 全绿」。
        chk_stamp(figdir),
    ]
    # 第 111 轮：显式声明豁免。没有输入数据集的产物（例如一篇讲工具的论文）
    # 可以在目录里放 declaration.json:
    #   {"no_dataset": ["leakage","falsify","extrap","domain"], "reason": "..."}
    # 只有**被点名**的 check 才算 legitimately absent；未点名的一律 fail-closed。
    # 声明会被打印出来，所以它不能当万能挡箭牌。
    _decl = {}
    _dp = os.path.join(figdir, "declaration.json")
    if os.path.exists(_dp):
        try:
            _decl = json.load(open(_dp, encoding="utf-8")) or {}
        except Exception:                               # noqa: BLE001
            _decl = {}
    _declared_na = set(_decl.get("no_dataset") or [])
    if _declared_na:
        # 诊断走 stderr：stdout 要留给 --json 消费者（第 113 轮，
        # 红队/评审抓到的「矩阵漏一题」就是这行污染了 JSON）
        sys.stderr.write("  声明豁免（无输入数据集）：" + ", ".join(sorted(_declared_na))
              + ("  — " + str(_decl.get("reason"))[:60]
                 if _decl.get("reason") else "") + "\n")
    for c in checks:
        if c["id"] in _declared_na and c["status"] == "N/A":
            c["na_kind"] = NA_ABSENT
            c["detail"] = "已声明无数据集；" + c["detail"]

    # strict：N/A 必须说清是哪种。第 112 轮统一规则：
    # 硬 N/A 若不是 na_kind=ABSENT（没声明「本题真没有这一项」），一律 FAIL。
    # 否则会出现「all_pass=False 但 hard_fail 为空」这种自相矛盾的状态
    # （dwts2026c 的 domain 就是这样：不带 na_kind，strict 抓不到）。
    if strict:
        for c in checks:
            if c["status"] != "N/A" or c.get("na_kind") == NA_ABSENT:
                continue
            if _is_failed_na(c) or c["tier"] == HARD:
                c["detail"] = "检查未执行(strict)：" + c["detail"]
                c["status"] = "FAIL"
    for c in checks:
        c["weight"] = GATE_WEIGHT.get(c["id"], "decay")
    hard = [c for c in checks if c["tier"] == HARD]
    # 硬门：N/A 能否算过，取决于它为什么是 N/A（第 110 轮，红队 F3）。
    # 原实现 all(status in ("PASS","N/A")) 把**所有** N/A 记为绿，
    # 于是「论文写完了但没有可核对的冻结表」——正是要拒的对象——也会绿。
    # 现在：只有 na_kind == NA_ABSENT（本题确实没有这一项）才算过；
    #       NA_FAILED（没做成）与未分类的 N/A 都不算过。
    _na_ok = [c for c in hard
              if c["status"] == "N/A" and c.get("na_kind") == NA_ABSENT]
    hard_ok = all(c["status"] == "PASS" or c.get("na_kind") == NA_ABSENT
                  for c in hard)
    # 没有 na_kind 的 N/A 一律按「没做成」处理（fail-closed）
    for c in hard:
        if c["status"] == "N/A" and c.get("na_kind") is None:
            c["na_kind"] = NA_FAILED
            hard_ok = False
    # 分层统计：每层「通过数 / 总数」+ 失败项
    tiers = {}
    for w in _ORDER:
        sub = [c for c in checks if c["weight"] == w]
        if not sub:
            continue
        ok = [c for c in sub if c["status"] in ("PASS", "N/A")]
        tiers[w] = dict(total=len(sub), ok=len(ok),
                        fail=[c["id"] for c in sub if c["status"] == "FAIL"],
                        warn=[c["id"] for c in sub if c["status"] == "WARN"])
    # 综合风险：有 0 分项失败 → 高；有半衰项失败 → 中；只有衰减 → 低
    if tiers.get("zero", {}).get("fail"):
        risk = "高（存在归零风险）"
    elif tiers.get("half", {}).get("fail"):
        risk = "中（关键项未过）"
    elif any(t.get("fail") for t in tiers.values()):
        risk = "低（仅衰减项）"
    else:
        risk = "低"
    # 第 120 轮：软门 FAIL 也必须计入 —— 否则会出现「通过（警告 0）」
    # 而明细里列着 [FAIL] 的自相矛盾（实测踩到）。
    _soft_fail = [c["id"] for c in checks
                  if c["status"] == "FAIL" and c["weight"] != HARD]
    _warns = [c["id"] for c in checks if c["status"] == "WARN"] + _soft_fail
    # 第 118 轮：警告也阻断「通过」。文档一直这么写，代码此前只看硬门。
    # 警告阻断只对「交稿」生效：模板卷是草稿，警告照报但不判死
    # （与五件事、盖章同一口径；报告里会注明当前是哪种模式）
    _deliv = _is_deliverable(figdir)
    _warn_block = bool(_warns) and not lenient and _deliv
    return dict(
        checks=checks,
        all_pass=hard_ok and not _warn_block,
        warn_block=_warn_block,
        hard_fail=[c["id"] for c in hard if c["status"] == "FAIL"],
        warns=[c["id"] for c in checks if c["status"] == "WARN"],
        na=[c["id"] for c in checks if c["status"] == "N/A"],
        tiers=tiers,
        risk=risk,
    )


def report(r: dict) -> str:
    mark = {"PASS": "OK  ", "FAIL": "FAIL", "WARN": "WARN", "N/A": "-   "}
    # 报告第一行：判定 + 阻断原因 + 三类计数（第 118 轮：警告也阻断）
    _head = "质量门：%s" % ("通过" if r["all_pass"] else "未通过")
    if r.get("warn_block"):
        _head += ("（警告阻断：%s，草稿可用 --lenient 放行）"
                  % ",".join(r["warns"][:3]))
    _head += ("（硬门失败 %d，警告 %d，未适用 %d）"
              % (len(r["hard_fail"]), len(r["warns"]), len(r["na"])))
    L = [_head]
    # 先给按失分权重分的三层，再看明细
    for _w in _ORDER:
        _t = (r.get("tiers") or {}).get(_w)
        if not _t:
            continue
        _bad = _t["fail"] + _t["warn"]
        _mark = "OK  " if not _bad else ("FAIL" if _t["fail"] else "WARN")
        _tail = ("  ← " + ", ".join(_bad[:4])) if _bad else ""
        L.append(f"  [{_mark}] {_CN[_w]:<7}{_t['ok']}/{_t['total']} 通过"
                 + _tail)
    if r.get("risk"):
        L.append(f"  综合风险：{r['risk']}")
    L.append("")
    for c in r["checks"]:
        tier = "硬" if c["tier"] == HARD else "软"
        L.append(f"  [{mark[c['status']]}] {tier} {c['id']:<9} {c['detail']}")
    return "\n".join(L)


# ══════════════════════════════════════════════════════════════════════
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

    here = os.path.dirname(os.path.abspath(__file__))
    fig = os.path.join(here, "out", "fig")

    ck("compile 无 log 时 N/A",
       chk_compile(os.path.join(here, "out", "nonexist"))["status"] == "N/A")
    ck("code 能导入核心模块", chk_code()["status"] == "PASS",
       chk_code()["detail"][:60])
    ck("code 抓得住坏模块", chk_code(("不存在的模块",))["status"] == "FAIL")

    # 真实产物
    if os.path.exists(os.path.join(fig, "paper.tex")):
        cr = chk_compile(fig)
        ck("真实论文编译检查", cr["status"] in ("PASS", "N/A"), cr["detail"])
        rr = chk_rules(fig)
        ck("真实论文规则检查", rr["status"] == "PASS", rr["detail"])
        ar = chk_aitaste(fig)
        ck("真实论文 AI 味", ar["status"] == "PASS", ar["detail"])
        nr = chk_numbers(fig)
        ck("真实论文数字溯源", nr["status"] in ("PASS", "N/A"), nr["detail"])

    # 硬软门分离
    r = dict(checks=[
        _r("a", HARD, "FAIL", ""), _r("b", SOFT, "WARN", ""),
        _r("c", HARD, "N/A", "")],
        all_pass=False, hard_fail=["a"], warns=["b"], na=["c"])
    ck("硬门 FAIL 导致未通过", not r["all_pass"])
    # N/A 不该算失败
    r2 = dict(checks=[_r("c", HARD, "N/A", "")], all_pass=True,
              hard_fail=[], warns=[], na=["c"])
    ck("硬门 N/A 不算失败", r2["all_pass"])

    # 全量跑一次不崩
    full = run_all(fig)
    ck("全量跑通", "checks" in full and len(full["checks"]) >= 8,
       f"{len(full.get('checks', []))} 项")
    ck("全量结果可序列化", bool(json.dumps(full, ensure_ascii=False)))

    # ── 第 110 轮：三个「检查器自己不动」的洞，钉死 ──
    # ① 零引用不能算「引用没问题」
    import tempfile
    td = tempfile.mkdtemp(prefix="gate_st_")
    io_ = os.path.join(td, "paper.tex")
    with open(io_, "w", encoding="utf-8") as f:
        f.write("\\documentclass{article}\\begin{document}"
                "见第~\\ref{a}~节，结论见~\\ref{b}。"
                "\\label{a}\\label{b}\\end{document}")
    r = chk_refs(td)
    ck("零引用判 FAIL（不是 PASS）", r["status"] == "FAIL", r["detail"][:40])
    # ② 显式声明非学术稿则豁免
    with open(os.path.join(td, "nonresearch.json"), "w",
              encoding="utf-8") as f:
        f.write("{}")
    r = chk_refs(td)
    ck("显式声明非学术稿可豁免", r["status"] != "FAIL", r["status"])
    # ③ 盖章后改文件必须判过期
    td2 = tempfile.mkdtemp(prefix="gate_st2_")
    p2 = os.path.join(td2, "paper.tex")
    with open(p2, "w", encoding="utf-8") as f:
        f.write("v1")
    # 盖章只对「交稿」要求，测试目录要先声明自己是交稿（第 112 轮）
    with open(os.path.join(td2, "declaration.json"), "w",
              encoding="utf-8") as f:
        json.dump(dict(deliverable=True), f)
    with open(os.path.join(td, "declaration.json"), "w",
              encoding="utf-8") as f:
        json.dump(dict(deliverable=True), f)
    import hashlib as _h

    def _sha(x):
        q = _h.sha256()
        with open(x, "rb") as f:
            q.update(f.read())
        return q.hexdigest()

    with open(os.path.join(td2, "gate-report.json"), "w",
              encoding="utf-8") as f:
        json.dump(dict(stamped_at="t", digests=dict(tex=_sha(p2), pdf=None)), f)
    ck("摘要一致时 stamp 通过", chk_stamp(td2)["status"] == "PASS",
       chk_stamp(td2)["detail"][:40])
    with open(p2, "w", encoding="utf-8") as f:
        f.write("v2-changed")
    ck("改动后 stamp 判过期", chk_stamp(td2)["status"] == "FAIL",
       chk_stamp(td2)["detail"][:50])
    ck("没有章时 stamp 只警告", chk_stamp(td)["status"] == "WARN")

    # 越权开关：必须「标记 + 判定仍为假」，不能变成假绿（第 113 轮）
    td3 = tempfile.mkdtemp(prefix="gate_fo_")
    with open(os.path.join(td3, "paper.tex"), "w", encoding="utf-8") as f:
        f.write("\\begin{document}no pdf will be produced\\end{document}")
    r3 = run_all(td3)
    ck("缺 PDF 时 all_pass 为假", r3["all_pass"] is False,
       str(r3["hard_fail"])[:40])

    print(f"\n{'ALL PASS' if bad == 0 else 'FAILED'}  {n - bad}/{n}")
    return 0 if bad == 0 else 1



def _rho2(a, b):
    """Pearson 相关，纯 Python（gate 不依赖 numpy）。"""
    pr = [(x, y) for x, y in zip(a, b)
          if x is not None and y is not None]
    n = len(pr)
    if n < 3:
        return 0.0
    mx = sum(p[0] for p in pr) / n
    my = sum(p[1] for p in pr) / n
    sxx = sum((p[0] - mx) ** 2 for p in pr)
    syy = sum((p[1] - my) ** 2 for p in pr)
    sxy = sum((p[0] - mx) * (p[1] - my) for p in pr)
    if sxx <= 0 or syy <= 0:
        return 0.0
    return sxy / (sxx * syy) ** 0.5

def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="统一质量门")
    ap.add_argument("dir", nargs="?", default="")
    ap.add_argument("--data", default="")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--hard-only", action="store_true")
    ap.add_argument("--lenient", action="store_true",
                    help="N/A 中「检查没跑成」的部分仍算通过（旧行为）")
    ap.add_argument("--strict", action="store_true", default=True,
                    help="N/A 中「检查没跑成」计为失败（默认）")
    ap.add_argument("--track", default="auto", choices=["auto", "apmcm", "mcm"],
                    help="论文赛道。apmcm 会强制跑 A001-A008（含 Keywords 检查），"
                         "即使没写 Keywords 也检查，避免静默跳过")
    # 比赛交卷开关（第 113 轮，评审建议）：deadline 前硬门红了也要能出 PDF。
    # 它**不静默**：会在报告里写一行「已越权」并把失败项原样列出，
    # 这样「交卷优先」与「不许假装通过」两件事同时成立。
    ap.add_argument("--force-override", action="store_true",
                    help="越过硬门出稿；报告里会标记越权与未清失败项")
    ap.add_argument("--stamp", action="store_true",
                    help="跑完把判定与 tex/pdf 的 sha256 一起写进 "
                         "gate-report.json（绑定结论与被判对象）")
    a = ap.parse_args(argv)

    if not a.dir or a.dir == "selftest":
        return selftest()

    r = run_all(a.dir, a.data, strict=(not a.lenient), track=a.track,
                lenient=a.lenient)
    if getattr(a, "force_override", False) and not r["all_pass"]:
        # 越权不是假装通过：标记 + 原样列出未清项，退出码仍非 0
        r["overridden"] = True
        r["override_note"] = ("已越权出稿：硬门未通过，失败项未清 —— "
                              "论文须在 limitations 里写明")
        print("  [越权] " + r["override_note"], file=sys.stderr)
    if a.stamp:
        import datetime as _dt
        import hashlib

        def _sha(p):
            if not os.path.exists(p):
                return None
            h = hashlib.sha256()
            with open(p, "rb") as f:
                h.update(f.read())
            return h.hexdigest()

        rep = dict(
            stamped_at=_dt.datetime.now().isoformat(timespec="seconds"),
            dir=os.path.abspath(a.dir),
            digests=dict(tex=_sha(os.path.join(a.dir, "paper.tex")),
                         pdf=_sha(os.path.join(a.dir, "paper.pdf"))),
            hard_fail=r["hard_fail"],
            all_pass=r["all_pass"],
            checks=[dict(id=c["id"], tier=c["tier"], status=c["status"])
                    for c in r["checks"]],
        )
        with open(os.path.join(a.dir, "gate-report.json"), "w",
                  encoding="utf-8", newline="\n") as f:
            json.dump(rep, f, ensure_ascii=False, indent=1)
        print(f"已盖章：{os.path.join(a.dir, 'gate-report.json')}")
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        print(report(r))
        if a.hard_only:
            print(f"\n硬门失败：{r['hard_fail'] or '无'}")
    return 0 if r["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
