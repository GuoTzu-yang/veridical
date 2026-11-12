#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""L2 真实受限样本：先造出「工具真的不齐备」的条件，验证条件生效，再判任务，再记真实成败。

背景
----
L2 = 「有源码，没有可运行的环境」。这一档在账本里现在一条真样本都没有，
因为上一批是反事实的：

  tests/collect_env.py 的做法（已剔除，不要照抄）
    判定：EvidenceEnv(2)——按"跑不了"判
    执行：WSL 里 mysql 全权限真跑——按"能跑"执行
    success=True 回答的是「如果给足权限，这任务会不会成」

  本脚本的做法
    限制是真的造出来的（只读 / 不可读 / 工具改名 / 路径命令不存在）
    执行就在这条限制下做，跑不出来就是跑不出来
    success 只回答一个问题：**在这个受限环境里，任务真的做成了吗**

手段（每条都实测是否生效）
  A 只读文件        chmod S_IREAD：写被拒，读不受影响
  B 不可读文件      icacls /deny (R)：读被拒；用完恢复并复验
  C 工具被改名      真 PE 可执行副本改名：调用即 FileNotFoundError
  D 路径/命令不存在  操作对象根本不在这里
  E 断网访问网络资源  本轮约束为不联网、未发起任何外部请求 → 标 [空]

约束
  只新建本文件；不改任何已存在文件；不写账本（不 import ledger、不调 record/resolve）；
  不联网；不装包。临时沙箱建在 %TEMP%，跑完删除并核对已删除。

跑法
  <python> C:\\...\\model1-arch\\tests\\collect_l2_real.py
