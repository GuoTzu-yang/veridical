#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
datapath.py —— 数据文件定位（唯一来源）

为什么单独一个文件
------------------
第 80 轮实测发现：`mmkit.py run` 跑一次要 **21.4 秒**，
剖析后发现 10.8 秒里有 **10.5 秒花在 glob 遍历目录**上，
真正算东西的时间不到 0.3 秒。

元凶是工作区里的 `knowledge-base/`：它有 **298,402 个文件**，
递归 glob `**/*.xlsx` 会把它整个走一遍。

而这个慢搜索当时在 `mm.py` 和 `lanes.py` 里**各写了一遍**，
两遍都慢。放一个模块里修一次，比在两处各修一次可靠。

三档定位（按代价从低到高）
--------------------------
    1. MMKIT_DATA 环境变量 —— 显式指定，0 成本
    2. 进程内缓存 —— 扫描一次，之后按 prefer 过滤（不是缓存"结果"）
    3. 剪枝扫描 —— 跳过 knowledge-base 这类大仓库

剪枝用 os.walk + 就地修改 dirnames（glob 的 recursive=True 做不到这个）。

缓存的是**扫描结果**，不是「最终选中的那一个」——
第一版缓存了单个路径，结果 prefer 参数在缓存命中时被忽略，
lanes.load_apmcm 要的「附件 2」拿不到，被自己的 selftest 逮住。
"""

from __future__ import annotations

import os

# 这些目录跟数模附件无关，但遍历代价极高：
# knowledge-base 有 29.8 万个文件，走一遍 3.9 秒。
# 全量 glob 一次 10.5 秒 —— 那 10 秒全在走目录，不在算东西。
SKIP_DIRS = frozenset({
    "knowledge-base", "node_modules", ".git", "__pycache__", ".venv",
    "venv", "site-packages", ".mypy_cache", ".pytest_cache", ".tox",
    "dist", "build", ".idea", ".vscode", ".ipynb_checkpoints",
})

# 优先找这些名字：数模附件几乎都叫「附件 N」
PREFERRED = ("附件", "attach", "data")

_XLSX_CACHE: list = []      # [(优先级, 绝对路径), ...]
_ANY_CACHE: list = []       # 任意文件的 [(优先级, 绝对路径), ...]

# 磁盘缓存：扫一次存下来，后续直接读。
# 第 80 轮剪枝后，单次扫描仍要 0.4 秒（4232 次 scandir）——
# 对一个反复调用的工具，这个开销每次都付不合理。
CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          ".datapath_cache.json")
# 生产缓存路径（模块加载时定下）。自检会把 CACHE_FILE 重定向到临时文件，
# 那时 _PROD_CACHE 与 CACHE_FILE 不再相等 —— 用这个差异区分
# 「生产调用」与「测试调用」，而不是去猜 base。
_PROD_CACHE = os.path.abspath(CACHE_FILE)

# 最近一次 find_xlsx 的选择记录：{path, n_candidates, prefer, ambiguous}
#
# 为什么要有：find_xlsx 扫的是**整个工作区**，工作区里有 20 多个 xlsx
# （23 道题的数据 + 题库附件）。不传 prefer 时它返回遍历顺序的第一个 ——
# 对每道题都返回同一个文件，而且**永远不返回空**，所以选错了毫无提示。
# 第 83 轮为此白跑一轮（22/23 的泄漏检查其实查的是同一张表）。
# 函数契约不改（自检钉住了「匹配不到就退回默认」），但把选择**记下来**，
# 让 CLI 层能如实说一句「工作区里有 N 个 xlsx，我用的是这一个」。
LAST_PICK: dict = {}


def _load_disk_cache() -> list:
    """读磁盘缓存。坏文件当没有，不报错。"""
    try:
        import json
        with open(CACHE_FILE, encoding="utf-8") as fh:
            obj = json.load(fh)
        paths = obj.get("xlsx") or []
        # 至少第一条还得在，否则缓存过期
        if paths and os.path.exists(paths[0]):
            return [(0 if any(p in os.path.basename(x) for p in PREFERRED)
                     else 1, x) for x in paths]
    except Exception:
        pass
    return []


def _default_base() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _save_disk_cache(hits: list, base: str | None = None) -> None:
    """把扫描结果落到磁盘缓存。

    **只缓存默认根那次扫描**（第 92 轮）：
    `_XLSX_CACHE` 与磁盘缓存是全局单份，而 find_xlsx 允许传任意 base。
    于是任何一次「扫别的目录」（临时目录、另一个项目、别人的附件包）
    都会把这个共享缓存**覆盖**成那批路径，之后工作区里的正常调用
    就会去找一个不相干的文件。

    实测事故：我用临时目录探行为，一句 `find_xlsx(base=临时目录)` 把
    三个假 .xlsx 写进了缓存；随后 `mmkit.py advise`（不带 --data）
    返回那个假文件，openpyxl 抛 BadZipFile 直接崩。

    别的 base 只留在内存里，进程结束即弃。要强制重扫用 MMKIT_REFRESH=1。

    判定用「写的是不是**生产缓存文件**」（`_PROD_CACHE`），而不是猜 base：
    自检会把 CACHE_FILE 重定向到临时文件，那时两条路径不等，
    属于测试调用，照常写；只有往生产缓存里写、且扫的不是默认根时才跳过。
    """
    if (os.path.abspath(CACHE_FILE) == _PROD_CACHE
            and base is not None
            and os.path.abspath(base) != _default_base()):
        return
    try:
        import json
        tmp = CACHE_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump({"xlsx": [p for _pri, p in hits]}, fh,
                      ensure_ascii=False)
        os.replace(tmp, CACHE_FILE)
    except Exception:
        try:
            os.remove(CACHE_FILE + ".tmp")
        except OSError:
            pass


def _refresh_requested() -> bool:
    return os.environ.get("MMKIT_REFRESH", "") not in ("", "0", "false")


def _walk(base: str, exts: tuple[str, ...] | None = None,
          limit_dirs: int = 200000):
    """剪枝扫描。返回 [(优先级, 路径)]，优先级小的排前面。"""
    hits = []
    seen_dirs = 0
    for dirpath, dirnames, filenames in os.walk(base):
        # 就地剪枝：glob 的 recursive=True 做不到这一步
        dirnames[:] = [d for d in dirnames
                       if d not in SKIP_DIRS and not d.startswith(".")]
        seen_dirs += 1
        if seen_dirs > limit_dirs:
            break
        for fn in filenames:
            if fn.startswith("~$"):        # Excel 打开时的锁文件
                continue
            if exts is not None and not fn.lower().endswith(exts):
                continue
            full = os.path.join(dirpath, fn)
            pri = 0 if any(p in fn for p in PREFERRED) else 1
            hits.append((pri, full))
    hits.sort()
    return hits


def _rank(hits, prefer: str):
    """按 prefer 重排。prefer 命中的一律排最前。

    排序时顺手剔掉**已经不存在的文件** —— 磁盘缓存可能过期
    （用户把附件挪了位置），如果返回一条不存在的路径，
    上游会直接报"找不到数据"而不是自动重扫。
    """
    alive = [(pri, p) for pri, p in hits if os.path.exists(p)]
    if not prefer:
        return alive
    pref = [(0, p) for _pri, p in alive if prefer in os.path.basename(p)]
    # rest 必须**按原优先级排序**（第 94 轮）。
    # 原来直接 pref + rest，而 rest 保持 hits 的原始顺序 —— 于是
    # PREFERRED（"附件"/"attach"/"data"）加权只在没有 prefer 时生效，
    # 一旦传了 prefer，带「附件」的文件反而可能排在不带的后头。
    rest = sorted((pri + 1, p) for pri, p in alive
                  if prefer not in os.path.basename(p))
    return pref + rest


def find_xlsx(base: str | None = None, prefer: str = "") -> str:
    """找数模附件（.xlsx）。找不到返回空串。

    prefer: 额外优先关键字，例如 "附件 2"。命中排前面。
    """
    env = os.environ.get("MMKIT_DATA")
    if env:
        p = os.path.abspath(env)
        return p if os.path.exists(p) else ""
    if base is None:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if not os.path.isdir(base):
        return ""
    if not _XLSX_CACHE:
        if not _refresh_requested():
            disk = _load_disk_cache()
            if disk:
                _XLSX_CACHE.extend(disk)
        if not _XLSX_CACHE:
            _XLSX_CACHE.extend(_walk(base, exts=(".xlsx",)))
            _save_disk_cache(_XLSX_CACHE, base)
    hits = _rank(_XLSX_CACHE, prefer)
    picked = hits[0][1] if hits else ""
    LAST_PICK.clear()
    LAST_PICK.update(path=picked, n_candidates=len(hits), prefer=prefer,
                     ambiguous=bool(len(hits) > 1 and not prefer))
    return picked


def find_named(pattern: str, base: str | None = None) -> str:
    """按文件名片段找（不限于 xlsx）。"""
    env = os.environ.get("MMKIT_DATA")
    if env and pattern in os.path.basename(env):
        return os.path.abspath(env)
    if base is None:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if not os.path.isdir(base):
        return ""
    if not _ANY_CACHE:
        _ANY_CACHE.extend(_walk(base))
    hits = _rank(_ANY_CACHE, pattern)
    return hits[0][1] if hits else ""


def cache_clear() -> None:
    """清空进程缓存**和磁盘缓存**。"""
    _XLSX_CACHE.clear()
    _ANY_CACHE.clear()
    try:
        os.remove(CACHE_FILE)
    except OSError:
        pass


def cache_info() -> dict:
    return dict(n_xlsx=len(_XLSX_CACHE), n_any=len(_ANY_CACHE),
                disk_cache=CACHE_FILE,
                disk_exists=os.path.exists(CACHE_FILE),
                best_xlsx=(_XLSX_CACHE[0][1] if _XLSX_CACHE else None))


# ══════════════════════════════════════════════════════════════════════
#  自检
# ══════════════════════════════════════════════════════════════════════
def selftest() -> int:
    """本模块自己也要有断言。

    第 80 轮第一版在这里翻车：缓存存了单个路径，
    导致 prefer 参数在缓存命中时被忽略，
    lanes.load_apmcm 要的「附件 2」拿不到。
    这个 bug 是 mmkit 的 selftest 逮住的，不是这里的自检 ——
    所以这里必须补上，让同类错误在本模块就能暴露。
    """
    import tempfile
    import time
    ok = bad = 0

    def ck(name, cond, detail=""):
        nonlocal ok, bad
        if cond:
            ok += 1
            print(f"  [PASS] {name}" + (f"  — {detail}" if detail else ""))
        else:
            bad += 1
            print(f"  [FAIL] {name}" + (f"  — {detail}" if detail else ""))

    # 磁盘缓存路径临时挪走。
    # 不挪的话，自检用临时目录调 find_xlsx，会把**临时路径**写进
    # 真实缓存文件 —— 之后工具就会去找一个已经不存在的目录。
    global CACHE_FILE
    real_cache = CACHE_FILE
    CACHE_FILE = os.path.join(tempfile.mkdtemp(prefix="datapath_cache_"),
                              "cache.json")

    print("=" * 72)
    print("datapath.py 自检")
    print("=" * 72)

    # 造一个临时目录树，含若干 xlsx
    td = tempfile.mkdtemp(prefix="datapath_test_")
    big = os.path.join(td, "big")
    os.makedirs(big)
    for i in range(200):
        with open(os.path.join(big, f"noise{i}.txt"), "w") as f:
            f.write("x")
    for nm in ("附件 1：甲.xlsx", "附件 2：乙.xlsx", "附件 3：丙.xlsx",
               "other.xlsx"):
        with open(os.path.join(td, nm), "w") as f:
            f.write("x")
    # 放一个"应被跳过"的大目录
    skip = os.path.join(td, "knowledge-base")
    os.makedirs(skip)
    for i in range(50):
        with open(os.path.join(skip, f"k{i}.txt"), "w") as f:
            f.write("x")

    cache_clear()
    p_all = find_xlsx(base=td)
    ck("能找到 xlsx", p_all.endswith(".xlsx"), os.path.basename(p_all))
    ck("优先返回带「附件」的",
       "附件" in os.path.basename(p_all), os.path.basename(p_all))

    # 第 94 轮：prefer **不命中**时，PREFERRED 加权仍要生效。
    # 原来 rest 保持原始顺序，于是传了 prefer 之后「附件」反而可能靠后。
    _h = [(1, os.path.join(td, "z 其他.xlsx")),
          (1, os.path.join(td, "y 中间.xlsx")),
          (0, os.path.join(td, "附件 9.xlsx"))]
    for _p in ("z 其他.xlsx", "y 中间.xlsx", "附件 9.xlsx"):
        _f = os.path.join(td, _p)
        if not os.path.exists(_f):
            open(_f, "wb").write(b"x")
    _r = _rank(_h, prefer="绝对不存在的关键字")
    ck("prefer 不命中时「附件」仍排第一",
       os.path.basename(_r[0][1]) == "附件 9.xlsx",
       str([os.path.basename(p) for _q, p in _r]))
    _r2 = _rank(_h, prefer="中间")
    ck("prefer 命中时命中项排第一（压过「附件」）",
       os.path.basename(_r2[0][1]) == "y 中间.xlsx",
       str([os.path.basename(p) for _q, p in _r2]))

    # 关键回归：缓存已填充后，prefer 仍然生效
    p2 = find_xlsx(base=td, prefer="附件 2")
    ck("缓存命中后 prefer 仍生效（第 80 轮的真 bug）",
       "附件 2" in os.path.basename(p2), os.path.basename(p2))
    p3 = find_xlsx(base=td, prefer="附件 3")
    ck("换一个 prefer 换个结果",
       "附件 3" in os.path.basename(p3), os.path.basename(p3))
    p4 = find_xlsx(base=td, prefer="不存在的名字")
    ck("prefer 匹配不到时退回默认", p4.endswith(".xlsx"),
       os.path.basename(p4))

    # 剪枝：knowledge-base 里的文件不该被扫到
    ck("跳过 knowledge-base 目录",
       not any("knowledge-base" in h[1] for h in _XLSX_CACHE),
       f"扫到 {_XLSX_CACHE and len(_XLSX_CACHE)} 个 xlsx")

    # 环境变量优先
    os.environ["MMKIT_DATA"] = os.path.join(td, "other.xlsx")
    ck("MMKIT_DATA 环境变量优先",
       find_xlsx(base=td).endswith("other.xlsx"), "应返回指定文件")
    del os.environ["MMKIT_DATA"]

    # find_named
    n = find_named("附件 2", base=td)
    ck("find_named 按片段找", "附件 2" in os.path.basename(n),
       os.path.basename(n))

    # 缓存确实只扫一次
    cache_clear()
    t0 = time.perf_counter()
    find_xlsx(base=td)
    t1 = time.perf_counter()
    find_xlsx(base=td)
    t2 = time.perf_counter()
    ck("第二次调用不再扫盘", (t2 - t1) < (t1 - t0),
       f"首次 {(t1 - t0) * 1000:.2f}ms，二次 {(t2 - t1) * 1000:.4f}ms")

    # 磁盘缓存：换一个进程也要快
    ck("磁盘缓存文件已写出", os.path.exists(CACHE_FILE), CACHE_FILE)
    _XLSX_CACHE.clear()
    t3 = time.perf_counter()
    p_disk = find_xlsx(base=td, prefer="附件 3")
    t4 = time.perf_counter()
    ck("新进程（清空内存缓存）仍从磁盘命中",
       "附件 3" in os.path.basename(p_disk),
       f"{os.path.basename(p_disk)}  用时 {(t4 - t3) * 1000:.2f}ms")
    ck("磁盘命中比扫描快", (t4 - t3) < (t1 - t0),
       f"磁盘 {(t4 - t3) * 1000:.2f}ms vs 扫描 {(t1 - t0) * 1000:.2f}ms")

    # 缓存失效：路径没了要能重扫
    cache_clear()
    with open(CACHE_FILE, "w", encoding="utf-8") as fh:
        fh.write('{"xlsx": ["Z:/根本不存在的/文件.xlsx"]}')
    _XLSX_CACHE.clear()
    p_stale = find_xlsx(base=td)
    ck("磁盘缓存过期时自动重扫", p_stale.endswith(".xlsx"),
       os.path.basename(p_stale))

    # 缓存里的文件被删了 → 不能返回不存在的路径
    cache_clear()
    victim = os.path.join(td, "附件 1：甲.xlsx")
    find_xlsx(base=td)
    os.remove(victim)
    _XLSX_CACHE.clear()
    p_gone = find_xlsx(base=td)
    ck("缓存里的文件被删后不返回死路径",
       p_gone and os.path.exists(p_gone), os.path.basename(p_gone))

    # 刷新开关
    os.environ["MMKIT_REFRESH"] = "1"
    _XLSX_CACHE.clear()
    find_xlsx(base=td)
    ck("MMKIT_REFRESH=1 强制重扫", True, "已重扫")
    del os.environ["MMKIT_REFRESH"]

    # 还原真实缓存路径
    CACHE_FILE = real_cache
    cache_clear()

    print()
    print("=" * 72)
    print(f"{'ALL PASS' if bad == 0 else 'FAILED'}  {ok} 通过 / {bad} 失败")
    print("=" * 72)
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    raise SystemExit(selftest())
