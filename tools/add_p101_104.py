import ast
import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "patches.py")
s = open(P, encoding="utf-8").read()

NEW = []
NEW.append(("P101", "④ 验证", "验收脚本的子串陷阱",
  '"通过" in "未通过" 为 True，于是硬门失败的题被报成通过',
  '''def _p101_wired():
    import os as _o
    bad = []
    for f in ("tools/battle.py", "tools/verify_all.py"):
        p = _o.path.join(HERE, f)
        t = open(p, encoding="utf-8").read()
        if '"通过" in' in t:
            bad.append(f + ' still uses bare "通过" in ...')
        if 'startswith("质量门：通过")' not in t:
            bad.append(f + ' lacks startswith check')
    if bad:
        return False, "; ".join(bad)
    return True, "两处验收脚本改用 startswith，未通过不再算通过"
'''))
NEW.append(("P102", "④ 验证", "\\ref{sec:selection} 悬空",
  "label 只在 multimodel 非空时生成，AI 声明里的引用却无条件输出",
  '''def _p102_wired():
    import os as _o
    p = open(_o.path.join(HERE, "paper.py"), encoding="utf-8").read()
    if "_has_sel" not in p:
        return False, "sec:selection ref not conditional"
    t = _o.path.join(HERE, "out", "runs", "review_microwave", "paper.tex")
    if _o.path.exists(t):
        tt = open(t, encoding="utf-8").read()
        if "Section~\\\\ref{sec:selection}" in tt and "\\\\label{sec:selection}" not in tt:
            return False, "dangling ref still produced"
    return True, "引用改为条件输出；无 multimodel 时不再写 Section~\\\\ref"
'''))
NEW.append(("P103", "④ 验证", "残差节移出 multimodel 分支",
  "label/tab:diag 埋在 if _mm3 里，multimodel 为空时整节消失；_diag_ctx 还把 y 自身当 x",
  '''def _p103_wired():
    import os as _o
    p = open(_o.path.join(HERE, "paper.py"), encoding="utf-8").read()
    m = open(_o.path.join(HERE, "mmkit.py"), encoding="utf-8").read()
    bad = []
    if "_xs_y" not in m:
        bad.append("_diag_ctx does not drop y from x")
    # 残差节应在 _mm3 块之外：缩进 4 的注释标记
    for ln in p.splitlines():
        if "残差诊断：题目的" in ln:
            if len(ln) - len(ln.lstrip()) != 4:
                bad.append("residual block still nested (indent %d)"
                           % (len(ln) - len(ln.lstrip())))
            break
    for n in ("review_microwave", "review_pacifier", "real_c2024"):
        t = _o.path.join(HERE, "out", "runs", n, "paper.tex")
        if _o.path.exists(t):
            tt = open(t, encoding="utf-8").read()
            if "tab:diag" not in tt:
                bad.append(n + " lacks tab:diag")
    if bad:
        return False, "; ".join(bad)
    return True, "残差节移到 multimodel 之外；3 道边界题都出表了"
'''))
NEW.append(("P104", "⑥ 打包", "22 道题全量配置",
  "external 里 184 个数据文件只用了 6 个；现在 22 道全跑通",
  '''def _p104_wired():
    import json as _j
    import os as _o
    cfg = _j.load(open(_o.path.join(HERE, "runs.json"), encoding="utf-8"))
    if len(cfg) < 22:
        return False, "only %d problems" % len(cfg)
    built = sum(1 for c in cfg.values()
                if _o.path.exists(_o.path.join(HERE, c["out"], "paper.pdf")))
    if built < 22:
        return False, "only %d/22 PDFs" % built
    return True, "22 道题（含 8 道真实真题/数据集）全部出稿"
'''))

for pid, cat, title, why, fn in reversed(NEW):
    if pid in s:
        continue
    k = s.find("def _p100_wired")
    assert k > 0
    s = s[:k] + fn + "\n\n" + s[k:]
    anchor = '    Patch("P100",'
    entry = ('    Patch("' + pid + '", "' + cat + '", "' + title + '",\n'
             '          "' + why + '",\n'
             '          _' + pid.lower() + '_wired,\n'
             '          tags=["已做", "' + cat.split(" ")[1] + '"]),\n'
             + anchor)
    s = s.replace(anchor, entry, 1)

ast.parse(s)
compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  added P101-P104")