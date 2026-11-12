"""为最终论文收集全部数字，落 out/final/data.json。

原则：论文里的每个数都要能追溯到这里的某个字段；
字段值必须现场测量（读文件 / 跑一遍），不许手填。

跑法：python tools/collect_paper_data.py
"""
import io
import json
import os
import re
import subprocess
import sys
import time

HERE = r"C:\Users\21246\Documents\deepseek-harness\default-workspace\model1-arch"
PY = sys.executable
os.chdir(HERE)
OUT = os.path.join(HERE, "out", "final")
os.makedirs(OUT, exist_ok=True)

D = {}


def _run(argv, timeout=900, env_extra=None):
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    if env_extra:
        env.update(env_extra)
    t0 = time.time()
    try:
        r = subprocess.run(argv, capture_output=True, text=True,
                           encoding="utf-8", errors="replace",
                           cwd=HERE, env=env, timeout=timeout)
        return r.returncode, r.stdout, r.stderr, time.time() - t0
    except subprocess.TimeoutExpired:
        return -1, "", "timeout", time.time() - t0


# ── 1 能力面 ──
src = io.open("schema.json", encoding="utf-8").read()
sj = json.loads(src)
D["n_commands"] = sj["n_commands"]
D["n_declared_args"] = sj.get("n_declared_args")
D["schema_bytes"] = len(src.encode("utf-8"))

# ── 2 gate 检查项 ──
code, out, err, _ = _run([PY, "-c",
    "import sys;sys.path.insert(0,'.');import gate;"
    "r=gate.run_all('out/runs/queueing');"
    "print(len(r['checks']));"
    "print(sum(1 for c in r['checks'] if c['tier']=='hard'));"
    "print(sum(1 for c in r['checks'] if c['tier']!='hard'))"])
try:
    ln = [x for x in out.splitlines() if x.strip()]
    D["n_gate_checks"] = int(ln[0])
    D["n_gate_hard"] = int(ln[1])
    D["n_gate_soft"] = int(ln[2])
except Exception:
    D["n_gate_checks"] = None

# ── 3 回归与自检覆盖 ──
s = io.open(os.path.join("tests", "run_all.py"), encoding="utf-8").read()
m = re.search(r"CORE\s*=\s*\[(.*?)\n\]", s, re.S)
core = m.group(1)
D["n_regression_pins"] = len(re.findall(r"^\s*\(", core, re.M))

mods = []
for d in (".", "tools", "tests"):
    p = os.path.join(HERE, d)
    if not os.path.isdir(p):
        continue
    for f in sorted(os.listdir(p)):
        if not f.endswith(".py"):
            continue
        try:
            t = io.open(os.path.join(p, f), encoding="utf-8").read()
        except Exception:
            continue
        mods.append((f if d == "." else d + "/" + f,
                     bool(re.search(r"^def selftest", t, re.M))))
D["n_py_files"] = len(mods)
D["n_modules_with_selftest"] = sum(1 for _n, h in mods if h)

# ── 4 补丁账本 ──
code, out, err, _ = _run([PY, "patches.py", "verify"])
mm = re.search(r"(\d+)/(\d+)\s*已落实", out)
D["n_patches_done"], D["n_patches_total"] = (
    (int(mm.group(1)), int(mm.group(2))) if mm else (None, None))

# ── 5 逐题：gate / 数字溯源 / 图 / 页数 ──
cfg = json.load(io.open("runs.json", encoding="utf-8"))
rows = []
for name, it in cfg.items():
    d = it["out"]
    row = dict(name=name, out=d)
    tex = os.path.join(d, "paper.tex")
    pdf = os.path.join(d, "paper.pdf")
    row["has_pdf"] = os.path.exists(pdf)
    row["pdf_bytes"] = os.path.getsize(pdf) if row["has_pdf"] else 0
    # 页数
    if row["has_pdf"]:
        c2, o2, e2, _t = _run([PY, "-c",
            "from pypdf import PdfReader;import sys;"
            "r=PdfReader(sys.argv[1]);"
            "print(len(r.pages));"
            "print(sum(len(p.images) for p in r.pages))", pdf], timeout=180)
        _l2 = [x for x in o2.splitlines() if x.strip()]
        try:
            row["pages"] = int(_l2[0])
            # PDF 里**真正嵌入**的图数（fig/ 里的文件不一定都被引用）
            row["n_emb_imgs"] = int(_l2[1]) if len(_l2) > 1 else None
        except Exception:
            row["pages"] = None
            row["n_emb_imgs"] = None
    # 图数（fig 目录）
    figdir = os.path.join(d, "fig")
    # 只数 .pdf：每个图都有 pdf+png 两份，数文件会翻倍（第 109 轮踩过）
    row["n_figs"] = (len([f for f in os.listdir(figdir)
                          if f.lower().endswith(".pdf")])
                     if os.path.isdir(figdir) else 0)
    # 第 123 轮补：`n_fig_env` = 源文件里的 figure 环境数。
    # 图注写的是「vector figures counted from the source」，数 fig/ 目录是错的。
    # 这个字段**从来没有被采集过**，而 make_final_figs.fig_pages_figs 依赖它：
    # 缺了就 `if not rows: return` 静默跳过，于是 fig8_pages_figs 从 11-10 起
    # 一直没更新，而论文引用了它一次 —— 一张孤儿图，没有任何围栏报。
    # 是 arch_invariants 的 I12（图不许旧于其数据）把它翻出来的。
    if os.path.exists(tex):
        try:
            _t4 = io.open(tex, encoding="utf-8", errors="replace").read()
            row["n_fig_env"] = len(re.findall(r"\\begin\{figure", _t4))
        except Exception:                               # noqa: BLE001
            row["n_fig_env"] = None
    else:
        row["n_fig_env"] = None
    # 数字溯源
    if os.path.exists(tex):
        c3, o3, e3, _t = _run([PY, "verify.py", tex], timeout=180)
        m3 = re.search(r"(\d+)/(\d+)\s*\(([\d.]+)%\)", o3)
        if m3:
            row["num_ok"] = int(m3.group(1))
            row["num_total"] = int(m3.group(2))
            row["num_pct"] = float(m3.group(3))
    # gate
    c4, o4, e4, _t = _run([PY, "-c",
        "import sys;sys.path.insert(0,'.');import gate;"
        "r=gate.run_all(sys.argv[1]);"
        "print(sum(1 for c in r['checks'] if c['status']=='PASS'));"
        "print(sum(1 for c in r['checks'] if c['status']=='FAIL'));"
        "print(sum(1 for c in r['checks'] if c['status']=='WARN'));"
        "print([c['detail'] for c in r['checks'] if c['id']=='numbers'][0])", d],
        timeout=300)
    ln4 = [x for x in o4.splitlines() if x.strip()]
    try:
        row["gate_pass"] = int(ln4[0])
        row["gate_fail"] = int(ln4[1])
        row["gate_warn"] = int(ln4[2])
    except Exception:
        pass
    # gate 口径的数字溯源率（只数小数；与 verify.py 的全量口径不同）
    if len(ln4) > 3:
        mg = re.search(r"(\d+)/(\d+)", ln4[3])
        mp = re.search(r"无出处\s*([\d.]+)%", ln4[3])
        if mg:
            row["gate_num_ok"] = int(mg.group(1))
            row["gate_num_total"] = int(mg.group(2))
            row["gate_num_pct"] = round(
                100.0 * int(mg.group(1)) / max(1, int(mg.group(2))), 1)
        if mp:
            row["gate_num_untraced_pct"] = float(mp.group(1))
    rows.append(row)
