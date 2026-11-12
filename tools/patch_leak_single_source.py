"""第 5 轮：把泄漏判定下沉到 mm.py（单一定义处），并让 mm.fit 带出结论。

动机：
  泄漏判定原先只存在于 gate.py（事后检查）。配置写错时，要等到出稿、
  跑 gate 才知道。治因的做法是在**建模入口**就算一次，结论跟着结果走，
  让任何调用方（mmkit、paper、gate）看到同一份判断。

  同时把 gate 里的 _is_time_like / _is_lag_pair 改成委托 mm.*，
  避免两份实现各改各的、慢慢漂移（这种事本轮已经遇到过一次）。
"""
import io
import sys

HERE = r"C:\Users\21246\Documents\deepseek-harness\default-workspace\model1-arch"
MM = HERE + r"\mm.py"
GATE = HERE + r"\gate.py"

HELPERS = '''# ══════════════════════════════════════════════════════════════════════
#  泄漏判定：单一定义处（gate.py 委托这里，不再各写一份）
# ══════════════════════════════════════════════════════════════════════
# 名字像时间 / 序号列？保守识别，认不出就当「不是」，宁可多报一条假警。
# 不能拿「年」「月」「日」做裸字包含 —— 「年龄」含「年」但不是时间轴，
# 实测把 age 判成时间列后，一条真的「年龄→目标」高相关被静默放过。
_TIME_COMPOUND = ("年份", "月份", "日期", "年度", "季度", "周次", "期数",
                  "时间", "编号", "序号")
_TIME_EN = ("year", "month", "date", "time", "period", "index", "week",
            "quarter")

LEAK_THRESHOLD = 0.95


def is_time_like(name) -> bool:
    """是不是时间轴 / 序号轴。"""
    if not name:
        return False
    s = str(name).strip().lower()
    if re.fullmatch(r"(19|20)\\d{2}", s):
        return True
    if re.fullmatch(r"(19|20)\\d{2}\\s*[-\\u2013\\u2014~]\\s*(19|20)\\d{2}", s):
        return True
    if any(w in s for w in _TIME_COMPOUND):
        return True
    return any(re.search(r"\\b%s\\b" % w, s) for w in _TIME_EN)


def is_lag_pair(a, b) -> bool:
    """两列是不是同一序列的不同期（滞后自变量）。

    pop2000 → pop2005 用上一期同口径值预测下一期，是人口/存量类问题的标准做法，
    不是泄漏；而 total_votes → helpful_votes 虽然也高度相关，却是包含关系。
    判据：去掉结尾数字后主干相同、数字部分不同。
    """
    def stem(s):
        t = str(s or "").strip().lower()
        m = re.match(r"^(.*?)[\\s_\\-]*(\\d+)$", t)
        if not m:
            return t, None
        return re.sub(r"[\\s_\\-]+$", "", m.group(1)), m.group(2)

    sa, na = stem(a)
    sb, nb = stem(b)
    if not sa or sa != sb or len(sa) < 2:
        return False
    return na is not None and nb is not None and na != nb


def suspect_leak(ds, yname, xnames=None, thr: float = LEAK_THRESHOLD):
    """检查 x 里有没有「响应的另一份 / 组成部分」。

    返回 [(列名, 相关系数, 类别)]，类别：
      "time" —— 时间/序号列与趋势共变（正当建模，不是泄漏）
      "lag"  —— 同一序列的滞后项（持续性模型，不是泄漏）
      "leak" —— 其余高度相关（拿响应或其组成部分冒充自变量）

    逐个检查**所有**超阈值的列，不只最相关那一个：只看最大值时，
    一个正当的滞后项（相关 1.000）会把后面真正的泄漏掩盖掉。
    """
    yv = np.asarray(ds.col(yname), dtype=float)
    if xnames is None:
        xnames = [c for c in ds.num_names
                  if c != yname and "编号" not in c]
    out = []
    for c in xnames:
        if c == yname or c not in ds.num_names:
            continue
        xv = np.asarray(ds.col(c), dtype=float)
        if xv.std() == 0 or yv.std() == 0:
            continue
        try:
            cc = float(np.corrcoef(xv, yv)[0, 1])
        except Exception:                           # noqa: BLE001
            continue
        if not (cc == cc) or abs(cc) <= thr:        # NaN 或未超阈值
            continue
        if is_time_like(c) or is_time_like(yname):
            kind = "time"
        elif is_lag_pair(c, yname):
            kind = "lag"
        else:
            kind = "leak"
        out.append((c, cc, kind))
    out.sort(key=lambda t: -abs(t[1]))
    return out


'''

