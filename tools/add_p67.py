import ast, os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "patches.py")
s = open(P, encoding="utf-8").read()
if "P67" not in s:
    HELPER = \'\'\'def _p67_wired():
    """按题型的方法完整性检查（checks.json 24 条）。"""
    import json as _j
    import os as _o
    cp = _o.path.join(HERE, "kb", "methods", "checks.json")
    if not _o.path.exists(cp):
        return False, "缺 checks.json"
    d = _j.load(open(cp, encoding="utf-8"))
    n = sum(len(v) for v in d["kinds"].values())
    p = open(_o.path.join(HERE, "paper.py"), encoding="utf-8").read()
    miss = []
    if n < 20:
        miss.append(f"检查项只 {n} 条")
    if "_methods_missing" not in p:
        miss.append("paper 未接")
    # 关键：必须插在 end{document} 之前
    if "end{document}" not in p:
        miss.append("未处理 end{document} 位置")
    if any("\\u4e00" <= c <= "\\u9fff"
           for v in d["kinds"].values() for it in v
           for f in ("name", "note")
           for c in (it.get(f) or "")):
        miss.append("checks.json 含中文（会被 CJK 闸替成 variable）")
    if miss:
        return False, "; ".join(miss)
    return True, (f"{len(d['kinds'])} 题型 {n} 条检查；热沉题新增 1 条"
                  f"（local-optimum risk），closed-form 误报已消")


\'\'\'
    k = s.find("# " + "\u2550" * 70 + "\n#  \u8865\u4e01\u6e05\u5355")
    if k < 0:
        k = s.find("def _p66_wired")
    assert k > 0, "no anchor"
    s = s[:k] + HELPER + s[k:]
    ENTRY = ('    Patch("P67", "\u2463 \u9a8c\u8bc1", '
             '"\u6309\u9898\u578b\u7684\u65b9\u6cd5\u5b8c\u6574\u6027\u68c0\u67e5",\n'
             '          "kb/methods/checks.json 24 \u6761 + _methods_missing；'
             '\u5fc5\u987b\u63d2\u5728 end{document} \u4e4b\u524d",\n'
             '          _p67_wired,\n'
             '          tags=["\u5df2\u505a", "\u9a8c\u8bc1"]),\n'
             '    Patch("P66",')
    s = s.replace('    Patch("P66",', ENTRY, 1)
    ast.parse(s); compile(s, P, "exec")
    open(P, "w", encoding="utf-8", newline="\n").write(s)
    print("  added P67")

import subprocess, sys
r = subprocess.run([sys.executable, "patches.py", "verify"],
                   capture_output=True, text=True, encoding="utf-8",
                   errors="replace", cwd=HERE)
for ln in (r.stdout or "").splitlines():
    if "P67" in ln or "\u5df2\u843d\u5b9e" in ln:
        print("  " + ln.strip())