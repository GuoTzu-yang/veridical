"""gate.chk_falsify 第 3 轮：放宽列数门槛 + 承认语句报出节名。

两件事：
  1. `len(cols) < 4` 是「前 3 列当 x、后 2 列当 y」盲测时代留下的门槛。
     现在用论文声明的 y/x，只需 y + 至少一个 x，门槛降到 2。
     但不能只改数字：没有第三个数值列时 `signs` 为空，原代码会走到
     「控制后符号一致」那条 PASS —— 明明没做控制，却说控制后一致。
     所以新增 uncontrolled 计数，如实报「无数值列可作对照」。

  2. 承认语句不要判「必须在 Limitations 节」：实测模板论文和 d2026c 都没有
     叫 Limitations 的节（承认写在 Evaluation / What each claim rests on），
     按标题硬判会把 20 篇合格论文打成 WARN。改为**报出证据所在节名**，
     让人能核对，而不是假装能判断位置是否恰当。
"""
import io
import sys

P = r"C:\Users\21246\Documents\deepseek-harness\default-workspace\model1-arch\gate.py"

HELPER_ANCHOR = '''def _is_time_like(name):
    """判断某列是不是时间轴 / 序号轴。'''

HELPER = '''_ADMIT_PATS = (r"fail(s|ed)?\\s+locally",
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
             for m in re.finditer(r"\\\\section\\{([^{}]*)\\}", s)]
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


'''

OLD_GUARD = '''        if len(cols) < 4:
            return _r("falsify", SOFT, "N/A", "数值列不足 4 个")'''
NEW_GUARD = '''        # 门槛从 4 降到 2：旧门槛是「前 3 列当 x、后 2 列当 y」时代留下的。
        # 现在用论文声明的 y/x，只需 y + 至少一个 x。
        if len(cols) < 2:
            return _r("falsify", SOFT, "N/A", "数值列不足 2 个")'''

OLD_CTR = '''        marginal = 0
        real = []'''
NEW_CTR = '''        marginal = 0
        real = []
        uncontrolled = 0'''

OLD_CTRL = '''                if signs and all(s < 0 for s in signs):
                    continue        # 控制后符号一致 → 反例来自混淆
                if signs:
                    real.append(f"{x[:6]}→{y[:6]}")'''
NEW_CTRL = '''                if not others:
                    # 没有第三个数值列可控制：既不能把反例归因于混淆，
                    # 也不能就此放行。单独计数，最后如实报「未做对照」。
                    uncontrolled += 1
                    continue
                if signs and all(s < 0 for s in signs):
                    continue        # 控制后符号一致 → 反例来自混淆
                if signs:
                    real.append(f"{x[:6]}→{y[:6]}")'''

OLD_ADM = '''        _admits = False
        try:
            # 这个函数签名里只有 figdir，没有 tex；写 open(tex) 会
            # NameError，被 except 吞掉，_admits 永远是 False。
            _tp = os.path.join(figdir, "paper.tex")
            _tt = open(_tp, encoding="utf-8").read()
            # 关键词匹配，不是语义理解：论文用什么话承认「局部非单调」
            # 无法穷举。用正则而不是字面子串，因为字面匹配已经误判过一次：
            # d2026c 原文写的是「hold on average but fail locally」，
            # 而关键词写成 "fails locally"（多一个 s）→ 判成「没承认」。
            _pats = (r"fail(s|ed)?\\s+locally",
                     r"no claim of monotonic",
                     r"[Nn]ot monoton|[Nn]on-?monoton",
                     r"local reversal",
                     r"局部非单调", r"非单调", r"局部反例")
            _admits = any(re.search(_p, _tt) for _p in _pats)
        except Exception:                   # noqa: BLE001
            _admits = False
        if real and _admits:
            return _r("falsify", SOFT, "PASS",
                      f"{len(real)} 组局部非单调，论文局限节已承认" + _tag)
        if real:
            return _r("falsify", SOFT, "WARN",
                      f"{len(real)} 组边际反例且控制后符号仍矛盾："
                      + "、".join(real[:3]) + _tag)
        if marginal:
            return _r("falsify", SOFT, "PASS",
                      f"{marginal} 组边际反例，但控制后符号一致"
                      f"（来自混淆，非真非单调）" + _tag)'''

NEW_ADM = '''        _admits, _sec = _admission(os.path.join(figdir, "paper.tex"))
        _where = ("论文「%s」节已承认" % _sec) if _admits else ""
        _unc = ("，另有 %d 组无数值列可对照" % uncontrolled) if uncontrolled else ""
        if real and _admits:
            return _r("falsify", SOFT, "PASS",
                      f"{len(real)} 组局部非单调，{_where}{_unc}" + _tag)
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
                      f"（来自混淆，非真非单调）" + _tag)'''


def main():
    src = io.open(P, encoding="utf-8").read()
    orig = src
    if "_admission(" in src:
        print("SKIP helper: already present")
    elif HELPER_ANCHOR not in src:
        print("FAIL: helper anchor not found")
        return 2
    else:
        src = src.replace(HELPER_ANCHOR, HELPER + HELPER_ANCHOR, 1)
        print("OK helper inserted")
    for name, old, new in (("列数门槛", OLD_GUARD, NEW_GUARD),
                           ("计数器", OLD_CTR, NEW_CTR),
                           ("无对照分支", OLD_CTRL, NEW_CTRL),
                           ("承认与结论", OLD_ADM, NEW_ADM)):
        if old not in src:
            print("FAIL: %s 锚点未命中" % name)
            return 3
        src = src.replace(old, new, 1)
        print("OK %s" % name)
    if src == orig:
        print("NO CHANGE")
        return 0
    io.open(P, "w", encoding="utf-8", newline="\n").write(src)
    print("written %s" % P)
    return 0


if __name__ == "__main__":
    sys.exit(main())
