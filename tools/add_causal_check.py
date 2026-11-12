"""新增 chk_causal：因果措辞必须有设计支撑（第 114 轮）。

种子缺陷基准里，唯一 0/5 的缺陷是 `unsupported_claim` —— 把「相关」改写成
「证明了因果」，而 gate 里没有任何一条检查因果措辞。这是真实缺口：
观测数据上的因果断言是最常见的过度声称，也正是评审最容易抓的。

判据（写死在这里，可复核）：
  ① 因果措辞：proves / causes / causal effect / leads to / drives / because of
  ② 设计支撑：experiment / randomis / instrument / counterfactual / difference-in
     / Granger / control group / natural experiment
  ③ 有 ① 无 ② → WARN（不判硬失败：语料里「驱动因素」这类用法不一定过度；
     但警告必须被清掉，所以它进得了 gate 的可见状态）
"""
import io

P = r"C:\Users\21246\Documents\deepseek-harness\default-workspace\model1-arch\gate.py"
s = io.open(P, encoding="utf-8").read()

anchor = "def chk_claims(figdir: str) -> dict:"
new = '''def chk_causal(figdir: str) -> dict:
    """因果措辞是否配了因果设计（第 114 轮，种子缺陷基准逼出来的缺口）。

    一个把「相关」写成「证明了因果」的论文，能通过原来的全部检查 ——
    因为没有任何一条读措辞。这里加一条最小可行的：断言因果就要说明设计。
    """
    import re as _re
    p = os.path.join(figdir, "paper.tex")
    if not os.path.exists(p):
        return _na("causal", SOFT, "没有 paper.tex", NA_ABSENT)
    t = io.open(p, encoding="utf-8").read().lower()
    claim = ("proves", "prove that", "causes", "causal effect", "leads to",
             "drives", "because of", "证明了", "导致", "因果")
    design = ("experiment", "randomis", "randomiz", "instrument",
              "counterfactual", "difference-in-difference", "granger",
              "control group", "natural experiment", "ablation",
              "准实验", "随机", "反事实")
    hit_c = [w for w in claim if w in t]
    hit_d = [w for w in design if w in t]
    if not hit_c:
        return _r("causal", SOFT, "PASS", "没有因果措辞，无需设计支撑")
    if hit_d:
        return _r("causal", SOFT, "PASS",
                  "有因果措辞（%s），并且交代了设计（%s）"
                  % (", ".join(hit_c[:2]), ", ".join(hit_d[:2])))
    return _r("causal", SOFT, "WARN",
              "有因果措辞（%s）但没有交代任何识别设计 —— "
              "要么降级为相关，要么说明凭什么能推因果"
              % ", ".join(hit_c[:3]))


''' + anchor
assert anchor in s, "chk_claims 锚点未匹配"
s = s.replace(anchor, new, 1)

# 挂进 checks 列表（claims 之后）
a2 = '        chk_claims(figdir),'
s = s.replace(a2, a2 + '\n        chk_causal(figdir),', 1)

io.open(P, "w", encoding="utf-8", newline="\n").write(s)
print("chk_causal 已加入 gate")
