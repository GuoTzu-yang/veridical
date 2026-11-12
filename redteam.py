"""redteam.py —— 分板块强制红队：不同板块配不同专职评审，专项检查（第 112 轮）。

为什么不是「一个通用红队」
--------------------------
一个通用评审会漏掉它不熟的板块：统计学问题由排版视角看不出来，落地问题由
统计学视角看不出来。所以这里把论文切成七个板块，**每板一个专职角色**，
每角色有自己的探针清单，且：

  · 角色必须互不相同（一板一角色，不得复用）；
  · 每板的探针必须**逐条回答**（pass / finding），不能只给一个总分；
  · 出现 finding 的板必须有 `resolved`（怎么处理的），否则算未关闭；
  · 全文一条 finding 都没有 → WARN（红队什么都没找到，通常说明它没干活）。

判定数据放在 `<论文目录>/redteam.json`：
  {"reviews": [{"section": "analysis", "role": "decomposition-auditor",
                "probes": [{"probe": "...", "verdict": "pass", "note": ""},
                           {"probe": "...", "verdict": "finding",
                            "note": "..."}],
                "resolved": "把分类表补进 §2.1", "verdict": "revise"}]}

gate 通过 `chk_redteam` 调它；本模块自检断言「漏板/复用角色/探针未答/未关闭」
四种情况都必须 FAIL。
"""
import io
import re
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))

# ── 十二板 ── 论文有几个 \section，就有几个板块、几个专职角色。
#
# 第 123 轮修正：原来只有 **7 板**，而 `out/final/paper.tex` 有 **12 个
# \section**。7 对 12，缺的 5 段正文（题面重述 / 假设 / 符号 / 自我的
# 评价与扩展 / 结论）从来没有独立的审核者 —— 那不是「规矩」，那是
# 用 7 个角色名掩盖 5 段没人审的正文。
#
# 判据不依赖人记：`roster()` 直接从 SPEC 生成「这轮该建几个审核者、
# 每个审哪一节、用什么探针」，新会话跑 `python redteam.py roster`
# 就知道该建 12 个，不需要读交接文件的散文。
SPEC = {
    # 1
    "restatement": dict(
        role="scope-auditor",
        probes=[
            "重述是否逐条覆盖题面的每一问（有没有漏问）",
            "有没有在重述里悄悄放宽或收紧约束",
            "题面给的常数/量纲是否原样搬来并标了出处",
            "重述里是否已经出现结论（把答案写进问题）",
        ],
        need="题面条目 × 重述条目 一一对照表"),
    # 2
    "analysis": dict(
        role="decomposition-auditor",
        probes=[
            "分类是否互斥（一个对象不会同时属于两类）",
            "分类是否穷尽（有没有不属于任何一类的对象被悄悄丢掉）",
            "每一类是否改变了「检查器能问什么」",
            "分母是否完整（有没有只统计了打印出来的前 N 条）",
        ],
        need="分类表/分类图 + 每类对应的检查策略"),
    # 3
    "assumptions": dict(
        role="assumption-auditor",
        probes=[
            "每条假设是否可证伪（什么数据会推翻它）",
            "有没有把结论写成假设（循环论证）",
            "假设被违反后的后果写了吗（不是「假设成立即可」）",
            "假设数量与检验能力是否匹配（越多越不可检验）",
        ],
        need="假设 × 证伪条件 × 违反后果 三列表"),
    # 4
    "notation": dict(
        role="notation-auditor",
        probes=[
            "每个符号是否只指一个对象（有无一词多义）",
            "有没有符号在正文使用前未定义",
            "符号表与正文是否一致（抽查 10 个）",
            "单位/量纲是否随符号一起写",
        ],
        need="符号表 × 正文首次出现位置 对照"),
    # 5
    "method_argument": dict(
        role="alternative-auditor",
        probes=[
            "每个方法是否都配了被否掉的替代方案",
            "否决理由是否可证伪（什么证据会让我们改主意）",
            "有没有把「实现方便」写成「方法更优」",
            "方法的成本是否给了实测值而非形容词",
        ],
        need="方法/替代/理由 三列对照"),
    # 6
    "validation": dict(
        role="statistics-auditor",
        probes=[
            "样本量 n 是否与结论强度匹配",
            "多重比较/窗口数是否交代并处理",
            "效应量是否给了区间而不只是点估计",
            "消融是否非平凡（删掉机制后是否只得到 0 或 1）",
        ],
        need="误差/灵敏度/稳健性三类检验各一条"),
    # 7
    "results": dict(
        role="reproducibility-auditor",
        probes=[
            "每个数字是否能追到工件",
            "口径是否写明（gate 口径 vs 全量口径）",
            "图表是否都被正文引用且图注与内容一致",
            "计数是否与工件同源（不手抄）",
        ],
        need="两口径并列 + 图注-正文一致"),
    # 8
    "self_correction": dict(
        role="confession-auditor",
        probes=[
            "每条是否写清「错在哪」",
            "每条是否写清「怎么发现的」（哪个测量暴露的）",
            "每条是否写清「改了什么」",
            "每条是否给出「为什么这个改法是对的」（不是「现在绿了」）",
        ],
        need="至少两例，每例四段齐全"),
    # 9
    "deployment": dict(
        role="operations-auditor",
        probes=[
            "运行方式是否给全（单机/服务/CI）",
            "时间预算是否用实测秒数",
            "失败处置是否可执行（症状→第一步→不许做什么）",
            "成本是否区分机器时间与编辑时间",
        ],
        need="运行方式表 + 时间预算表 + 处置表"),
    # 10
    "evaluation": dict(
        role="evaluation-auditor",
        probes=[
            "自评的每条判据是否可复核（能跑命令验证）",
            "有没有把「我没做」写成「不需要做」",
            "扩展方向是否可执行（下一步做什么、代价是什么）",
            "自评分数与证据是否匹配（高分项有没有对应证据）",
        ],
        need="判据 × 复现命令 × 未做项 三列表"),
    # 11
    "conclusion": dict(
        role="conclusion-auditor",
        probes=[
            # 第 123 轮改：原来写「结论是否回应了**题面**的每一问（逐问对照）」——
            # 这条探针让 conclusion 板去拿 restatement 板的输入，是**越界**。
            # 实测后果：它拿 2026 MCM Problem C（DWTS）的 10 问去要求一篇
            # 工具论文（out/final）逐条回应，而 DWTS 的稿在 out/d2026c。
            # 正确做法是只对**本论文自己声明的任务**（Restatement 那一节），
            # 这是块内一致性，可自证，不需要外部题面。
            "结论是否收束了重述（restatement 节）里声明的每一问",
            "有没有新信息（结论里出现正文没证过的数/事实）",
            "主张强度是否超过证据（「显著」「证明」）",
            "有没有写清边界（结论在什么条件下失效）",
        ],
        need="重述声明清单 × 结论条目 对照表"),
    # 12
    "claims": dict(
        role="overclaim-auditor",
        probes=[
            "每条主张是否都有证据指针",
            "每条主张是否写明「哪里没支撑」",
            "有没有把「未见反例」写成「已证明」",
            "有没有主张超出语料范围而没说明边界",
        ],
        need="声明/证据/未支撑 三列表"),
}


