#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""prompt_fidelity.py —— 题面必须落地、必须被逐字引用、每一问必须被回应。

用户的原话：**「要约束 LLM 认真地读取题目信息，不允许猜，不允许跳过。」**

这三件事原来**零约束**：

1. **题面根本没落地**
   实测 `out/d2026c`：目录里没有任何题面原文文件，正文的
   `What the problem asks` 是「The task is to reconstruct it, to say how much
   confidence..., to compare..., to quantify..., to propose...」—— 这是**概括**。
   概括不是错，但**无法核实它是否忠实**：读者不知道题面是不是真的这么问的。

2. **Restatement 可以凭空写**
   `paper.tex` 里有 `\\section{Restatement of the problem}` 就算过 —— 而这一节
   完全可以凭记忆写，没有任何东西比对它与原文。

3. **「每一问」没有机械计数**
   题面说「讨论 (1)(2)(3)」，论文只答 (1)(2) —— 没有工具会红。
   红队 `restatement` 板有探针，但那依赖 agent 认真做，不是机械保证。

判据（三件）：

  A. `out/<dir>/题目.md`（或 `prompt.md` / `题目.txt`）存在，且长度 ≥ 200 字符。
     —— 这是「原文落地」，不许用概括代替。

  B. `paper.tex` 的 Restatement 节里，有一段 ≥ 40 个字符与题面**逐字连续一致**。
     —— 这证明作者真的读过原文，而不是凭记忆转述。
     允许用 LaTeX 转义（`\\%` `\\_` `$` `\\&`），比对前统一剥离。

  C. 题面里的编号小问（`(1)` `(2)` / `1.` `2.` / `Problem 1` / `问1`）的个数
     **不大于**论文里 `\\textbf{Problem N.}` / `Problem N` / `(N)` 的覆盖数。
     —— 「不许跳过」。

用法：
    python tools/prompt_fidelity.py out/d2026c
    python tools/prompt_fidelity.py --all
退出码：0 全过；1 有缺。
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CANDIDATES = ("题目.md", "题目.txt", "prompt.md", "prompt.txt", "PROBLEM.md")
MIN_PROMPT = 200
MIN_QUOTE = 40


def _norm(s):
    """把 LaTeX 转义与空白归一，便于逐字比对。"""
    s = re.sub(r"\\[%_&$#{}]", lambda m: m.group(0)[1], s)
    s = re.sub(r"\s+", "", s)
    return s


def find_prompt(d):
    for n in CANDIDATES:
        p = os.path.join(d, n)
        if os.path.exists(p):
            return p
    return None


def sub_questions(prompt):
    """题面里的编号小问。返回集合（去重后的编号）。"""
    nums = set()
    for pat in (r"\((\d{1,2})\)", r"(?m)^\s*(\d{1,2})[.、]", r"Problem\s+(\d{1,2})",
                r"问题\s*(\d{1,2})", r"第\s*(\d{1,2})\s*问"):
        for m in re.finditer(pat, prompt):
            nums.add(int(m.group(1)))
    return nums


def answered(tex):
    """论文里被回应的编号。"""
    nums = set()
    for pat in (r"\\textbf\{Problem\s+(\d{1,2})", r"Problem\s+(\d{1,2})",
                r"\\paragraph\{Problem\s+(\d{1,2})", r"(?m)^\s*\((\d{1,2})\)",
                r"问题\s*(\d{1,2})"):
        for m in re.finditer(pat, tex):
            nums.add(int(m.group(1)))
    return nums


