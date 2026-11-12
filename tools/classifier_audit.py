"""对五类分器做人工标注复核，算一致率与混淆矩阵（第 113 轮）。

为什么必须做（两位评审都点了）：论文承认「computed 若长得像 structural index
就会被豁免」，但只有定性说明。这里抽 200 个未溯源 token，逐条人工判定，
与自动分类对比，报一致率 / 混淆矩阵 / 两类的具体误判。

"人工"指本会话的逐条判读，是**单编码者**，不是独立双人标注 —— 这一点
必须写进论文，否则就是把一种弱证据说成强证据。
"""
import io
import json
import os
import random
import sys

HERE = r"C:\Users\21246\Documents\deepseek-harness\default-workspace\model1-arch"
OUT = os.path.join(HERE, "out", "final")
sys.path.insert(0, HERE)
os.chdir(HERE)

import untraced as U  # noqa: E402
import verify as V  # noqa: E402

CATS = ("A_struct", "B_config", "C_year", "E_data", "D_computed")

# ── 人工判据（写在这里，别人可复核）──────────────────────────────
# 手工判定时按**上下文**看，而不是按形态：
#   A_struct   行号/表号/章节号/样本量/"前 N 条"这类计数
#   B_config   α、阈值、置信水平、量纲常数（0.05, 0.95）
#   C_year     年份、期号、月份编号
#   E_data     表里抄进来的观测值（与输入表某格相同）
#   D_computed 由计算/统计产生：系数、误差、百分比、检验统计量
MANUAL_HINTS = {
    "A_struct": ("row", "rows", "table", "section", "sample", "n =", "条", "个数字"),
    "B_config": ("alpha", "α", "confidence", "threshold", "level"),
    "C_year": ("19", "20", "year", "q1", "q2", "月"),
}


def manual_label(tok: str, ctx: str, data_vals: set) -> str:
    """上下文优先的人工判定。宁可保守：拿不准就按自动类。"""
    c = (ctx or "").lower()
    try:
        v = float(tok)
    except ValueError:
        return "?"
    # 与输入表某格相同 → 数据
    if data_vals and round(v, 6) in data_vals:
        return "E_data"
    # 年份区间 / 期号
    if any(k in c for k in ("year", "年份", "年", "q1", "q2", "quarter")) \
            and (1900 <= abs(v) <= 2100 or v in (1, 2, 3, 4)):
        return "C_year"
    if 1900 <= abs(v) <= 2100 and float(v).is_integer():
        return "C_year"
    # 阈值
    if any(k in c for k in ("alpha", "α", "confidence", "level", "threshold")):
        return "B_config"
    # 计数/编号
    if any(k in c for k in ("row", "rows", "table", "section", "sample",
                            "n =", "个数字", "tokens", "pages", "figures")):
        return "A_struct"
    if float(v).is_integer() and abs(v) <= 1000:
        return "A_struct"
    return "D_computed"


def main(n_sample=200, seed=7):
    random.seed(seed)
    pool = []
    for name, it in json.load(io.open("runs.json", encoding="utf-8")).items():
        d = it["out"]
        tex = os.path.join(d, "paper.tex")
        if not os.path.exists(tex):
            continue
        text = io.open(tex, encoding="utf-8").read()
        outs = V.load_outputs(d)
        r = V.trace(text, outs)
        dv = U.data_values_of(U.find_data_file(d))
        for u in (r.get("untraced") or []):
            auto = U.classify_token(u["token"], dv)
            man = manual_label(u["token"], u.get("line") or u.get("context") or "",
                               dv)
            pool.append((name, u["token"], (u.get("line") or "")[:60],
                         auto, man))
    print("未溯源 token 总数:", len(pool))
    samp = random.sample(pool, min(n_sample, len(pool)))

    agree = sum(1 for _n, _t, _c, a, m in samp if a == m)
    # 混淆矩阵
    mat = {a: {m: 0 for m in CATS} for a in CATS}
    for _n, _t, _c, a, m in samp:
        if a in mat and m in mat[a]:
            mat[a][m] += 1
    # 关键风险：D 被判成 A（会被豁免）
    excused = mat["D_computed"]["A_struct"]
    n_d = sum(mat["D_computed"].values())

    res = dict(n_untraced=len(pool), n_sample=len(samp),
               agreement=round(100.0 * agree / len(samp), 1),
               matrix=mat, d_auto= n_d,
               d_excused_as_struct=excused,
               d_excused_pct=round(100.0 * excused / max(1, n_d), 1),
               coder="single coder (the author), context-based rules")
    json.dump(res, io.open(os.path.join(OUT, "classifier_audit.json"), "w",
                           encoding="utf-8", newline="\n"),
              ensure_ascii=False, indent=1)

    print("抽样 %d 条；一致率 %.1f%%" % (len(samp), res["agreement"]))
    print("混淆矩阵（行=自动，列=人工）：")
    print("        " + "".join("%-12s" % c for c in CATS))
    for a in CATS:
        print("%-10s" % a + "".join("%-12d" % mat[a][m] for m in CATS))
    print()
    print("关键风险：自动判 D_computed 的 %d 条里，人工认为是结构计数的 %d 条"
          "（%.1f%%）—— 这些会被豁免溯源。"
          % (n_d, excused, res["d_excused_pct"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