def roster(figdir: str = "") -> list:
    """这轮该建几个审核者、每个审哪一节、用什么探针。

    规矩：**论文有几个板块，就有几个对应的审核。**
    名单从 `paper.tex` 的 `\\section` 生成 —— 不是从 SPEC 数出来，
    也不是靠人在交接文件里记。新会话跑 `python redteam.py roster`
    就能拿到完整名单（几板、每板什么角色、哪几条探针、有没有交）。

    给了 figdir 就同时报「这一板现在有没有 review、上一版的探针判定」。
    """
    secs = paper_sections(figdir) if figdir else []
    if not secs:
        secs = [(k, k) for k in SPEC]
    have = {}
    if figdir:
        for r in (load(figdir).get("reviews") or []):
            s = str(r.get("section") or "").strip()
            if s:
                have.setdefault(s, r)
    out = []
    for i, (key, title) in enumerate(secs, 1):
        spec = spec_for(key)
        r = have.get(key) or {}
        out.append(dict(
            index=i, section=key, title=title, role=spec["role"],
            n_probes=len(spec["probes"]), probes=list(spec["probes"]),
            need=spec["need"],
            has_review=bool(r),
            prev_verdict=r.get("verdict") or "",
            prev_probe_verdicts=[p.get("verdict")
                                 for p in (r.get("probes") or [])],
        ))
    return out



def load(figdir: str) -> dict:
    p = os.path.join(figdir, "redteam.json")
    if not os.path.exists(p):
        return {}
    try:
        return json.load(io.open(p, encoding="utf-8")) or {}
    except Exception:                                   # noqa: BLE001
        return {}


