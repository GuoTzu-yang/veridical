"""跨段一致性检查：找出「说同一件事、但数字不同」的句子对。

为什么需要它：gate 的 numbers 只查「每个数有没有出处」，不查「同一结论在两处
是否是同一个数」。实测风险：正文写 83.5%、表格写 83.4%，两个都可能各有出处，
numbers 会全部放行。

方法：按句切分 -> 去 LaTeX 命令与停用词 -> 对每对句子算实词 Jaccard 相似度
-> 相似度高于阈值且两侧数字集合不同时报告。相似度高意味着在讲同一件事。

用法：
    python chk_cross.py out/d2026c/paper.tex
    python chk_cross.py out/d2026c/paper.tex --json
"""
import argparse
import itertools
import json
import re
import sys

STOP = set("""a an the of to in on for and or but as at by with from is are was were be been
this that these those it its we our us they their them not no than then which who whom whose
when where while if so such can could may might must shall should will would do does did
have has had one two three four both each any all more most less least very only also such
thus hence therefore however although because since given under over between among within
across per via using used use show shows shown report reports reported find finds found
table figure section appendix eq equation eqref ref cite textbf emph label""".split())

NUM = re.compile(r"-?\d+(?:\.\d+)?")
WORD = re.compile(r"[A-Za-z][A-Za-z\-]{3,}")
# 句中的人名/机构名等多词专有实体。两句若指向不同实体（不同选手、不同数据集），
# 数字不同是正常的，不该算冲突。
ENT = re.compile(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b")


def strip_latex(t):
    t = re.sub(r"(?<!\\)%.*$", "", t, flags=re.M)          # 注释
    t = re.sub(r"\\[a-zA-Z]+\*?(\[[^\]]*\])?(\{[^{}]*\})?", " ", t)
    t = re.sub(r"[{}$&\\_^~]", " ", t)
    return t


def sentences(t):
    t = strip_latex(t)
    t = re.sub(r"\s+", " ", t)
    parts = re.split(r"(?<=[.;:])\s+", t)
    return [p.strip() for p in parts if len(p.strip()) > 40]


def words(s):
    return {w.lower() for w in WORD.findall(s)} - STOP


def nums(s):
    return {float(x) for x in NUM.findall(s)}


def _same_measure(ni, nj, pool_all, tol=0.01):
    """两个数字集是否可能只是同一量的两种表示（计数 vs 百分比）。

    实测踩到：正文写「in all 136 weeks where the rules disagree」，结论段写
    「in 70.5% of weeks」，两处说的是同一件事（136/193 = 70.5%）。这不是矛盾，
    只是表述不同。判据：存在 a∈ni, b∈nj, m∈全文数字 使 |a*100 - b*m| 的相对
    误差 < tol。分母 m 必须取自全文 —— 它（193）通常不与 a、b 同时出现。
    """
    for a in ni:
        for b in nj:
            for m in pool_all:
                if m <= 0 or m == a or m == b:
                    continue
                if abs(a * 100.0 - b * m) / max(1.0, abs(a * 100.0)) < tol:
                    return True
    return False


def check(tex, thresh=0.5, min_shared=5, min_gap=5):
    sents = sentences(tex)
    pool_all = {float(x) for x in NUM.findall(strip_latex(tex))}
    bag = [(i, s, words(s), nums(s)) for i, s in enumerate(sents)]
    bag = [b for b in bag if len(b[2]) >= min_shared and b[3]]
    hits = []
    for (i, si, wi, ni), (j, sj, wj, nj) in itertools.combinations(bag, 2):
        inter = wi & wj
        if len(inter) < min_shared:
            continue
        # 「跨段」的前提是有距离。实测踩到：falsify 会生成一批相邻的模板句
        # （「For variable, the clearest violation is x with local correlation …」，
        # x 是未替换的占位符），每句对应不同变量，数字自然不同。
        # 它们是枚举，不是矛盾。相邻句一律不看。
        if abs(i - j) < min_gap:
            continue
        jac = len(inter) / len(wi | wj)
        if jac < thresh:
            continue
        # 不同实体（不同选手/数据集/机构）→ 是并列案例，不是同一结论
        ea = set(ENT.findall(si))
        eb = set(ENT.findall(sj))
        if ea and eb and ea != eb:
            continue
        # 只关心「两边都有数字、集合不同、且互不包含」的情况。
        # 互不包含这一条能排除两类常见误报：
        #   ① 一方信息更全（如 B 同时给出 136/193 与 29.5/57/193）
        #   ② 互补表述（57 与 136 相加为 193）
        if ni and nj and ni != nj and not (ni <= nj or nj <= ni):
            if _same_measure(ni, nj, pool_all):
                continue
            hits.append(dict(
                i=i, j=j, jaccard=round(jac, 3),
                shared=sorted(inter)[:8],
                nums_a=sorted(ni), nums_b=sorted(nj),
                a=si[:160], b=sj[:160],
            ))
    hits.sort(key=lambda h: -h["jaccard"])
    return hits, len(sents)


def selftest() -> int:
    """区分度自检：能抓真冲突，不误伤相邻枚举与同值重复。"""
    good = ("The percentage rule reproduces the observed elimination "
            "in 83.5 of 231 season-weeks.")
    bad = good.replace("83.5", "84.2")
    fill = [
        "Some filler sentence about audience vote and judge score and placement here.",
        "Another filler sentence about the feasibility set and its width here.",
        "A third filler about reconstruction and constraints and shares here.",
        "A fourth filler about cross validation and residual scale here.",
        "A fifth filler about champion agreement and weight sensitivity here.",
        "A sixth filler about residual diagnostics and heteroscedasticity here.",
    ]
    ok = True

    def ck(name, cond, detail=""):
        nonlocal ok
        ok = ok and cond
        print("  [%s] %s %s" % ("PASS" if cond else "FAIL", name, detail))

    h, _ = check(" ".join([good] + fill + [bad]))
    ck("相隔远且值不同 -> 检出", len(h) == 1, "%d 处" % len(h))
    h, _ = check(" ".join([good] + fill + [good]))
    ck("同值重复 -> 不报", len(h) == 0, "%d 处" % len(h))
    h, _ = check(" ".join([good, bad] + fill))
    ck("相邻枚举 -> 不报", len(h) == 0, "%d 处" % len(h))
    h, _ = check(" ".join([good] + fill + ["an unrelated line about the weather"]))
    ck("无共享实词 -> 不报", len(h) == 0, "%d 处" % len(h))
    print("\n%s" % ("ALL PASS" if ok else "FAILED"))
    return 0 if ok else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description="跨段一致性检查")
    ap.add_argument("paper")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--thresh", type=float, default=0.5)
    ap.add_argument("--min-shared", type=int, default=5)
    ap.add_argument("--min-gap", type=int, default=5,
                    help="两句至少相隔多少句才算「跨段」")
    a = ap.parse_args(argv)

    if a.paper == "selftest":
        return selftest()

    tex = open(a.paper, encoding="utf-8").read()
    hits, n = check(tex, a.thresh, a.min_shared, a.min_gap)

    if a.json:
        print(json.dumps(dict(n_sentences=n, n_conflicts=len(hits),
                              conflicts=hits), ensure_ascii=False, indent=2))
        return 0 if not hits else 1

    print("跨段一致性：%d 句，%d 处疑似冲突" % (n, len(hits)))
    for h in hits:
        print("\n  [%.2f] 共享实词 %s" % (h["jaccard"], ", ".join(h["shared"])))
        print("    A(%d) %s" % (h["i"], h["a"]))
        print("    B(%d) %s" % (h["j"], h["b"]))
        print("    数字 A=%s  B=%s" % (h["nums_a"], h["nums_b"]))
    return 0 if not hits else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
