"""把论文里的数字统一刷新到当前测量（第 110 轮末）。

红队 F2/H3 的教训：手改数字必然漂移。这里一次替换，并把每一对写在代码里，
改不中就报。
"""
import io
import json
import os
import re

HERE = r"C:\Users\21246\Documents\deepseek-harness\default-workspace\model1-arch"
OUT = os.path.join(HERE, "out", "final")
P = os.path.join(OUT, "paper.tex")
s = io.open(P, encoding="utf-8").read()

D = json.load(io.open(os.path.join(OUT, "data.json"), encoding="utf-8"))
U = json.load(io.open(os.path.join(HERE, "out", "untraced_corpus.json"),
                      encoding="utf-8"))
A = json.load(io.open(os.path.join(OUT, "ablation.json"), encoding="utf-8"))

n_tok = sum(u["n_tokens"] for u in U)
n_unt = sum(u["n_untraced"] for u in U)
cls = {k: sum(u.get(k, 0) for u in U) for k in
       ("A_struct", "B_config", "C_year", "E_data", "D_computed")}
pct = {k: 100.0 * v / max(1, n_unt) for k, v in cls.items()}
rec_kb = round(D["record_bytes"] / 1024.0)

print("当前实测：")
print("  tokens=%d untraced=%d (%.1f%%)" % (n_tok, n_unt, 100.0 * n_unt / n_tok))
for k, v in cls.items():
    print("    %-11s %5d  %.1f%%" % (k, v, pct[k]))

PAIRS = [
    # 摘要（Problem 1）
    ("structural (41.7\\% of the untraced residue), configuration (0\\%), temporal\n"
     "label (41.7\\%), computed (16.6\\%). Only the last can be wrong in the way that\n"
     "matters, so a checker that treats all numbers alike measures the wrong thing.",
     "structural (%.1f\\%% of the untraced residue), configuration (%.1f\\%%),\n"
     "temporal label (%.1f\\%%), tabulated input data (%.1f\\%%), computed (%.1f\\%%).\n"
     "Only the last class must trace to a computation, so a checker that treats all\n"
     "numbers alike measures the wrong thing."
     % (pct["A_struct"], pct["B_config"], pct["C_year"], pct["E_data"],
        pct["D_computed"])),
    # 摘要（Problem 2）两个口径
    ("Under the gate's scope numbers trace\nat 94.1--100\\%; under a stricter scope the median is 95.0\\% and the weakest\n78.5\\%.",
     "Under the gate's scope numbers trace\nat 94.1--100\\%; under the stricter scope that counts every token, the median is\n91.0\\% and the weakest 76.3\\%."),
    # 消融（摘要）
    ("Deleting the frozen table while leaving the prose untouched drops\ntracing to 0.0\\% on all five ablated problems, so tracing is a property of the\nmechanism rather than of care.",
     "Deleting the frozen table while leaving the prose untouched drops tracing from\n81.7--94.9\\% to 10.4--12.2\\% on the five ablated problems, so tracing is a property\nof the mechanism rather than of care."),
    # §Analysis 表注
    ("our decomposition of every numeric token in the corpus",
     "our decomposition of every numeric token in the corpus"),
    # §Validation 两口径
    ("Under the gate's\nscope every problem is at or above 94.1\\%; under the stricter scope the median\nis 95.0\\% and the weakest 78.5\\%.",
     "Under the gate's\nscope every problem is at or above 94.1\\%; under the stricter scope the median\nis 91.0\\% and the weakest 76.3\\%."),
    # 消融正文
    ("with the frozen table,\n85.3--96.2\\% of numeric tokens resolve; with it deleted, 0.0\\% on all five\nproblems",
     "with the frozen table,\n81.7--94.9\\% of numeric tokens resolve; with it deleted, 10.4--12.2\\% on the\nsame five problems --- the residue is incidental, read from other artifacts in the\ndirectory, not from the frozen table"),
    # 记录体量与轮数
    ("124\\,kB engineering log covering 29 recorded\nrounds", "125\\,kB engineering log covering %d recorded\nrounds" % D["n_record_rounds"]),
    ("over 29 repair\nrounds logged in 124\\,kB", "over %d repair\nrounds logged in 125\\,kB" % D["n_record_rounds"]),
    ("from a 124\\,kB engineering log covering 29 recorded", "from a 125\\,kB engineering log covering %d recorded" % D["n_record_rounds"]),
    # 临界值
    ("about $0.218$", "about $0.2146$"),
    # Case 1 的历史数字：改成现在诚实的三次尝试
    ("Because the object being measured changed without the\nreports changing: the untraced residue fell from 278 to 199 tokens and the\ngenuinely computed untraced count from 116 to 33. A metric that moves when only\nthe parser changes is not measuring provenance, and the corrected number is the\none we report --- the median traceability of the stricter scope moved from\n93.2\\% to 95.0\\% because of this fix alone.",
     "Because the object being measured changed without the reports changing.\nThree corrections were needed, and each moved the number in the same direction:\nthe tokenizer (this case), the denominator (we had classified only the first 15\nprinted tokens per report rather than all untraced tokens, understating the\nresidue by a factor of seven), and the token classes themselves (tabulated input\ndata is not a computed result). The corrected measurement is %d tokens with\n%d untraced (%0.1f\\%%), of which %d (%.1f\\%%) are computed values with no source\n--- the number we report, and the one we can defend." %
     (n_tok, n_unt, 100.0 * n_unt / n_tok, cls["D_computed"], pct["D_computed"])),
    # 方法表里的 ablation 引用
    ("measured at 0.12\\,s per report", "measured at 0.12\\,s per report"),
]

hit = 0
for old, new in PAIRS:
    if old in s:
        s = s.replace(old, new, 1)
        hit += 1
    elif old != new:
        print("  [未命中] %s..." % old[:60].replace("\n", " "))

io.open(P, "w", encoding="utf-8", newline="\n").write(s)
print()
print("替换 %d/%d 对" % (hit, len(PAIRS)))

# 残留检查：正文里是否还有旧口径数字
for stale in ("95.0\\%", "78.5\\%", "0.0\\% (0/", "124\\,kB", "93.2\\%"):
    n = s.count(stale)
    if n:
        print("  仍需处理：%r 出现 %d 次" % (stale, n))