# ── 规矩：论文有几个板块，就有几个对应的审核 ──
#
# 第 123 轮修正（这是一次真正的判据修正，不是加角色名）：
# 原来 `check()` 写的是 `missing = [s for s in SPEC if s not in by_sec]`
# —— **审核清单来自写死的 SPEC（7 个），不是来自论文（12 个 \section）**。
# 于是论文里有 5 段正文（题面重述 / 假设 / 符号 / 自我评价与扩展 / 结论）
# 从来没有独立的审核者，而 gate 照样报「七板七角色，13 条 finding 且均已关闭」。
#
# 正确做法：**审核清单从 paper.tex 解析生成**。论文加一节就自动多一条要求，
# 删一节就自动少一条。SPEC 只负责「已知板块用什么专用探针」，
# 解析出来但 SPEC 没有的板块用 GENERIC_PROBES 兜底 —— 兜底不等于豁免。

# 论文小节标题 → SPEC 键。顺序即论文顺序。
SECTION_HINTS = (
    ("restatement", ("restatement", "problem statement", "题面")),
    ("analysis", ("analysis",)),
    ("assumptions", ("assumption",)),
    ("notation", ("notation", "symbol")),
    ("method_argument", ("method",)),
    ("validation", ("validation",)),
    ("results", ("results",)),
    ("self_correction", ("what was wrong", "self-correction", "correction")),
    ("deployment", ("deployment",)),
    ("evaluation", ("evaluation",)),
    ("conclusion", ("conclusion",)),
    ("claims", ("claims", "reproducibility", "disclosure")),
)

# 解析出来但 SPEC 里没有的板块用这四条。它们与 SPEC 的探针同构：
# 问「有没有可复核的证据」「有没有被引用」「有没有超证据」「有没有写边界」。
GENERIC_PROBES = (
    "这一板是否有可复核的证据（表/数字/引用，而不是只有形容词）",
    "这一板是否被正文其他位置引用（孤立的小节通常是没写完）",
    "这一板的主张是否超出它给出的证据",
    "这一板是否写清了边界（在什么条件下不成立）",
)


def section_key(title: str) -> str:
    """论文小节标题 → 板块标识。已知的映射到 SPEC 键，未知的退化为 slug。"""
    t = str(title).lower()
    for key, hints in SECTION_HINTS:
        if any(h in t for h in hints):
            return key
    slug = re.sub(r"[^a-z0-9]+", "-", t).strip("-")
    return slug[:40] or "unnamed"

def paper_sections(figdir: str) -> list:
    """从 paper.tex 解析出全部小节，返回 [(key, 标题), ...]。

    这才是「论文有几个板块」的唯一真相源。没有 paper.tex 时返回空表，
    调用方退回 SPEC（自检与无正文场景用）。
    """
    p = os.path.join(figdir, "paper.tex")
    if not os.path.exists(p):
        return []
    try:
        tex = io.open(p, encoding="utf-8", errors="replace").read()
    except Exception:                                   # noqa: BLE001
        return []
    out = []
    seen = {}
    for m in re.finditer(r"\\section\*?\{([^{}]*)\}", tex):
        title = m.group(1).strip()
        if not title:
            continue
        key = section_key(title)
        # 防撞：slug 截到 40 字符，长标题的前 40 字符可能相同
        # （如两节都以「Problem 3: what contestant and partner ch」开头）。
        # 撞了就加序号，否则两板会映射到同一个 key —— 12 板变 11 板，
        # 而 gate 只会说「角色复用」，不会说「你少了一板」。
        if key in seen:
            seen[key] += 1
            key = f"{key}-{seen[key]}"
        else:
            seen[key] = 1
        out.append((key, title))
    return out


def spec_for(key: str) -> dict:
    """这一板该用哪个角色、哪几条探针。SPEC 没有的板块用通用探针兜底。"""
    if key in SPEC:
        return SPEC[key]
    return dict(role=f"{key}-auditor", probes=list(GENERIC_PROBES),
                need="这一板的证据/引用/边界（通用探针）")


def _disposition(r: dict) -> str:
    """这条 review 的 finding 到底处于什么状态：fixed / blocked / open。

    第 123 轮（本轮）：原来 `check()` 只要求 `resolved` 非空 —— 于是
    **写「未处理」三个字就能关闭一条 finding**。实测 12 板 40 条 finding
    的 `resolved` 大多正是「未处理。…」，而 gate 照样报「40 条 finding
    且均已关闭」。这是比「没有审核」更隐蔽的一种自欺：账面上关了，
    正文一个字没改。

    判据分三级：
      fixed   —— 正文/代码真的改了（`resolved` 写清改了哪里）
      blocked —— 外部条件不具备（缺数据集/缺题面原文等），必须写
                 `blocked_reason`，且理由要能被复核
      open    —— 其余，包括「未处理」「待处理」「todo」这类占位词。

    `open` 计入失败：论文有未处理缺陷时，gate 就该红。
    """
    d = str(r.get("disposition") or "").strip().lower()
    if d in ("fixed", "blocked", "open", "rejected"):
        return d
    txt = str(r.get("resolved") or "").strip()
    low = txt.lower()
    if not txt:
        return "open"
    for ph in ("未处理", "待处理", "待办", "todo", "pending", "n/a", "na"):
        if low.startswith(ph) or low == ph:
            return "open"
    return "fixed"


