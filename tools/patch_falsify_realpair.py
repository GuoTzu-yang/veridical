"""gate.chk_falsify 升级：用论文声明的 y/x，而不是按列序盲测。

问题：
  xs = cols[:3]; ys = cols[3:5] —— 拿「前 3 个数值列」当自变量、「第 4-5 个」
  当响应。这与论文声称的任何关系都无关，于是这条 SOFT 检查的结论
  （「N 组边际反例且控制后符号仍矛盾」）说的是任意列对的稳健性，
  读者会误以为它在检验论文的主张。

修法：
  1. 从 冻结数字.json 取 y 与 x，用 _pick_col 对到真实列名（与 leakage 同一套）。
  2. 拿不到才退回按列序盲测，并在 detail 里**明确标注是盲测**，不冒充实测。
  3. 承认语句的匹配放宽到中英两种写法（仍是关键词，不是语义理解，注释里写清）。
"""
import io
import sys

P = r"C:\Users\21246\Documents\deepseek-harness\default-workspace\model1-arch\gate.py"

OLD_SEL = '''        ds = mm.DS(data)
        cols = [c for c in ds.num_names if "编号" not in c]
        if len(cols) < 4:
            return _r("falsify", SOFT, "N/A", "数值列不足 4 个")
        xs = cols[:3]
        ys = cols[3:5]
        marginal = 0
        real = []'''

NEW_SEL = '''        ds = mm.DS(data)
        cols = [c for c in ds.num_names if "编号" not in c]
        if len(cols) < 4:
            return _r("falsify", SOFT, "N/A", "数值列不足 4 个")

        # 优先测论文**声明**的那对 y / x；拿不到才按列序盲测并标注。
        # 原来直接 xs=cols[:3]、ys=cols[3:5]，测的是任意列对，
        # 而 detail 写着「符号仍矛盾」——读者会以为在检验论文的主张。
        xs, ys, _mode = cols[:3], cols[3:5], "blind"
        _fz = os.path.join(figdir, "冻结数字.json")
        if os.path.exists(_fz):
            try:
                import json as _json
                _fd = _json.load(open(_fz, encoding="utf-8"))
                _y = _pick_col(ds, _fd.get("y"))
                _x = [c for c in (_pick_col(ds, v) for v in (_fd.get("x") or []))
                      if c and c != _y]
                if _y and _x:
                    xs, ys, _mode = _x, [_y], "paper"
            except Exception:                   # noqa: BLE001
                pass
        _tag = "" if _mode == "paper" else "（严格说这是盲测：冻结表里没有可用的 y/x）"
        marginal = 0
        real = []'''

PASS_OK = '''        if marginal:
            return _r("falsify", SOFT, "PASS",
                      f"{marginal} 组边际反例，但控制后符号一致"'''

PASS_NEW = '''        if marginal:
            return _r("falsify", SOFT, "PASS",
                      f"{marginal} 组边际反例，但控制后符号一致" + _tag'''

WARN_OLD = '''        if real:
            return _r("falsify", SOFT, "WARN",
                      f"{len(real)} 组边际反例且控制后符号仍矛盾："
                      + "、".join(real[:3]))'''

WARN_NEW = '''        if real:
            return _r("falsify", SOFT, "WARN",
                      f"{len(real)} 组边际反例且控制后符号仍矛盾："
                      + "、".join(real[:3]) + _tag)'''

ADM_OLD = '''            _admits = ("Monotonicity is not universal" in _tt
                       or "fails locally" in _tt)'''

ADM_NEW = '''            # 关键词匹配，不是语义理解：论文用什么话承认「局部非单调」
            # 无法穷举，这里只覆盖常见的中英写法。匹配不到不等于没写。
            _pats = ("Monotonicity is not universal", "fails locally",
                     "non-monotone", "not monotone", "local reversal",
                     "局部非单调", "非单调", "局部反例")
            _admits = any(_p in _tt for _p in _pats)'''


def main():
    src = io.open(P, encoding="utf-8").read()
    orig = src
    for name, old, new in (
            ("y/x 选择", OLD_SEL, NEW_SEL),
            ("PASS tag", PASS_OK, PASS_NEW),
            ("WARN tag", WARN_OLD, WARN_NEW),
            ("承认语句", ADM_OLD, ADM_NEW)):
        if new.split("\n")[0] and old not in src:
            print("FAIL: %s 锚点未命中" % name)
            return 2
        src = src.replace(old, new, 1)
        print("OK %s" % name)
    if src == orig:
        print("NO CHANGE")
        return 0
    io.open(P, "w", encoding="utf-8", newline="\n").write(src)
    print("written %s" % P)
    return 0


if __name__ == "__main__":
    sys.exit(main())