D["problems"] = rows

# ── 6 题型覆盖（人工标注 vs advise 判定）──
SYN = {"explain": "regression", "optimize": "optimization",
       "evaluate": "evaluation", "forecast": "prediction"}
cov = []
for name, it in cfg.items():
    d = it["out"]
    fz = os.path.join(d, "冻结数字.json")
    tp = os.path.join(d, "题型.json")
    if not (os.path.exists(fz) and os.path.exists(tp)):
        continue
    fd = json.load(io.open(fz, encoding="utf-8"))
    srcname = str(fd.get("source") or "").split(" · ")[0].strip()
    cands = [os.path.join("out", "data", srcname),
             os.path.join("out", "data", srcname + ".xlsx")]
    data = next((c for c in cands if os.path.exists(c)), None)
    if not data:
        continue
    argv = [PY, "mmkit.py", "advise", "--data", data,
            "--y", str(fd.get("y")),
            "--x", ",".join(str(x) for x in (fd.get("x") or [])), "--json"]
    _min = [x.strip() for x in str(it.get("min") or "").split(",") if x.strip()]
    if _min:
        argv += ["--min", ",".join(_min)]
    if it.get("problem"):
        argv += ["--problem", str(it["problem"])]
    c5, o5, e5, _t = _run(argv, timeout=180)
    try:
        j = json.loads(o5)
    except Exception:
        continue
    ks = [SYN.get(k, k) for k in (j.get("kinds") or [j.get("kind", "?")])]
    gold = json.load(io.open(tp, encoding="utf-8")).get("kinds") or []
    cov.append(dict(name=name, advise=ks, curated=gold,
                    full=(not set(gold) - set(ks))))
D["type_coverage"] = cov

# ── 7 缺陷分类（从优化记录里按关键词计数；**分类是我做的，不是机器判定**）─
rec = io.open("OPTIMIZATION-优化记录.md", encoding="utf-8").read()
parts = re.split(r"^# 优化记录（第 (\d+) 轮）", rec, flags=re.M)
rounds = [(parts[i], parts[i + 1]) for i in range(1, len(parts), 2)]
CLASSES = {
    "vacuous-check": ("恒真", "恒为", "永不", "不可达", "从没被赋值",
                      "空判据", "摆设", "不能失败"),
    "silent-default": ("默认", "自动", "静默", "悄悄", "没人负责"),
    "duplicate-logic": ("两套", "分叉", "不一致", "同义", "漂移", "重复"),
    "self-report": ("自报", "样本量", "报成", "打印成", "数字不对"),
    "self-test-broken": ("崩溃", "IndexError", "自检不在", "不在回归链"),
    "contract-unenforced": ("契约", "校验", "没验", "绕过"),
}
tax = {k: [] for k in CLASSES}
for rn, body in rounds:
    for k, kws in CLASSES.items():
        if any(w in body for w in kws):
            tax[k].append(int(rn))
D["defect_taxonomy"] = {k: dict(n_rounds=len(v), rounds=sorted(set(v)))
                        for k, v in tax.items()}
D["n_record_rounds"] = len(rounds)

# ── 8 记录的体量 ──
D["record_bytes"] = len(rec.encode("utf-8"))

with io.open(os.path.join(OUT, "data.json"), "w", encoding="utf-8",
             newline="\n") as f:
    json.dump(D, f, ensure_ascii=False, indent=1)

print("已写 out/final/data.json")
for k in ("n_commands", "n_gate_checks", "n_regression_pins",
          "n_modules_with_selftest", "n_py_files", "n_patches_done",
          "n_patches_total", "n_record_rounds", "record_bytes"):
    print("  %-28s %s" % (k, D.get(k)))
print("  逐题:", len(D["problems"]), "道")
print("  题型覆盖:", len(D["type_coverage"]), "道可测")
print("  缺陷分类:", {k: v["n_rounds"] for k, v in D["defect_taxonomy"].items()})