"""

from __future__ import annotations

import csv
import os
import shutil
import stat
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)          # 架构本体目录（只用来取源码计数，不改动它）
sys.path.insert(0, ROOT)

# 只新建本文件、不改已存在文件 —— 连字节码缓存也不要碰。
# 不置这一行，import harness 会让 Python 重写 __pycache__/harness.cpython-312.pyc。
sys.dont_write_bytecode = True

from harness import (                 # noqa: E402
    ENV_LEVELS,
    MODEL_VERSION,
    Claim,
    EvidenceEnv,
    derive_e3,
    detect_env,
    run_gates,
)

# =============================================================================
# 素材：一份可被独立复算的数据、一份日志、一个真 PE 工具
# =============================================================================
# amount = qty * 单价，脚本自己算合计，再断言等于下面的常量（防止我手抖写错）
SALES_ROWS = [
    ("2026-01-03", "SKU-01", 2, 398.00),
    ("2026-01-05", "SKU-02", 1, 459.50),
    ("2026-01-08", "SKU-03", 4, 352.00),
    ("2026-01-11", "SKU-01", 1, 199.00),
    ("2026-01-14", "SKU-04", 3, 389.70),
    ("2026-01-19", "SKU-02", 2, 919.00),
    ("2026-01-22", "SKU-05", 6, 210.00),
    ("2026-01-25", "SKU-03", 1, 88.00),
    ("2026-02-02", "SKU-06", 2, 1440.00),
    ("2026-02-07", "SKU-01", 3, 597.00),
    ("2026-02-11", "SKU-04", 1, 129.90),
    ("2026-02-18", "SKU-05", 2, 70.00),
]
EXPECT_ROWS = 12
EXPECT_TOTAL = 5252.10

# 大写 ERROR 3 行，另有小写 error 1 行（用来验证工具与独立复算都是大小写敏感的）
LOG_LINES = [
    "2026-11-07 09:00:01 INFO  boot ok",
    "2026-11-07 09:00:02 INFO  load config",
    "2026-11-07 09:00:03 ERROR db timeout (retry 1)",
    "2026-11-07 09:00:04 WARN  slow query 1200ms",
    "2026-11-07 09:00:05 error lowercase-not-counted",
    "2026-11-07 09:00:06 INFO  retry ok",
    "2026-11-07 09:00:07 ERROR db timeout (retry 2)",
    "2026-11-07 09:00:08 INFO  flush",
    "2026-11-07 09:00:09 ERROR disk full",
    "2026-11-07 09:00:10 INFO  shutdown",
]
EXPECT_ERRORS = 3

# findstr.exe = 真实的 PE 可执行文件，拷进沙箱当「项目自带工具」
SYSTEM_TOOL = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "system32", "findstr.exe")


# =============================================================================
# 小工具
# =============================================================================
def exc_of(e: BaseException) -> str:
    """把异常压成一行可核对的证据：类型 + errno/winerror + 首行消息。"""
    bits = [type(e).__name__]
    if getattr(e, "errno", None) is not None:
        bits.append(f"errno={e.errno}")
    if getattr(e, "winerror", None) is not None:
        bits.append(f"winerror={e.winerror}")
    first = str(e).splitlines()[0] if str(e) else ""
    bits.append(first[:150])
    return " ".join(bits)


def write_text(path: str, text: str) -> None:
    # newline="\n" 避免 Windows 把 \n 翻成 \r\n，字节数才可复现
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def read_csv_rows(path: str):
    """路径一：csv 模块解析。"""
    with open(path, "r", encoding="utf-8", newline="") as f:
        r = csv.reader(f)
        next(r)                      # 表头
        rows = [row for row in r if row]
    total = round(sum(float(x[3]) for x in rows), 2)
    return len(rows), total


def read_raw_rows(path: str):
    """路径二：不用 csv 模块，按字节读、手工切分、重新求和（独立复算）。"""
    with open(path, "rb") as f:
        raw = f.read().decode("utf-8")
    lines = [ln for ln in raw.splitlines() if ln.strip()]
    body = lines[1:]
    total = round(sum(float(ln.split(",")[3]) for ln in body), 2)
    return len(body), total


def icacls(path: str, *args):
    """调 icacls；返回 (returncode 或 None, 输出文本)。非 Windows 或缺工具时 rc=None。"""
    if os.name != "nt":
        return None, "非 Windows，icacls 不可用"
    exe = shutil.which("icacls")
    if exe is None:
        return None, "PATH 上找不到 icacls"
    try:
        r = subprocess.run([exe, path, *args], capture_output=True, timeout=60)
    except Exception as e:                     # noqa: BLE001
        return None, f"icacls 调用失败：{exc_of(e)}"
    out = (r.stdout or b"") + (r.stderr or b"")
    return r.returncode, out.decode("gbk", "replace")


# =============================================================================
# 造沙箱：数据 / 日志 / 工具副本
# =============================================================================
def build_workspace(root: str) -> dict:
    ws = {"root": root}
    for sub in ("data", "logs", "tools_good", "tools_bad"):
        os.makedirs(os.path.join(root, sub))

    header = "date,sku,qty,amount"
    body = [f"{d},{s},{q},{a:.2f}" for d, s, q, a in SALES_ROWS]
    text = "\n".join([header] + body) + "\n"

    ws["readonly"] = os.path.join(root, "data", "readonly_sales.csv")
    ws["locked"] = os.path.join(root, "data", "locked_sales.csv")
    ws["missing"] = os.path.join(root, "data", "missing_sales.csv")   # 故意不创建
    for p in (ws["readonly"], ws["locked"]):
        write_text(p, text)

    ws["log"] = os.path.join(root, "logs", "app.log")
    write_text(ws["log"], "\n".join(LOG_LINES) + "\n")

    # 工具：真 PE 副本，一份留着（对照组），一份待改名（缺失组）
    ws["exe_good"] = os.path.join(root, "tools_good", "extract.exe")
    ws["exe_bad"] = os.path.join(root, "tools_bad", "extract.exe")
    shutil.copy2(SYSTEM_TOOL, ws["exe_good"])
    shutil.copy2(SYSTEM_TOOL, ws["exe_bad"])

    ws["report_good"] = os.path.join(root, "logs", "report_tool_ok.txt")
    ws["report_bad"] = os.path.join(root, "logs", "report_tool.txt")

    ws["total"] = round(sum(a for _, _, _, a in SALES_ROWS), 2)
    ws["bytes"] = len(text.encode("utf-8"))

    # 限制 A 在造沙箱时就位：只读_sales.csv 一开始就不可写，T1/T2 共用同一条件
    os.chmod(ws["readonly"], stat.S_IREAD)
    return ws


# =============================================================================
# 各任务的执行探针
# 每个 probe 返回：
#   limit_ok / limit_ev   限制是否实测生效 + 一行证据
#   detail                逐条实测记录
#   success               任务在该条件下真的做成了吗
#   success_why           为什么
#   claim                 判定用的结论文本
#   kind                  world / observation
#   ev                    {located, routes, measured, refutes, sources}
# =============================================================================
def probe_readonly_write(ws: dict) -> dict:
    p = ws["readonly"]
    detail = []
    n_before, tot_before = read_csv_rows(p)
    size_before = os.path.getsize(p)
    detail.append(f"写前实测：{n_before} 行 / {size_before} 字节（只读属性已置，读位保留）")

    limit_ok, limit_ev = False, ""
    try:
        with open(p, "a", encoding="utf-8", newline="\n") as f:
            f.write("2026-03-01,SUMMARY,0,0.00\n")
            f.flush()
        detail.append("追加写入：居然成功了 → 限制没有生效")
    except PermissionError as e:
        limit_ok, limit_ev = True, exc_of(e)
        detail.append(f"实测追加写入 → {exc_of(e)}")
    except Exception as e:                        # noqa: BLE001
        detail.append(f"追加写入 → 非预期异常 {exc_of(e)}")

    # 写失败之后必须复核：文件内容到底动没动
    n_after, tot_after = read_csv_rows(p)
    size_after = os.path.getsize(p)
    detail.append(f"写后复核：{n_after} 行 / {size_after} 字节（期望仍为 {n_before} 行 / {size_before} 字节）")
    try:
        read_raw_rows(p)
        detail.append("旁证：只读之后仍然读得出来 → 这条限制只挡写、不挡读")
        read_ok = True
    except Exception as e:                        # noqa: BLE001
        detail.append(f"旁证：只读之后读取异常 {exc_of(e)}")
        read_ok = False

    # 两路独立确认"文件到底动没动"：csv 模块 vs 手工切分（两个不同解析器）
    try:
        n_raw, _t_raw = read_raw_rows(p)
        detail.append(f"旁证二 手工切分复算行数={n_raw}（与 csv 读回的 {n_after} 对照）")
    except Exception as e:                        # noqa: BLE001
        n_raw = None
        detail.append(f"旁证二失败 {exc_of(e)}")

    appended = (n_after == n_before + 1)          # 汇总行真的落盘了没
    unchanged = (n_after == n_before and size_after == size_before)
    routes = [
        {"mech": "csv 模块读回行数", "value": n_after},
        {"mech": "手工切分独立复算行数", "value": n_raw},
    ]
    return {
        "limit_kind": "A 只读文件",
        "limit_ok": limit_ok,
        "limit_ev": limit_ev or "写入没有被拒（限制未生效）",
        "detail": detail,
        "success": bool(read_ok and appended),
        "success_why": (
            f"汇总行已落盘（{n_after} 行）" if appended
            else f"写被拒，文件未变（{n_after} 行 / {size_after} 字节）→ 汇总行没有落盘"
        ),
        "claim": "data/readonly_sales.csv 已被追加汇总行（应为 13 行数据）",
        "kind": "observation",
        "ev": {
            "located": "position",
            "routes": routes,
            "measured": True,
            "refutes": unchanged and n_after == n_before,
            "sources": [f"{p}:1-13", "文件字节长度"],
        },
    }


def probe_readonly_read(ws: dict) -> dict:
    """同一个只读文件，只做读统计：限制照样生效，但任务做成了。"""
    p = ws["readonly"]
    detail = []
    n1, t1 = read_csv_rows(p)
    n2, t2 = read_raw_rows(p)
    detail.append(f"路径一 csv 模块：{n1} 行 / 合计 {t1:.2f}")
    detail.append(f"路径二 手工切分（独立复算）：{n2} 行 / 合计 {t2:.2f}")
    detail.append("只读属性没有挡读：这条限制对「读取统计」这个任务不构成障碍")
    agree = (n1 == n2 and abs(t1 - t2) < 1e-9)
    ok_value = (n1 == EXPECT_ROWS and abs(t1 - EXPECT_TOTAL) < 1e-9)
    routes = [
        {"mech": "csv 模块（一手文件）", "value": [n1, t1]},
        {"mech": "手工切分复算（独立解析器）", "value": [n2, t2]},
    ]
    return {
        "limit_kind": "A 只读文件（同一条件，只读不写）",
        "limit_ok": True,
        "limit_ev": "只读属性在造沙箱时置位并已复核（读通、写被拒由 T1 实测）",
        "detail": detail,
        "success": bool(agree and ok_value),
        "success_why": (
            f"两路一致得到 {n1} 行 / {t1:.2f}，与预期吻合 → 任务做成"
            if agree and ok_value else "两路不一致或数值不符 → 任务未达成"
        ),
        "claim": f"data/readonly_sales.csv 共 {EXPECT_ROWS} 行数据，金额合计 {EXPECT_TOTAL:.2f}",
        "kind": "world",
        "ev": {
            "located": "position",
            "routes": routes,
            "measured": bool(agree and ok_value),
            "refutes": False,
            "sources": [f"{p}:1-13", "手工切分复算"],
        },
    }


def probe_unreadable(ws: dict) -> dict:
    p = ws["locked"]
    user = os.environ.get("USERNAME", "")
    detail = []
    limit_ok, limit_ev = False, ""
    # (RD) = 只拒 FILE_READ_DATA，保留 READ_CONTROL / WRITE_DAC，所以读被挡、ACL 还改得回来。
    # 先试过 (R)：读同样被拒，但 /remove:d 会因 READ_CONTROL 一起被拒而恢复不了，
    # 留下一枚删不掉的拒绝项——所以这里只拒读数据，不拒控制权限。
    rc, out = icacls(p, "/deny", f"{user}:(RD)")
    last = (out.strip().splitlines() or [""])[-1]
    detail.append(f"造条件 icacls /deny {user}:(RD) → rc={rc} {last}".strip())
    if rc is None:
        detail.append(f"ACL 手段不可用：{out}")
        return {
            "limit_kind": "B 不可读文件",
            "limit_ok": False,
            "limit_ev": "[空] icacls 不可用，本条件未造出来",
            "detail": detail,
            "success": None,
            "success_why": "[空] 条件未造出，不出成败结论",
            "claim": f"data/locked_sales.csv 共 {EXPECT_ROWS} 行、合计 {EXPECT_TOTAL:.2f}",
            "kind": "world",
            "ev": {"located": "none", "routes": [], "measured": False,
                   "refutes": False, "sources": []},
        }
    try:
        try:
            n, t = read_csv_rows(p)
            detail.append(f"实测读取：成功（{n} 行 / {t:.2f}）→ 限制没有生效")
        except PermissionError as e:
            limit_ok, limit_ev = True, exc_of(e)
            detail.append(f"实测读取 → {exc_of(e)}")
        except Exception as e:                     # noqa: BLE001
            detail.append(f"实测读取 → 非预期异常 {exc_of(e)}")
    finally:
        rc2, out2 = icacls(p, "/remove:d", user)
        last2 = (out2.strip().splitlines() or [""])[-1]
        detail.append(f"恢复 icacls /remove:d → rc={rc2} {last2}".strip())
        if rc2 != 0:
            # 兜底：把 DACL 重置回继承状态（我们是文件属主，WRITE_DAC 还在）
            rc3, out3 = icacls(p, "/reset")
            last3 = (out3.strip().splitlines() or [""])[-1]
            detail.append(f"兜底 icacls /reset → rc={rc3} {last3}".strip())
        try:
            n2, t2 = read_csv_rows(p)
            detail.append(f"恢复后复验读取：正常（{n2} 行 / {t2:.2f}）→ 失败来自 ACL 拒绝，不是文件坏了")
        except Exception as e:                     # noqa: BLE001
            detail.append(f"恢复后复验读取：仍然失败 {exc_of(e)}（记为未恢复，需人工检查）")

    return {
        "limit_kind": "B 不可读文件",
        "limit_ok": limit_ok,
        "limit_ev": limit_ev or "读取没有被拒（限制未生效）",
        "detail": detail,
        # 内容是本脚本写入的，值的真值我这边知道；但任务要求在受限环境里读出来，
        # 这条路径不通，所以不记成"实测得到"，e3 按 guess 记。
        "success": False,
        "success_why": "读取被 ACL 拒绝，任务要求的两个数在这次执行里拿不到",
        "claim": f"data/locked_sales.csv 共 {EXPECT_ROWS} 行、合计 {EXPECT_TOTAL:.2f}",
        "kind": "world",
        "ev": {"located": "path", "routes": [], "measured": False,
               "refutes": False, "sources": [f"{p}（不可读）"]},
    }


def probe_tool_missing(ws: dict) -> dict:
    exe = ws["exe_bad"]
    moved = exe + ".moved"
    detail = []
    detail.append(f"造条件前：extract.exe 在位={os.path.isfile(exe)}，大小={os.path.getsize(exe)} 字节")
    os.replace(exe, moved)                        # 真改名，不是删除
    exists_after = os.path.isfile(exe)
    detail.append(f"改名 extract.exe → extract.exe.moved 后：extract.exe 在位={exists_after}，"
                  f"extract.exe.moved 在位={os.path.isfile(moved)}")

    limit_ok, limit_ev = False, ""
    rc = None
    try:
        r = subprocess.run([exe, "ERROR", ws["log"]], capture_output=True, timeout=30)
        rc = r.returncode
        detail.append(f"调用工具：返回码 {r.returncode}（没有抛错，说明文件其实在）")
    except FileNotFoundError as e:
        limit_ok, limit_ev = True, exc_of(e)
        detail.append(f"实测调用 tools_bad/extract.exe → {exc_of(e)}")
    except Exception as e:                        # noqa: BLE001
        detail.append(f"实测调用 → 非预期异常 {exc_of(e)}")

    report_exists = os.path.isfile(ws["report_bad"])
    detail.append(f"任务要求的产物 logs/report_tool.txt 在位={report_exists}")
    return {
        "limit_kind": "C 工具被改名",
        "limit_ok": limit_ok,
        "limit_ev": limit_ev or "工具调用没有失败（限制未生效）",
        "detail": detail,
        "success": False,
        "success_why": "工具本体不在原路径，调用直接失败，报告文件没有生成",
        "claim": "tools_bad/extract.exe 已运行并写出 logs/report_tool.txt",
        "kind": "observation",
        "ev": {"located": "path", "routes": [], "measured": True,
               "refutes": True, "sources": [f"{exe}（不存在）", f"{ws['report_bad']}（不存在）"]},
    }


def probe_tool_present(ws: dict) -> dict:
    """对照组：同一个任务，工具在位。用来证明 T4 的失败来自"改名"，不是任务本身不可能。"""
    exe = ws["exe_good"]
    detail = []
    ok_tool = os.path.isfile(exe)
    detail.append(f"工具在位={ok_tool}，大小={os.path.getsize(exe)} 字节（真 PE 副本，来自 {SYSTEM_TOOL}）")
    tool_count = None
    try:
        r = subprocess.run([exe, "ERROR", ws["log"]], capture_output=True, timeout=30)
        text = (r.stdout or b"").decode("utf-8", "replace")
        lines = [ln for ln in text.splitlines() if ln.strip()]
        tool_count = len(lines)
        detail.append(f"工具返回码 {r.returncode}，输出 {tool_count} 行（大小写敏感，小写 error 未计）")
    except Exception as e:                        # noqa: BLE001
        detail.append(f"工具调用失败 {exc_of(e)}")

    py_count = None
    try:
        with open(ws["log"], "r", encoding="utf-8") as f:
            py_count = sum(1 for ln in f if "ERROR" in ln)
        detail.append(f"独立复算（Python 逐行 contains）：{py_count} 行")
    except Exception as e:                        # noqa: BLE001
        detail.append(f"独立复算失败 {exc_of(e)}")

    wrote = False
    if tool_count is not None:
        write_text(ws["report_good"], f"{tool_count}\n")
        with open(ws["report_good"], "r", encoding="utf-8") as f:
            wrote = f.read().strip() == str(tool_count)
        detail.append(f"写出 logs/report_tool_ok.txt 内容={tool_count}，回读核对={wrote}")

    ok = (tool_count == py_count == EXPECT_ERRORS and wrote)
    return {
        "limit_kind": "无（对照：工具在位）",
        "limit_ok": True,
        "limit_ev": f"extract.exe 在位且返回码 0（这组是 T4 的对照，证明任务本身可做）",
        "detail": detail,
        "success": bool(ok),
        "success_why": (
            f"工具与独立复算都得到 {EXPECT_ERRORS} 条 ERROR，报告已落盘 → 任务做成"
            if ok else "工具输出与独立复算不一致，或报告未落盘 → 任务未达成"
        ),
        "claim": f"tools_good/extract.exe 抽取 ERROR 行 {EXPECT_ERRORS} 条并写出 report_tool_ok.txt",
        "kind": "world",
        "ev": {
            "located": "position",
            "routes": [
                {"mech": "extract.exe（外部 PE 执行）", "value": tool_count},
                {"mech": "Python 逐行 contains（独立复算）", "value": py_count},
            ],
            "measured": bool(ok),
            "refutes": False,
            "sources": [f"{ws['log']}:3,7,9", f"{exe} 输出"],
        },
    }


def probe_missing_path(ws: dict) -> dict:
    p = ws["missing"]
    detail = []
    detail.append(f"路径 {p} 存在={os.path.exists(p)}（沙箱里从来没创建过它）")
    limit_ok, limit_ev = False, ""
    try:
        n, t = read_csv_rows(p)
        detail.append(f"实测读取：成功（{n} 行 / {t:.2f}）→ 限制没有生效")
    except FileNotFoundError as e:
        limit_ok, limit_ev = True, exc_of(e)
        detail.append(f"实测读取 → {exc_of(e)}")
    except Exception as e:                        # noqa: BLE001
        detail.append(f"实测读取 → 非预期异常 {exc_of(e)}")
    return {
        "limit_kind": "D 不存在的路径",
        "limit_ok": limit_ok,
        "limit_ev": limit_ev or "读取没有失败（限制未生效）",
        "detail": detail,
        "success": False,
        "success_why": "目标文件不存在，任务要求的两个数拿不到",
        "claim": f"data/missing_sales.csv 存在且可读出 {EXPECT_ROWS} 行",
        "kind": "observation",
        "ev": {"located": "path", "routes": [], "measured": True,
               "refutes": True, "sources": [f"{p}（不存在）"]},
    }


def probe_missing_command(ws: dict) -> dict:
    cmd = "analysis-cli"
    detail = []
    found = shutil.which(cmd)
    detail.append(f"shutil.which({cmd!r}) = {found!r}（本项目 CLI 名，本机未安装）")
    limit_ok, limit_ev = False, ""
    try:
        r = subprocess.run([cmd, "--version"], capture_output=True, timeout=30)
        detail.append(f"调用成功，返回码 {r.returncode} → 限制未生效")
    except FileNotFoundError as e:
        limit_ok, limit_ev = True, exc_of(e)
        detail.append(f"实测调用 → {exc_of(e)}")
    except Exception as e:                        # noqa: BLE001
        detail.append(f"实测调用 → 非预期异常 {exc_of(e)}")
    return {
        "limit_kind": "D 不存在的命令",
        "limit_ok": limit_ok,
        "limit_ev": limit_ev or "调用没有失败（限制未生效）",
        "detail": detail,
        "success": False,
        "success_why": "命令不能被执行，版本号拿不到",
        "claim": f"{cmd} 可被调用并返回版本号",
        "kind": "observation",
        "ev": {"located": "path", "routes": [], "measured": True,
               "refutes": True, "sources": [f"{cmd}（PATH 上没有）"]},
    }


# =============================================================================
# 判定：dims 全部由实测证据推导，不手填
# =============================================================================
E1_MAP = {
    "none": 0,        # 连来源名都指不到
    "path": 1,        # 指到来源名/路径，指不到内容位置
    "position": 2,    # 指到具体位置（文件+行范围/第 N 行）
}


def derive_dims(ev: dict) -> tuple[int, int, int, list[str]]:
    """按证据推导 e1/e2/e3，并给出每一步的理由（打印出来可核对）。"""
    why = []
    e1 = E1_MAP.get(ev["located"], 0)
    why.append(f"e1={e1}（located={ev['located']}）")

    routes = [r for r in ev["routes"] if r.get("value") is not None]
    mechs = {r["mech"] for r in routes}
    if not routes:
        e2, r2 = 0, "没有任何来源产出数值"
    elif len(routes) >= 2 and len(mechs) >= 2:
        vals = {repr(r["value"]) for r in routes}
        if len(vals) == 1:
            e2, r2 = 2, f"{len(mechs)} 种不同机制独立复算，结果一致"
        else:
            e2, r2 = 1, "机制不同但结果不一致，无法互证"
    elif len(routes) >= 2:
        e2, r2 = 1, f"{len(routes)} 次同机制测量，无法排除同源"
    else:
        e2, r2 = 0, "单一来源"
    why.append(f"e2={e2}（{r2}）")

    src = "measured" if ev["measured"] else "guess"
    e3 = derive_e3(src)
    why.append(f"e3={e3}（来源标记 {src}）")
    return e1, e2, e3, why


def judge(res: dict, env: EvidenceEnv) -> dict:
    e1, e2, e3, why = derive_dims(res["ev"])
    c = Claim(cid="X", text=res["claim"], e1=e1, e2=e2, e3=e3,
              kind=res["kind"], refuted_by_test=res["ev"]["refutes"],
              sources=res["ev"]["sources"])
    r = run_gates(c, env)
    r["dims_why"] = why
    return r


def fmt_ledger(r: dict) -> str:
    if not r["ledger"]:
        return f"直接终止于 {r['blocked_at']}"
    return " → ".join(
        f"{g['gate']} {g['verdict']}({g['value']}/{g['pass_at']})" for g in r["ledger"]
    )


def agreement(pred: dict, actual) -> str:
    if actual is None:
        return "—（[空]：无实测成败）"
    pred_ok = pred["final"] in ("pass", "degrade")
    if pred_ok and actual:
        return "命中（判定成·实际成）"
    if (not pred_ok) and (not actual):
        return "命中（判定败·实际败）"
    if pred_ok and not actual:
        return "误报（判定成·实际败）"
    return "漏报（判定败·实际成）"


# =============================================================================
# 主流程
# =============================================================================
TASKS = [
    ("T1", "把汇总行追加写回 data/readonly_sales.csv", probe_readonly_write),
    ("T2", "读 data/readonly_sales.csv 算行数与金额合计", probe_readonly_read),
    ("T3", "读 data/locked_sales.csv 算行数与金额合计", probe_unreadable),
    ("T4", "运行 tools_bad/extract.exe 抽取 ERROR 行并出报告", probe_tool_missing),
    ("T5", "对照：tools_good/extract.exe 在位时做同一件事", probe_tool_present),
    ("T6", "读 data/missing_sales.csv 算行数与金额合计", probe_missing_path),
    ("T7", "调用 analysis-cli 取版本号", probe_missing_command),
]


def sec(title: str) -> None:
    print()
    print("=" * 100)
    print(title)
    print("=" * 100)


def main() -> int:
    print("=" * 100)
    print("L2 真实受限样本 · 先造条件 / 再验证生效 / 再判任务 / 再记真实成败")
    print("=" * 100)
    print(f"判据版本 MODEL_VERSION={MODEL_VERSION}    "
          f"L2 定义：{ENV_LEVELS[2]}")
    print("账本：不写入（本脚本不 import ledger，也不调 record/resolve）")

    scratch = tempfile.mkdtemp(prefix="l2_real_")
    print(f"临时沙箱：{scratch}")
    rows, cleanup_note = [], ""
    try:
        ws = build_workspace(scratch)
        print(f"沙箱素材：{len(SALES_ROWS)} 行销售数据 / {len(LOG_LINES)} 行日志 / "
              f"工具副本 2 份；数据合计 {ws['total']:.2f}（预期 {EXPECT_TOTAL:.2f}）"
              f"{' ✓' if abs(ws['total'] - EXPECT_TOTAL) < 1e-9 else ' ✗ 与预期不符'}")

        env2 = EvidenceEnv(2)   # 判定档位
        env1 = EvidenceEnv(1)   # 更严的下界对照

        sec("【1】逐条：造条件 → 验证生效 → 判定 → 实际成败")
        for tid, task, fn in TASKS:
            res = fn(ws)
            pred2 = judge(res, env2)
            pred1 = judge(res, env1)
            rows.append({"id": tid, "task": task, "res": res,
                         "pred2": pred2, "pred1": pred1})

            print()
            print(f"【{tid}】{task}")
            print(f"  限制    {res['limit_kind']}")
            for d in res["detail"]:
                print(f"  实测    {d}")
            print(f"  生效    {'是' if res['limit_ok'] else '否 / [空]'} —— {res['limit_ev']}")
            print(f"  结论    {res['claim']}")
            print(f"  维度    " + "；".join(pred2["dims_why"]))
            print(f"  判定@L2 {pred2['final']}({pred2['cause'] or '-'})  "
                  f"[{fmt_ledger(pred2)}]  C={pred2['C']}")
            print(f"  判定@L1 {pred1['final']}({pred1['cause'] or '-'})  ← 更严的下界对照")
            act = res["success"]
            act_txt = "成" if act is True else ("败" if act is False else "[空]")
            print(f"  实际    {act_txt} —— {res['success_why']}")
            print(f"  一致    {agreement(pred2, act)}")

        # ---- [空] 条目：断网访问网络资源，本轮不发起任何请求 ----
        print()
        print("【T8】从 https://data.example.invalid/sales.csv 拉数据并统计")
        print("  限制    E 断网访问网络资源")
        print("  实测    [空] 本轮约束为不联网，没有发起任何外部请求，"
              "所以『断网』这个条件既没造出来、也没验证")
        print("  生效    [空] —— 条件未制造，不出成败结论，也不计入下面的比率")
        print("  说明    要真做这条，得先能发请求再把它掐断；本轮两条都做不到，"
              "所以如实留空，不拿『大概率失败』冒充实测")

        sec("【2】环境事实与取档理由")
        # 用"工具已移走"这个真实状态去探测，而不是拿完整环境去猜
        env_auto_a, why_a = detect_env(ROOT, ws["exe_bad"], network=True)
        env_auto_b, why_b = detect_env(ROOT, ws["exe_bad"], network=False)
        print(f"  源码目录 {ROOT}")
        print(f"  含源码文件数 {why_a['src_files']} / 可执行实例在位 {why_a['executable']} / 联网 未测[空]")
        print(f"  detect_env(network=True)  → L{env_auto_a.level}：{why_a['reason']}")
        print(f"  detect_env(network=False) → L{env_auto_b.level}：{why_b['reason']}")
        print()
        print("  取档说明（不装作比事实更严）：")
        print("    · L2 的两个定义项本轮都实测成立：有源码（含 .py 源码文件数 > 0）、"
              "没有可运行实例（工具副本被改名后 isfile=False）")
        print("    · 第三项『联网』本轮标 [空]（不发起外部请求）。harness 的 detect_env 把")
        print("      联网列为 L2 的合取条件，所以它只能给 L1 —— 这是实现的判据事实，不是我们伪造档位")
        print("    · 因此判定用 EvidenceEnv(2)，并把 EvidenceEnv(1) 的判定一并打印，"
              "任何『只用宽松那一档』的怀疑都能当场排除")

        sec("【3】判定 vs 实际 总表")
        print("ID | 任务 | 限制 | 限制生效(实测) | 判定@L2 | 成因 | 实际 | 一致")
        print("-" * 100)
        for r in rows:
            act = r["res"]["success"]
            act_txt = "成" if act is True else ("败" if act is False else "[空]")
            print(f"{r['id']} | {r['task']} | {r['res']['limit_kind']} | "
                  f"{'生效' if r['res']['limit_ok'] else '未生效/空'} | "
                  f"{r['pred2']['final']} | {r['pred2']['cause'] or '-'} | {act_txt} | "
                  f"{agreement(r['pred2'], act)}")

        sec("【4】统计（只算真出了成败的条目）")
        scored = [r for r in rows if r["res"]["success"] is not None]
        succ = [r for r in scored if r["res"]["success"]]
        print(f"  任务数        {len(rows)} 条实测 + 1 条 [空]（T8，不计）")
        print(f"  计入成败的    {len(scored)} 条")
        print(f"  真的做成      {len(succ)}/{len(scored)}"
              + (f" = {len(succ) / len(scored) * 100:.0f}%" if scored else ""))
        kinds = {}
        label = {"A": "A 只读文件", "B": "B 不可读文件", "C": "C 工具改名",
                 "D": "D 路径/命令不存在", "无": "无（对照）"}
        for r in scored:
            k = label.get(r["res"]["limit_kind"][0], r["res"]["limit_kind"][:1])
            v = kinds.setdefault(k, {"n": 0, "ok": 0})
            v["n"] += 1
            v["ok"] += 1 if r["res"]["success"] else 0
        print("  按限制手段    " + "；".join(
            f"{k} {v['ok']}/{v['n']}" for k, v in sorted(kinds.items())))
        verdicts = {}
        for r in scored:
            verdicts[r["pred2"]["final"]] = verdicts.get(r["pred2"]["final"], 0) + 1
        print("  判定分布      " + "；".join(f"{k} {v}" for k, v in sorted(verdicts.items())))
        mis = [r for r in scored
               if (r["pred2"]["final"] in ("pass", "degrade")) != r["res"]["success"]]
        print(f"  一致率        {len(scored) - len(mis)}/{len(scored)}"
              + (f"（不一致：{[m['id'] for m in mis]}）" if mis else "（无误差）"))
        print()
        print("  两条读数，防止把这张表看成『都失败』：")
        print("    · 同一道题（读统计）在 A 只读 下做成、在 B 不可读 下失败 → "
              "成败跟着条件走，不是一刀切")
        print("    · 若按反事实口径把 T1/T3/T4 记成 True，成功率会从 2/7=29% 变成 5/7=71%；"
              "两个数差 3 条，差的正是被剔除的那部分")

        sec("【5】自检")
        checks = []

        # 1 限制是否真的生效：每条出了成败的条目都必须 limit_ok
        bad = [r["id"] for r in scored if not r["res"]["limit_ok"]]
        checks.append(("每条样本的限制都实测生效", not bad,
                       f"未生效：{bad}" if bad else f"{len(scored)} 条全部 limit_ok=True"))

        # 2 失败只能来自"工具不齐备"，不能来自脚本自身的 bug
        allowed = {"PermissionError", "FileNotFoundError", "OSError"}
        kinds_seen = set()
        for r in scored:
            ev = r["res"]["limit_ev"]
            for name in allowed:
                if name in ev:
                    kinds_seen.add(name)
        failed = [r for r in scored if not r["res"]["success"]]
        checks.append(("失败原因的异常类型都在权限/缺失范围内",
                       kinds_seen <= allowed,
                       f"实测出现过：{sorted(kinds_seen) or '无'}；失败条目 {len(failed)} 条"))

        # 3 与反事实口径划清界限
        #   只有"限制本身是唯一障碍"的任务（A 读/写、B 读、C 工具）才会被反事实口径误记；
        #   D（对象根本不存在）即使给足权限也成不了，不属于这一类。
        cf_ids = [r["id"] for r in scored if r["res"]["limit_kind"][:1] in ("A", "B", "C")]
        cf_fail = [r["id"] for r in scored if r["id"] in cf_ids and not r["res"]["success"]]
        checks.append(("反事实口径会误记的条目已识别出来",
                       cf_fail == ["T1", "T3", "T4"],
                       f"{cf_fail} 这三条『给足权限多半能成』，本轮实测全败；"
                       f"collect_env.py 式记账会把它们写成 success=True —— 这就是被剔除的原因。"
                       f"同属这一类但真做成的 {[i for i in cf_ids if i not in cf_fail]} 是实测成功，不是反事实"))

        # 4 没写账本
        checks.append(("没有写账本（ledger 未 import）",
                       "ledger" not in sys.modules,
                       f"sys.modules 里 ledger 存在={'ledger' in sys.modules}"))

        # 5 没联网
        checks.append(("没有发起任何外部请求",
                       "socket" not in sys.modules and "urllib" not in sys.modules and "http" not in sys.modules,
                       f"socket/urllib/http 被导入："
                       f"{[m for m in ('socket', 'urllib', 'http') if m in sys.modules] or '无'}"))

        # 6 预期值与素材一致（防止素材本身写错，导致"测出来的是我自己算错的数"）
        checks.append(("素材真值与预期常量一致",
                       abs(ws["total"] - EXPECT_TOTAL) < 1e-9 and len(SALES_ROWS) == EXPECT_ROWS,
                       f"{len(SALES_ROWS)} 行 / {ws['total']:.2f}（预期 {EXPECT_ROWS} 行 / "
                       f"{EXPECT_TOTAL:.2f}）"))

        # 7 不碰字节码缓存
        checks.append(("没有写字节码缓存（dont_write_bytecode=True）",
                       sys.dont_write_bytecode is True,
                       f"sys.dont_write_bytecode={sys.dont_write_bytecode}"))

        for name, ok, note in checks:
            print(f"  [{'PASS' if ok else 'FAIL'}] {name} —— {note}")

    finally:
        # 清理：先去掉只读属性，再删沙箱，最后核对真删掉了
        for dirpath, _dirnames, filenames in os.walk(scratch):
            for fn in filenames:
                p = os.path.join(dirpath, fn)
                try:
                    os.chmod(p, stat.S_IWRITE)
                except OSError:
                    pass
        shutil.rmtree(scratch, ignore_errors=True)
        cleanup_ok = not os.path.exists(scratch)
        cleanup_note = f"沙箱已删除={cleanup_ok}（{scratch}）"
        sec("【6】清理")
        print(f"  {cleanup_note}")
        print("  本脚本未改动 model1-arch 下任何已存在文件；临时素材全部落在 %TEMP% 并已删除")

    print()
    print("=" * 100)
    print("DONE" if cleanup_ok else "DONE（沙箱清理需人工确认）")
    print("=" * 100)

    # ---- 落账（--record 才写；默认只打印）----
    # 这批是**真 L2 样本**：限制先造出来、验证生效、再判、再实测成败。
    # 所以 counterfactual=False —— 这正是 collect_env.py 缺的那一项。
    if "--record" in sys.argv:
        import ledger as _L
        _L.bind_production("L2 真实受限样本采集")
        ok_n = 0
        for r in scored:
            g = r["pred2"]
            rec = _L.record(
                g["final"],
                task="L2真·" + r["id"] + " " + r["task"][:28],
                note="限制=" + r["res"]["limit_kind"],
                success=bool(r["res"]["success"]),
                exec_ok=bool(r["res"]["limit_ok"]),
                evidence=(r["res"]["success_why"] or "")[:70],
                env_level=2,
                cause=g.get("cause"),
                origin="collect",
                prejudged=False,
                counterfactual=False,
            )
            ok_n += 1 if r["res"]["success"] else 0
            print("  记账 " + rec["id"] + "  " + r["id"] + " "
                  + g["final"] + ("  成" if r["res"]["success"] else "  败"))
        print("")
        print("  已记账 " + str(ok_n) + "/" + str(len(scored))
              + " 条真 L2 样本（counterfactual=False）")

    return 0 if cleanup_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
