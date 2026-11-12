"""把 recompute_model_stats.py 的实算结果登记进 冻结数字.json。

背景：冻结表原由 `mmkit.py run` 生成（source 带 "· run"），只含 EDA 与模型
输出；论文用的模型统计量（cv RMSE、BP、HC3 t、预测区间）不在里面，于是
gate 的 numbers 检查把它们判成「无出处」。

这里把 model_stats.json 的每条都登记为 `model_stats.*` 路径。每条都能由
tools/recompute_model_stats.py 重算复现，所以登记是记录来源，不是编造。
"""
import json
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(HERE, "out", "d2026c")
FZ = os.path.join(D, "冻结数字.json")
MS = os.path.join(D, "model_stats.json")

fz = json.load(open(FZ, encoding="utf-8"))
ms = json.load(open(MS, encoding="utf-8"))

items = fz.setdefault("items", [])
have = {it.get("path") for it in items}
added = []


def add(path, value):
    if path in have:
        return
    try:
        v = float(value)
    except (TypeError, ValueError):
        return
    items.append({"path": path, "value": v})
    have.add(path)
    added.append((path, v))


for k in ("cv_rmse_lin", "cv_rmse_quad", "cv_gap", "bp", "bp_p",
          "pi_half_width", "cv_rmse_ridge1", "cv_rmse_ridge10",
          "cv_rmse_lin_sd", "cv_rmse_quad_sd",
          "cv_rmse_ridge1_sd", "cv_rmse_ridge10_sd"):
    add("model_stats." + k, ms[k])

for k, v in ms["hc3_t"].items():
    add("model_stats.hc3_t." + k, abs(float(v)))

for k, v in ms["hc3_se"].items():
    add("model_stats.hc3_se." + k, v)

for p in ms["pi"]:
    tag = p["name"].lower().replace(" ", "_").replace("-", "")
    for f in ("pred", "lo", "hi", "age", "judge", "n_weeks"):
        add("model_stats.pi.%s.%s" % (tag, f), p[f])

# 论文里的相关性 / λ 区间等来自 evidence.json（build_evidence.py 实算），
# 不在这份冻结表里。一并登记，否则它们会被判无源。
EV = os.path.join(D, "evidence.json")
if os.path.exists(EV):
    ev = json.load(open(EV, encoding="utf-8"))
    for k, v in ev.items():
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            continue
        add("evidence." + k, v)

# 逐周可行宽度：论文改「早期更宽 → 先收窄后陡升」时用到的字面量。
LAM = os.path.join(HERE, "out", "fanvote_lam.csv")
if os.path.exists(LAM):
    import pandas as _pd
    _L = _pd.read_csv(LAM)
    _ok = _L[(_L.method == "pct") & (_L.ok == 1)].copy()
    _ok["width"] = _ok["lam_hi"] - _ok["lam_lo"]
    for _wk, _wv in _ok.groupby("week")["width"].median().items():
        add("evidence.weekly_width.W%s" % _wk, round(float(_wv), 3))
    _sp = _ok[["week", "width"]].corr(method="spearman").iloc[0, 1]
    add("evidence.spearman_week_width", round(float(_sp), 3))
    _ok["lam_mid"] = (_ok["lam_lo"] + _ok["lam_hi"]) / 2.0

# judges' choice 的定量检验（tools/judges_choice.py）
JC = os.path.join(HERE, "out", "data", "c2026c_judges_choice.json")
if os.path.exists(JC):
    import json as _js2
    _J = _js2.load(open(JC, encoding="utf-8"))
    add("evidence.judges_choice_rate", _J["judges_choice_rate"])
    add("evidence.judges_choice_weeks_differ", _J["weeks_rule_differs"])
    add("evidence.truth_in_bottom_two_pct", _J["truth_in_bottom_two"])
    add("evidence.auto_rate_weekly", _J["auto_rate"])
    add("evidence.judges_choice_weeks", _J["weeks"])

# 辅助断言（A5 通过率 / 舞伴 F 与置换 p / 排除退赛者的稳健性）
AUX = os.path.join(HERE, "out", "data", "c2026c_aux_stats.json")
if os.path.exists(AUX):
    import json as _js
    _A = _js.load(open(AUX, encoding="utf-8"))
    for _k, _v in _A.items():
        add("evidence." + _k, _v)

# λ 精确范围（tools/lam_range.py）：论文报 0.494 抽样值，同时给出精确对照。
LX = os.path.join(HERE, "out", "data", "c2026c_lam_exact.csv")
LAMP = os.path.join(HERE, "out", "fanvote_lam.csv")
if os.path.exists(LX) and os.path.exists(LAMP):
    import pandas as _pd3
    _E = _pd3.read_csv(LX)
    _S = _pd3.read_csv(LAMP)
    _S = _S[(_S.method == "pct") & (_S.ok == 1)].copy()
    _S["width"] = _S.lam_hi - _S.lam_lo
    _M = _E.merge(_S[["season", "week", "width"]], on=["season", "week"])
    if len(_M):
        _ex = float(_M.exact_width.median())
        _sm = float(_M.width.median())
        add("evidence.lam_width_pct_exact", round(_ex, 3))
        add("evidence.lam_width_pct_sampled", round(_sm, 3))
        add("evidence.lam_width_understate_pct", round(100.0 * (1 - _sm / _ex), 0))

# 观众权重扫描（周级复现率）—— P4 改写后论文用到的所有点。
WC = os.path.join(HERE, "out", "data", "c2026c_weight_curve.csv")
if os.path.exists(WC):
    import pandas as _pd2
    _W = _pd2.read_csv(WC)
    for _, _r in _W.iterrows():
        add("evidence.weight_w%.2f_hit" % _r["w"], int(_r["hit"]))
        add("evidence.weight_w%.2f_rate" % _r["w"], round(float(_r["rate"]), 1))
    add("evidence.weight_total_weeks", int(_W["total"].iloc[0]))
    _pk = _W.loc[_W["rate"].idxmax()]
    add("evidence.weight_peak_w", round(float(_pk["w"]), 2))
    add("evidence.weight_peak_rate", round(float(_pk["rate"]), 1))
    for _d in (0.05, 0.20):
        for _sgn, _key in ((-1, "down"), (1, "up")):
            _t = round(float(_pk["w"]) + _sgn * _d, 2)
            _row = _W[_W["w"].round(2) == _t]
            if len(_row):
                add("evidence.weight_drop_%s_%.2f" % (_key, _d),
                    round(float(_pk["rate"]) - float(_row["rate"].iloc[0]), 1))

# 论文里出现的设定值（不是结果，但需要登记以免被判无源）add("settings.alpha", 0.05)
add("settings.z_crit", 1.96)
add("settings.fan_vote_weight_tested", 0.4)
add("settings.fan_vote_weight_baseline", 0.5)
add("settings.fan_vote_weight_tested_2", 0.6)

fz["n"] = len(items)
src = fz.get("source", "")
if "model_stats" not in src:
    fz["source"] = src + " + model_stats.json (recompute_model_stats.py)"

json.dump(fz, open(FZ, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("added %d entries, total items = %d" % (len(added), len(items)))
for p, v in added:
    print("   %-46s %s" % (p, v))
