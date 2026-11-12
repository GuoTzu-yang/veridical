"""剖析（修正版）：用 verify.trace 的**完整**未溯源集合，不再解析截断的打印输出。

红队 F1 的教训：上一版解析 `verify.py` 的 stdout，而它只打印前 15 条，
于是「199 个未溯源」其实是「打印出来的那 199 条」，全量是 1,293。
分母被截断，整个「只有 33 个是真缺陷」的结论就建立在 15% 的样本上。
"""
import io
import json
import os
import re
import sys

HERE = r"C:\Users\21246\Documents\deepseek-harness\default-workspace\model1-arch"
OUT = os.path.join(HERE, "out", "final")
sys.path.insert(0, HERE)
os.chdir(HERE)

import mm  # noqa: E402
import verify as V  # noqa: E402

cfg = json.load(io.open("runs.json", encoding="utf-8"))


def _data_values(path: str) -> set:
    """输入表里出现过的所有数值（用于判定「这个数是抄进来的数据」）。"""
    try:
        import pandas as _pd
        vals = set()
        for sheet in _pd.ExcelFile(path).sheet_names:
            df = _pd.read_excel(path, sheet_name=sheet)
            for c in df.columns:
                col = _pd.to_numeric(df[c], errors="coerce").dropna()
                for v in col.tolist():
                    vals.add(round(float(v), 6))
        return vals
    except Exception:
        return set()


def classify(tok: str) -> str:
    t = tok.strip()
    try:
        v = float(t)
    except ValueError:
        return "?"
    has_dot = "." in t
    if not has_dot and 1900 <= v <= 2100 and float(v).is_integer():
        return "C_year"
    if has_dot and any(abs(v - c) < 1e-9
                       for c in (0.05, 0.01, 0.95, 0.90, 0.5)):
        return "B_config"
    if not has_dot and abs(v) <= 1000 and float(v).is_integer():
        return "A_struct"
    return "D_computed"


rows = []
for name, it in cfg.items():
    tex = os.path.join(HERE, it["out"], "paper.tex")
    if not os.path.exists(tex):
        continue
    text = io.open(tex, encoding="utf-8").read()
    # 找到这道题的输入表（冻结表里记了 source）
    _fz = os.path.join(HERE, it["out"], "冻结数字.json")
    _vals = set()
    if os.path.exists(_fz):
        _src = str(json.load(io.open(_fz, encoding="utf-8")).get("source")
                   or "").split(" · ")[0].strip()
        for _cand in (os.path.join("out", "data", _src),
                      os.path.join("out", "data", _src + ".xlsx")):
            if os.path.exists(_cand):
                _vals = _data_values(_cand)
                break
    outs = V.load_outputs(os.path.dirname(tex))
    r = V.trace(text, outs)
    n_tok = len(V.extract_numbers(text))
    unt = r.get("untraced") or []
    cnt = {"A_struct": 0, "B_config": 0, "C_year": 0,
           "E_data": 0, "D_computed": 0, "?": 0}
    dex = []
    for u in unt:
        k = classify(u["token"])
        # 抄进表格的原始数据：值能在输入表里找到 → 输入溯源问题，不是计算问题
        if k == "D_computed" and _vals:
            try:
                if round(float(u["token"]), 6) in _vals:
                    k = "E_data"
            except Exception:
                pass
        cnt[k] = cnt.get(k, 0) + 1
        if k == "D_computed" and len(dex) < 4:
            dex.append([u["token"], (u.get("context") or "")[:70]])
    rows.append(dict(name=name, total=n_tok, ok=n_tok - len(unt),
                     n_untraced=len(unt), **cnt, d_examples=dex))

json.dump(rows, io.open(os.path.join(OUT, "anatomy.json"), "w",
                        encoding="utf-8", newline="\n"),
          ensure_ascii=False, indent=1)

agg = dict(A_struct=0, B_config=0, C_year=0, E_data=0, D_computed=0)
tot = unt_all = 0
for r in rows:
    for k in agg:
        agg[k] += r[k]
    tot += r["total"]
    unt_all += r["n_untraced"]
    print("%-16s %6d 个数字  未溯源 %5d  (A%d B%d C%d E%d D%d)"
          % (r["name"], r["total"], r["n_untraced"], r["A_struct"],
             r["B_config"], r["C_year"], r["E_data"],
             r["D_computed"]))
print()
print("合计：%d 个数字，未溯源 %d（%.1f%%）"
      % (tot, unt_all, 100.0 * unt_all / max(1, tot)))
for k in agg:
    print("   %-11s %5d  (%.1f%% of untraced)"
          % (k, agg[k], 100.0 * agg[k] / max(1, unt_all)))
