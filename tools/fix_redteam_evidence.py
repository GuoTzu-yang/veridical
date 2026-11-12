"""把 redteam 的证据要求从「论文引文」改成「代码/工件里的可 grep 标记」（第 119 轮，第三版）。

为什么改
--------
第二版要求每条 finding 带论文引文，实测**选句不可靠**：关键词 "199" 取到了
"the falsifier does not weigh the whole" 这种不相干的句子 —— 那又变成了布景。

正确的落点：这 13 条 finding 说的都是**工具**的缺陷，修复也发生在工具里。
所以证据应当是「在哪个文件的哪段文字里能看到这个修复」。gate 去 grep，
找不到就 FAIL。于是编一条 finding 必须先让那段代码真的存在。

规则
----
每条 finding 必须带：
  · where    —— 相对插件根的文件路径，必须存在
  · evidence —— >=8 字符的标记，必须**逐字**出现在该文件里
"""
import io
import os

P = r"C:\Users\21246\Documents\deepseek-harness\default-workspace\model1-arch\redteam.py"
s = io.open(P, encoding="utf-8").read()

old = '''        # 第 119 轮：finding 必须带**可被 grep 的引文**。
        # 编一条 finding 就得先把它写进论文 —— 那它就不再是编的。
        for p in found:
            q = str(p.get("quote") or "").strip()
            if len(q) < 20:
                problems.append(f"{s} 的 finding 没有 >=20 字的引文")
            else:
                try:
                    _paper = io.open(os.path.join(figdir, "paper.tex"),
                                     encoding="utf-8").read()
                except Exception:                       # noqa: BLE001
                    _paper = ""
                if _paper and q not in re.sub(r"\\s+", " ", _paper):
                    problems.append(f"{s} 的引文在论文里找不到：{q[:24]}…")'''
new = '''        # 第 119 轮：finding 必须带**落地的证据**（文件 + 逐字标记）。
        # 这些 finding 说的是工具的缺陷，修复也在工具里，所以证据应当是
        # 「哪个文件的哪段文字能看到这个修复」。编一条 finding 就必须先让
        # 那段代码真的存在 —— 造假成本高于照做，机制才成立。
        for p in found:
            w = str(p.get("where") or "").strip()
            ev = str(p.get("evidence") or "").strip()
            if not w or len(ev) < 8:
                problems.append(f"{s} 的 finding 缺 where/evidence（>=8 字符）")
                continue
            fp = os.path.join(HERE, w)
            if not os.path.exists(fp):
                problems.append(f"{s} 的 finding 指向不存在的文件：{w}")
                continue
            try:
                body = io.open(fp, encoding="utf-8", errors="replace").read()
            except Exception:                           # noqa: BLE001
                problems.append(f"{s} 的 finding 无法读取：{w}")
                continue
            if ev not in body:
                problems.append(f"{s} 的 evidence 在 {w} 里找不到：{ev[:20]}…")'''
assert old in s, "redteam 证据块未匹配"
s = s.replace(old, new, 1)

# 自检样本也随之改：没有 where/evidence 必须 FAIL
s = s.replace(
    'quote=("We decompose the object into classes"\n'
    '                                    " with different sources") )',
    'where="gate.py", evidence="NA_ABSENT")')
io.open(P, "w", encoding="utf-8", newline="\n").write(s)
print("redteam：证据要求改为 文件 + 逐字标记")
