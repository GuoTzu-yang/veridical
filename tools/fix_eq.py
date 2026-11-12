import ast
import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "paper.py")
s = open(P, encoding="utf-8").read()

OLD = ('    _is_generic = (det.get("key") == "generic")\n'
       '    _eq, _eq2 = (_dom.equations(det)\n'
       '                 if (_mech == "full" or _is_generic)\n'
       '                 else ("", ""))')
assert OLD in s, "no anchor"
NEW = ('    _is_generic = (det.get("key") == "generic")\n'
       '    # domain_extra 里那五个领域（评价/预测/图论/排队/增长）的公式是\n'
       '    # **通用式**：加权和、预测区间、最短路、Little 定律、logistic 增长。\n'
       '    # 它们不含任何题目的专有名词，任何题用都不算错，所以不必等\n'
       '    # _mech == "full"。原来这里把它们和 heat_transfer 的 Nu/Re/Pr\n'
       '    # 一视同仁地挡在 full 之后，结果 22 道题里 0 道用上这些公式 ——\n'
       '    # 造好了、从没进过论文。\n'
       '    # 仍然拦在 full 之后的只有含专有名词的领域（传热等）。\n'
       '    _SAFE_EQ = {"generic", "evaluation", "prediction", "network",\n'
       '                "queueing", "population"}\n'
       '    _eq_ok = (_mech == "full" or _is_generic\n'
       '              or str(det.get("key") or "") in _SAFE_EQ)\n'
       '    _eq, _eq2 = (_dom.equations(det) if _eq_ok else ("", ""))')
s = s.replace(OLD, NEW, 1)
ast.parse(s); compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  公式现在对 5 个通用领域生效")