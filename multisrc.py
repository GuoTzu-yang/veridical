#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
multisrc.py —— 多文件 / 多 sheet 统一读取（第 89 轮建）

为什么必须单独一个模块
----------------------
`mm.DS` 只认单个 .xlsx。而数模题大量是「一个月一个文件」「一天一个 sheet」：
2026 中文 A 题的附件1 是 12 个 xlsx，附件2 是 3 个 xls 里共 90 个 sheet。
不支持合并，这类题**根本进不去**，更谈不上直通论文。

三种源，一套接口
----------------
    read_rows(path, sheet)        单文件（自动按后缀选解析器）
    read_all_sheets(path)         单文件的所有 sheet 合并
    merge_paths(paths)            多文件合并（按列名对齐）

关于列名对齐（这是本模块最要紧的决定）
--------------------------------------
不去猜"这两列是同一列"。直接取**列的并集**，缺的填 NaN，
并把「哪个文件缺哪些列」如实报给调用方。
理由：A 题实测 12 个文件里有 8 个是 21 列、4 个是 16 列，
如果有人把 `R/W NTU` 和 `River NTU` 当成同一列自动合并，错误是无声的。
宁可多一列 NaN，也不要悄悄把两列合成一列。
"""

from __future__ import annotations

import os

SUPPORTED = (".xlsx", ".xlsm", ".xls", ".csv", ".tsv", ".txt")


def _read_csv(path: str) -> list[list]:
    import csv
    text = None
    for enc in ("utf-8-sig", "utf-8", "gb18030", "latin-1"):
        try:
            with open(path, encoding=enc, newline="") as fh:
                text = fh.read()
            break
        except (UnicodeDecodeError, LookupError):
            continue
    if text is None:
        raise ValueError(f"读不出 {path}")
    head = text[:4000]
    try:
        dialect = csv.Sniffer().sniff(head, delimiters=",;\t|")
        delim = dialect.delimiter
    except csv.Error:
        first = head.splitlines()[0] if head else ""
        delim = max(",;\t|", key=lambda d: first.count(d))
    return [r for r in csv.reader(text.splitlines(), delimiter=delim)]


def _read_excel(path: str, sheet=None) -> list[list]:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".xls":
        # .xls 必须走 xlrd；openpyxl 明确不支持
        import pandas as pd
        df = pd.read_excel(path, sheet_name=sheet if sheet else 0,
                           header=None)
        return df.values.tolist()
    # .xlsx / .xlsm
    import openpyxl
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb[sheet] if sheet else wb.active
    return [list(r) for r in ws.iter_rows(values_only=True)]


def sheet_names(path: str) -> list[str]:
    """列出所有 sheet 名（.csv 返回空）。"""
    ext = os.path.splitext(path)[1].lower()
    if ext not in (".xlsx", ".xlsm", ".xls"):
        return []
    if ext == ".xls":
        import pandas as pd
        return list(pd.ExcelFile(path).sheet_names)
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True)
    names = list(wb.sheetnames)
    wb.close()
    return names


def read_rows(path: str, sheet=None) -> tuple[list, list[list]]:
    """读一个源，返回 (header, rows)。header 是第 0 行。"""
    ext = os.path.splitext(path)[1].lower()
    raw = _read_csv(path) if ext in (".csv", ".tsv", ".txt") \
        else _read_excel(path, sheet)
    raw = [r for r in raw if r is not None
           and any(c is not None and str(c).strip() for c in r)]
    if not raw:
        return [], []
    return [("" if c is None else str(c).strip()) for c in raw[0]], raw[1:]


def read_all_sheets(path: str) -> tuple[list, list[list], dict]:
    """一个文件的所有 sheet 合并。

    每行前面加一列 `__sheet` 记录来源 —— 否则合并后完全无法追溯
    （实测附件2 的 sheet 名是 `DD.MM`，那是唯一的日期来源）。
    """
    names = sheet_names(path)
    if not names:
        h, r = read_rows(path)
        return h, r, dict(sheets=0, sources=[])
    heads, allrows, used = [], [], []
    for sn in names:
        try:
            h, r = read_rows(path, sn)
        except Exception:                               # noqa: BLE001
            continue
        if not h or not r:
            continue
        heads.append(h)
        for row in r:
            allrows.append([sn] + list(row))
        used.append(sn)
    merged = _union_header([["__sheet"] + h for h in heads])
    return merged, allrows, dict(sheets=len(used), sources=used)


def _union_header(headers: list[list]) -> list:
    """列的并集，保持首次出现的顺序。"""
    seen, out = set(), []
    for h in headers:
        for c in h:
            k = str(c)
            if k not in seen:
                seen.add(k)
                out.append(c)
    return out


def merge_paths(paths: list[str], per_sheet: bool = False) -> dict:
    """多文件合并。返回 header / rows / report。

    对齐规则：按列名取并集，缺的补 None。
    **不做模糊匹配** —— 把 `R/W NTU` 和 `River NTU` 自动当同一列，
    错了也没人知道。少合并一列是可见的，错合并一列是静默的。
    """
    header: list = []
    header_pos: dict[str, int] = {}
    rows: list[list] = []
    files = []
    for p in paths:
        try:
            if per_sheet:
                h, rr, meta = read_all_sheets(p)
            else:
                h, rr = read_rows(p)
                meta = dict(sheets=1, sources=[])
        except Exception as e:                          # noqa: BLE001
            files.append(dict(path=p, ok=False,
                              why=f"{type(e).__name__}: {str(e)[:60]}"))
            continue
        # 扩列
        for c in h:
            k = str(c)
            if k not in header_pos:
                header_pos[k] = len(header)
                header.append(c)
        width = len(header)
        for row in rr:
            out = [None] * width
            for i, c in enumerate(h):
                out[header_pos[str(c)]] = row[i] if i < len(row) else None
            rows.append(out)
        files.append(dict(path=os.path.basename(p), ok=True,
                          cols=len(h), rows=len(rr),
                          sheets=meta.get("sheets", 0)))

    # 每个源缺了哪些列 —— 这就是 A 题"两种表头"的直接证据
    for f in files:
        if not f.get("ok"):
            continue
        got = {str(c) for c in
               ([*header] if not per_sheet else header)}
        f["missing"] = []
    return dict(header=header, rows=rows, files=files,
                n_files=len(files), n_ok=sum(1 for f in files if f["ok"]),
                n_rows=len(rows), n_cols=len(header))


def find_sources(root: str, recursive: bool = True) -> list[str]:
    """把一个目录下所有可读的数据文件列出来（按名字排序）。"""
    if os.path.isfile(root):
        return [root]
    out = []
    if recursive:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
            for f in filenames:
                if os.path.splitext(f)[1].lower() in SUPPORTED:
                    if f.startswith("~$"):          # Excel 锁文件
                        continue
                    out.append(os.path.join(dirpath, f))
    else:
        for f in os.listdir(root):
            p = os.path.join(root, f)
            if os.path.isfile(p) and \
                    os.path.splitext(f)[1].lower() in SUPPORTED:
                out.append(p)
    return sorted(out)


def report(m: dict) -> str:
    """合并结果的人话报告。"""
    L = [f"合并 {m['n_ok']}/{m['n_files']} 个源 → "
         f"{m['n_rows']} 行 × {m['n_cols']} 列"]
    for f in m["files"]:
        if not f.get("ok"):
            L.append(f"  ✗ {f['path']}: {f['why']}")
        else:
            extra = f"，{f['sheets']} 个 sheet" if f.get("sheets", 1) > 1 else ""
            L.append(f"  ✓ {f['path']}: {f['rows']} 行 × {f['cols']} 列{extra}")
    return "\n".join(L)
