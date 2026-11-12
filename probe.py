#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
探针：把一个任务描述真正执行一次

为什么单独成模块（第四十八轮）：
  执行逻辑原来只在 `tests/collect_io.py` 里。账本里的样本因此**无法重跑**——
  `task` 字段只是人读的描述，审计只能查账本自相矛盾，查不了"这条样本测得对不对"。

  提成本体模块后，两件事同时成立：
    1. 采集脚本和重跑审计用**同一份**执行逻辑（不会各写一套、各错一处）
    2. 样本可以只存 `{"domain":..., "task":{...}}` 这个规格，事后重跑核对

干什么：文件读/列/写、HTTP HEAD。SQL 需要 WSL，不在这一层——那类样本标"不可复现"。
"""

from __future__ import annotations

import os
import urllib.error
import urllib.request

# 哪些领域能在这里真跑。其他领域的样本重跑时如实报告"不可复现"。
# file 的 "create" 和 "write" 是同一个动作的两个叫法——判据用 create（先看父目录），
# 执行用 write。两个都收，否则 F4/F6 这类样本会被误判成"不可重跑"。
EXECUTABLE = {"file": ("read", "listdir", "write", "create", "dir"),
              "http": ("head",),
              "sql": ("query",),
              "data": ("assert",),
              "image": ("assert",),
              "explain": ("assert",)}

# data 域支持的断言。每条都是**确定性的**：读完数据、算一次、给对错。
# 这是把真题数据喂进架构的接口——题目拆成主张，主张挂上这类断言。
DATA_ASSERTS = ("row_count", "column_exists", "value_bounds",
                "corr_sign", "no_null_in", "monotone_quarters",
                "closed_curve")

# image 域支持的断言。同样是算一遍就有答案：尺寸、位深、暗像素占比。
IMAGE_ASSERTS = ("dimensions", "mode", "dark_ratio", "unique_gray_levels")

DISTRO = "Ubuntu-22.04"
TMP_WSL = "/mnt/c/Users/21246/AppData/Local/Temp"


# 各域的 do_exec 返回值**回答的是哪个问题**。这一步不能含糊：
#
#   execution —— 返回「这个操作跑通了没有」
#                对应记账里的 exec_ok；success（意图达成）是另一回事
#   assertion —— 返回「这个断言成不成立」
#                对应记账里的 success，因为断言的真假**就是**主张的真假
#
# 第五十一轮踩过：拿 execution 的尺子去比 assertion 的返回值，
# 给 5 条被推翻的真题样本报了假漂移。这是同一个混淆的第五次。
CHECK_KIND = {
    "file": "execution",
    "http": "execution",
    "sql": "execution",
    "data": "assertion",
    "image": "assertion",
    "explain": "assertion",
}


def check_kind(domain: str) -> str:
    return CHECK_KIND.get(domain, "execution")


# 各域的默认操作——规格里没写 op 时用它。


# http 和 sql 的执行方式只有一种（HEAD / 跑语句），规格里不必重复写 op。
_DEFAULT_OP = {"file": "read", "http": "head", "sql": "query",
               "data": "assert", "image": "assert", "explain": "assert"}


_READONLY_SQL = ("select", "explain", "show", "desc", "with")


def replayable(domain: str, task: dict) -> bool:
    """这条规格能不能机器重跑。

    sql 只收**无副作用**的语句（SELECT / EXPLAIN / SHOW / DESC / WITH）。
    理由：`CREATE INDEX` 第二次跑必然失败，`INSERT` 会重复插数据——
    这类语句重跑的结果和当初不同，是**语义决定的**，不是"样本漂移"。
    把它们算进重跑，只会制造假警报（第四十九轮实测踩过）。
    """
    ops = EXECUTABLE.get(domain)
    if not ops:
        return False
    op = task.get("op") or _DEFAULT_OP.get(domain)
    if op not in ops:
        return False
    if domain == "sql":
        head = (task.get("sql") or "").strip().lower()
        return head.startswith(_READONLY_SQL)
    return True


def do_exec(domain: str, task: dict) -> tuple[bool, str]:
    """真执行一次。返回 (成功与否, 依据)。

    `domain` 决定怎么执行；`file` 用 `task["op"]`，`http` 固定 HEAD，`sql` 跑一条语句。
    """
    op = task.get("op", "read")
    if domain == "file":
        return _do_file(op, task)
    if domain == "http":
        return _do_http(task)
    if domain == "sql":
        return do_exec_many("sql", [task])[0]
    if domain == "data":
        return _do_data(task)
    if domain == "image":
        return _do_image(task)
    if domain == "explain":
        return _do_explain(task)
    return False, f"没有 {domain} 域的执行器"


def do_exec_many(domain: str, tasks: list[dict]) -> list[tuple[bool, str]]:
    """批量执行，返回与 tasks 等长的结果列表。

    为什么要有批量：sql 每跑一条都要起一次 WSL（含等 seekdb 起来），
    单条调用会慢到无法接受。整批塞进**一次** WSL 调用才可行。
    """
    if domain == "sql":
        return _do_sql_batch(tasks)
    return [do_exec(domain, t) for t in tasks]


def query_rows(sql: str, db: str = "bench_l3") -> tuple[bool, list[str]]:
    """跑一条查询，取回**所有数据行**（去掉分隔线）。返回 (是否拿到, 行列表)。

    为什么需要它（第六十六轮）：
        query_scalar 只取第一格，够用于 COUNT(*) 这类。
        但 EXPLAIN 的结果是多行多列的，要判断「走没走索引」
        得把整段计划文本拿回来自己匹配。

    过滤掉纯符号行（`====`、`----`），它们来自 shell/客户端的排版，不是数据。
    """
    import subprocess
    import tempfile

    script = [
        "set -u",
        "systemctl start seekdb >/dev/null 2>&1",
        "for i in $(seq 1 40); do",
        "  mysql -h127.0.0.1 -P2881 -uroot@sys --connect-timeout=2 "
        "-e 'select 1' >/dev/null 2>&1 && break",
        "  sleep 1",
        "done",
        "if ! mysql -h127.0.0.1 -P2881 -uroot@sys --connect-timeout=3 "
        "-e 'select 1' >/dev/null 2>&1; then",
        "  echo '__NODB__'",
        "  exit 0",
        "fi",
        "mysql -h127.0.0.1 -P2881 -uroot@sys " + db + " -N -B -e " + _shq(sql)
        + " 2>&1 || echo '__FAIL__'",
    ]

    tmp = os.path.join(tempfile.gettempdir(), "m1_rows.sh")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(script))

    env = dict(os.environ)
    env["WSL_UTF8"] = "1"
    try:
        r = subprocess.run(["wsl.exe", "-d", DISTRO, "--", "bash",
                            TMP_WSL + "/m1_rows.sh"],
                           capture_output=True, timeout=420, env=env)
        out = (r.stdout or b"").decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001
        return False, [f"WSL 调用失败：{type(e).__name__}: {e}"]

    if "__NODB__" in out:
        return False, ["seekdb 起不来，取不到结果"]
    if "__FAIL__" in out:
        return False, ["语句执行失败"]

    rows = []
    for line in out.splitlines():
        s = line.strip()
        if not s:
            continue
        if set(s) <= set("=-+ "):
            continue          # 纯分隔线
        rows.append(line.rstrip())
    return True, rows


def query_scalar(sql: str, db: str = "bench_l3") -> tuple[bool, str]:
    """跑一条查询，取回**第一行第一个值**。返回 (是否拿到, 值或错误)。

    为什么需要它（第六十轮）：
        环境事实 {"scale": {"value": 5000, "from": "..."}} 里的 from 如果只是
        一句字符串，那它只是**声称**，没被验证过——一个没验证的数字能把
        有证据的结论打成 degrade，方向是反的。

        有了 query_scalar，出处就能**真跑一次对账**：说 5000 行，
        就去数一遍，对不上就拒收。

    只取标量：多列多行一律只认第一格。取不到就如实说取不到，不猜。
    """
    import subprocess
    import tempfile

    script = [
        "set -u",
        "systemctl start seekdb >/dev/null 2>&1",
        "for i in $(seq 1 40); do",
        "  mysql -h127.0.0.1 -P2881 -uroot@sys --connect-timeout=2 "
        "-e 'select 1' >/dev/null 2>&1 && break",
        "  sleep 1",
        "done",
        "if ! mysql -h127.0.0.1 -P2881 -uroot@sys --connect-timeout=3 "
        "-e 'select 1' >/dev/null 2>&1; then",
        "  echo '__NODB__'",
        "  exit 0",
        "fi",
        "mysql -h127.0.0.1 -P2881 -uroot@sys " + db + " -N -B -e " + _shq(sql)
        + " 2>&1 || echo '__FAIL__'",
    ]

    tmp = os.path.join(tempfile.gettempdir(), "m1_scalar.sh")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(script))

    env = dict(os.environ)
    env["WSL_UTF8"] = "1"
    try:
        r = subprocess.run(["wsl.exe", "-d", DISTRO, "--", "bash",
                            TMP_WSL + "/m1_scalar.sh"],
                           capture_output=True, timeout=420, env=env)
        out = (r.stdout or b"").decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001
        return False, f"WSL 调用失败：{type(e).__name__}: {e}"

    if "__NODB__" in out:
        return False, "seekdb 起不来，取不到值"
    if "__FAIL__" in out:
        return False, "语句执行失败"

    for line in out.splitlines():
        line = line.strip()
        if line:
            return True, line
    return False, "查询没有返回任何行"


def _shq(s: str) -> str:
    """塞进 bash 单引号里。"""
    return "'" + s.replace("'", "'\\''") + "'"


def _do_sql_batch(tasks: list[dict]) -> list[tuple[bool, str]]:
    """一次 WSL 调用跑完所有 SQL。

    起库 → 逐条执行 → 用标记行切分结果。
    连接失败等环境问题按 False 记，但依据里会写清楚是环境失败还是语句失败。
    """
    import subprocess
    import tempfile

    if not tasks:
        return []

    script = ["set -u",
              "systemctl start seekdb >/dev/null 2>&1",
              "for i in $(seq 1 40); do",
              "  mysql -h127.0.0.1 -P2881 -uroot@sys --connect-timeout=2 "
              "-e 'select 1' >/dev/null 2>&1 && break",
              "  sleep 1",
              "done",
              "if ! mysql -h127.0.0.1 -P2881 -uroot@sys --connect-timeout=3 "
              "-e 'select 1' >/dev/null 2>&1; then",
              "  echo 'NODB'",
              "  exit 0",
              "fi"]
    for i, t in enumerate(tasks):
        sql = (t.get("sql") or "").replace("'", "'\\''")
        script.append(f"if mysql -h127.0.0.1 -P2881 -uroot@sys -e '{sql}' "
                      f">/dev/null 2>&1; then")
        script.append(f"  echo \"R{i}=ok\"")
        script.append("else")
        script.append(f"  echo \"R{i}=fail\"")
        script.append("fi")

    tmp = os.path.join(tempfile.gettempdir(), "m1_probe_sql.sh")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(script))

    env = dict(os.environ)
    env["WSL_UTF8"] = "1"
    try:
        r = subprocess.run(["wsl.exe", "-d", DISTRO, "--", "bash",
                            TMP_WSL + "/m1_probe_sql.sh"],
                           capture_output=True, timeout=420, env=env)
        out = (r.stdout or b"").decode("utf-8", "replace") + \
              (r.stderr or b"").decode("utf-8", "replace")
    except Exception as e:
        return [(False, f"WSL 调用失败：{type(e).__name__}: {e}") for _ in tasks]

    if "NODB" in out:
        return [(False, "seekdb 起不来，这批整批不可判定") for _ in tasks]

    got: dict[int, bool] = {}
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("R") and "=" in line:
            k, _, v = line.partition("=")
            try:
                got[int(k[1:])] = (v.strip() == "ok")
            except ValueError:
                continue

    res = []
    for i, _t in enumerate(tasks):
        if i in got:
            res.append((got[i], "语句执行成功" if got[i] else "语句执行失败"))
        else:
            res.append((False, "没拿到这条的结果（可能被前一条中断）"))
    return res


def _do_file(op: str, task: dict) -> tuple[bool, str]:
    try:
        if op in ("read", "dir"):
            p = task["path"]
            if op == "dir":
                if not os.path.isdir(p):
                    return False, "不是目录" if os.path.exists(p) else "路径不存在"
                return True, f"列出 {len(os.listdir(p))} 项"
            if os.path.isdir(p):
                return False, "是目录，读不了"
            with open(p, "rb") as f:
                n = len(f.read(64))
            return True, f"读到 {n} 字节"
        if op == "listdir":
            n = len(os.listdir(task["path"]))
            return True, f"列出 {n} 项"
        if op in ("write", "create"):
            p = task["path"]
            # 不偷偷建目录：判据要求父目录已存在，执行就得遵守同一条规则。
            # 早先这里 makedirs 了，判据说"父目录不存在"、执行却能成功，
            # 两边口径不一致，F4 因此被判错。
            with open(p, "w", encoding="utf-8") as f:
                f.write("probe")
            return True, "写入成功"
    except Exception as e:
        return False, f"{type(e).__name__}: {str(e)[:60]}"
    return False, f"未知 file 操作：{op}"


def _col_values(rows: list, idx: int) -> tuple[list, int]:
    """安全取第 idx 列的数值。返回 (有效值列表, 行宽不足的行数)。

    为什么需要它（第六十二轮，真实数据逼出来的）：
        2021-B 的介质文件**表头 3 列、数据只有 2 列**（缺 k）。
        直接用 r[idx] 会 IndexError，而一个跑不完的断言
        **不等于主张成立**，更不该让整批核对挂掉。

        行宽不足时按"这行没有该列的值"处理，并把缺了几行报出来。
    """
    vals, short = [], 0
    for r in rows:
        if idx < len(r):
            if r[idx] is not None:
                vals.append(r[idx])
        else:
            short += 1
    return vals, short


def _do_data(task: dict) -> tuple[bool, str]:
    """对一份数据文件做一次确定性断言。

    这是真题投喂的接口：题目读完后拆成主张，主张挂一条这里的断言，
    执行一次就能给出「成立 / 不成立」，不靠人眼看。
    """
    path = task.get("file")
    if not path or not os.path.exists(path):
        return False, f"数据文件不存在：{path}"

    try:
        cols, rows = _read_table(path, task.get("sheet"),
                                 int(task.get("header_row", 1)))
    except Exception as e:  # noqa: BLE001
        return False, f"读表失败：{type(e).__name__}: {str(e)[:60]}"

    kind = task.get("assert")
    p = task.get("params") or {}
    low = {c.lower().strip(): i for i, c in enumerate(cols)}

    if kind == "row_count":
        n = len(rows)
        op, v = p.get("op", ">="), int(p.get("value", 0))
        ok = {">=": n >= v, ">": n > v, "<=": n <= v, "<": n < v,
              "==": n == v}.get(op, False)
        return ok, f"行数 {n} {op} {v}"

    if kind == "column_exists":
        name = (p.get("column") or "").lower()
        hit = name in low
        return hit, (f"列 {p.get('column')!r} 存在（共 {len(cols)} 列）" if hit
                     else f"列 {p.get('column')!r} 不存在；有 {cols[:8]}")

    if kind == "value_bounds":
        # 支持按列名，也支持按列序号（无表头的表只能用序号）
        idx = None
        if p.get("column_index") is not None:
            idx = int(p["column_index"])
            if not (0 <= idx < len(cols)):
                return False, f"列序号 {idx} 越界（共 {len(cols)} 列）"
        else:
            name = (p.get("column") or "").lower()
            if name not in low:
                return False, f"列 {p.get('column')!r} 不存在"
            idx = low[name]
        label = p.get("column") or f"第 {idx + 1} 列"
        vals, short = _col_values(rows, idx)
        if not vals:
            return False, (f"{label} 没有数值"
                           + (f"（{short} 行宽度不足，缺这一列）" if short else ""))
        lo, hi = min(vals), max(vals)
        ok_lo = lo >= float(p["min"]) if "min" in p else True
        ok_hi = hi <= float(p["max"]) if "max" in p else True
        return ok_lo and ok_hi, f"{label} 范围 [{lo}, {hi}]"

    if kind == "corr_sign":
        x, y = (p.get("x") or "").lower(), (p.get("y") or "").lower()
        if x not in low or y not in low:
            return False, f"列不存在：{p.get('x')!r}/{p.get('y')!r}"
        xi, yi = low[x], low[y]
        xs, ys = [], []
        for r in rows:
            if xi < len(r) and yi < len(r) and r[xi] is not None and r[yi] is not None:
                xs.append(r[xi])
                ys.append(r[yi])
        if len(xs) < 3:
            return False, f"有效样本只有 {len(xs)} 行，算不了相关"
        c = _pearson(xs, ys)
        want = p.get("expect", "positive")
        ok = (c > 0) if want == "positive" else (c < 0)
        return ok, f"corr({p.get('x')}, {p.get('y')}) = {c:.3f}，期望 {want}"

    if kind == "no_null_in":
        name = (p.get("column") or "").lower()
        if name not in low:
            return False, f"列 {p.get('column')!r} 不存在"
        idx = low[name]
        short = sum(1 for r in rows if idx >= len(r))
        nulls = sum(1 for r in rows if idx < len(r) and r[idx] is None)
        total = nulls + short
        return total == 0, (f"列 {p.get('column')!r} 空值 {nulls}/{len(rows)}"
                            + (f"，另有 {short} 行缺该列" if short else ""))

    if kind == "monotone_quarters":
        name = (p.get("column") or "").lower()
        if name not in low:
            return False, f"列 {p.get('column')!r} 不存在"
        idx = low[name]
        vals = [r[idx] for r in rows if r[idx] is not None]
        if len(vals) < 8:
            return False, f"有效点 {len(vals)} 个，太少"
        q = max(1, len(vals) // 4)
        means = [sum(vals[i:i + q]) / q for i in range(0, q * 4, q)]
        want = p.get("expect", "increasing")
        inc = all(means[i] <= means[i + 1] for i in range(len(means) - 1))
        dec = all(means[i] >= means[i + 1] for i in range(len(means) - 1))
        ok = inc if want == "increasing" else dec
        return ok, f"{p.get('column')!r} 四段均值 {[round(m, 3) for m in means]}，期望 {want}"

    if kind == "closed_curve":
        # 首点与末点是否重合（闭合曲线）。
        # 这是"看一眼觉得对"最容易出错的地方——必须算。
        if len(rows) < 2:
            return False, "点太少，判不了是否闭合"
        first = [v for v in rows[0] if v is not None]
        last = [v for v in rows[-1] if v is not None]
        if len(first) < 2 or len(last) < 2:
            return False, "首/末点没有成对坐标"
        tol = float(p.get("tol", 0.5))
        d = max(abs(a - b) for a, b in zip(first, last))
        return d <= tol, (f"首点 {first[:2]} 末点 {last[:2]} 最大差 {d:.3f}"
                          f"（容差 {tol}）")

    return False, f"未知断言 {kind!r}；支持 {DATA_ASSERTS}"


def _do_explain(task: dict) -> tuple[bool, str]:
    """验证一条查询的执行计划里有没有预期特征。

    为什么单独一个域（第六十六轮踩出来的）：
        优化类任务的结果是「走没走索引」，这是**只读、幂等**的，
        用 EXPLAIN 就能验，不需要重跑 CREATE INDEX 那种非幂等操作。

        但不能拿 `sql` 域来跑 EXPLAIN —— sql 域返回的是
        「这条语句执行成功没有」，而 EXPLAIN 永远执行成功。
        规格问的问题必须和 success 问的问题**是同一个**，
        否则重跑出来的"一致"全是假的。

    规格：{"sql": "EXPLAIN SELECT ...", "marker": "ix_"}
    返回：计划算子行里出没出现 marker。
    """
    sql = task.get("sql") or ""
    marker = (task.get("marker") or "").upper()
    if not sql or not marker:
        return False, "需要 sql 和 marker 两个字段"

    ok, rows = query_rows(sql)
    if not ok:
        return False, "取不到计划：" + (rows[0][:60] if rows else "")

    ops = []
    for ln in rows:
        s = ln.strip()
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if len(cells) < 2:
            continue
        if any(k in cells[1].upper() for k in ("SCAN", "GET", "LOOKUP")):
            name = cells[2] if len(cells) > 2 else ""
            ops.append(cells[1] + " " + name)

    if not ops:
        return False, "计划里没找到算子行"
    joined = " ".join(ops).upper()
    hit = marker in joined
    return hit, "算子=" + ops[0][:70]


def _do_image(task: dict) -> tuple[bool, str]:
    """对一张图做一次确定性断言。

    真题里图片类题目最多（2021-A 有 7 张），但以前架构完全碰不了图像。
    这四种断言都是「算一遍就知道」的，不需要任何视觉判断。
    """
    path = task.get("file")
    if not path or not os.path.exists(path):
        return False, f"图像不存在：{path}"

    try:
        from PIL import Image
        im = Image.open(path)
    except Exception as e:  # noqa: BLE001
        return False, f"打不开图像：{type(e).__name__}: {str(e)[:60]}"

    kind = task.get("assert")
    p = task.get("params") or {}

    if kind == "dimensions":
        w, h = im.size
        want_w, want_h = p.get("w"), p.get("h")
        ok = (want_w is None or w == int(want_w)) and (want_h is None or h == int(want_h))
        return ok, f"尺寸 {w}x{h}，期望 {want_w}x{want_h}"

    if kind == "mode":
        want = (p.get("expect") or "L").upper()
        ok = im.mode.upper() == want
        return ok, f"位深模式 {im.mode}，期望 {want}"

    if kind == "dark_ratio":
        g = im.convert("L")
        px = list(g.getdata())
        dark = sum(1 for v in px if v < int(p.get("threshold", 128)))
        ratio = dark / len(px) * 100 if px else 0.0
        lo = float(p.get("min", 0))
        hi = float(p.get("max", 100))
        return lo <= ratio <= hi, f"暗像素 {ratio:.1f}%，期望落在 [{lo}, {hi}]%"

    if kind == "unique_gray_levels":
        g = im.convert("L")
        n = len(set(g.getdata()))
        op, v = p.get("op", ">="), int(p.get("value", 1))
        ok = {">=": n >= v, ">": n > v, "<=": n <= v, "<": n < v,
              "==": n == v}.get(op, False)
        return ok, f"灰度级数 {n} {op} {v}"

    return False, f"未知图像断言 {kind!r}；支持 {IMAGE_ASSERTS}"


def _read_table(path: str, sheet: str | int | None = None,
                header_row: int = 1):
    """读一份表格（xlsx / xls / csv），返回 (列名列表, 行列表)。

    `header_row` 是**第几行是表头**（1 起）。默认 1。
    真题数据经常第一行是大标题、第二行才是表头——2026-B 的附件 2 就是。
    硬编码第 1 行会把标题当列名，整张表全读错。
    """
    low = path.lower()
    skip = max(0, int(header_row) - 1)

    if low.endswith(".csv"):
        import csv
        with open(path, encoding="utf-8-sig", newline="") as f:
            rd = list(csv.reader(f))
        if len(rd) <= skip:
            return [], []
        return rd[skip], [[_num(c) for c in row] for row in rd[skip + 1:]]

    if low.endswith(".xls") and not low.endswith(".xlsx"):
        import xlrd
        wb = xlrd.open_workbook(path)
        sh = wb.sheet_by_name(sheet) if isinstance(sheet, str) else \
            wb.sheet_by_index(int(sheet or 0))
        if sh.nrows <= skip:
            return [], []
        cols = [str(c.value) for c in sh.row(skip)]
        rows = [[_num(c.value) for c in sh.row(i)] for i in range(skip + 1, sh.nrows)]
        return cols, rows

    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb[sheet] if isinstance(sheet, str) and sheet in wb.sheetnames else wb.worksheets[0]
    it = ws.iter_rows(values_only=True)
    for _ in range(skip):
        try:
            next(it)
        except StopIteration:
            wb.close()
            return [], []
    try:
        cols = [str(c) if c is not None else "" for c in next(it)]
    except StopIteration:
        wb.close()
        return [], []
    rows = [[_num(c) for c in r] for r in it]
    wb.close()
    return cols, rows


def _num(v):
    """能转数字就转，转不了返回 None（缺失值）。"""
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return None


def _pearson(xs, ys) -> float:
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    dx = sum((a - mx) ** 2 for a in xs) ** 0.5
    dy = sum((b - my) ** 2 for b in ys) ** 0.5
    if dx == 0 or dy == 0:
        return 0.0
    return num / (dx * dy)


def _do_http(task: dict) -> tuple[bool, str]:
    try:
        url = task["url"]
        # 超时可按 task 指定（第 80 轮加）。
        # 默认仍是 12 秒 —— 活探测要留足网络余量；
        # 但"重跑核对"只想知道结论变没变，窗口可以短。
        timeout = float(task.get("timeout", 12))
        req = urllib.request.Request(url, method="HEAD",
                                     headers={"User-Agent": "model1-probe/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status < 400, f"HTTP {r.status}"
    except urllib.error.HTTPError as e:
        # 4xx/5xx 是"服务器回应了"——连接本身是通的
        return e.code < 400, f"HTTP {e.code}"
    except urllib.error.URLError as e:
        return False, f"连接失败：{e.reason}"
    except Exception as e:  # noqa: BLE001
        return False, f"{type(e).__name__}: {str(e)[:60]}"


def selftest() -> int:
    import tempfile
    fails = []

    def check(name, cond, detail=""):
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  — {detail}" if detail else ""))
        if not cond:
            fails.append(name)

    print("=" * 70)
    print("PROBE  执行器自测")
    print("=" * 70)
    tmp = tempfile.mkdtemp(prefix="m1_probe_")
    f_ok = os.path.join(tmp, "a.txt")
    with open(f_ok, "w", encoding="utf-8") as fh:
        fh.write("x")

    ok, why = do_exec("file", {"path": f_ok, "op": "read"})
    check("读存在的文件 → 成功", ok, why)
    ok, why = do_exec("file", {"path": os.path.join(tmp, "nope"), "op": "read"})
    check("读不存在的文件 → 失败", not ok, why)
    ok, why = do_exec("file", {"path": tmp, "op": "dir"})
    check("列目录 → 成功", ok, why)
    ok, why = do_exec("file", {"path": tmp, "op": "read"})
    check("把目录当文件读 → 失败", not ok, why)
    ok, why = do_exec("file", {"path": os.path.join(tmp, "b.txt"), "op": "write"})
    check("父目录存在时写 → 成功", ok, why)
    ok, why = do_exec("file", {"path": r"C:\no_such_root_xyz\a.txt", "op": "write"})
    check("父目录不存在时写 → 失败（不偷偷建目录）", not ok, why)

    check("file 可重跑", replayable("file", {"path": f_ok, "op": "read"}))
    check("sql 只读语句可重跑", replayable("sql", {"sql": "SELECT 1"}))
    # 没有 sql 就判不了它是不是只读——不猜，一律按不可重跑
    check("sql 缺语句不可重跑", not replayable("sql", {}))
    check("sql 写操作不可重跑",
          not replayable("sql", {"sql": "CREATE INDEX a ON b(c)"}))
    check("sql INSERT 不可重跑",
          not replayable("sql", {"sql": "INSERT INTO a VALUES (1)"}))
    check("未知域不可重跑", not replayable("nosuch", {}))
    check("file 的未知 op 不可重跑", not replayable("file", {"op": "chmod"}))
    check("data 域可重跑", replayable("data", {"file": f_ok, "assert": "row_count"}))

    # sql 批量执行（依赖 WSL + seekdb，跑不通就如实报，不当成通过）
    print()
    print("  --- sql 批量执行 ---")
    res = do_exec_many("sql", [
        {"sql": "SELECT 1"},
        {"sql": "SELECT * FROM bench_l3.no_such_table_xyz"},
    ])
    print(f"  结果: {res}")
    check("sql 批量返回等长结果", len(res) == 2, str(len(res)))
    if res[0][1].startswith("seekdb 起不来"):
        print("  （seekdb 不可用，跳过语义断言）")
    else:
        check("合法语句 → 成功", res[0][0] is True, res[0][1])
        check("查不存在的表 → 失败", res[1][0] is False, res[1][1])

    import shutil
    shutil.rmtree(tmp, ignore_errors=True)

    print()
    print("=" * 70)
    print(f"{'ALL PASS' if not fails else 'FAILED: ' + str(fails)}")
    print("=" * 70)
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(selftest())
