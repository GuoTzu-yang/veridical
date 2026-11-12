import os, subprocess, sys
PY = sys.executable
D = "out/data/scope_test.xlsx"
CASES = [
 ("A 回归", [["mmkit.py","advise","--data",D],
             ["mmkit.py","race","--data",D,"--y","产量","--x","反应温度,操作压力","--json"],
             ["mmkit.py","solve","--data",D,"--y","产量","--x","反应温度,操作压力","--maximize","--json"],
             ["lanes.py","--data",D,"--y","产量","--x","反应温度,操作压力"],
             ["falsify.py","counter","--data",D,"--y","产量","--x","反应温度","--sign","1"]]),
 ("B 预测", [["mmkit.py","forecast","--data",D,"--t","反应温度","--y","产量","--horizon","5","--json"],
             ["mmkit.py","grey","--data",D,"--y","产量","--horizon","5","--json"]]),
 ("C 评价", [["mmkit.py","ahp","--ahp","1,3,5|1/3,1,3|1/5,1/3,1","--names","温度,压力,时间","--json"],
             ["mmkit.py","greyrel","--matrix","3,2,1|2,3,4|3,4,5","--directions","1,-1,1","--json"]]),
 ("D 多目标", [["mmkit.py","solve","--data",D,"--y","产量","--x","反应温度,操作压力","--maximize","--constraint","能耗<=54","--json"]]),
]
for name, cmds in CASES:
    print("  === %s ===" % name)
    for c in cmds:
        r = subprocess.run([PY]+c, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        # falsify 找到反例时返回 1，那是「证伪成功」，不是失败
        _expect1 = "falsify.py" in c[0]
        ok = ("OK " if (r.returncode == 0 or (_expect1 and r.returncode == 1))
              else "FAIL")
        err = ""
        if r.returncode != 0:
            err = ((r.stderr or "") + (r.stdout or "")).strip().splitlines()
            err = err[-1][:70] if err else "?"
        print("    %s %-46s %s" % (ok, " ".join(c[:2]), err))