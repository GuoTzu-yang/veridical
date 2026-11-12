"""A + B：口径统一 + 删掉重复分词器（第 118 轮）。

A 口径统一
----------
`AGENTS.md` 写「硬门失败 0、警告 0 才算这一战打完」，而 `all_pass` 只看硬门。
实测：3 条警告下 gate 仍报「通过」—— 声称与行为不一致，正是本文批的那类缺陷。

新语义：
  all_pass = 硬门全过 **且** 没有警告
  ……除非显式 --lenient（草稿模式，允许警告）或 --force-override（交卷越权）。
判定里同时给出 `warn_block=True`，让报告能解释为什么「没通过」。

B 删掉重复分词器
----------------
`verify.py`（全量 token）与 `freeze.check_paper`（只取小数）各有一套抽取规则，
已经造成过一次矛盾判决（17.1% vs 100%）。现在 freeze 走 verify.extract_numbers，
自己只做「只保留带小数的」过滤 —— 一套抽取，两个视图。
"""
import io

GATE = r"C:\Users\21246\Documents\deepseek-harness\default-workspace\model1-arch\gate.py"
FREEZE = r"C:\Users\21246\Documents\deepseek-harness\default-workspace\model1-arch\freeze.py"

# ── A ──────────────────────────────────────────────────────────────
s = io.open(GATE, encoding="utf-8").read()
old = """    return dict(
        checks=checks,
        all_pass=hard_ok,"""
new = """    _warns = [c["id"] for c in checks if c["status"] == "WARN"]
    # 第 118 轮：警告也阻断「通过」。文档一直这么写，代码此前只看硬门。
    _warn_block = bool(_warns) and not lenient
    return dict(
        checks=checks,
        all_pass=hard_ok and not _warn_block,
        warn_block=_warn_block,"""
assert old in s, "all_pass 块未匹配"
s = s.replace(old, new, 1)

# run_all 需要 lenient 参数：签名里加，调用处透传
s = s.replace("def run_all(figdir: str, data: str = \"\", strict: bool = True,\n            track: str = \"auto\") -> dict:",
              "def run_all(figdir: str, data: str = \"\", strict: bool = True,\n            track: str = \"auto\", lenient: bool = False) -> dict:")
s = s.replace("r = run_all(a.dir, a.data, strict=(not a.lenient), track=a.track)",
              "r = run_all(a.dir, a.data, strict=(not a.lenient), track=a.track,\n                lenient=a.lenient)")
# 报告行要能解释「为什么没通过」
s = s.replace("""    L = [f"质量门：{'通过' if r['all_pass'] else '未通过'}\"""",
              """    L = [f"质量门：{'通过' if r['all_pass'] else '未通过'}"
         + ("（警告阻断：%s，用 --lenient 可放行草稿）" % ",".join(r["warns"][:3])
            if r.get("warn_block") else "")""")
io.open(GATE, "w", encoding="utf-8", newline="\n").write(s)
print("A 已改：警告阻断（--lenient 放行）")

# ── B ──────────────────────────────────────────────────────────────
f = io.open(FREEZE, encoding="utf-8").read()
old_b = """    _tex = re.sub(r"\\\\code\\{[^}]*\\}", " ", tex)
    _tex = re.sub(r"\\\\verb\\|[^|]*\\|", " ", _tex)
    _t = re.sub(r"\\[[^\\]]*\\]", " ", _tex)
    toks = re.findall(r"(?<![\\w.])-?\\d+\\.\\d+(?![\\w.])", _t)"""
new_b = """    # 第 118 轮：不再自己分词。走 verify.extract_numbers（全量 token），
    # 这里只过滤「带小数」的那些 —— 一套抽取规则，两个视图。
    # 这样 numbers 与 verify 永远不会给出互相矛盾的判决。
    try:
        import verify as _V
        _all = _V.extract_numbers(tex, skip_meta=False)
    except Exception:                                   # noqa: BLE001
        _all = []
    toks = [t for t, _line in _all if "." in t]"""
if old_b in f:
    f = f.replace(old_b, new_b, 1)
    io.open(FREEZE, "w", encoding="utf-8", newline="\n").write(f)
    print("B 已改：freeze 复用 verify 的分词")
else:
    print("B 未匹配，需人工核对 freeze 的分词块")
