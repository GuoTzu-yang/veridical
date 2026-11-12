#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mmkit.py 的回归：钉住「算 → 验 → 报告」这条接缝。

这份测试的重点不是「程序能跑」，而是**接缝处的语义没走样**：
    1. mm 算出来的偏相关，和 lanes 的方向通道判出来的，必须是同一个数
    2. 声明主张 → 可被 reject；不声明 → 最多 degrade
    3. --reproduced 才允许 pass
    4. 简单相关和偏相关方向相反时，工具必须按偏相关走
"""

from __future__ import annotations

import io
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

fails = []


def check(name, cond, detail=""):
    tag = "[PASS]" if cond else "[FAIL]"
    print(f"  {tag} {name}" + (f"  — {detail}" if detail else ""))
    if not cond:
        fails.append(name)


def run_split(args):
    """跑一次，**分开**返回 (退出码, stdout, stderr)。

    `--json` 的契约是「stdout 只有 JSON、提示全走 stderr」。
    第 109 轮之前这个 smoke 用 `run()`（把两个流合并）去 `json.loads` 整个输出，
    等于在测「合并后还能不能解析」—— 那不是契约。
    当时恰好没有提示输出到 stderr，所以一直是绿的；一加提示就红，
    而插件其实完全合规（实测 stdout 是纯 JSON）。
    """
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    env["MMKIT_DATA"] = os.path.join(ROOT, "out", "data", "heat_sink.xlsx")
    r = subprocess.run(
        [sys.executable, os.path.join(ROOT, "mmkit.py")] + args,
        capture_output=True, cwd=ROOT, env=env, timeout=600)
    dec = lambda b: (b or b"").decode("utf-8", "replace")  # noqa: E731
    return r.returncode, dec(r.stdout), dec(r.stderr)


def run(args):
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    # 测试必须固定数据文件（第 92 轮）。
    # 原来这些用例都不给 --data，全指望 find_xlsx() 在工作区里「搜到那个热阻附件」。
    # 那是一次**任意**选择：工作区有 80 多个 xlsx，顺序一变就可能搜到别的附件，
    # 于是「宽度/深高/排数 不存在」→ 整个 smoke 红掉，而代码其实没问题。
    # MMKIT_DATA 是 find_xlsx 的第一优先级分支，一处设定覆盖所有调用。
    env["MMKIT_DATA"] = os.path.join(ROOT, "out", "data", "heat_sink.xlsx")
    r = subprocess.run(
        [sys.executable, os.path.join(ROOT, "mmkit.py")] + args,
        capture_output=True, cwd=ROOT, env=env, timeout=600)
    return r.returncode, ((r.stdout or b"") + (r.stderr or b"")).decode(
        "utf-8", "replace")


def main() -> int:
    # ---------- 1 自检 ----------
    code, out = run(["selftest"])
    check("mmkit selftest 退出码 0", code == 0, f"exit={code}")
    m = re.search(r"ALL PASS\s+(\d+) 通过", out)
    check("自检断言全过", m is not None, m.group(0) if m else "没找到")

    # ---------- 2 声明主张：可 reject ----------
    code, out = run(["run", "--y", "热阻", "--x", "宽度,深高,排数",
                     "--claim", "深高:负"])
    check("带主张跑通", code == 0, f"exit={code}")
    check("出现主张段落", "你声明的主张" in out)
    check("K1 编号按声明顺序", "【K1】" in out and "【K2】" not in out,
          "只声明一条就该只有 K1")
    check("反方向主张判 reject", "闸门：reject" in out, "深高对热阻实际是正相关")
    check("direction 通道被标为否决",
          bool(re.search(r"direction\s+oppose", out)),
          "方向通道是唯一说反的")

    # ---------- 3 不声明主张：最多 degrade ----------
    code, out = run(["run", "--y", "热阻", "--x", "宽度,深高,排数"])
    check("无主张跑通", code == 0, f"exit={code}")
    check("出现提示段落", "数据提示" in out)
    check("明确写「不是结论」", "不是结论" in out)
    # 这条从 craft_smoke 迁过来：含 0 的自变量取不了对数，结构必须判不适用
    check("对数/幂律判不适用（含 0）",
          "取不了对数" in out,
          "这条消失说明数据被过滤了")
    # 注意：说明文字里本来就有 "reject"（"reject → 不许写"），
    # 所以要盯「闸门：reject」这个判决形式，不能只看关键词。
    check("无主张时不出 reject", "闸门：reject" not in out,
          "没声明方向就不该有推翻")
    check("提示表里三个自变量都在",
          out.count("（提示）") >= 3, f"{out.count('（提示）')} 处")

    # ---------- 4 --reproduced 才允许 pass ----------
    code, out = run(["run", "--y", "热阻", "--x", "宽度,深高,排数",
                     "--claim", "宽度:负"])
    check("未重跑时没有 pass", "pass" not in out.split("八、")[0]
          or "闸门：degrade" in out, "闸门那行应是 degrade")
    check("未重跑给出提示", "最高只能是 degrade" in out)
    code2, out2 = run(["run", "--y", "热阻", "--x", "宽度,深高,排数",
                       "--claim", "宽度:负", "--reproduced"])
    check("声明重跑后出现 pass", "闸门：pass" in out2, "闸门那行应是 pass")
    check("重跑声明被标成需要交代",
          "怎么重跑的" in out2, "工具不替用户背书")

    # ---------- 5 JSON 输出可机读 ----------
    # 只吃 stdout：契约是「stdout 只有 JSON，提示全走 stderr」。
    code, jout, jerr = run_split(["run", "--y", "热阻", "--x", "宽度,深高,排数",
                                  "--claim", "宽度:负", "--json"])
    ok_json = False
    _why = ""
    try:
        rep = json.loads(jout)
        ok_json = ("verify" in rep and "fit" in rep and "eda" in rep
                   and len(rep["verify"]) == 1)
        if not ok_json:
            _why = "键不全：" + str(sorted(rep)[:8])
    except Exception as e:
        _why = ("stdout 不是纯 JSON：%s；前 80 字：%r"
                % (type(e).__name__, jout[:80]))
    check("--json 的 stdout 是纯 JSON 且字段齐", ok_json,
          _why or "verify/fit/eda 都要在")
    check("提示没有污染 stdout（全在 stderr）",
          code == 0 and "标识列" in jerr, "stderr 里应有数据提示")

    # ---------- 6 多目标 ----------
    code, out = run(["run", "--y", "热阻", "--x", "宽度,深高,排数",
                     "--min", "热阻,压降,温度"])
    check("多目标跑通", code == 0, f"exit={code}")
    check("帕累托前沿 12/84", "12 / 84" in out)
    check("权重扫描给出最稳解", "#64" in out)

    # ---------- 7 约束优化（离散设计） ----------
    code, out = run(["solve", "--x", "宽度,深高,排数", "--obj", "压降",
                     "--constraint", "热阻<=0.74", "--constraint", "温度<=0.79"])
    check("solve 退出码 0", code == 0, f"exit={code}")
    check("全离散走组合搜索", "离散组合搜索" in out, "不该是连续优化")
    check("算出 120 种组合", "120 种组合" in out)
    check("给出观测最优第 62 行", "第 62 行" in out)
    check("明确说明「真做过的」", "真做过的" in out,
          "观测解和预测解必须分开说")
    check("解释为什么不用连续优化", "插值产物" in out)

    # ---------- 8 报告导出 ----------
    import tempfile
    rp = os.path.join(tempfile.gettempdir(), "mmkit_report_test.md")
    if os.path.exists(rp):
        os.remove(rp)
    code, out = run(["run", "--y", "热阻", "--x", "宽度,深高,排数",
                     "--claim", "宽度:负", "--min", "热阻,压降,温度",
                     "--out", rp])
    check("带 --out 跑通", code == 0, f"exit={code}")
    check("报告文件生成了", os.path.exists(rp), rp)
    if os.path.exists(rp):
        md = open(rp, encoding="utf-8").read()
        check("报告有标题", md.startswith("# 建模报告"), md[:40])
        for seg in ("## 一、数据体检", "## 二、结构竞速", "## 三、结论验证",
                    "## 边界声明"):
            check(f"报告含「{seg}」", seg in md)
        check("报告有表格", "|---" in md, "markdown 表格线")
        check("报告写明了 e3 状态", "e3（可复现）" in md)
        check("报告提到权重是立场",
              "取哪个值是立场" in md, "这条边界不能省")
        os.remove(rp)

    # ---------- 9 多种子竞速 ----------
    code, out = run(["race", "--y", "热阻", "--x", "宽度,深高,排数"])
    check("race 退出码 0", code == 0, f"exit={code}")
    check("竞速列出每个种子", "种子0" in out and "种子2" in out)
    check("指出换种子结论变不变",
          ("换种子结论不变" in out) or ("换种子结论就变" in out))
    check("给出残差诊断", "异方差 BP" in out and "残余结构" in out)

    # ---------- 10 机理：ODE ----------
    code, out = run(["ode", "--rhs=0.7*y", "--y0=1.0", "--t1=5"])
    check("ode 退出码 0", code == 0, f"exit={code}")
    m = re.search(r"y\(末\) = ([\d.]+)", out)
    check("ode 算出 e^3.5≈33.115", m is not None
          and abs(float(m.group(1)) - 33.115452) < 0.01,
          m.group(0) if m else "没找到")
    check("ode 声明外推边界", "区间外的预测没有依据" in out)

    # ---------- 11 机理：量纲 ----------
    code, out = run(["dim", "--var", "周期=T", "--var", "长度=L",
                     "--var", "重力=L*T^-2", "--var", "质量=M"])
    check("dim 退出码 0", code == 0, f"exit={code}")
    check("单摆算出 1 个 Pi", "独立无量纲组合 1 个" in out)
    check("Pi 里含长度与重力", "长度" in out and "重力" in out)
    check("说明变量降维", "变量个数从 4 降到 1" in out)

    # ---------- 12 安全边界 ----------
    code, out = run(["ode", "--rhs=__import__('os').system('echo x')",
                     "--t1=1"])
    check("危险表达式被拒绝（退出码非 0 或报错）",
          code != 0 or "表达式有问题" in out, f"exit={code}")

    # ---------- 13 预测（含误用识别） ----------
    code, out = run(["forecast", "--y", "热阻", "--horizon", "4"])
    check("forecast 退出码 0", code == 0, f"exit={code}")
    check("列出候选方法", "线性趋势" in out and "朴素" in out)
    check("给出留出 RMSE", "留出 RMSE" in out)
    check("给出预测区间", "95% 下界" in out and "95% 上界" in out)
    # 这份数据是横截面，工具必须自己指出来
    check("识别出这不是时间序列", "这份预测不能用" in out,
          "样本编号是 1..84，行序是编号不是时间")
    check("说明为什么不能用", "编号" in out)

    # ---------- 14 评价（不需要 y/x） ----------
    code, out = run(["run", "--cost", "热阻,压降,温度"])
    check("评价段不需要 --y/--x 也能跑", code == 0, f"exit={code}")
    check("算出熵权", "熵权法自动定" in out)
    check("给出 TOPSIS 排名", "排名" in out and "#64" in out)
    check("说明跳过了建模段", "跳过建模段" in out,
          "评价和建模是两条独立路径")

    # ---------- 15 聚类 ----------
    code, out = run(["cluster", "--x", "宽度,深高,排数"])
    check("cluster 退出码 0", code == 0, f"exit={code}")
    check("列出各 k 的轮廓系数", "轮廓系数" in out and "簇内平方和" in out)
    check("给出零模型基线", "零模型基线" in out,
          "没有基线的轮廓系数读不出意义")
    check("簇中心换回原量纲", "各簇中心（原量纲）" in out)
    # 这份数据没有自然簇数，工具必须自己说
    check("识别出数据没有自然簇数", "不建议把它写成" in out,
          "轮廓系数到上界仍在上升")

    # ---------- 16 绘图 ----------
    import tempfile as _tf
    pdir = _tf.mkdtemp(prefix="mmkit_smoke_plot_")
    for kind, extra in (
        ("scatter", ["--x", "宽度", "--y", "热阻"]),
        ("bar", ["--cost", "热阻,压降,温度"]),
        ("pareto", ["--min", "热阻,压降,温度"]),
        ("forecast", ["--y", "热阻"]),
    ):
        png = os.path.join(pdir, f"{kind}.png")
        code, out = run(["plot", "--kind", kind, "--out-png", png] + extra)
        check(f"{kind} 图生成", code == 0 and os.path.exists(png),
              f"exit={code}")
        if os.path.exists(png):
            with open(png, "rb") as fh:
                check(f"{kind} 是真 PNG",
                      fh.read(8) == b"\x89PNG\r\n\x1a\n", "magic")
    # 预测图必须带「这张图不能用」的警告
    code, out = run(["plot", "--kind", "forecast", "--y", "热阻",
                     "--out-png", os.path.join(pdir, "w.png")])
    check("预测图带上不可用警告", "这张图对应的预测不可用" in out,
          "横截面数据不该画趋势图而不解释")

    print()
    if fails:
        print(f"  失败 {len(fails)} 项：{fails}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