FIT_OLD = '''    baseline_rmse = float(np.std(y))
    return dict(y=yname, x=xnames, cands=rows, best=best, linear=base,
                cond_linear=cond, n=len(y),
                baseline_rmse=baseline_rmse,
                baseline_kind="intercept-only (mean predictor)")'''

FIT_NEW = '''    baseline_rmse = float(np.std(y))
    # 建模入口就算一次泄漏：配置写错时在这里就能看见，不必等出稿后跑 gate。
    leak = suspect_leak(ds, yname, xnames)
    _bad = [t for t in leak if t[2] == "leak"]
    if _bad:
        print("   [泄漏] 自变量里有响应的组成部分：")
        for c, cc, _ in _bad:
            print("     · %s 与 %s 相关 %+0.3f" % (c, yname, cc))
        print("     → 删掉这些列后重跑；它们的系数没有解释意义。")
    return dict(y=yname, x=xnames, cands=rows, best=best, linear=base,
                cond_linear=cond, n=len(y),
                baseline_rmse=baseline_rmse,
                baseline_kind="intercept-only (mean predictor)",
                leak_suspects=leak,
                leak_bad=[c for c, _, _ in _bad])'''

GATE_TIME_OLD = '''    if not name:
        return False
    s = str(name).strip().lower()
    # 纯四位年份（1953 / 2005）与年份区间（1965-1970）
    if re.fullmatch(r"(19|20)\\d{2}", s):
        return True
    if re.fullmatch(r"(19|20)\\d{2}\\s*[-\\u2013\\u2014~]\\s*(19|20)\\d{2}", s):
        return True
    if any(w in s for w in _TIME_COMPOUND):
        return True
    # 英文按词边界，避免 "index" 命中 "superindex" 之类
    return any(re.search(r"\\b%s\\b" % w, s) for w in _TIME_EN)'''

GATE_TIME_NEW = '''    import mm
    return mm.is_time_like(name)'''


def main():
    mm_src = io.open(MM, encoding="utf-8").read()
    gate_src = io.open(GATE, encoding="utf-8").read()
    changed = []

    # 1) mm.py 插入单一定义处
    anchor = "def fit(ds: DS, yname: str, xnames: list[str]) -> dict:"
    if "def suspect_leak(" in mm_src:
        print("SKIP mm helpers: already present")
    elif anchor not in mm_src:
        print("FAIL: mm.fit anchor not found")
        return 2
    else:
        mm_src = mm_src.replace(anchor, HELPERS + anchor, 1)
        changed.append("mm helpers inserted")

    # 2) mm.fit 带出结论
    if "leak_suspects" in mm_src:
        print("SKIP mm.fit: already carries leak_suspects")
    elif FIT_OLD not in mm_src:
        print("FAIL: mm.fit return block not matched")
        return 3
    else:
        mm_src = mm_src.replace(FIT_OLD, FIT_NEW, 1)
        changed.append("mm.fit carries leak_suspects")

    # 3) gate 委托 mm
    if "import mm\n    return mm.is_time_like(name)" in gate_src:
        print("SKIP gate _is_time_like: already delegates")
    elif GATE_TIME_OLD not in gate_src:
        print("FAIL: gate _is_time_like body not matched")
        return 4
    else:
        gate_src = gate_src.replace(GATE_TIME_OLD, GATE_TIME_NEW, 1)
        changed.append("gate _is_time_like delegates to mm")

    for path, src, tag in ((MM, mm_src, "mm.py"), (GATE, gate_src, "gate.py")):
        if src != io.open(path, encoding="utf-8").read():
            io.open(path, "w", encoding="utf-8", newline="\n").write(src)
            print("written %s" % tag)
    for c in changed:
        print("OK %s" % c)
    return 0


if __name__ == "__main__":
    sys.exit(main())
