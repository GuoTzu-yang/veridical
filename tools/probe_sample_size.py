"""量两件事：

① 未测模块清单：仓库里有多少 .py，其中多少带 selftest、多少完全没有自检。
② 题型覆盖：23 道题经 advise 判定后，各落在哪个题型上。
   —— 插件声称覆盖「关系与解释/预测/优化/评价」四类，题库里有没有每一类，
      才是「题型全覆盖」这句话的样本基础。
"""
import io
import json
import os
import re
import subprocess
import sys

HERE = r"C:\Users\21246\Documents\deepseek-harness\default-workspace\model1-arch"
PY = sys.executable
os.chdir(HERE)


def modules():
    out = []
    for d in (".", "tools", "tests"):
        p = os.path.join(HERE, d)
        if not os.path.isdir(p):
            continue
        for f in sorted(os.listdir(p)):
            if not f.endswith(".py"):
                continue
            fp = os.path.join(p, f)
            try:
                t = io.open(fp, encoding="utf-8").read()
            except Exception:
                continue
            has = bool(re.search(r"^def selftest", t, re.M))
            out.append((f if d == "." else d + "/" + f, has))
    return out


def kinds():
    cfg = json.load(io.open("runs.json", encoding="utf-8"))
    tab = {}
    rows = []
    for name, it in cfg.items():
        d = os.path.join(HERE, it["out"])
        fz = os.path.join(d, "冻结数字.json")
        if not os.path.exists(fz):
            rows.append((name, "无冻结表"))
            continue
        fd = json.load(io.open(fz, encoding="utf-8"))
        y, xs = fd.get("y"), fd.get("x") or []
        # runs.json 的 data 字段是 null —— 数据文件靠 find_xlsx() 自动发现。
        # 冻结表的 source 记着每题真正用的那个文件名，按它还原。
        src = str(fd.get("source") or "")
        fname = src.split(" · ")[0].strip()
        cands = [os.path.join(HERE, "out", "data", fname),
                 os.path.join(HERE, fname),
                 os.path.join(HERE, "out", "data", fname + ".xlsx")]
        data = next((c for c in cands if os.path.exists(c)), None)
        if not data:
            rows.append((name, "找不到数据(%s)" % fname[:30]))
            continue
        argv = [PY, "mmkit.py", "advise", "--data", data]
        if y:
            argv += ["--y", str(y)]
        if xs:
            argv += ["--x", ",".join(str(x) for x in xs)]
        # 目标列要一起给（第 106 轮）：不带就看不见「这题要寻优」。
        # 冻结表里没记 min（实测是 None），所以从 runs.json 的配置取。
        _min = it.get("min") or ""
        _objs = [x.strip() for x in str(_min).split(",") if x.strip()]
        if _objs:
            argv += ["--min", ",".join(_objs)]
        # 题面也要给（第 107 轮）：network/simulation/mechanism 这些
        # 题型只看数据是认不出来的，线索在题面里。
        _prob = str(it.get("problem") or "")
        if _prob:
            argv += ["--problem", _prob]
        argv += ["--json"]
        try:
            r = subprocess.run(argv, capture_output=True, text=True,
                               encoding="utf-8", errors="replace",
                               cwd=HERE, timeout=180)
            j = json.loads(r.stdout or "{}")
        except Exception as e:
            rows.append((name, "解析失败:%s" % type(e).__name__))
            continue
        ks = j.get("kinds") or [j.get("kind", "?")]
        # 与人工题面 题型.json 比。两边**词表不同**，先做同义映射
        # （映射是我按语义定的，不是从代码里读出来的）：
        #   explain  ≈ regression      optimize ≈ optimization
        #   evaluate ≈ evaluation      forecast ≈ prediction
        # 题型.json 另有 network / simulation / mechanism / multiobjective，
        # advise 从来不报这四个 —— 那部分差距是真的。
        SYN = {"explain": "regression", "optimize": "optimization",
               "evaluate": "evaluation", "forecast": "prediction"}
        # 与人工题面 题型.json 比
        tp = os.path.join(d, "题型.json")
        gold = []
        if os.path.exists(tp):
            gold = json.load(io.open(tp, encoding="utf-8")).get("kinds") or []
        for k in ks:
            tab[k] = tab.get(k, 0) + 1
        ks2 = [SYN.get(k, k) for k in ks]
        cov = sorted(set(ks2) & set(gold))
        miss = sorted(set(gold) - set(ks2))
        rows.append((name, "advise=%s | 题面=%s | 覆盖=%s%s" % (
            "/".join(ks2), "/".join(gold), ",".join(cov) or "无",
            ("  缺=" + ",".join(miss)) if miss else "")))
    return tab, rows


def main():
    ms = modules()
    with_st = [m for m, h in ms if h]
    without = [m for m, h in ms if not h]
    print("=" * 70)
    print("① 模块自检覆盖")
    print("=" * 70)
    print("  .py 模块总数: %d" % len(ms))
    print("  带 selftest:  %d" % len(with_st))
    print("  无 selftest:  %d  <- 这些代码没有任何自测" % len(without))
    for m in without:
        print("      %s" % m)

    print()
    print("=" * 70)
    print("② 题型覆盖（advise 判定 23 道题）")
    print("=" * 70)
    tab, rows = kinds()
    for k, v in sorted(tab.items(), key=lambda kv: -kv[1]):
        print("  %-28s %d" % (k, v))
    print()
    for n, k in rows:
        print("    %-18s %s" % (n, k))


if __name__ == "__main__":
    main()
