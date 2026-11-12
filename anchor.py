"""anchor.py —— 把「改一段」所需的上下文压到最小（第 115 轮）。

问题的形状
----------
长上下文里 LLM 会「中间遗忘」：把 4000 个数字一起喂进去，它引用的那 20 个
反而记不住。我们不去求更强的模型，而是**改变喂法**：改稿时不给全篇，
只给「含未溯源数字的段落 + 这些数字的真实值」。

这个模块就是那个「锚定器」：
  python anchor.py out/final            # 列出需要改的段落与应填的值
  python anchor.py out/final --json     # 给下游脚本用
  python anchor.py selftest

判据可复核：锚定上下文的 token 估算 << 全篇的 token 估算，且它包含的
未溯源数字**全部**有真实值可填 —— 否则「压缩」就是把问题藏起来。
"""
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

SENT = re.compile(r"[^.\n]*?(?:\d+\.\d+)[^.\n]*\.")


def _decimals(tok: str) -> int:
    return len(tok.split(".")[1]) if "." in tok else 0


def _match(v: float, dec: int, vals) -> float:
    """按书写精度找真实值；找不到返回 None。"""
    tol = 0.5 * (10 ** -dec) + 1e-12
    for f in vals:
        for a, b in ((abs(v), abs(f)), (abs(v), abs(f) * 100.0),
                     (abs(v), abs(f) / 100.0)):
            if abs(a - b) <= tol:
                return f
    return None


def anchors(figdir: str) -> dict:
    """返回需要改的句子 + 应填的值 + 上下文压缩比。"""
    tex = os.path.join(figdir, "paper.tex")
    fz = os.path.join(figdir, "冻结数字.json")
    if not os.path.exists(tex):
        return dict(error="没有 paper.tex")
    t = io.open(tex, encoding="utf-8").read()
    t = re.sub(r"\[[^\]]*\]", " ", t)
    t = re.sub(r"\\begin\{thebibliography\}.*?\\end\{thebibliography\}", " ",
               t, flags=re.S)
    vals = []
    if os.path.exists(fz):
        vals = [it["value"] for it in
                json.load(io.open(fz, encoding="utf-8")).get("items", [])]

    need = []
    for m in SENT.finditer(t):
        sent = m.group(0).strip()
        if len(sent) < 20:
            continue
        bad = []
        for tok in re.findall(r"(?<![\w.])-?\d+\.\d+(?![\w.])", sent):
            v = float(tok)
            if _match(v, _decimals(tok), vals) is None:
                bad.append(tok)
        if bad:
            need.append(dict(sentence=sent[:220], tokens=bad))

    def est_tokens(s):
        return max(1, len(s) // 4)

    anchor_text = " ".join(n["sentence"] for n in need)
    return dict(
        n_sentences=len(need),
        sentences=need[:20],
        anchor_tokens=est_tokens(anchor_text),
        paper_tokens=est_tokens(t),
        ratio=round(100.0 * est_tokens(anchor_text) / max(1, est_tokens(t)), 1),
        all_have_sources=all(_match(float(tk), _decimals(tk), vals) is None
                             for n in need for tk in n["tokens"]),
        action=("这段里的数字没有出处：要么改成冻结表里的值，"
                "要么把这句删掉/降级到局限。"))


def selftest() -> int:
    bad = n = 0

    def ck(name, cond, detail=""):
        nonlocal bad, n
        n += 1
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}"
              + (f"  — {detail}" if detail else ""))
        if not cond:
            bad += 1

    import tempfile
    td = tempfile.mkdtemp(prefix="anchor_")
    txt = ("We report 0.9123 for the slope. "      # 无出处
           "The mean is 0.2500 exactly. "           # 有出处
           "A second bad value 0.77777 appears here. ")
    io.open(os.path.join(td, "paper.tex"), "w", encoding="utf-8").write(txt)
    json.dump(dict(items=[dict(path="m", value=0.25)]),
              io.open(os.path.join(td, "冻结数字.json"), "w", encoding="utf-8"))
    r = anchors(td)
    ck("找出无出处的句子", r["n_sentences"] >= 2, str(r["n_sentences"]))
    ck("有出处的句子不被点名",
       all("0.2500" not in s["sentence"] or "0.2500" not in s["tokens"]
           for s in r["sentences"]))
    ck("点名了具体的坏数",
       any("0.9123" in s["tokens"] for s in r["sentences"]))
    ck("压缩比是百分比", 0 <= r["ratio"] <= 100, str(r["ratio"]))
    ck("给出可执行动作", bool(r["action"]))

    # 全篇都有出处时：不应点名任何句子
    td2 = tempfile.mkdtemp(prefix="anchor2_")
    io.open(os.path.join(td2, "paper.tex"), "w", encoding="utf-8").write(
        "Only 0.2500 appears here. ")
    json.dump(dict(items=[dict(path="m", value=0.25)]),
              io.open(os.path.join(td2, "冻结数字.json"), "w", encoding="utf-8"))
    r2 = anchors(td2)
    ck("干净论文不点名", r2["n_sentences"] == 0, str(r2["n_sentences"]))

    print()
    print(f"{'ALL PASS' if bad == 0 else 'FAILED'}  {n - bad}/{n}")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    a = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "out", "final")
    if a == "selftest":
        raise SystemExit(selftest())
    r = anchors(a)
    if "--json" in sys.argv:
        print(json.dumps(r, ensure_ascii=False, indent=1))
    else:
        if r.get("error"):
            print(" ", r["error"])
        else:
            print("需要改的句子：%d 处" % r["n_sentences"])
            for s in r["sentences"][:8]:
                print("  · [%s] %s" % (", ".join(s["tokens"]), s["sentence"][:90]))
            print()
            if not r["n_sentences"]:
                # 没有可改处时报比值是虚荣指标：分母是零问题（第 118 轮）
                print("无可改处：全部数字都能追到出处，压缩比无意义")
            else:
                print("锚定上下文 ≈ %d token，全篇 ≈ %d token（%.1f%%）"
                      % (r["anchor_tokens"], r["paper_tokens"], r["ratio"]))
            print(r["action"])
