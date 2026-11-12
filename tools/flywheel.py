#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""flywheel.py —— 生态飞轮的六环仪表盘。

飞轮的六环（每一环都必须能被单独测量，否则整圈空转）：

  环 1  做工作       改代码、改论文
  环 2  成果写进论文  算出来的东西必须进正文，而不是留在工件里
  环 3  红队攻       12 板独立审核（板数由 paper.tex 的 section 数决定）
  环 4  分诊          fixed、blocked、rejected、open 四态，不许混
  环 5  修           改论文 + 更新证据 + 重盖章
  环 6  台账          这一圈到底净修了几条

历史教训（每一条都是实测，不是假设）：
  · 环 2 会漏：E 让 5 篇模板卷转绿、D_computed 1053→28，论文却还写 1482/1053
  · 环 3 会**用错基准**：conclusion 板拿 out/d2026c（DWTS）的 10 问去要求
    out/final（工具论文）的结论逐条回应
  · 环 4 会自欺：写「未处理」三个字就当成关闭，40 条 finding 全报「已关闭」
  · 环 5 会有副作用：改论文让 finding 的 evidence 失效，而这种失效本身是正确行为
  · 环 1 会**假断**：run_all 实测 344 s，本工具曾用 timeout=300 → 超时被读成「断」

用法：
    python tools/flywheel.py            # 六环快照 + 缺口
    python tools/flywheel.py --log      # 同时把快照追加到 out/flywheel_ledger.jsonl
    python tools/flywheel.py --history  # 只看历史（净修曲线）
