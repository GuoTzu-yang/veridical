"""堵住三条得手的攻击（第 120 轮）。

共同根因：护栏**相信递给它的文件**，而不核对文件与论文是否一致。

A1 空稿  —— 0 个数字时 `n_traced >= min(must, n)` 恒真 → 空过。
          修：数字个数本身必须 >= must，否则判 `few_numbers`。
A2 自我冻结 —— 冻结表可以就是论文自己的数字 → 溯源率必然 100%。
          修：冻结表必须声明 `generated_from`（生成它的脚本/工件），且该文件
          存在；条目必须带 `path`（来自哪次计算），`self` 之类不算。
A3 只留文献 —— `biblio` 直接信 `lit_bound.json` → 记录说谎就通过。
          修：`biblio` 自己从 paper.tex 数 bibitem 与 \\cite，与记录对账；
          对不上判 FAIL（记录与论文不符）。
"""
import io

HERE = r"C:\Users\21246\Documents\deepseek-harness\default-workspace\model1-arch"
FR = HERE + r"\freeze.py"
GT = HERE + r"\gate.py"

# ── A1 + A2：freeze ────────────────────────────────────────────────
s = io.open(FR, encoding="utf-8").read()

old_ok = '''    ok=((len(traced) >= min(must, n)) and ratio <= max_untraced
            and not (single_point and hp)),'''
new_ok = '''    # A1（第 120 轮）：数字太少不能算通过 —— 空稿曾报「0/0 可溯源，通过」。
    # 原来写的是 >= min(must, n)，n=0 时恒真。
    few = n < must
    # A2：冻结表必须交代它是谁生成的，且条目要带来源路径；
    # 否则「拿论文自己的数字生成冻结表」就能自证 100%。
    _gf = str(frozen.get("generated_from") or "").strip()
    _src_ok = bool(_gf) and os.path.exists(os.path.join(HERE, _gf)) \\
        if _gf and not os.path.isabs(_gf) else bool(_gf) and os.path.exists(_gf)
    _paths = [str(it.get("path") or "") for it in (frozen.get("items") or [])]
    _self_证明 = bool(_paths) and all(
        p.strip().lower() in ("", "self", "paper", "tex") for p in _paths)
    ok=(not few and ratio <= max_untraced and _src_ok and not _self_证明
        and not (single_point and hp)),'''
assert old_ok in s, "ok 表达式未匹配"
s = s.replace(old_ok, new_ok, 1)

s = s.replace('        n_from_data=n_data,',
              '        n_from_data=n_data,\n'
              '        few_numbers=few,\n'
              '        frozen_has_source=_src_ok,\n'
              '        frozen_self_proving=_self_证明,')

if "import os" not in s.split("def ")[0]:
    s = s.replace("import io\n", "import io\nimport os\n", 1)
io.open(FR, "w", encoding="utf-8", newline="\n").write(s)
print("freeze：已堵 A1（数字太少）与 A2（自我冻结）")

# ── A3：gate 的 biblio 自己数 ──────────────────────────────────────
g = io.open(GT, encoding="utf-8").read()
old_b = '''    unbound = d.get("unbound") or []
    uncited = d.get("uncited") or []'''
new_b = '''    # A3（第 120 轮）：不能全信记录 —— 自己从论文里数一遍对账。
    # 攻击样例：只写 1 条 bibitem，记录里写 uncited=[]，就被判「全部绑定且被引用」。
    try:
        _tex = open(os.path.join(figdir, "paper.tex"), encoding="utf-8").read()
    except Exception:                                   # noqa: BLE001
        _tex = ""
    _n_bib = len(re.findall(r"\\\\bibitem\\{", _tex))
    _cited = set()
    for _m in re.finditer(r"\\\\cite\\{([^}]*)\\}", _tex):
        for _k in _m.group(1).split(","):
            _cited.add(_k.strip())
    _keys = re.findall(r"\\\\bibitem\\{([^}]*)\\}", _tex)
    _uncited_real = [k for k in _keys if k not in _cited]
    if _tex and int(d.get("n") or 0) != _n_bib:
        return _r("biblio", SOFT, "FAIL",
                  "记录说 %s 条，论文里实际 %d 条 —— 记录与论文不符"
                  % (d.get("n"), _n_bib))
    if _tex and sorted(_uncited_real) != sorted(d.get("uncited") or []):
        return _r("biblio", SOFT, "FAIL",
                  "未引用清单与论文不符：实际 %s" % (_uncited_real[:4] or "无"))
    unbound = d.get("unbound") or []
    uncited = _uncited_real if _tex else (d.get("uncited") or [])'''
assert old_b in g, "biblio 块未匹配"
g = g.replace(old_b, new_b, 1)
io.open(GT, "w", encoding="utf-8", newline="\n").write(g)
print("gate：已堵 A3（biblio 自己对账）")
