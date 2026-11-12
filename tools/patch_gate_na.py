"""把 gate.py 的 N/A 语义从「字符串猜」升级为「类型化」，并把默认改为安全侧。

改什么：
  1. 新增 _na / _na_err / _is_failed_na，N/A 带上 na_kind（absent | failed）。
  2. 17 个 except 返回点改用 _na_err，不再靠 detail 里出现 "KeyError" 来判定。
  3. run_all 的 strict 默认 True；新增 --lenient 恢复旧行为。
  4. _na_is_error 保留为 legacy 兜底（老调用点没带 na_kind 时仍能判）。

为什么改：
  旧实现用 _NA_ERR_MARK 匹配 detail 文本判断「检查器是不是崩了」。文本匹配的
  反例很直白：某检查合法地返回含 "Error" 字样的中文理由就会被误判为崩溃；反过来
  自定义异常类名（MyBug）不在表里，真崩了也判不出来。类型化之后判定与文案无关。
"""
import io
import re
import sys

P = r"C:\Users\21246\Documents\deepseek-harness\default-workspace\model1-arch\gate.py"

HELPERS = '''

# ── N/A 的两种含义：类型化，不再靠 detail 文本猜 ────────────────────
# absent —— 本题确实没有这一项（题目不含该结构），硬门算通过
# failed —— 检查没跑成（读错表 / KeyError / 依赖缺失），硬门必须算失败
NA_ABSENT, NA_FAILED = "absent", "failed"


def _na(cid, tier, detail, kind=NA_ABSENT):
    r = _r(cid, tier, "N/A", detail)
    r["na_kind"] = kind
    return r


def _na_err(cid, tier, exc):
    """异常路径统一出口：类型即证据，不依赖异常文本。"""
    return _na(cid, tier, "%s: %s" % (type(exc).__name__, exc), kind=NA_FAILED)


def _is_failed_na(c):
    """带 na_kind 的按类型判；没带的老调用点退回文本匹配。"""
    k = c.get("na_kind")
    if k is not None:
        return k == NA_FAILED
    return _na_is_error(c.get("detail", ""))
'''


def main():
    src = io.open(P, encoding="utf-8").read()
    orig = src

    # 1) 插入 helper：紧跟 _na_is_error 函数体之后
    anchor = 'def _na_is_error(detail: str) -> bool:\n    d = str(detail)\n    return any(m in d for m in _NA_ERR_MARK)\n'
    if "_na_err" in src:
        print("SKIP helpers: already present")
    elif anchor not in src:
        print("FAIL: anchor for helpers not found")
        return 2
    else:
        src = src.replace(anchor, anchor + HELPERS, 1)
        print("OK helpers inserted")

    # 2) 17 个 except 返回点 -> _na_err
    pat = re.compile(
        r'return _r\("([a-z_]+)", (HARD|SOFT), "N/A", f"\{type\(e\)\.__name__\}: \{e\}"\)')
    n = len(pat.findall(src))
    src = pat.sub(lambda m: 'return _na_err("%s", %s, e)' % (m.group(1), m.group(2)), src)
    print("OK except sites rewritten: %d" % n)

    # 3) run_all 默认 strict=True
    old_sig = 'def run_all(figdir: str, data: str = "", strict: bool = False,'
    if old_sig in src:
        src = src.replace(old_sig,
                          'def run_all(figdir: str, data: str = "", strict: bool = True,', 1)
        print("OK run_all default strict=True")
    else:
        print("SKIP run_all signature (already changed?)")

    # 4) strict 分支改用类型化判定
    old_blk = ('    if strict:\n'
               '        for c in checks:\n'
               '            if c["status"] == "N/A" and _na_is_error(c["detail"]):\n')
    new_blk = ('    if strict:\n'
               '        for c in checks:\n'
               '            if c["status"] == "N/A" and _is_failed_na(c):\n')
    if old_blk in src:
        src = src.replace(old_blk, new_blk, 1)
        print("OK strict branch uses _is_failed_na")
    else:
        print("FAIL: strict branch block not matched")
        return 3

    # 5) CLI：--strict 默认开，新增 --lenient
    old_cli = 'ap.add_argument("--strict", action="store_true",'
    if old_cli in src:
        # 找到该 add_argument 的整条语句（可能跨行），替换为互斥组
        m = re.search(r'    ap\.add_argument\("--strict", action="store_true",[\s\S]{0,200}?\)\n', src)
        if not m:
            print("FAIL: cannot isolate --strict argument statement")
            return 4
        block = m.group(0)
        new = ('    ap.add_argument("--lenient", action="store_true",\n'
               '                    help="N/A 中「检查没跑成」的部分仍算通过（旧行为）")\n'
               '    ap.add_argument("--strict", action="store_true", default=True,\n'
               '                    help="N/A 中「检查没跑成」计为失败（默认）")\n')
        src = src[:m.start()] + new + src[m.end():]
        print("OK CLI rewritten (strict default on, --lenient added)")
    else:
        print("SKIP CLI (no --strict found)")

    # 6) run_all 调用点传 strict
    src = src.replace('r = run_all(a.dir, a.data, strict=a.strict, track=a.track)',
                      'r = run_all(a.dir, a.data, strict=(not a.lenient), track=a.track)')

    if src == orig:
        print("NO CHANGE")
        return 0
    io.open(P, "w", encoding="utf-8", newline="\n").write(src)
    print("written %s" % P)
    return 0


if __name__ == "__main__":
    sys.exit(main())