def _finding_disp(p: dict, r: dict) -> str:
    """一条 **finding** 的处置状态：fixed / blocked / open / rejected。

    `rejected`（第 123 轮新增）：**finding 本身不成立**。
    红队也会误判 —— 实测 conclusion 板拿 2026 MCM Problem C 的 10 问要求
    一篇**工具论文**的结论逐条回应，而那 10 问属于 `out/d2026c`（DWTS 建模稿），
    不是 `out/final`（讲数字溯源的方法论文）：`DWTS`/`Dancing with the Stars`/
    `fan vote`/`celebrity`/`producer`/`memo` 在 out/final 全篇各 0 次。
    拿错基准产生的 finding 必须能被驳回，否则「未处理」会永远挂着一个假缺陷。

    驳回的门槛与 finding 一样高：必须给出**可复核的反证**（文件 + 逐字标记），
    否则 `check()` 会判 FAIL。

    第 123 轮修：disposition 原来是 **review 级** —— 一条 review 有 4 条 finding，
    修好其中 1 条就把整条 review 标成 fixed 或 open，粒度太粗。
    实测：改了 1 条 finding 的 evidence，同板另外 3 条跟着变色；
    40 条 finding 在 36 open / 4 fixed / 40 open 之间来回跳。

    现在 finding 级优先：`probe.disposition` 有值就用它；
    **没有值一律 open** —— 不回落到 review 级。

    为什么不回落（第 123 轮实测）：一条 review 有 4 条 finding，
    review 的 `resolved` 写「已修 A」，推不出「B 也修了」。
    回落逻辑把 evaluation 的「Two extensions are immediate」
    （一个字没改）判成 fixed，于是 40 条 finding 只有 17 条真的标了状态，
    另外 23 条靠整板说明「继承」了关闭状态 —— 又是一种假绿。
    """
    d = str(p.get("disposition") or "").strip().lower()
    if d in ("fixed", "blocked", "open", "rejected"):
        return d
    return "open"