def check_dir(d):
    tex_p = os.path.join(d, "paper.tex")
    if not os.path.exists(tex_p):
        return None
    tex = io.open(tex_p, encoding="utf-8", errors="replace").read()
    probs, notes = [], []

    pp = find_prompt(d)
    if not pp:
        probs.append(f"没有题面原文（找过 {', '.join(CANDIDATES)}）—— "
                     "「认真读题」无法核实：正文的 Restatement 可能是凭记忆转述的。"
                     "开工第一步就该把原题存成 题目.md")
        return dict(dir=d, problems=probs, notes=notes, prompt=None)

    prompt = io.open(pp, encoding="utf-8", errors="replace").read()
    if len(prompt) < MIN_PROMPT:
        probs.append(f"题面只有 {len(prompt)} 字符（< {MIN_PROMPT}）—— "
                     "看着像摘要而不是原文")

    # B. 逐字引用
    np_, nt = _norm(prompt), _norm(tex)
    hit = 0
    L = MIN_QUOTE
    while L <= len(np_) and L <= 400:
        found = False
        for i in range(0, len(np_) - L + 1, max(1, L // 4)):
            if np_[i:i + L] in nt:
                found = True
                break
        if found:
            hit = L
            break
        L += 20
    if not hit:
        probs.append(f"正文与题面**没有 {MIN_QUOTE} 字以上的逐字一致片段** —— "
                     "Restatement 是转述，无法证明读过原文。"
                     "（允许 LaTeX 转义，比对前已归一）")
    else:
        notes.append(f"最长逐字一致片段 ≥ {hit} 字符")

    # C. 小问覆盖
    qs = sub_questions(prompt)
    ans = answered(tex)
    if qs:
        miss = sorted(qs - ans)
        if miss:
            probs.append(f"题面有编号小问 {sorted(qs)}，正文只回应了 {sorted(ans)} —— "
                         f"**跳过** {miss}。不许跳过：要么答，要么在正文写明「不作答 + 理由」")
        else:
            notes.append(f"题面 {len(qs)} 问，正文覆盖 {len(qs)} 问")
    else:
        notes.append("题面没有编号小问（无法做「不许跳过」的机械检查）")
    return dict(dir=d, problems=probs, notes=notes, prompt=os.path.basename(pp))


def cmd_seed():
    """从 runs.json 的 `problem` 字段，为每一题生成 `题目.md`。

    这是「题面落地」的自动通道：23 道题的题面原文本来就在 `runs.json` 里，
    只是从没被写成文件，于是 `prompt_fidelity` 无从比对，Restatement 也就
    可以凭记忆写。**原文一直都在，缺的只是落地这一步。**

    不覆盖已存在的文件（人工存过的原文优先）。
    """
    import json
    runs = json.load(io.open(os.path.join(HERE, "runs.json"), encoding="utf-8"))
    n_new = n_skip = n_none = 0
    for name, cfg in runs.items():
        prob = cfg.get("problem")
        if not prob:
            n_none += 1
            continue
        outdir = cfg.get("out") or os.path.join("out", "runs", name)
        d = outdir if os.path.isabs(outdir) else os.path.join(HERE, outdir)
        if not os.path.isdir(d):
            n_none += 1
            continue
        dst = os.path.join(d, "题目.md")
        if os.path.exists(dst):
            n_skip += 1
            continue
        io.open(dst, "w", encoding="utf-8", newline="\n").write(
            "<!-- 原文，来自 runs.json 的 problem 字段；不要改写 -->\n\n"
            + str(prob).strip() + "\n")
        n_new += 1
    print(f"题面落地：新写 {n_new}，已存在 {n_skip}，无题面/无目录 {n_none}")
    return 0


def main(argv):
    if "--seed" in argv:
        return cmd_seed()
    if "--all" in argv:
        # 只扫**交稿目录**（有 declaration.json 且 deliverable=true）。
        # 原来扫 out/**/paper.tex，命中 89 个 —— 其中 66 个是 out/runs 复制出来的
        # 派生物（out/drill/*、out/domains/*、out/t1-t5），它们不是原创目录，
        # 要求每个都有题面是噪声，会把真缺口埋掉。
        import json
        dirs = []
        for root, _ds, fs in os.walk(os.path.join(HERE, "out")):
            if "paper.tex" not in fs:
                continue
            decl = os.path.join(root, "declaration.json")
            if not os.path.exists(decl):
                continue
            try:
                j = json.load(io.open(decl, encoding="utf-8"))
            except Exception:                       # noqa: BLE001
                continue
            if j.get("deliverable"):
                dirs.append(root)
        if not dirs:
            print("没有 deliverable 目录 —— 先在各目录写 declaration.json")
            return 0
    else:
        dirs = [a for a in argv[1:] if not a.startswith("-")] or \
               [os.path.join(HERE, "out", "final")]
    rows = [r for r in (check_dir(d) for d in dirs) if r]
    bad = [r for r in rows if r["problems"]]
    for r in rows:
        tag = "缺" if r["problems"] else "全"
        print(f"  [{tag}] {os.path.relpath(r['dir'], HERE)}"
              + (f"   题面: {r['prompt']}" if r.get("prompt") else ""))
        for p in r["problems"]:
            print(f"       ✗ {p}")
        for n in r["notes"]:
            print(f"       · {n}")
    print()
    print(f"检查 {len(rows)} 个目录：有缺 {len(bad)}，全过 {len(rows) - len(bad)}")
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
