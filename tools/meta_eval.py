"""评审要的三件测量（第 113 轮）。

上一版我**自己编过命令行**，计时表测的是「调用失败」的耗时（exit=2），
这种证据不能发。这一版复用 `tools/verify_runbook.py` 里那 9 条已验证可跑的
命令，只做计时与消融，不改命令；失败清单交给独立的 `tools/_fails_probe.py`。

① 时间口径：逐段实测，明确计入/未计入。
② 机制消融：只报可测的输出变化（不报「评分下降」——没有独立评分者）。
③ 失败清单：逐题非 PASS 项及原因。

对照组（人工队 vs 插件队）无法在本机完成：没有第二作者、没有独立评分者。
这条写进局限，不拿自评分数冒充。
"""
import importlib.util
import io
import json
import os
import subprocess
import sys
import time

HERE = r"C:\Users\21246\Documents\deepseek-harness\default-workspace\model1-arch"
OUT = os.path.join(HERE, "out", "final")
sys.path.insert(0, HERE)
os.chdir(HERE)


def run(argv, timeout=900):
    t0 = time.time()
    try:
        r = subprocess.run(argv, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
        return r.returncode, (r.stdout or ""), (r.stderr or ""), time.time() - t0
    except subprocess.TimeoutExpired:
        return -1, "", "timeout", time.time() - t0


# ── 复用已验证的命令列表 ────────────────────────────────────────────
spec = importlib.util.spec_from_file_location(
    "vr", os.path.join(HERE, "tools", "verify_runbook.py"))
vr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vr)
STEPS = vr.STEPS

# ── ① 计时 ─────────────────────────────────────────────────────────
timing = []
for no, desc, argv in STEPS:
    code, out, err, dt = run(argv)
    timing.append(dict(step=no, name=desc, seconds=round(dt, 2), exit=code))

# ── ② 机制消融 ─────────────────────────────────────────────────────
abl = {}

A = json.load(io.open(os.path.join(OUT, "ablation.json"), encoding="utf-8"))
abl["frozen_table"] = dict(
    with_pct=[a["with_table"] for a in A],
    without_pct=[a["without_table"] for a in A],
    source="tools/ablate_provenance.py")

code, out, err, dt = run(STEPS[6][2])          # 第 7 步 = 证伪
abl["falsify"] = dict(
    ran=code in (0, 1), seconds=round(dt, 2),
    reports_reversal=("反例" in out or "不成立" in out),
    first_line=next((x.strip() for x in out.splitlines() if x.strip()), "")[:90])

code, out, err, _ = run([sys.executable, "gate.py", "selftest"])
abl["stamp"] = dict(selftest_ok=("ALL PASS" in out),
                    pinned="盖章 → 改 tex → 判过期（FAIL）")

# ── ③ 失败清单 ─────────────────────────────────────────────────────
code, out, _e, _dt = run([sys.executable,
                          os.path.join("tools", "_fails_probe.py")],
                         timeout=1800)
fails = json.loads(out) if (code == 0 and out.strip().startswith("{")) else {}

res = dict(
    timing=timing,
    timing_total_s=round(sum(t["seconds"] for t in timing), 2),
    ablation=abl,
    failures=fails,
    scope=dict(
        included="the nine verified runbook commands, wall clock, one machine",
        excluded="prose writing, reading figures, debugging, reruns, reading "
                 "the problem statement",
        note="A 'minutes to PDF' figure includes prose writing, which is not "
             "automatically measurable; this table reports only the measurable "
             "segments and makes no claim about the total."),
    no_control_group="A human-vs-tool comparison needs a second author and an "
                     "independent rater; neither exists here.")

json.dump(res, io.open(os.path.join(OUT, "meta_eval.json"), "w",
                       encoding="utf-8", newline="\n"),
          ensure_ascii=False, indent=1)

print("① 时间口径（只计已验证命令）")
for t in timing:
    print("   %-2s %-30s %6.2fs exit=%s" % (t["step"], t["name"][:30],
                                            t["seconds"], t["exit"]))
print("   合计 %.2fs" % res["timing_total_s"])
print()
print("② 机制消融")
print("   冻结表: %s -> %s" % (abl["frozen_table"]["with_pct"],
                             abl["frozen_table"]["without_pct"]))
print("   证伪  : ran=%s reversal=%s" % (abl["falsify"]["ran"],
                                        abl["falsify"]["reports_reversal"]))
print("   盖章  : selftest=%s" % abl["stamp"]["selftest_ok"])
print()
print("③ 失败清单：%d 题有非 PASS 项" % len(fails))
print("已写", os.path.join(OUT, "meta_eval.json"))
