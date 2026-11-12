"""gate.py 数据表定位升级：从「工作区里找一个 xlsx」改为「按题精确解析」。

问题（本轮实测）：
  chk_leakage / chk_falsify 在没有显式 --data 时调用 mm.find_xlsx()，那是在
  工作区里找**某一个** xlsx。它返回的是 APMCM 2026 B 题附件，于是 23 道题里
  22 道拿同一张热阻表去查自己的 y 名 → KeyError → N/A → 硬门算通过。
  也就是说：这道硬门从未在正确的表上跑过。

修法：
  1. 新增 _resolve_data：显式路径 → runs.json 登记的表 → out/data/<题名>.xlsx
     → 放弃（并说明原因）。绝不扫描工作区。
  2. chk_leakage（硬门）拿不到表 → N/A 且 kind=failed，严格模式下计失败。
     「硬门没跑成」不能再是绿的。
  3. chk_falsify 同样改走 _resolve_data。
  4. 新增 _pick_col：y 名先精确匹配，再唯一包含匹配（题面常写简称，
     如「热阻」对「无量纲热阻」）。多解则放弃，不猜。
"""
import io
import re
import sys

P = r"C:\Users\21246\Documents\deepseek-harness\default-workspace\model1-arch\gate.py"

HELPERS = '''

# ── 数据表定位：按题解析，不扫描工作区 ────────────────────────────────
def _resolve_data(figdir: str, data: str = ""):
    """返回 (路径, 失败原因)。路径为空时原因说明为什么拿不到。

    顺序：显式路径 → runs.json 里这道题登记的表 → out/data/<题名>.xlsx|.csv → 放弃。
    刻意不调用 mm.find_xlsx()：那是「在工作区里找一个 xlsx」，与本题无关。
    实测它恒返回 APMCM 2026 B 题附件，导致 22/23 道题用别人的表做泄漏检查。
    """
    if data:
        if os.path.exists(data):
            return data, ""
        alt = os.path.join(HERE, "out", "data", os.path.basename(data))
        if os.path.exists(alt):
            return alt, ""
        return "", "给定了数据表但文件不存在：%s" % data

    name = os.path.basename(os.path.normpath(figdir))
    # ① runs.json 登记
    try:
        import json as _json
        cfg = _json.load(open(os.path.join(HERE, "runs.json"), encoding="utf-8"))
        ent = (cfg.get(name) or {})
        fn = ent.get("data")
        if fn:
            cand = fn if os.path.isabs(fn) else os.path.join(
                HERE, "out", "data", os.path.basename(fn))
            if os.path.exists(cand):
                return cand, ""
    except Exception:                               # noqa: BLE001
        pass
    # ② 按产物目录名
    for ext in (".xlsx", ".csv"):
        p = os.path.join(HERE, "out", "data", name + ext)
        if os.path.exists(p):
            return p, ""
    return "", "没有这道题的数据表（runs.json 未登记，out/data/%s.xlsx 不存在）" % name


def _pick_col(ds, name):
    """把题面里的变量名对到真实列名：精确 → 唯一包含 → 放弃。

    题面常写简称（「热阻」），表里是全称（「无量纲热阻」）。只接受唯一解；
    多解或无解都返回 None，让调用方报清楚，而不是随便挑一列。
    """
    if not name:
        return None
    names = list(getattr(ds, "num_names", []) or [])
    if name in names:
        return name
    cands = [c for c in names if name in c]
    if len(cands) == 1:
        return cands[0]
    return None
'''


def main():
    src = io.open(P, encoding="utf-8").read()
    orig = src

    # 1) 插入 helper（放在 _is_failed_na 之后）
    anchor = ('def _is_failed_na(c):\n'
              '    """带 na_kind 的按类型判；没带的老调用点退回文本匹配。"""\n'
              '    k = c.get("na_kind")\n'
              '    if k is not None:\n'
              '        return k == NA_FAILED\n'
              '    return _na_is_error(c.get("detail", ""))\n')
    if "_resolve_data" in src:
        print("SKIP helpers: already present")
    elif anchor not in src:
        print("FAIL: helper anchor not found")
        return 2
    else:
        src = src.replace(anchor, anchor + HELPERS, 1)
        print("OK helpers inserted")

    # 2) chk_leakage：换掉 find_xlsx 兜底
    old_leak = '''        if not data:
            data = mm.find_xlsx() or ""
        fz = os.path.join(figdir, "冻结数字.json")'''
    new_leak = '''        data, why = _resolve_data(figdir, data)
        fz = os.path.join(figdir, "冻结数字.json")'''
    if old_leak in src:
        src = src.replace(old_leak, new_leak, 1)
        print("OK chk_leakage uses _resolve_data")
    else:
        print("FAIL: chk_leakage fallback block not matched")
        return 3

    old_leak2 = '''        if not data:
            return _r("leakage", HARD, "N/A", "找不到数据")'''
    new_leak2 = '''        if not data:
            # 硬门没跑成，不能算通过：严格模式会把它计为失败
            return _na("leakage", HARD, why, kind=NA_FAILED)'''
    if old_leak2 in src:
        src = src.replace(old_leak2, new_leak2, 1)
        print("OK chk_leakage missing-data is failed-N/A")
    else:
        print("FAIL: chk_leakage missing-data block not matched")
        return 4

    # 3) chk_leakage：y / x 名走 _pick_col
    old_y = '''            hit = _fd.get("y") or None
            xused = list(_fd.get("x") or [])'''
    new_y = '''            hit = _pick_col(ds, _fd.get("y"))
            xused = [c for c in (_pick_col(ds, v) for v in (_fd.get("x") or []))
                     if c]'''
    if old_y in src:
        src = src.replace(old_y, new_y, 1)
        print("OK chk_leakage y/x name resolution")
    else:
        print("FAIL: chk_leakage y/x block not matched")
        return 5

    old_hit = '''        if hit is None:
            return _r("leakage", HARD, "N/A", "冻结表里没记 y")'''
    new_hit = '''        if hit is None:
            _fd_y = (_fd.get("y") if os.path.exists(fz) else None)
            return _na("leakage", HARD,
                       "冻结表的 y=%r 对不上表里的列（有：%s）"
                       % (_fd_y, "、".join(list(ds.num_names)[:6])),
                       kind=NA_FAILED)'''
    if old_hit in src:
        src = src.replace(old_hit, new_hit, 1)
        print("OK chk_leakage unresolved y is failed-N/A")
    else:
        print("FAIL: chk_leakage y-missing block not matched")
        return 6

    # 4) chk_falsify：换掉 find_xlsx 兜底
    old_f = '''    if not data:
        try:
            import mm
            data = mm.find_xlsx() or ""
        except Exception:                           # noqa: BLE001
            data = ""
    if not data or not os.path.exists(data):
        return _r("falsify", SOFT, "N/A", "找不到数据")'''
    new_f = '''    data, why = _resolve_data(figdir, data)
    if not data:
        return _na("falsify", SOFT, why, kind=NA_FAILED)'''
    if old_f in src:
        src = src.replace(old_f, new_f, 1)
        print("OK chk_falsify uses _resolve_data")
    else:
        print("FAIL: chk_falsify fallback block not matched")
        return 7

    if src == orig:
        print("NO CHANGE")
        return 0
    io.open(P, "w", encoding="utf-8", newline="\n").write(src)
    print("written %s" % P)
    return 0


if __name__ == "__main__":
    sys.exit(main())
