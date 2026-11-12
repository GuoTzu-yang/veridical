#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""chk_proof.py / chk_iterlog.py 的判据实现（第 124 轮）。

**为什么加这两道门**：

外部评审在对工具论文的评语里说：
  「A/B 实验节方向正确……但插件臂在问题 2 上丢分，因为它用**可检查的等式替代了证明**。」

这句话点出的是插件的结构性缺陷，不是使用问题：
**33 道门里没有一道查「你有没有把关键推导写成命题并给出证明」。**
门在哪，注意力就在哪 —— 所以证明变薄了。

## 门 1：`proof`

判据三件：
  A. 有命题环境（`\\begin{proposition}` / `theorem` / `lemma` / `corollary`）≥ 1 个
  B. 有证明环境（`\\begin{proof}`）≥ 1 个
  C. **证明不空**：`\\begin{proof}` 与 `\\end{proof}` 之间 ≥ 60 字符（去掉空白）

为什么 C 也要查：`\\begin{proof}\\end{proof}` 是能被 A/B 骗过的空壳。

## 门 2：`iteration-log`

第 124 轮读了对照组的 `PROCESS_SUMMARY.md`，它最值得抄的一件东西是这张表：

    轮 | 现象 | 诊断 | 修正
    1  | θ=3.58e6 异常大 | 储能功率无 LDR 项 | 给 p^c/p^d/e 加仿射响应
    2  | θ=0 | 模型自造「负遗憾」 | θ 改双向
    ...

标题是「**迭代史（每轮都是「解出来了但结论不可信」）**」。

这是「自我怀疑」的可执行形式。我的插件有 7 个纠错案例，但**没有一张「逐轮」表**
—— 案例是「事后复盘」，迭代史是「过程中每次不信」。

判据：
  A. 有一张表，表头同时含「轮」与（「现象」或「症状」）与（「诊断」或「原因」）与（「修正」或「处理」）
  B. 表体 ≥ 3 行
  C. 至少一行同时出现「不可信 / 异常 / 对不上 / 反而 / 退化」这类**不信判据**词

用法：
    python tools/quality_doors.py proof out/final
    python tools/quality_doors.py iterlog out/final
    python tools/quality_doors.py selftest        # 构造缺陷自校
退出码：0 通过；1 不通过。
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PROP_ENVS = ("proposition", "theorem", "lemma", "corollary")
DOUBT = (
    # 中文
    "不可信", "异常", "对不上", "反而", "退化", "不合理", "不符合",
    "可疑", "冲突", "不是预期", "反直觉", "错了",
    # 英文（第 124 轮补：英文工具论文的迭代表用的是这些词）
    "not believable", "implausible", "wrong sign", "wrongly", "was wrong",
    "false positive", "disagree", "looked like", "would have meant",
    "too large", "too small", "unexpected",
)
MIN_PROOF_CHARS = 60
MIN_ITER_ROWS = 3


def _tex(figdir):
    for n in ("paper.tex", "main.tex"):
        for sub in ("", "paper"):
            p = os.path.join(figdir, sub, n) if sub else os.path.join(figdir, n)
            if os.path.exists(p):
                return io.open(p, encoding="utf-8", errors="replace").read(), p
    return None, None


def _subs(t):
    """把 \\input 进来的文件也拼上（tab_checks 之类）。"""
    out = t
    d = None
    for m in re.finditer(r"\\input\{([^}]*)\}", t):
        f = m.group(1)
        for cand in (f, f + ".tex"):
            p = os.path.join(HERE, "out", "final", cand)
            if os.path.exists(p):
                out += "\n" + io.open(p, encoding="utf-8", errors="replace").read()
                break
    return out


def check_proof(t):
    """门 1。返回 (ok, detail, problems)。"""
    probs = []
    n_prop = 0
    for e in PROP_ENVS:
        n_prop += len(re.findall(r"\\begin\{%s\}" % e, t))
    proofs = re.findall(r"\\begin\{proof\}(.*?)\\end\{proof\}", t, re.S)
    n_proof = len(proofs)
    if n_prop == 0:
        probs.append("没有任何命题环境（proposition/theorem/lemma）—— "
                     "关键推导没有写成可证对象，外部评审会认为「只有等式没有证明」")
    if n_proof == 0:
        probs.append("没有任何 proof 环境 —— 有命题没证明")
    empty = [i + 1 for i, p in enumerate(proofs)
             if len(re.sub(r"\s|%.*", "", p)) < MIN_PROOF_CHARS]
    if empty:
        probs.append(f"第 {empty} 个 proof 少于 {MIN_PROOF_CHARS} 个有效字符 —— 空壳证明不算证明")
    if probs:
        return False, "；".join(probs), probs
    return True, f"{n_prop} 个命题，{n_proof} 个证明，最短 {min(len(re.sub(r'[ \t\n]', '', p)) for p in proofs)} 字符", []


