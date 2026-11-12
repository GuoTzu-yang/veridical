"""批量压力测试：对多道不同类型的题跑完整链路，汇总弱点。

目的
----
同一道题反复打磨只能修「这一题」的毛病。不同题型才会暴露「这一类题」的坑：
预测题会撞时间趋势伪相关、优化题会撞不可行、评价题会撞权重任意性、
聚类题会撞簇数选择…… 每次跑完把 gate 的失败/警告按**检查项**聚起来，
就知道下一轮该修哪儿。

用法
    python tools/stress.py --names prediction,network,clustering
    python tools/stress.py --all              # runs.json 里所有有数据的题
    python tools/stress.py --names a,b --no-compile   # 不出 PDF，更快

产物
    out/drill/<题>/...          每题的完整产物
    out/drill/_stress.json      汇总（耗时、gate 各项、异常）
    stdout                      按检查项聚合的弱点表
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable
DRILL = os.path.join(HERE, "out", "drill")


def sh(args, timeout=1800):
    t0 = time.time()
    try:
        p = subprocess.run([PY] + args, cwd=HERE, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
        return time.time() - t0, p.returncode, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired:
        return time.time() - t0, -9, "TIMEOUT"


def parse_gate(out):
    """从 gate 文本输出里抽出每项的 状态/详情。"""
    items = {}
    for line in out.splitlines():
        s = line.strip()
        if not s.startswith("["):
            continue
        for mark, st in (("OK  ", "PASS"), ("FAIL", "FAIL"),
                         ("WARN", "WARN"), ("-   ", "NA")):
            if s.startswith("[" + mark):
                rest = s[len(mark) + 2:].strip()
                parts = rest.split(None, 2)
                # 只收「硬 xxx」/「软 xxx」形态的单项行。
                # 形如 [OK] 0 分项 9/9 通过、[OK] 半衰项 4/4 通过 是分层汇总，
                # 不是检查项 —— 早期版本把它们解析成 items["0"]、items["半衰项"]。
                if len(parts) >= 2 and parts[0] in ("硬", "软"):
                    items[parts[1]] = dict(status=st,
                                           detail=(parts[2] if len(parts) > 2 else ""))
                break
    return items


def run_one(name, cfg, compile_pdf=True):
    d = os.path.join(DRILL, name)
    data = os.path.join(HERE, "out", "data", cfg.get("data", ""))
    rec = dict(name=name, data=cfg.get("data"), steps={}, items={}, error="")

    if not os.path.exists(data):
        rec["error"] = "数据文件不存在: %s" % cfg.get("data")
        return rec
    if os.path.isdir(d):
        shutil.rmtree(d)
    os.makedirs(d, exist_ok=True)

    cmd = ["mmkit.py", "run", "--data", data]
    if cfg.get("y"):
        cmd += ["--y", cfg["y"]]
    if cfg.get("x"):
        cmd += ["--x", cfg["x"]]
    if cfg.get("min"):
        cmd += ["--min", cfg["min"]]
    cmd += ["--out", os.path.join(d, "report.md"),
            "--tex", os.path.join(d, "paper.tex")]
    if compile_pdf:
        cmd.append("--compile")

    dt, rc, out = sh(cmd)
    rec["steps"]["run"] = dict(sec=round(dt, 1), rc=rc)
    rec["run_tail"] = "\n".join([x for x in out.splitlines() if x.strip()][-6:])
    if rc != 0:
        rec["error"] = "run 失败 rc=%d" % rc

    dt2, rc2, out2 = sh(["gate.py", d, "--data", data])
    rec["steps"]["gate"] = dict(sec=round(dt2, 1), rc=rc2)
    rec["items"] = parse_gate(out2)
    rec["gate_head"] = next((x.strip() for x in out2.splitlines()
                             if "质量门" in x), "")

    pdf = os.path.join(d, "paper.pdf")
    rec["pdf_kb"] = round(os.path.getsize(pdf) / 1024.0, 1) \
        if os.path.exists(pdf) else 0
    tex = os.path.join(d, "paper.tex")
    rec["tex_kb"] = round(os.path.getsize(tex) / 1024.0, 1) \
        if os.path.exists(tex) else 0
    return rec


def main(argv=None):
    ap = argparse.ArgumentParser(description="批量压力测试")
    ap.add_argument("--names", default="")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--no-compile", action="store_true")
    a = ap.parse_args(argv)

    cfg = json.load(open(os.path.join(HERE, "runs.json"), encoding="utf-8"))
    if a.all:
        names = [k for k, c in cfg.items() if c.get("data")]
    else:
        names = [x.strip() for x in a.names.split(",") if x.strip()]
    if not names:
        ap.error("需要 --names 或 --all")

    os.makedirs(DRILL, exist_ok=True)
    recs = []
    for i, n in enumerate(names, 1):
        if n not in cfg:
            print("[%d/%d] %-16s 跳过（runs.json 无此题）" % (i, len(names), n))
            continue
        print("[%d/%d] %-16s 跑..." % (i, len(names), n), end="", flush=True)
        r = run_one(n, cfg[n], compile_pdf=not a.no_compile)
        recs.append(r)
        bad = [k for k, v in r["items"].items() if v["status"] in ("FAIL",)]
        warn = [k for k, v in r["items"].items() if v["status"] == "WARN"]
        print(" %5.1fs  PDF %5.0fKB  %s%s%s"
              % (r["steps"].get("run", {}).get("sec", 0), r["pdf_kb"],
                 (r["gate_head"] or r["error"])[:34],
                 ("  FAIL=" + ",".join(bad)) if bad else "",
                 ("  WARN=" + ",".join(warn)) if warn else ""))

    # ── 按检查项聚合 ──
    agg = {}
    for r in recs:
        for k, v in r["items"].items():
            s = agg.setdefault(k, dict(PASS=0, WARN=0, FAIL=0, NA=0, details=[]))
            s[v["status"]] = s.get(v["status"], 0) + 1
            if v["status"] in ("FAIL", "WARN") and len(s["details"]) < 3:
                s["details"].append("%s: %s" % (r["name"], v["detail"][:70]))

    print("\n" + "=" * 78)
    print("弱点聚合（按检查项）")
    print("=" * 78)
    print("  %-14s %5s %5s %5s %5s" % ("检查项", "PASS", "WARN", "FAIL", "N/A"))
    for k, s in sorted(agg.items(), key=lambda kv: (-kv[1].get("FAIL", 0),
                                                    -kv[1].get("WARN", 0))):
        print("  %-14s %5d %5d %5d %5d"
              % (k, s.get("PASS", 0), s.get("WARN", 0),
                 s.get("FAIL", 0), s.get("NA", 0)))
        for det in s["details"]:
            print("        · %s" % det)

    total = sum(r["steps"].get("run", {}).get("sec", 0) for r in recs)
    print("\n合计 %d 题，出稿+编译 %.1fs（%.1fs/题）"
          % (len(recs), total, total / max(1, len(recs))))

    p = os.path.join(DRILL, "_stress.json")
    json.dump(dict(records=recs, agg=agg), open(p, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print("明细已写入 %s" % p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