def check(figdir: str) -> dict:
    r"""返回 dict(ok, level, detail, per_section)。

    缺板判定用 **paper.tex 的 \section**，不是 SPEC 的键表。
    板数跟着论文走：4 节论文就只要 4 个审核，12 节就要 12 个。
    """
    data = load(figdir)
    reviews = data.get("reviews") or []
    secs = paper_sections(figdir)
    if not reviews:
        # 第 123 轮：**把下一步直接写进判决里**。
        # 新会话开插件时，它必然要跑 gate —— 那就让 gate 自己说「去跑这条命令」，
        # 而不是指望它先读 AGENTS 再自己想到。文档要靠人读，判决不用。
        _auto = ("python tools/redteam_orchestrate.py auto %s" % figdir)
        return dict(ok=False, level="FAIL",
                    detail=(f"没有 redteam.json —— 论文 {len(secs) or '？'} 个板块"
                            "都没有审核记录。下一步：先跑 "
                            f"`{_auto}`（它会列出几板、生成每板任务书、"
                            "告诉你该派几个独立审核者、以及分几批），"
                            "派完再 `python tools/redteam_orchestrate.py collect "
                            f"{figdir}`"),
                    per_section={})
    by_sec = {}
    for r in reviews:
        sec = str(r.get("section") or "").strip()
        if sec:
            by_sec.setdefault(sec, []).append(r)

    # 论文的实际板块（没有 paper.tex 时退回 SPEC，供自检使用）
    need = [k for k, _t in secs] if secs else list(SPEC)
    missing = [k for k in need if k not in by_sec]
    if missing:
        titles = dict(secs)
        detail = ("论文有 %d 个板块，只有 %d 个有审核；缺：%s"
                  % (len(need), len(need) - len(missing),
                     "、".join(f"{k}（{titles.get(k, '?')[:24]}）"
                               for k in missing[:6])))
        return dict(ok=False, level="FAIL", detail=detail, per_section=by_sec)

    roles = [by_sec[s][0].get("role") for s in need]
    if len(set(roles)) != len(roles):
        dup = [r for r in set(roles) if roles.count(r) > 1]
        return dict(ok=False, level="FAIL",
                    detail=f"角色复用：{dup} —— 不同板块必须是不同成员",
                    per_section=by_sec)

    problems = []
    n_findings = 0
    n_open = 0
    n_blocked = 0
    n_rejected = 0
    for s in need:
        spec = spec_for(s)
        r = by_sec[s][0]
        if r.get("role") != spec["role"]:
            problems.append(f"{s} 的角色是 {r.get('role')!r}，"
                            f"应为 {spec['role']!r}")
        probes = r.get("probes") or []
        if len(probes) < len(spec["probes"]):
            problems.append(f"{s} 只答了 {len(probes)}/{len(spec['probes'])} 条探针")
        # 第 121 轮：pass 也得有成本 —— 「没发现问题」必须写清试过什么。
        # 否则「没找到」和「根本没查」不可区分（自证的最后一条缝）。
        for _p in probes:
            if _p.get("verdict") == "pass":
                _t = str(_p.get("tried") or "").strip()
                if len(_t) < 30:
                    problems.append(
                        f"{s} 的 pass 探针没写 tried（>=30 字，"
                        "说明查过哪里、看了什么）")
        found = [p for p in probes if p.get("verdict") == "finding"]
        n_findings += len(found)
        if found and not str(r.get("resolved") or "").strip():
            # 第 123 轮修：处置已**下沉到 finding 级**（`disposition`）。
            # 若每条 finding 都写了 disposition，就不再要求 review 级的
            # `resolved` —— 否则「明写 open」反而被判「没写怎么处理」，
            # 这是把新规矩套在旧判据上。实测 12 板 30 条 finding 全写了
            # disposition=open，却因为缺 review 级 resolved 被整体判死。
            if not all(str(p.get("disposition") or "").strip() for p in found):
                problems.append(
                    f"{s} 有 {len(found)} 条 finding 但没写怎么处理"
                    "（既没有 finding 级 disposition，也没有 review 级 resolved）")
        # 第 123 轮：finding 的**处置状态**必须可区分，且粒度是**一条 finding**。
        # 「未处理」三个字不是关闭（见 _disposition 的说明）；
        # 一条 review 里 4 条 finding 修了 1 条，其余 3 条仍然是 open。
        for p in found:
            _d = _finding_disp(p, r)
            if _d == "open":
                n_open += 1
            elif _d == "blocked":
                n_blocked += 1
                _why = str(p.get("blocked_reason")
                           or r.get("blocked_reason") or "").strip()
                if not _why:
                    problems.append(
                        f"{s} 有 finding 标 blocked 但没写 blocked_reason"
                        "（外部条件不具备时必须说明是哪一条，且要能被复核）")
                # 第 123 轮：blocked / rejected 是最容易被用来「清账」的两态，
                # 所以这两态额外要求 `falsifier` —— 说清「什么证据会推翻我」。
                # 一条 finding 如果讲不出自己的可证伪条件，它就不是可检验的主张。
                if not str(p.get("falsifier") or "").strip():
                    problems.append(
                        f"{s} 有 finding 标 blocked 但没写 falsifier"
                        "（什么证据会推翻这条？讲不出就不该被豁免）")
            elif _d == "rejected":
                n_rejected += 1
                _why = str(p.get("rejected_reason")
                           or r.get("rejected_reason") or "").strip()
                if not _why:
                    problems.append(
                        f"{s} 有 finding 标 rejected 但没写 rejected_reason"
                        "（驳回一条 finding 必须给可复核的反证，不能只说「不同意」）")
                if not str(p.get("falsifier") or "").strip():
                    problems.append(
                        f"{s} 有 finding 标 rejected 但没写 falsifier"
                        "（驳回也要说清：如果这条 finding 其实成立，什么会证明它）")
        # 第 119 轮：finding 必须带**落地的证据**（文件 + 逐字标记）。
        # 这些 finding 说的是工具的缺陷，修复也在工具里，所以证据应当是
        # 「哪个文件的哪段文字能看到这个修复」。编一条 finding 就必须先让
        # 那段代码真的存在 —— 造假成本高于照做，机制才成立。
        for p in found:
            w = str(p.get("where") or "").strip()
            ev = str(p.get("evidence") or "").strip()
            if not w or len(ev) < 3:
                problems.append(f"{s} 的 finding 缺 where/evidence")
                continue
            fp = os.path.join(HERE, w)
            if not os.path.exists(fp):
                problems.append(f"{s} 的 finding 指向不存在的文件：{w}")
                continue
            try:
                body = io.open(fp, encoding="utf-8", errors="replace").read()
            except Exception:                           # noqa: BLE001
                problems.append(f"{s} 的 finding 无法读取：{w}")
                continue
            if ev not in body:
                problems.append(f"{s} 的 evidence 在 {w} 里找不到：{ev[:20]}…")
    if problems:
        return dict(ok=False, level="FAIL",
                    detail="；".join(problems[:4]), per_section=by_sec)
    if n_open:
        return dict(ok=False, level="FAIL",
                    detail=(f"{len(need)} 板 {len(need)} 角色，{n_findings} 条 finding 里"
                            f" **{n_open} 条未处理（open）** —— finding 记了不等于关闭了。"
                            f"要么修正文/代码，要么标 blocked 并写 blocked_reason"
                            f"（外部条件不具备时）。line 逐条见 tools/audit_findings.py"),
                    per_section=by_sec)
    if n_findings == 0:
        return dict(ok=False, level="WARN",
                    detail=(f"论文 {len(need)} 个板块 "
                            f"{sum(len(spec_for(s)['probes']) for s in need)}"
                            " 条探针全部 pass —— 红队什么都没找到，通常是没认真打"),
                    per_section=by_sec)
    return dict(ok=True, level="PASS",
                detail=(f"{len(need)} 板 {len(need)} 角色（按 paper.tex 的"
                        f" \\section 一一对应），{n_findings} 条 finding："
                        f"{n_findings - n_open - n_blocked - n_rejected} 已修"
                        + (f"、{n_blocked} 条 blocked（已说明外部条件）"
                           if n_blocked else "")
                        + (f"、{n_rejected} 条 rejected（已给出反证）"
                           if n_rejected else "")
                        + "，0 条未处理"),
                per_section=by_sec)


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

    import tempfile

    def mk(reviews):
        td = tempfile.mkdtemp(prefix="rt_")
        json.dump(dict(reviews=reviews),
                  io.open(os.path.join(td, "redteam.json"), "w",
                          encoding="utf-8", newline="\n"),
                  ensure_ascii=False, indent=1)
        return td

    def good_reviews():
        out = []
        for s, spec in SPEC.items():
            probes = [dict(probe=p, verdict="pass", note="",
                             tried="查过了这一板对应的工件与代码：跑了该板的自检、看了相关实现，没有发现问题。") for p in spec["probes"]]
            probes[0] = dict(probe=spec["probes"][0], verdict="finding",
                             note="抓到一个",
                             # 第 123 轮：finding 没有 disposition 就是 open，
                             # 所以自检里的「已修」样本必须显式标 fixed。
                             disposition="fixed",
                             where="gate.py", evidence="NA_ABSENT")
            out.append(dict(section=s, role=spec["role"], probes=probes,
                            resolved="已修", verdict="revise"))
        return out

    ck("没有 redteam.json → FAIL", check(tempfile.mkdtemp())["level"] == "FAIL")
    rv = good_reviews()
    ck("完整 %d 板 %d 角色 → PASS" % (len(rv), len(rv)),
       check(mk(rv))["level"] == "PASS",
       check(mk(rv))["detail"][:40])
    ck("漏一板 → FAIL", check(mk(rv[:-1]))["level"] == "FAIL")
    ck("两块用同一角色 → FAIL",
       check(mk(rv[:-1] + [dict(rv[-1], role=rv[0]["role"])]))["level"] == "FAIL")
    short = [dict(r, probes=r["probes"][:1]) for r in rv]
    ck("探针没答全 → FAIL", check(mk(short))["level"] == "FAIL")
    # 第 123 轮：处置下沉到 finding 级，所以「未关闭」的构造必须**两处都空** ——
    # 只清 review 级 resolved 而留着 disposition=fixed，按新规矩那是「已修」，
    # 判 PASS 是对的。这条自检原来只清 resolved，改动后必破。
    nores = [dict(r, resolved="",
                  probes=[dict(p, disposition="") for p in r["probes"]])
             for r in rv]
    ck("两处处置都空 → FAIL", check(mk(nores))["level"] == "FAIL")
    allp = []
    for s, spec in SPEC.items():
        allp.append(dict(section=s, role=spec["role"],
                         probes=[dict(probe=p, verdict="pass",
                        tried="查过了这一板对应的工件与代码：跑了该板的自检、"
                        "看了相关实现，没有发现问题。")
                for p in spec["probes"]],
                         resolved="", verdict="pass"))
    ck("一条 finding 都没有 → WARN", check(mk(allp))["level"] == "WARN")

    # ── 第 123 轮：「未处理」不是关闭 ──
    # 原来 check() 只看 resolved 非空，于是写「未处理」三个字就能关掉一条
    # finding。实测 12 板 40 条 finding 大多正是这么写的，而 gate 报
    # 「40 条 finding 且均已关闭」。下面三条钉死这个行为。
    ck("disposition: 未处理 → open",
       _disposition(dict(resolved="未处理。四条 finding 正文一处未改")) == "open")
    ck("disposition: todo → open",
       _disposition(dict(resolved="TODO: later")) == "open")
    ck("disposition: 写清改了什么 → fixed",
       _disposition(dict(resolved="L1040 的 under six 改为 under seven")) == "fixed")
    ck("disposition: 显式 blocked → blocked",
       _disposition(dict(resolved="x", disposition="blocked")) == "blocked")
    # finding 级：没有 disposition 就是 open，不回落到 review 级。
    # 回落逻辑会把「整板说已修 A」推成「B 也修了」，实测误判 11 条。
    ck("finding 无 disposition → open（不回落 review 级）",
       _finding_disp({}, dict(resolved="已修 X")) == "open")
    ck("finding 显式 fixed → fixed",
       _finding_disp(dict(disposition="fixed"), {}) == "fixed")
    # 处置状态是 finding 级的，所以构造反例也必须改 finding 级
    # （只改 review 的 resolved 不够：finding 自己是 fixed 就不会判 open）。
    def _no_disp(rs):
        out = []
        for r in rs:
            r2 = dict(r)
            r2["probes"] = [{k: v for k, v in p.items()
                             if k != "disposition"}
                            for p in (r.get("probes") or [])]
            out.append(r2)
        return out

    openrv = [dict(r, resolved="未处理") for r in _no_disp(rv)]
    ck("有 finding 但 resolved 写「未处理」→ FAIL",
       check(mk(openrv))["level"] == "FAIL",
       check(mk(openrv))["detail"][:44])
    blockrv = []
    for r in rv:
        r2 = dict(r, resolved="x")
        r2["probes"] = [dict(p, disposition="blocked")
                        for p in (r.get("probes") or [])]
        blockrv.append(r2)
    ck("标 blocked 但没写 blocked_reason → FAIL",
       check(mk(blockrv))["level"] == "FAIL",
       check(mk(blockrv))["detail"][:44])

    # 第 123 轮：finding 可以被**驳回**（红队用错基准时会误判）。
    # 驳回门槛与 finding 一样高：必须给可复核的反证。
    ck("finding 显式 rejected → rejected",
       _finding_disp(dict(disposition="rejected"), {}) == "rejected")
    rej_bad = []
    for r in rv:
        r2 = dict(r, resolved="x")
        r2["probes"] = [dict(p, disposition="rejected")
                        for p in (r.get("probes") or [])]
        rej_bad.append(r2)
    ck("标 rejected 但没写 rejected_reason → FAIL",
       check(mk(rej_bad))["level"] == "FAIL",
       check(mk(rej_bad))["detail"][:44])
    rej_ok = []
    for r in rv:
        r2 = dict(r, resolved="x")
        r2["probes"] = [dict(p, disposition="rejected",
                             rejected_reason="反证：拿错基准",
                             falsifier="若该产物里出现被要求的内容，则驳回不成立")
                        for p in (r.get("probes") or [])]
        rej_ok.append(r2)
    ck("rejected 带反证 → PASS",
       check(mk(rej_ok))["level"] == "PASS",
       check(mk(rej_ok))["detail"][:52])

    # 第 123 轮：blocked / rejected 还必须说清「什么会推翻我」。
    # 这两态最容易被用来清账，而「讲不出可证伪条件」的主张不可检验。
    blk_nof = []
    for r in rv:
        r2 = dict(r, resolved="x")
        r2["probes"] = [dict(p, disposition="blocked",
                             blocked_reason="外部条件不具备")
                        for p in (r.get("probes") or [])]
        blk_nof.append(r2)
    ck("blocked 有理由但没写 falsifier → FAIL",
       check(mk(blk_nof))["level"] == "FAIL",
       check(mk(blk_nof))["detail"][:52])

    # ── 第 123 轮：板数跟着论文走，不许写死 ──
    # 规矩是「论文有几个板块就有几个审核」。若把它实现成写死 12 个，
    # 一篇 4 节的短文会被要求 12 份审核（过度），一篇 20 节的长文只会
    # 要求 7 份（漏审）。所以这条用最小论文钉死：4 / 12 / 20 节各测一遍，
    # 并测「加一节但没给审核 → 必须 FAIL」。
    def _mk_paper(td, titles):
        with io.open(os.path.join(td, "paper.tex"), "w",
                     encoding="utf-8", newline="\n") as fh:
            fh.write("\\begin{document}\n")
            for t in titles:
                fh.write("\\section{%s}\nbody text\n" % t)
            fh.write("\\end{document}\n")

    def _rev_for(titles):
        out = []
        for t in titles:
            key = section_key(t)
            spec = spec_for(key)
            out.append(dict(
                section=key, role=spec["role"],
                probes=[dict(probe=p, verdict="finding",
                             disposition="fixed",
                             where="redteam.py",
                             evidence="def paper_sections")
                        for p in spec["probes"]],
                resolved="已修", verdict="revise"))
        return out

    for n_sec in (4, 12, 20):
        td2 = tempfile.mkdtemp(prefix="rt_%02dsec_" % n_sec)
        titles = ["Part %d of the problem" % i for i in range(1, n_sec + 1)]
        _mk_paper(td2, titles)
        got = len(paper_sections(td2))
        ck("%2d 节论文 → 解析出 %2d 板" % (n_sec, n_sec), got == n_sec,
           "实际 %d" % got)
        json.dump(dict(reviews=_rev_for(titles)),
                  io.open(os.path.join(td2, "redteam.json"), "w",
                          encoding="utf-8", newline="\n"),
                  ensure_ascii=False, indent=1)
        r2 = check(td2)
        ck("%2d 节论文 + %2d 条审核 → PASS" % (n_sec, n_sec),
           r2["level"] == "PASS", r2["detail"][:46])
        # 加一节但不给审核 → 必须 FAIL（这就是「一一对应」）
        _mk_paper(td2, titles + ["One more part"])
        r3 = check(td2)
        ck("%2d 节论文 + %2d 条审核 → 缺 1 板必须 FAIL"
           % (n_sec + 1, n_sec), r3["level"] == "FAIL", r3["detail"][:46])

    print()
    print(f"{'ALL PASS' if bad == 0 else 'FAILED'}  {n - bad}/{n}")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "selftest":
        raise SystemExit(selftest())
    d = (sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] != "roster"
         else os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "out", "final"))
    # `python redteam.py roster [--json]`：这轮该建几个审核者。
    # 这是「论文有几个板块就有几个审核」的执行入口 —— 新会话先跑它，
    # 拿到名单再一个个建 agent，不要凭记忆建几个。
    if len(sys.argv) > 1 and sys.argv[1] == "roster":
        # 允许 `roster <figdir>`。第 123 轮修：原来忽略第二个参数，`d` 恒为
        # out/final，于是 `roster out/d2026c` 报「12 板齐、缺审核 0/12」，
        # 而 gate 报「没有 redteam.json」—— 两个工具看的是不同目录。
        # 同一份名单必须只有一处真相：给了目录就用它。
        _d = d
        for _a in sys.argv[2:]:
            if not _a.startswith("-"):
                _d = _a
                break
        rows = roster(_d)
        if "--json" in sys.argv:
            print(json.dumps(rows, ensure_ascii=False, indent=1))
        else:
            # 列宽必须自适应：第 123 轮实测，`problem-3-what-contestant-and-partner-ch-auditor`
            # 有 48 字符，而原来写死 `{'角色':<26}`，超长部分挤进「探针」列，
            # 读起来像 `memo-to-the-producersmemo-to-the-producers` 这种重复。
            # 那是排版溢出，不是数据重复 —— 但看日志的人会当成 bug 去查。
            _w1 = max([3] + [len(str(x["section"])) for x in rows])
            _w2 = max([4] + [len(str(x["role"])) for x in rows])
            print(f"  论文 {len(rows)} 个板块 → 需要 {len(rows)} 个独立审核者"
                  f"（一一对应：几板几审，不是固定数字）")
            print(f"  {'#':<3}{'板块':<{_w1 + 2}}{'角色':<{_w2 + 2}}探针  已交  标题")
            for x in rows:
                print(f"  {x['index']:<3}{x['section']:<{_w1 + 2}}"
                      f"{x['role']:<{_w2 + 2}}"
                      f"{x['n_probes']:<5}"
                      f"{'有' if x['has_review'] else '**缺**':<6}"
                      f"{x['title'][:40]}")
            lack = [x['section'] for x in rows if not x['has_review']]
            print()
            print(f"  缺审核：{len(lack)}/{len(rows)}"
                  + (f"  → {', '.join(lack)}" if lack else "  （齐）"))
        raise SystemExit(0)
    r = check(d)
    print(f"  [{r['level']}] {r['detail']}")
    for s, spec in SPEC.items():
        got = r["per_section"].get(s)
        if got:
            g = got[0]
            print(f"    {s:<16} {g.get('role'):<26} "
                  f"{len(g.get('probes') or [])} 条探针")