"""
import io
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

OUT = os.path.join(HERE, "out", "final")
LEDGER = os.path.join(HERE, "out", "flywheel_ledger.jsonl")


def _run(mod_args, timeout=600):
    """跑一个模块并抓 stdout（用同一解释器）。

    timeout 默认 600 s：`tests/run_all.py` 实测 **344 s**，
    早先给 300 s 会把正常的一圈读成「环 1 断」—— 仪表自己先骗人。
    """
    try:
        r = subprocess.run([sys.executable] + mod_args, capture_output=True,
                           text=True, encoding="utf-8", errors="replace",
                           timeout=timeout, cwd=HERE)
        return (r.stdout or "") + (r.stderr or ""), r.returncode
    except Exception as e:                              # noqa: BLE001
        return "运行失败: %s" % e, -1


def ring1():
    """环 1：回归 + 自攻 + E 验收。"""
    out, _ = _run(["tests/run_all.py"])
    allpass = "ALL PASS" in out
    out2, _ = _run(["tools/attack_self.py"])
    m = re.search(r"漏了\s*(\d+)/(\d+)", out2)
    attack = ("%s/%s" % (m.group(1), m.group(2))) if m else "?"
    out3, _ = _run(["tools/e_verify.py"])
    m3 = re.search(r"红题数：\s*(\d+)", out3)
    redq = m3.group(1) if m3 else "?"
    return dict(run_all=allpass, attack_missed=attack, e_red=redq,
                ok=(allpass and attack.startswith("0/") and redq == "0"))


def ring2():
    """环 2：成果有没有写进论文（两个口径 + 活变量）。"""
    out, _ = _run(["gate.py", "out/final"])
    m = re.search(r"硬 numbers\s+(\d+)/(\d+)", out)
    nums = ("%s/%s" % (m.group(1), m.group(2))) if m else "?"
    out2, _ = _run(["tools/live_vars_check.py"])
    m2 = re.search(r"(\d+) 处命中，(\d+) 处不一致", out2)
    hit, bad = (m2.group(1), m2.group(2)) if m2 else ("?", "?")
    return dict(numbers=nums, live_hit=hit, live_bad=bad,
                ok=(bad == "0"))


def ring3():
    """环 3：红队。"""
    import redteam
    r = redteam.check(OUT)
    rows = redteam.roster(OUT)
    return dict(boards=len(rows), level=r["level"],
                detail=str(r["detail"])[:160],
                ok=(len(rows) > 0))


def ring4():
    """环 4：四态分诊。"""
    import redteam
    j = json.load(io.open(os.path.join(OUT, "redteam.json"), encoding="utf-8"))
    c = dict(fixed=0, blocked=0, rejected=0, open=0)
    for r in j["reviews"]:
        for p in r.get("probes") or []:
            if p.get("verdict") == "finding":
                c[redteam._finding_disp(p, r)] = c.get(redteam._finding_disp(p, r), 0) + 1
    total = sum(c.values())
    return dict(**c, total=total,
                ok=(c["open"] == 0),
                fix_rate=(round(100.0 * (c["fixed"] + c["rejected"] + c["blocked"])
                                / total, 1) if total else 0.0))


def ring5():
    """环 5：盖章是否与当前文件一致。"""
    out, _ = _run(["gate.py", "out/final"])
    ok = re.search(r"\[OK\s*\]\s*软 stamp", out) is not None
    m = re.search(r"盖章于\s*([0-9T:\-]+)", out)
    return dict(stamp_ok=ok, stamped_at=(m.group(1) if m else "?"), ok=ok)


def ring6(hist):
    """环 6：台账 —— 这一圈比上一圈净修了几条。"""
    prev = hist[-1] if hist else None
    return dict(has_history=bool(hist), prev=None if not prev else {
        "ts": prev.get("ts"), "fixed": prev.get("fixed"), "open": prev.get("open")})


def load_hist():
    if not os.path.exists(LEDGER):
        return []
    rows = []
    for ln in io.open(LEDGER, encoding="utf-8"):
        ln = ln.strip()
        if ln:
            try:
                rows.append(json.loads(ln))
            except Exception:                           # noqa: BLE001
                pass
    return rows


def main(argv):
    hist = load_hist()

    # `--history` 只读台账，**不许**跑六环。
    # 早先的写法是先算 r1..r5 再判 --history，于是查历史会顺带跑一遍
    # run_all（实测 344 s），被当成「卡住」—— 仪表的第二个自骗。
    if "--history" in argv:
        print("飞轮台账：%d 圈" % len(hist))
        for i, h in enumerate(hist, 1):
            print("  第%2d圈 %s  fixed=%-3s open=%-3s rejected=%-2s blocked=%-2s numbers=%s"
                  % (i, str(h.get("ts", "?"))[:19], h.get("fixed"), h.get("open"),
                     h.get("rejected"), h.get("blocked"), h.get("numbers")))
        if len(hist) >= 2:
            a, b = hist[-2], hist[-1]
            print()
            print("  最近一圈变化：open %s → %s（%+d），"
                  "fixed %s → %s（%+d）"
                  % (a.get("open"), b.get("open"),
                     (b.get("open") or 0) - (a.get("open") or 0),
                     a.get("fixed"), b.get("fixed"),
                     (b.get("fixed") or 0) - (a.get("fixed") or 0)))
        return 0

    r1, r2, r3, r4, r5 = ring1(), ring2(), ring3(), ring4(), ring5()
    r6 = ring6(hist)

    print("=" * 74)
    print("生态飞轮 · 六环快照  %s" % time.strftime("%Y-%m-%dT%H:%M:%S"))
    print("=" * 74)
    print("  环1 做工作    run_all=%-3s  自攻漏=%-4s  E红题=%s   %s"
          % (r1["run_all"], r1["attack_missed"], r1["e_red"],
             "OK" if r1["ok"] else "**断**"))
    print("  环2 写进论文  numbers=%-6s 活变量 %s/%s 一致   %s"
          % (r2["numbers"], r2["live_hit"],
             ("0 不一致" if r2["live_bad"] == "0" else "%s 处不一致" % r2["live_bad"]),
             "OK" if r2["ok"] else "**断**"))
    print("  环3 红队攻    %d 板 · %s   %s"
          % (r3["boards"], r3["level"], "OK" if r3["ok"] else "**断**"))
    print("  环4 分诊      fixed=%-3d blocked=%-2d rejected=%-2d open=%-3d"
          "  处置率 %.1f%%   %s"
          % (r4["fixed"], r4["blocked"], r4["rejected"], r4["open"],
             r4["fix_rate"], "OK" if r4["ok"] else "**断（还有未处理）**"))
    print("  环5 修        stamp=%-3s（%s）   %s"
          % (r5["stamp_ok"], r5["stamped_at"],
             "OK" if r5["ok"] else "**断**"))
    print("  环6 台账      %s"
          % ("有历史 %d 圈" % len(hist) if hist else "首次运行（本条即第 1 圈）"))

    breaks = [k for k, v in (("环1", r1), ("环2", r2), ("环5", r5)) if not v["ok"]]
    if not r4["ok"]:
        breaks.append("环4")
    print()
    print("  断点：%s" % ("、".join(breaks) if breaks else "无（飞轮整圈通）"))
    if not r4["ok"]:
        print("  环4 的 %d 条 open 是**论文的真实缺陷**，不是仪表故障 —— "
              "逐条见 tools/audit_findings.py" % r4["open"])

    if "--log" in argv:
        tex = os.path.join(OUT, "paper.tex")
        # 第 123 轮：加 paper_bytes / paper_mtime —— finding 计数反映不出
        # 「这一圈到底改没改论文」。实测第 3 圈修完了 deployment 的三处秒数
        # 和一处 caption 残句，但 fixed/open 一个没动（该条上一圈已标 fixed，
        # 是我标早了），只有 numbers 从 36/36 变 37/37 留下了痕迹。
        rec = dict(ts=time.strftime("%Y-%m-%dT%H:%M:%S"),
                   run_all=r1["run_all"], attack=r1["attack_missed"],
                   e_red=r1["e_red"], numbers=r2["numbers"],
                   live_bad=r2["live_bad"], boards=r3["boards"],
                   fixed=r4["fixed"], blocked=r4["blocked"],
                   rejected=r4["rejected"], open=r4["open"],
                   fix_rate=r4["fix_rate"], stamp=r5["stamp_ok"],
                   paper_bytes=(os.path.getsize(tex) if os.path.exists(tex) else None),
                   paper_mtime=(time.strftime("%H:%M:%S",
                                time.localtime(os.path.getmtime(tex)))
                                if os.path.exists(tex) else None))
        with io.open(LEDGER, "a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print()
        print("  已追加台账 → out/flywheel_ledger.jsonl（第 %d 圈）" % (len(hist) + 1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
