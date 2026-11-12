"""untraced.py —— 把「未溯源数字」逐类剖析，作为插件能力（第 110 轮）。

为什么要有这个模块
------------------
原来的溯源率是一个比例，把四类性质完全不同的 token 混在一起，于是
「78%可溯源」既像控诉又像吹牛。更糟的是我们一度用一个**被截断**的打印
列表当分母（红队 F1）：只分类了 15% 的未溯源 token，却在论文里写
「只有 33 个是真缺陷」——实际是 898。

本模块把未溯源集合**完整**取出来，按五类归档：

  A_struct    行号/表号/章节号/样本量 —— 布局，不该有计算出处
  B_config    α=0.05、阈值、置信水平 —— 方法约定，声明一次
  C_year      年份/期号 —— 数据标签
  E_data      值出现在输入表的单元格里 —— **输入溯源**问题，不是计算问题
  D_computed  其余带小数或大整数 —— **只有这一类**必须能追到计算产物

判据必须可复核：每一类的规则写在这里，`selftest` 断言边界。

用法
----
  python untraced.py <含 paper.tex 的目录>          # 一篇
  python untraced.py --corpus                        # 按 runs.json 全量
  python untraced.py selftest                        # 自检
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import verify as V  # noqa: E402

CLASSES = ("A_struct", "B_config", "C_year", "E_data", "D_computed")
CONFIG_CONSTANTS = (0.05, 0.01, 0.95, 0.90, 0.5)


def classify_token(tok: str, data_values=None, struct_limit: float = 1000) -> str:
    """一个 token 归到哪一类。规则就是这张表，别的没了。

    `struct_limit`（默认 1000）是 `A_struct` 的范围上界，**它是经验界不是定理**：
    为什么不是 500 或 5000 没有推导，只有「前沿表里的行号/个数不会超过一千」这个
    语料观察。第 123 轮把它提出来做参数，为的是能扫描
    （`tools/param_sensitivity.py`）—— 藏在函数体里的阈值无法被审查。
    """
    t = str(tok).strip()
    try:
        v = float(t)
    except ValueError:
        return "?"
    has_dot = "." in t
    if not has_dot and 1900 <= v <= 2100:
        return "C_year"
    if has_dot and any(abs(v - c) < 1e-9 for c in CONFIG_CONSTANTS):
        return "B_config"
    if not has_dot and abs(v) <= struct_limit:
        return "A_struct"
    if data_values:
        try:
            if round(v, 6) in data_values:
                return "E_data"
        except (TypeError, ValueError):
            pass
    return "D_computed"


def data_values_of(xlsx: str):
    """输入表里出现过的所有数值（六位小数为键）。读不到就返回空集。"""
    try:
        import pandas as pd
        vals = set()
        for sheet in pd.ExcelFile(xlsx).sheet_names:
            df = pd.read_excel(xlsx, sheet_name=sheet)
            for c in df.columns:
                col = pd.to_numeric(df[c], errors="coerce").dropna()
                for x in col.tolist():
                    vals.add(round(float(x), 6))
        return vals
    except Exception:                                   # noqa: BLE001
        return set()


def find_data_file(figdir: str) -> str:
    """从冻结表里读出这道题的输入表名，再在 out/data 下找。"""
    fz = os.path.join(figdir, "冻结数字.json")
    if not os.path.exists(fz):
        return ""
    try:
        src = str(json.load(io.open(fz, encoding="utf-8")).get("source")
                  or "").split(" · ")[0].strip()
    except Exception:                                   # noqa: BLE001
        return ""
    for cand in (os.path.join(HERE, "out", "data", src),
                 os.path.join(HERE, "out", "data", src + ".xlsx")):
        if os.path.exists(cand):
            return cand
    return ""


def analyse(figdir: str) -> dict:
    """一篇论文的剖析结果。分母是**完整**的未溯源集合。"""
    tex = os.path.join(figdir, "paper.tex")
    if not os.path.exists(tex):
        return dict(error="没有 paper.tex")
    text = io.open(tex, encoding="utf-8").read()
    outs = V.load_outputs(figdir)
    r = V.trace(text, outs)
    n_tok = len(V.extract_numbers(text))
    unt = r.get("untraced") or []
    dv = data_values_of(find_data_file(figdir))
    cnt = dict((k, 0) for k in CLASSES)
    cnt["?"] = 0
    examples = dict((k, []) for k in CLASSES)
    for u in unt:
        k = classify_token(u["token"], dv)
        cnt[k] = cnt.get(k, 0) + 1
        if len(examples.get(k, [])) < 5:
            examples.setdefault(k, []).append(
                [u["token"], (u.get("context") or "")[:70]])
    return dict(dir=figdir, n_tokens=n_tok, n_untraced=len(unt),
                traced_pct=round(100.0 * (n_tok - len(unt)) / max(1, n_tok), 1),
                counts=cnt, examples=examples,
                has_data=bool(dv))


def report(a: dict) -> str:
    if a.get("error"):
        return f"  {a['dir']}: {a['error']}"
    c = a["counts"]
    n = max(1, a["n_untraced"])
    lines = [f"  溯源 {a['traced_pct']}%  （{a['n_tokens']} 个数字，"
             f"未溯源 {a['n_untraced']}）"]
    for k in CLASSES:
        lines.append("    %-11s %4d  %5.1f%%" % (k, c[k], 100.0 * c[k] / n))
    if c.get("?"):
        lines.append("    ?           %4d" % c["?"])
    if not a["has_data"]:
        lines.append("    （找不到输入表：E_data 无法判定，已并入 D_computed）")
    return "\n".join(lines)


def corpus() -> int:
    cfg = json.load(io.open(os.path.join(HERE, "runs.json"), encoding="utf-8"))
    agg = dict((k, 0) for k in CLASSES)
    tot = unt = 0
    rows = []
    for name, it in cfg.items():
        d = os.path.join(HERE, it["out"])
        if not os.path.exists(os.path.join(d, "paper.tex")):
            continue
        a = analyse(d)
        if a.get("error"):
            continue
        rows.append(dict(name=name, **{k: a["counts"][k] for k in CLASSES},
                         n_tokens=a["n_tokens"], n_untraced=a["n_untraced"]))
        for k in CLASSES:
            agg[k] += a["counts"][k]
        tot += a["n_tokens"]
        unt += a["n_untraced"]
        print("%-16s %6d 未溯源 %5d" % (name, a["n_tokens"], a["n_untraced"]))
    print()
    print("合计 %d 个数字，未溯源 %d（%.1f%%）"
          % (tot, unt, 100.0 * unt / max(1, tot)))
    for k in CLASSES:
        print("   %-11s %5d  %5.1f%%" % (k, agg[k],
                                         100.0 * agg[k] / max(1, unt)))
    out = os.path.join(HERE, "out", "untraced_corpus.json")
    json.dump(rows, io.open(out, "w", encoding="utf-8", newline="\n"),
              ensure_ascii=False, indent=1)
    print("已写", out)
    return 0


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

    ck("年份归 C_year", classify_token("1975") == "C_year")
    ck("α=0.05 归 B_config", classify_token("0.05") == "B_config")
    ck("小整数归 A_struct", classify_token("84") == "A_struct")
    ck("负号小整数仍是 A_struct", classify_token("-12") == "A_struct")
    ck("大整数归 D_computed", classify_token("51737") == "D_computed")
    ck("小数归 D_computed", classify_token("0.00743") == "D_computed")
    ck("输入表里有的值归 E_data",
       classify_token("3.5", {3.5}) == "E_data")
    ck("输入表里没有仍是 D_computed",
       classify_token("3.5", {1.0}) == "D_computed")
    ck("科学计数法归 D_computed",
       classify_token("3.3342e-12") == "D_computed")
    ck("非数字返回 ?", classify_token("abc") == "?")

    # 分母必须是**完整**未溯源集合：这是 F1 的教训，钉死它
    import tempfile
    td = tempfile.mkdtemp(prefix="untraced_st_")
    with io.open(os.path.join(td, "paper.tex"), "w", encoding="utf-8") as f:
        # 30 个未溯源的小数 + 1 个整数
        f.write("\\begin{document}" + " ".join(
            "%.4f" % (0.1 + i) for i in range(30)) + " 7 end{document}")
    a = analyse(td)
    ck("未溯源集合不被截断（30+1 全进分母）",
       a["n_untraced"] >= 30, f"n_untraced={a.get('n_untraced')}")
    ck("各类之和等于未溯源总数",
       sum(a["counts"][k] for k in CLASSES) + a["counts"].get("?", 0)
       == a["n_untraced"], str(a["counts"]))

    print()
    print(f"{'ALL PASS' if bad == 0 else 'FAILED'}  {n - bad}/{n}")
    return 0 if bad == 0 else 1


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="未溯源数字逐类剖析")
    ap.add_argument("dir", nargs="?", default="")
    ap.add_argument("--corpus", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    if a.dir == "selftest" or (not a.dir and not a.corpus):
        return selftest()
    if a.corpus:
        return corpus()
    r = analyse(os.path.abspath(a.dir))
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=1))
    else:
        print(report(r))
    # 有 D_computed 就非零：这一类才是真缺陷
    return 0 if r.get("counts", {}).get("D_computed", 0) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
