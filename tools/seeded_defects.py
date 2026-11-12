"""种子缺陷基准：给已知论文植入已知缺陷，测检出率与误报率（第 114 轮）。

为什么这是「外部效度」的正确答案
--------------------------------
评审说「单语料、单作者」使可推广性不能成立 —— 这条靠再写几段话改不掉。
能改的是把问题换成可测的：**给定一个已知缺陷，gate 抓不抓得到？干净输入会不会
被误杀？** 这是敏感度/特异度，换谁来复核都能重跑。

六种缺陷，各自有「该抓到它的检查」：
  invented_number   把一处已溯源的小数换成一个不存在的值   → numbers
  dropped_source    从冻结表删掉一条                       → numbers
  zero_citation     删掉全部 \\cite                        → refs
  masked_na         删掉冻结表（应判 FAIL 而不是 N/A）     → numbers
  stale_verdict     盖章后改 tex                           → stamp
  unsupported_claim 把「相关」改成「证明了因果」           → rigor/falsify

输出：每种缺陷的检出率、以及**干净组的误报数**（把干净的论文也跑一遍）。
"""
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = r"C:\Users\21246\Documents\deepseek-harness\default-workspace\model1-arch"
OUT = os.path.join(HERE, "out", "final")
sys.path.insert(0, HERE)
os.chdir(HERE)

PY = sys.executable
# 选 5 道题做基准：覆盖回归/评价/预测/排队/多目标
TARGETS = ["heat_sink", "evaluation", "prediction", "queueing", "multiobjective"]


def gate_status(d):
    """跑 gate，返回 {check_id: status} 与硬门失败列表。"""
    code, out, err, _ = 0, "", "", 0
    r = subprocess.run([PY, "gate.py", d, "--json"], capture_output=True,
                       text=True, encoding="utf-8", errors="replace",
                       timeout=900)
    try:
        j = json.loads(r.stdout)
        return {c["id"]: c["status"] for c in j["checks"]}, j.get("hard_fail") or []
    except Exception:                                   # noqa: BLE001
        return {}, []


def plant(kind: str, d: str) -> str:
    """就地植入缺陷，返回描述。d 是临时副本目录。"""
    tex = os.path.join(d, "paper.tex")
    s = io.open(tex, encoding="utf-8").read()
    fz = os.path.join(d, "冻结数字.json")

    if kind == "invented_number":
        # 找一个已溯源的小数，换成不可能存在的值
        m = re.search(r"(?<![\d.])(0\.\d{3,6})(?![\d])", s)
        if not m:
            return "no decimal found"
        s = s[:m.start()] + "0.847192" + s[m.end():]
        io.open(tex, "w", encoding="utf-8", newline="\n").write(s)
        return "0.847192 planted"

    if kind == "dropped_source":
        if not os.path.exists(fz):
            return "no frozen table"
        j = json.load(io.open(fz, encoding="utf-8"))
        if j.get("items"):
            j["items"] = j["items"][:-1]
        json.dump(j, io.open(fz, "w", encoding="utf-8", newline="\n"),
                  ensure_ascii=False, indent=1)
        return "one frozen item removed"

    if kind == "zero_citation":
        s2 = re.sub(r"\\cite\{[^}]*\}", "", s)
        io.open(tex, "w", encoding="utf-8", newline="\n").write(s2)
        return "all \\cite removed"

    if kind == "masked_na":
        if os.path.exists(fz):
            os.remove(fz)
            return "frozen table deleted"
        return "no frozen table to delete"

    if kind == "stale_verdict":
        # 盖章只对「交稿」生效：基准里必须先把副本声明成交稿，
        # 否则 stamp 按设计判 N/A，看上去像「没抓到」（第 114 轮）。
        json.dump(dict(deliverable=True),
                  io.open(os.path.join(d, "declaration.json"), "w",
                          encoding="utf-8", newline="\n"))
        r = subprocess.run([PY, "gate.py", d, "--stamp"], capture_output=True,
                           text=True, encoding="utf-8", errors="replace")
        with io.open(tex, "a", encoding="utf-8") as f:
            f.write("\n% edited after the verdict\n")
        return "stamped then edited"

    if kind == "unsupported_claim":
        s2 = re.sub(r"\bcorrelat\w+", "proves the causal effect of", s, count=1)
        if s2 == s:
            s2 = re.sub(r"\bassociat\w+", "proves causation for", s, count=1)
        if s2 == s:
            return "no claim phrasing found"
        io.open(tex, "w", encoding="utf-8", newline="\n").write(s2)
        return "claim upgraded to causal"

    return "unknown"


EXPECT = {
    "invented_number": "numbers",
    "dropped_source": "numbers",
    "zero_citation": "refs",
    "masked_na": "numbers",
    "stale_verdict": "stamp",
    "unsupported_claim": "causal",
}


def main():
    results = []
    clean_fp = []
    for name in TARGETS:
        src = os.path.join(HERE, "out", "runs", name)
        if not os.path.exists(os.path.join(src, "paper.tex")):
            continue
        # 干净组：直接跑，记下非 PASS 项作为「误报」基线
        st, hf = gate_status(src)
        clean_fp.append((name, sorted(k for k, v in st.items() if v != "PASS"),
                         len(hf)))

        for kind in EXPECT:
            td = tempfile.mkdtemp(prefix="seed_%s_%s_" % (name, kind))
            for fn in os.listdir(src):
                p = os.path.join(src, fn)
                if os.path.isfile(p):
                    shutil.copy2(p, os.path.join(td, fn))
            desc = plant(kind, td)
            st2, hf2 = gate_status(td)
            tgt = EXPECT[kind]
            detected = st2.get(tgt) in ("FAIL", "WARN")
            results.append(dict(problem=name, defect=kind, expected=tgt,
                                planted=desc, status=st2.get(tgt),
                                detected=bool(detected),
                                hard_fail=len(hf2)))
            shutil.rmtree(td, ignore_errors=True)

    n = len(results)
    det = sum(1 for r in results if r["detected"])
    per = {}
    for r in results:
        k = r["defect"]
        per.setdefault(k, [0, 0])
        per[k][1] += 1
        per[k][0] += 1 if r["detected"] else 0
    fp = sum(len(x[1]) for x in clean_fp)

    res = dict(n_cases=n, detected=det,
               detection_rate=round(100.0 * det / max(1, n), 1),
               per_defect={k: dict(hit=v[0], n=v[1],
                                   rate=round(100.0 * v[0] / v[1], 1))
                           for k, v in per.items()},
               clean_nonpass=fp, clean=clean_fp, cases=results)
    json.dump(res, io.open(os.path.join(OUT, "seeded_defects.json"), "w",
                           encoding="utf-8", newline="\n"),
              ensure_ascii=False, indent=1)

    print("种子缺陷基准：%d 例，检出 %d（%.1f%%）"
          % (n, det, res["detection_rate"]))
    for k, v in res["per_defect"].items():
        print("   %-18s %d/%d  %.0f%%  -> %s"
              % (k, v["hit"], v["n"], v["rate"], EXPECT[k]))
    print()
    print("干净组非 PASS 项合计：%d（这是误报基线）" % fp)
    print("已写", os.path.join(OUT, "seeded_defects.json"))


if __name__ == "__main__":
    main()
