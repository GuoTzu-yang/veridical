#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
能力档位（capability）：描述「环境有什么」与「任务要什么」

已有的 L0~L3（harness.ENV_LEVELS）只回答**工具齐不齐**：
有源码 / 有可执行 / 能联网。它不回答**能力**：

    能不能模拟 1 亿行？      能不能跑 100 并发？
    CPU 架构是什么？          集群几个节点？      外网通不通？

于是出现过这种事：环境判成 L3「完整（可联网 + 可执行 + 有源码）」，
任务要 1 亿行，实际根本装不下——L3 这个标签没有错，它只是**没回答这个问题**。

本模块补的就是这一段。判据只有三态，和 precheck 一个语义：

    True    实测够（或者任务压根没要求这个维度）
    False   实测不够
    None    没测到 —— **不是「不够」**

三条硬规矩，写死在结构里：
    1. 能测的真测：架构、并发、可物化行数、可用内存，全是本地真跑出来的数
    2. 测不了的标 unknown：集群节点数单机看不到，就写 unknown，不填 1
    3. 「低于需求」不等于「做不到」：实测值常常只是**下限**（at_least），
       下限小于需求只说明没证到够，不构成否定——这种情况给 None

跑法：python capability.py
"""

from __future__ import annotations

import os
import platform
import shutil
import sys
import threading
import time
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# 维度
# ---------------------------------------------------------------------------
# 五个维度，少一个都会留下「L3 但干不了」的缝。
DIMENSIONS = ("scale", "concurrency", "arch", "nodes", "network")

DIM_DESC = {
    "scale": "一次性可处理的行数量级",
    "concurrency": "可同时存活的线程数",
    "arch": "CPU 架构",
    "nodes": "集群节点数",
    "network": "能否访问外网",
}

# 值的来源。只有 measured 才配当「实测」；declared 是别人告诉我的。
SOURCES = ("measured", "declared", "unknown")
# 实测值的强弱：exact=确知上界；at_least=只证到「至少这么多」。
BOUNDS = ("exact", "at_least")


@dataclass(frozen=True)
class Dim:
    """一个维度的取值。

    value  —— 值；unknown 时必须为 None
    source —— measured（本机真测）/ declared（题面声明）/ unknown（没测到）
    bound  —— exact（确知）/ at_least（只有下限）
    note   —— 这个数是怎么来的，写清楚，别人才能复核
    """

    value: object = None
    source: str = "unknown"
    bound: str = "exact"
    note: str = ""

    def __post_init__(self) -> None:
        if self.source not in SOURCES:
            raise ValueError(f"未知来源 {self.source!r}，可用：{SOURCES}")
        if self.bound not in BOUNDS:
            raise ValueError(f"未知强弱 {self.bound!r}，可用：{BOUNDS}")
        # 这两条是「不许瞎猜」的强制实现：
        #   标 unknown 却带值 → 那是在编；带值却标 unknown → 没人知道这数哪来的
        if self.source == "unknown" and self.value is not None:
            raise ValueError("source=unknown 时 value 必须为空，不许拿值冒充未知")
        if self.value is None and self.source != "unknown":
            raise ValueError(f"source={self.source} 却没给 value")

    def __str__(self) -> str:
        if self.source == "unknown":
            return f"unknown（{self.note or '未测'}）"
        mark = "≥" if self.bound == "at_least" else "="
        return f"{mark}{self.value}"


def measured(value, note: str = "", bound: str = "exact") -> Dim:
    return Dim(value, "measured", bound, note)


def declared(value, note: str = "") -> Dim:
    return Dim(value, "declared", "exact", note)


def unknown(note: str = "") -> Dim:
    return Dim(None, "unknown", "exact", note)


# ---------------------------------------------------------------------------
# Capability：环境有什么 / 任务要什么，用同一个结构描述
# ---------------------------------------------------------------------------
@dataclass
class Capability:
    """一组维度取值。

    环境侧：能测的全是 measured，测不到的留着 unknown。
    任务侧：全是 declared，表示「题面要求这个」。

    两侧共用一个结构，是为了让 fits() 只写一份比较逻辑——
    否则「环境说 8 核」和「任务要 8 线程」两套类型，迟早对不上。
    """

    label: str = ""
    dims: dict[str, Dim] = field(default_factory=dict)
    facts: dict[str, Dim] = field(default_factory=dict)   # 辅助实测事实（内存/磁盘/核数）

    def __post_init__(self) -> None:
        for k in self.dims:
            if k not in DIMENSIONS:
                raise ValueError(f"未知维度 {k!r}，可用：{DIMENSIONS}")

    def dim(self, name: str) -> Dim:
        """取一个维度；没探测过就是 unknown，不返回 None 让调用方自己编。"""
        return self.dims.get(name) or unknown("未探测")

    def fact(self, name: str) -> Dim | None:
        """辅助事实：没有就是 None（调用方必须显式处理缺失）。"""
        return self.facts.get(name)

    def missing(self) -> list[str]:
        return [d for d in DIMENSIONS if d not in self.dims]

    def describe(self) -> str:
        out = [f"{self.label or '能力'}："]
        for d in DIMENSIONS:
            v = self.dims.get(d)
            tail = f"   {v.note}" if v and v.note else ""
            out.append(f"  {d:<12}{DIM_DESC[d]:<22}{str(v or unknown('未探测')):<18}{tail}")
        for k, v in self.facts.items():
            if v.source == "measured":
                out.append(f"  ·{k:<11}{'':<22}{str(v):<18}{v.note}")
        return "\n".join(out)


# ---------------------------------------------------------------------------
# 探测：能测的真测，测不了的标 unknown
# ---------------------------------------------------------------------------
_ARCH_ALIAS = {
    "x86_64": "x86_64", "amd64": "x86_64", "x64": "x86_64", "em64t": "x86_64",
    "arm64": "arm64", "aarch64": "arm64", "arm64e": "arm64",
    "x86": "x86", "i386": "x86", "i486": "x86", "i586": "x86", "i686": "x86", "ia32": "x86",
    "arm": "arm", "armv7": "arm", "armv7l": "arm", "arm32": "arm",
    "ppc64": "ppc64", "ppc64le": "ppc64", "s390x": "s390x",
    "riscv64": "riscv64", "mips": "mips", "mips64": "mips",
}


def _norm_arch(s: str) -> str:
    """架构名归一：AMD64 / x86_64 / x64 是同一个东西，不归一就会误判不符。"""
    k = str(s).strip().lower()
    return _ARCH_ALIAS.get(k, k)


def probe_arch() -> Dim:
    """架构：本机能直接看到，测得了就实测，不推测。"""
    try:
        raw = platform.machine() or ""
    except Exception as e:                                  # 理论上不会发生
        return unknown(f"platform.machine 取不到：{type(e).__name__}: {e}")
    if not raw:
        return unknown("platform.machine 返回空")
    return measured(_norm_arch(raw), f"platform.machine() = {raw}", bound="exact")


def probe_memory() -> tuple[Dim, Dim]:
    """(可用内存, 总内存)，字节。

    用途是算「1 亿行 × 每行字节数」装不装得下——这个否定必须站在实测上。
    Windows 走 GlobalMemoryStatusEx，POSIX 读 /proc/meminfo，都不联网、不装包。
    """
    try:
        if os.name == "nt":
            import ctypes

            class _MemStatus(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            ms = _MemStatus()
            ms.dwLength = ctypes.sizeof(_MemStatus)
            ok = ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(ms))
            if not ok:
                return unknown("GlobalMemoryStatusEx 返回 0"), unknown("同上")
            return (measured(int(ms.ullAvailPhys), "GlobalMemoryStatusEx.ullAvailPhys"),
                    measured(int(ms.ullTotalPhys), "GlobalMemoryStatusEx.ullTotalPhys"))

        try:                                                # Linux
            vals = {}
            with open("/proc/meminfo", "r", encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    if ":" in line:
                        k, rest = line.split(":", 1)
                        num = rest.strip().split()[0]
                        vals[k.strip()] = int(num) * 1024
            if "MemAvailable" in vals and "MemTotal" in vals:
                return (measured(vals["MemAvailable"], "/proc/meminfo MemAvailable"),
                        measured(vals["MemTotal"], "/proc/meminfo MemTotal"))
        except Exception:
            pass

        avail = os.sysconf("SC_AVPHYS_PAGES") * os.sysconf("SC_PAGE_SIZE")
        total = os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE")
        return measured(int(avail), "sysconf SC_AVPHYS_PAGES"), \
            measured(int(total), "sysconf SC_PHYS_PAGES")
    except Exception as e:
        return (unknown(f"内存探测失败：{type(e).__name__}: {e}"),
                unknown(f"内存探测失败：{type(e).__name__}: {e}"))


def probe_disk_free(path: str = ".") -> Dim:
    try:
        u = shutil.disk_usage(os.path.abspath(path))
        return measured(int(u.free), f"shutil.disk_usage({path}).free")
    except Exception as e:
        return unknown(f"磁盘探测失败：{type(e).__name__}: {e}")


def probe_concurrency(max_threads: int = 256, hold_s: float = 3.0) -> Dim:
    """并发：真开线程，全部同时活着，数有多少个能同时存活。

    注意语义边界：测的是「同时驻留的线程数」，不是吞吐、也不是 IO 并发上限。
    比 os.cpu_count() 硬——核数 8 不代表只能 8 个线程，也不保证 100 个开得起来。
    """
    if max_threads < 1:
        return unknown("探针上限 < 1")
    hold = threading.Event()

    def _worker() -> None:
        hold.wait(hold_s)

    threads: list[threading.Thread] = []
    fail_at: int | None = None
    fail_msg = ""
    try:
        for i in range(1, max_threads + 1):
            t = threading.Thread(target=_worker, daemon=True)
            t.start()
            threads.append(t)
    except (RuntimeError, OSError) as e:
        fail_at = i
        fail_msg = f"{type(e).__name__}: {e}"
    finally:
        n = len(threads)
        hold.set()
        for t in threads:
            t.join(timeout=1.0)

    if n == 0:
        return unknown(f"一个线程都开不起来（{fail_msg}）")
    if fail_at is not None:
        return measured(
            n, f"实测同时存活 {n} 个线程；第 {fail_at} 个创建失败（{fail_msg}）——"
               f"容量介于 {n} 与 {fail_at - 1} 之间", bound="at_least")
    return measured(n, f"实测同时存活 {n} 个线程（探针上限 {max_threads}，未撞上限）",
                    bound="at_least")


def probe_scale(max_rows: int = 200_000, time_budget_s: float = 2.0) -> Dim:
    """规模：真在内存里物化行，翻倍加压，看能到多少行。

    这是 Python 侧的物化探针：4 字段元组/行。它不代表数据库或文件系统的规模能力，
    note 里写清楚，别把它当 1 亿行的通行证。
    一旦撞到探针上限或超时，手里只有一个**下限**——所以 bound 一律 at_least。
    """
    if max_rows < 1:
        return unknown("探针上限 < 1")
    rows: list[tuple] = []
    last = 0
    target = 0
    stop = "未开始"
    t0 = time.perf_counter()
    n = 1000
    try:
        while True:
            target = min(n, max_rows)
            while len(rows) < target:
                k = len(rows)
                rows.append((k, k * 2, f"r{k}", float(k)))
            last = target
            if target >= max_rows:
                stop = f"撞到探针上限 {max_rows:,} 行"
                break
            if time.perf_counter() - t0 > time_budget_s:
                stop = f"耗时超 {time_budget_s}s"
                break
            n *= 2
    except MemoryError:
        stop = f"MemoryError（{target:,} 行附近）"
    finally:
        del rows
    if last == 0:
        return unknown(f"第一档就没物化成功（{stop}）")
    return measured(last, f"实测在内存物化 {last:,} 行（4 字段/行），停在：{stop}",
                    bound="at_least")


def probe_nodes() -> Dim:
    """集群节点数：单机**测不到**。

    这里最容易犯的错是「就填 1」——本机是一个节点，但任务要的是集群规模，
    填 1 会让「要 100 节点」直接判成做不到。没有调度侧的证据，就是 unknown。
    """
    return unknown("单机看不到集群规模；节点数只能由调度侧声明，本模块不猜")


def probe_network(allow_connect: bool = False) -> Dim:
    """外网：默认不探。

    本模块承诺不联网，所以默认返回 unknown（并说明原因），而不是悄悄连一下。
    真要测，传 allow_connect=True，做一次 TCP 连接实测。
    """
    if not allow_connect:
        return unknown("本模块不联网，外网能力未探测（要测请显式 allow_connect=True）")
    try:
        import socket
        with socket.create_connection(("1.1.1.1", 443), timeout=3):
            pass
        return measured(True, "TCP 1.1.1.1:443 连接成功")
    except Exception as e:
        # 连不上就是实测过且失败——这才是真的「没有外网」
        return measured(False, f"TCP 1.1.1.1:443 连接失败：{type(e).__name__}: {e}")


def probe_environment(max_threads: int = 256,
                      max_rows: int = 200_000,
                      allow_connect: bool = False) -> Capability:
    """把本机的能力一次测完。测不到的照实留 unknown。"""
    avail, total = probe_memory()
    cpu = os.cpu_count()
    cap = Capability(label="本机实测能力")
    cap.dims = {
        "scale": probe_scale(max_rows=max_rows),
        "concurrency": probe_concurrency(max_threads=max_threads),
        "arch": probe_arch(),
        "nodes": probe_nodes(),
        "network": probe_network(allow_connect=allow_connect),
    }
    cap.facts = {
        "mem_avail_bytes": avail,
        "mem_total_bytes": total,
        "disk_free_bytes": probe_disk_free("."),
        "cpu_count": measured(int(cpu), "os.cpu_count()") if cpu else unknown("os.cpu_count() 返回 None"),
        "python": measured(platform.python_version(), "platform.python_version()"),
    }
    return cap


# ---------------------------------------------------------------------------
# 任务侧
# ---------------------------------------------------------------------------
def requirement(rows: int | None = None,
                concurrency: int | None = None,
                arch: str | None = None,
                nodes: int | None = None,
                network: bool | None = None,
                bytes_per_row: int | None = None,
                in_memory: bool | None = None,
                label: str = "任务需求") -> Capability:
    """任务要什么。全是 declared —— 任务侧不许混进实测值。

    bytes_per_row / in_memory 是两个**前提**：只有声明了「一次装进内存」和
    每行占多少字节，才谈得上用内存算术判「装不下」。不声明就不算，留给 None。
    """
    cap = Capability(label=label)
    if rows is not None:
        cap.dims["scale"] = declared(int(rows), "行数量级")
    if concurrency is not None:
        cap.dims["concurrency"] = declared(int(concurrency), "并发数")
    if arch is not None:
        cap.dims["arch"] = declared(str(arch), "目标架构")
    if nodes is not None:
        cap.dims["nodes"] = declared(int(nodes), "集群节点数")
    if network is not None:
        cap.dims["network"] = declared(bool(network), "是否需要外网")
    if bytes_per_row is not None:
        cap.facts["bytes_per_row"] = declared(int(bytes_per_row), "每行字节数")
    if in_memory is not None:
        cap.facts["in_memory"] = declared(bool(in_memory), "是否一次装进内存")
    return cap


# ---------------------------------------------------------------------------
# 比较：三态
# ---------------------------------------------------------------------------
VERDICT_LABEL = {True: "够", False: "不够", None: "没测到"}


def _cmp_scale(env: Capability, need: Capability) -> tuple[bool | None, str]:
    rows = int(need.dims["scale"].value)
    d = env.dim("scale")

    # 1) 已经实测到更大规模 → 够
    if d.source == "measured" and d.value is not None and int(d.value) >= rows:
        return True, f"实测已物化 {int(d.value):,} 行 ≥ 需求 {rows:,}"

    # 2) 实测且确知上界，仍小于需求 → 不够
    if d.source == "measured" and d.bound == "exact" and d.value is not None \
            and int(d.value) < rows:
        return False, f"实测上限 {int(d.value):,} 行 < 需求 {rows:,}"

    # 2b) **声明**的值明确小于需求 → 也不够。
    # 未核验只影响「说够」的资格，不影响「说不够」——
    # 声称只有 5,000 行、需求 1 亿行，核不核对都是不够。
    # 不加这条的话，核对器一挂 value 就变 None，degrade 会变成 pass。
    if d.source == "declared" and d.value is not None \
            and int(d.value) < rows:
        return False, (f"声明 {int(d.value):,} 行 < 需求 {rows:,}"
                       f"（未经核对，但声称本身已不足）")

    # 3) 内存算术。只在任务自己声明了前提时做——不替任务假设「一次装进内存」。
    bpr = need.fact("bytes_per_row")
    inmem = need.fact("in_memory")
    mem = env.fact("mem_avail_bytes")
    have_model = (bpr is not None and bpr.value
                  and inmem is not None and inmem.value is True
                  and mem is not None and mem.source == "measured" and mem.value)
    if have_model:
        need_b = rows * int(bpr.value)
        if need_b > int(mem.value):
            return False, (
                f"需求 {rows:,} 行 × 声明 {int(bpr.value)} B/行 = {need_b / 2 ** 30:.1f} GiB，"
                f"实测可用内存 {int(mem.value) / 2 ** 30:.1f} GiB → 装不下"
                f"（每行真实开销只会更大，所以这个否定只会更硬）")
        if d.source == "unknown" or (d.value is not None and int(d.value) < rows):
            return None, (
                f"内存算术上装得下（需 {need_b / 2 ** 30:.1f} GiB / 可用 "
                f"{int(mem.value) / 2 ** 30:.1f} GiB），但没实测到 {rows:,} 行这一量级")

    # 4) 剩下的一律没测到。下限小于需求 ≠ 做不到。
    if d.source == "unknown":
        return None, "规模能力没测到（既无实测行数，也没有可做的内存算术）"
    return None, (f"实测下限 {int(d.value or 0):,} 行 < 需求 {rows:,}；"
                  f"拿到的是下限，判不了够不够")


def _cmp_concurrency(env: Capability, need: Capability) -> tuple[bool | None, str]:
    n = int(need.dims["concurrency"].value)
    d = env.dim("concurrency")
    # 声明的值明确小于需求 → 不够。未核验只影响「说够」的资格，
    # 不影响「说不够」：声称只能跑 8 并发、任务要 100，核不核对都不够。
    # 必须放在 != measured 之前，否则会先被当成"没测到"返回 None。
    if d.source == "declared" and d.value is not None and int(d.value) < n:
        return False, (f"声明 {int(d.value)} 并发 < 需求 {n}"
                       f"（未经核对，但声称本身已不足）")
    if d.source != "measured" or d.value is None:
        return None, f"并发能力没测到（{d.note or '未探测'}）"

    v = int(d.value)
    if v >= n:
        return True, f"实测可同时存活 {v} 个线程 ≥ 需求 {n}"

    # 实测到「第 F 个创建失败」——那是在这个数量上真失败过，可以否定。
    fail = env.fact("concurrency_fail_at")
    if fail is not None and fail.source == "measured" and fail.value is not None \
            and n >= int(fail.value):
        return False, f"实测第 {int(fail.value)} 个线程即创建失败，任务要 {n} 并发"

    if d.bound == "exact":
        return False, f"实测上限 {v} 个线程 < 需求 {n}"
    return None, f"实测下限 {v} 个线程 < 需求 {n}；下限不构成否定"


def _cmp_arch(env: Capability, need: Capability) -> tuple[bool | None, str]:
    want = _norm_arch(str(need.dims["arch"].value))
    d = env.dim("arch")
    if d.source != "measured" or not d.value:
        return None, f"架构没测到（{d.note or '未探测'}）"
    have = _norm_arch(str(d.value))
    if have == want:
        return True, f"实测架构 {have} 与需求一致"
    return False, f"实测架构 {have} ≠ 需求 {want}"


def _cmp_nodes(env: Capability, need: Capability) -> tuple[bool | None, str]:
    n = int(need.dims["nodes"].value)
    d = env.dim("nodes")
    # 同 scale / concurrency：声称的节点数不够就不够，未核验不构成豁免。
    if d.source == "declared" and d.value is not None and int(d.value) < n:
        return False, (f"声明 {int(d.value)} 节点 < 需求 {n}"
                       f"（未经核对，但声称本身已不足）")
    if d.source != "measured" or d.value is None:
        return None, f"集群节点数没测到（{d.note or '未探测'}）"
    v = int(d.value)
    if v >= n:
        return True, f"实测节点 {v} ≥ 需求 {n}"
    if d.bound == "exact":
        return False, f"实测节点上限 {v} < 需求 {n}"
    return None, f"实测下限 {v} 个节点 < 需求 {n}；下限不构成否定"


def _cmp_network(env: Capability, need: Capability) -> tuple[bool | None, str]:
    want = bool(need.dims["network"].value)
    d = env.dim("network")
    if d.source != "measured" or d.value is None:
        return None, f"外网能力没测到（{d.note or '未探测'}）"
    have = bool(d.value)
    if have == want:
        return True, f"实测外网={'可' if have else '否'}，与需求一致"
    return False, (f"实测无外网，任务需要外网" if not have
                   else "实测有外网，任务要求断网")


_CMP = {
    "scale": _cmp_scale,
    "concurrency": _cmp_concurrency,
    "arch": _cmp_arch,
    "nodes": _cmp_nodes,
    "network": _cmp_network,
}


def fits(env: Capability, need: Capability) -> tuple[bool | None, str]:
    """环境够不够完成这个任务 → (True / False / None, 理由)。

    合并规则（顺序即语义）：
      任一维度 False            → False    有一个真的不够，就是不够
      否则任一维度 None         → None     有没测到的，就不能说够
      否则                      → True
    合并时 None 不会被 False 吞掉：没测到的维度不因为别的维度不够而变成「不够」。
    """
    lines: list[str] = []
    any_false = False
    any_none = False

    for name in DIMENSIONS:
        req = need.dims.get(name)
        if req is None:
            lines.append(f"  {name:<12}{'—':>4}  任务没声明，不算限制")
            continue
        verdict, why = _CMP[name](env, need)
        any_false = any_false or verdict is False
        any_none = any_none or verdict is None
        lines.append(f"  {name:<12}{VERDICT_LABEL[verdict]:>4}  {why}")

    overall: bool | None = False if any_false else (None if any_none else True)

    facts = []
    for k in ("bytes_per_row", "in_memory"):
        f = need.fact(k)
        if f is not None:
            facts.append(f"{k}={f.value}")
    if facts:
        lines.append(f"  声明前提：{' '.join(facts)}")

    head = f"{need.label} → {VERDICT_LABEL[overall]}"
    return overall, head + "\n" + "\n".join(lines)


def gaps(env: Capability) -> list[str]:
    """哪些维度还没测到。

    L3 被判「能力齐备」时，这一栏通常**不空**——这正是本模块存在的理由：
    档位说的是工具齐，不是能力够。
    """
    out = []
    for name in DIMENSIONS:
        d = env.dims.get(name) or unknown("未探测")
        if d.source != "measured":
            out.append(f"{name}（{DIM_DESC[name]}）：{d.note or '未探测'}")
    return out


# ---------------------------------------------------------------------------
# 自测
# ---------------------------------------------------------------------------
def selftest() -> int:
    # 本机 stdout 默认是 GBK（cp936）：中文会被下游按 UTF-8 解得乱码，
    # 少数符号（如 ▶）直接编不出来。显式切 UTF-8，不靠终端猜。
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    fails: list[str] = []

    def check(name: str, cond: bool, detail: str = "") -> None:
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  — {detail}" if detail else ""))
        if not cond:
            fails.append(name)

    def pick(why: str, key: str) -> str:
        """从 fits() 的理由里挑出真正下结论的那个维度那一行，别拿别的行充数。"""
        for line in why.splitlines():
            if line.strip().startswith(key):
                return line.strip()
        return why.splitlines()[0] if why else ""

    print("=" * 78)
    print("CAPABILITY  能力档位自测（本次全部为本机实测，不联网）")
    print("=" * 78)

    env = probe_environment()
    print()
    print(env.describe())

    print()
    print("还没测到的维度：")
    g = gaps(env)
    if g:
        for line in g:
            print(f"  · {line}")
    else:
        print("  （无）")

    # 选一个和本机不同的架构，用来验证「不符 → False」
    have_arch = _norm_arch(str(env.dim("arch").value or ""))
    other_arch = "arm64" if have_arch != "arm64" else "x86_64"

    cases = [
        ("小规模（1000 行，内存内）",
         requirement(rows=1_000, bytes_per_row=200, in_memory=True)),
        ("1 亿行（内存内，200 B/行）",
         requirement(rows=100_000_000, bytes_per_row=200, in_memory=True)),
        ("100 并发", requirement(concurrency=100)),
        ("1000 节点集群", requirement(nodes=1_000)),
        (f"{other_arch} 目标机", requirement(arch=other_arch)),
        ("要求外网", requirement(network=True)),
        ("空需求", requirement()),
    ]

    print()
    print("=" * 78)
    print("fits() 三态")
    print("=" * 78)
    results = {}
    for title, need in cases:
        label = f"{title}"
        v, why = fits(env, need)
        results[title] = v
        print()
        print(f">> {why}")
        print(f"  合计：{VERDICT_LABEL[v]}（{v}）")

    print()
    print("=" * 78)
    print("断言")
    print("=" * 78)

    # --- 结构与探测 ---
    check("五个维度齐全", set(env.dims) == set(DIMENSIONS), str(sorted(env.dims)))
    check("架构是实测值", env.dim("arch").source == "measured", str(env.dim("arch")))
    check("规模有实测值（探针真跑了）",
          env.dim("scale").source == "measured" and int(env.dim("scale").value or 0) > 0,
          str(env.dim("scale")))
    check("并发有实测值",
          env.dim("concurrency").source == "measured", str(env.dim("concurrency")))
    check("节点数是 unknown（单机测不到，不填 1）",
          env.dim("nodes").source == "unknown", env.dim("nodes").note[:40])
    check("外网默认 unknown（本模块不联网）",
          env.dim("network").source == "unknown", env.dim("network").note[:40])
    check("任务侧全部是 declared",
          all(d.source == "declared" for d in cases[1][1].dims.values()
              if d is not None), str({k: v.source for k, v in cases[1][1].dims.items()}))

    # --- 三态：够 / 不够 / 不知道 ---
    v_true, why_true = fits(env, requirement(rows=1_000, bytes_per_row=200, in_memory=True))
    check("【够】1000 行 → True", v_true is True, pick(why_true, "scale"))

    mem_ok = (env.fact("mem_avail_bytes") is not None
              and env.fact("mem_avail_bytes").source == "measured")
    v_false, why_false = fits(env, requirement(rows=100_000_000,
                                               bytes_per_row=200, in_memory=True))
    if mem_ok and int(env.fact("mem_avail_bytes").value) < 100_000_000 * 200:
        check("【不够】1 亿行装不下 → False", v_false is False, pick(why_false, "scale"))
    else:
        check("【不够】1 亿行装不下 → False", v_false is not False,
              f"内存测得 {env.fact('mem_avail_bytes')}，本机确实装得下，跳过否定断言")

    v_unknown, why_unknown = fits(env, requirement(nodes=1_000))
    check("【不知道】1000 节点 → None（不是 False）", v_unknown is None,
          pick(why_unknown, "nodes"))
    check("【不知道】不等于【不够】", v_unknown is not False)

    # --- 构造 fixture：验证 exact 与 at_least 的分界 ---
    fx_exact = Capability(label="fixture", dims={
        "concurrency": measured(8, "构造：确知上限 8", bound="exact"),
        "arch": measured("x86_64", "构造"),
        "nodes": unknown("构造"),
        "network": unknown("构造"),
        "scale": measured(1_000, "构造", bound="exact"),
    })
    v, _ = fits(fx_exact, requirement(concurrency=100))
    check("【不够】确知上限 8 < 需求 100 → False", v is False, str(v))

    fx_floor = Capability(label="fixture", dims={
        "concurrency": measured(8, "构造：只证到下限 8", bound="at_least"),
    })
    v, _ = fits(fx_floor, requirement(concurrency=100))
    check("【不知道】下限 8 < 需求 100 → None（下限不构成否定）", v is None, str(v))

    fx_net_unknown = Capability(label="fixture", dims={"network": unknown("构造：没探")})
    v, _ = fits(fx_net_unknown, requirement(network=True))
    check("【不知道】外网未探 → None", v is None, str(v))

    fx_net_off = Capability(label="fixture", dims={"network": measured(False, "构造：实测无外网")})
    v, _ = fits(fx_net_off, requirement(network=True))
    check("【不够】实测无外网 + 需要外网 → False", v is False, str(v))
    v, _ = fits(fx_net_off, requirement(network=False))
    check("实测无外网 + 任务也断网 → True", v is True, str(v))

    # --- 架构不符 ---
    v, why = fits(env, requirement(arch=other_arch))
    check(f"{other_arch} 需求 vs 本机 {have_arch} → False", v is False, pick(why, "arch"))

    # --- 空需求 ---
    v, _ = fits(env, requirement())
    check("空需求 → True（没要求就不构成限制）", v is True, str(v))

    # --- 未知维度会被点名 ---
    check("gaps() 点名 nodes", any(s.startswith("nodes") for s in g), str(g)[:60])

    # --- 结构校验：不许拿值冒充未知 ---
    bad = 0
    for attempt in ((1, "unknown"), (None, "measured"), (1, "瞎编"), (1, "measured", "瞎编")):
        try:
            Dim(*attempt)
        except ValueError:
            bad += 1
    check("非法 Dim 组合全部抛错（4/4）", bad == 4, f"{bad}/4")

    print()
    print("=" * 78)
    print("ALL PASS" if not fails else f"FAILED: {fails}")
    print("=" * 78)
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(selftest())