def check_iterlog(t):
    """门 2。找「轮 | 现象 | 诊断 | 修正」结构。"""
    probs = []
    # 找 tabular/longtable 块，看表头是否四件齐
    best = None
    for m in re.finditer(r"\\begin\{(?:tabular|longtable)\}(?:\{[^}]*\})(.*?)\\end\{(?:tabular|longtable)\}",
                         t, re.S):
        body = m.group(1)
        head = body.split("\\\\")[0] if "\\\\" in body else body[:300]
        # 中英两套都要认：本插件的中文论文与英文工具论文都存在
        hl = head.lower()
        has_round = ("轮" in head) or ("round" in hl)
        has_sym = ("现象" in head) or ("症状" in head) or ("symptom" in hl) or ("observed" in hl)
        has_diag = ("诊断" in head) or ("原因" in head) or ("diagnosis" in hl) or ("root cause" in hl)
        has_fix = ("修正" in head) or ("处理" in head) or ("fix" in hl) or ("repair" in hl)
        if has_round and has_sym and has_diag and has_fix:
            rows = [r for r in body.split("\\\\")[1:] if r.strip()]
            best = (len(rows), body)
            break
    if not best:
        probs.append("没有「轮 | 现象 | 诊断 | 修正」四件齐的表 —— "
                     "「解出来了但结论不可信」这件事没有被逐轮记下来。"
                     "对照组的这张表是它最强的东西，本插件缺这一项")
        return False, "；".join(probs), probs
    n_rows, body = best
    if n_rows < MIN_ITER_ROWS:
        probs.append(f"迭代表只有 {n_rows} 行（< {MIN_ITER_ROWS}）—— 少于三轮不像迭代史")
    if not any(w in body for w in DOUBT):
        probs.append("迭代表里没有任何「不信」判据词（不可信/异常/对不上/退化…）"
                     "—— 只有「改了」没有「为什么不信」")
    if probs:
        return False, "；".join(probs), probs
    return True, f"迭代表 {n_rows} 行，含不信判据", []


SAMPLE_BAD = r"""\documentclass{article}
\begin{document}
\section{Model}
We claim the dual holds.
\begin{equation} \sup E[Q] = \frac1N\sum Q + \varepsilon\|a\|_\infty \end{equation}
\end{document}
"""

SAMPLE_GOOD = r"""\documentclass{article}
\begin{document}
\section{Model}
\begin{proposition}[Dual]
If Q is affine in xi, then the worst-case expectation is finite and equals
the sample mean plus the radius times the dual norm of the coefficient vector.
\end{proposition}
\begin{proof}
The inner supremum separates componentwise. For each coordinate the sup of
a_j xi_j minus lambda times the absolute deviation is attained at the sample
point whenever the absolute coefficient does not exceed lambda, and is unbounded
otherwise; hence feasibility forces lambda at least the supremum norm and the
choice lambda equal to that norm is tight, which yields the stated identity.
\end{proof}
\section{Iterations}
\begin{tabular}{llll}
轮 & 现象 & 诊断 & 修正 \\
1 & theta 异常大 & 功率无响应项 & 加仿射响应 \\
2 & theta 等于零 & 自造负遗憾 & 改双向约束 \\
3 & 仍为零 & 可透支初始电量 & 加循环闭合 \\
\end{tabular}
\end{document}
"""


def selftest():
    """构造缺陷自校：坏样本必须两道都不过，好样本必须两道都过。"""
    ok = True
    for name, body, want in (("坏样本", SAMPLE_BAD, False), ("好样本", SAMPLE_GOOD, True)):
        p_ok, p_det, _ = check_proof(body)
        i_ok, i_det, _ = check_iterlog(body)
        both = p_ok and i_ok
        good = (both == want)
        ok = ok and good
        print("  [%s] %s → proof=%s iterlog=%s（期望%s）"
              % ("PASS" if good else "**FAIL**", name,
                 "过" if p_ok else "不过", "过" if i_ok else "不过",
                 "都过" if want else "都不过"))
        if not good:
            print("       proof: %s" % p_det[:120])
            print("       iterlog: %s" % i_det[:120])
    print()
    if not ok:
        print("**自校失败**：判据坏了，今天的结论都不能用")
        return 1
    print("自校通过：坏样本两道都拦住，好样本两道都放行。")
    return 0


def main(argv):
    if not argv or argv[0] == "selftest":
        return selftest()
    cmd = argv[0]
    d = argv[1] if len(argv) > 1 else os.path.join(HERE, "out", "final")
    if not os.path.isabs(d):
        d = os.path.join(HERE, d)
    t, path = _tex(d)
    if t is None:
        print("没有 %s/paper.tex 或 main.tex" % d)
        return 2
    t = _subs(t)
    if cmd == "proof":
        ok, det, _ = check_proof(t)
    elif cmd == "iterlog":
        ok, det, _ = check_iterlog(t)
    else:
        print("未知子命令：%s（proof / iterlog / selftest）" % cmd)
        return 2
    print("  [%s] %s —— %s" % ("OK" if ok else "FAIL", cmd, det))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

