import ast
import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "patches.py")
s = open(P, encoding="utf-8").read()

F = "\n".join([
 "def _p107_wired():",
 "    import os as _o",
 "    m = open(_o.path.join(HERE, 'mmkit.py'), encoding='utf-8').read()",
 "    o = open(_o.path.join(HERE, 'orchestrate.py'), encoding='utf-8').read()",
 "    bad = []",
 "    if 'def rule_propose' not in o:",
 "        bad.append('no rule_propose')",
 "    if 'a.cmd == \"experiment\"' not in m:",
 "        bad.append('experiment not wired')",
 "    if '\"experiment\"' not in m.split('choices=[')[1][:400]:",
 "        bad.append('experiment not in choices')",
 "    if bad:",
 "        return False, '; '.join(bad)",
 "    return True, 'mmkit experiment: propose-exec-judge loop, rule_propose built in'",
 "",
 "",
 "def _p108_wired():",
 "    import os as _o",
 "    m = open(_o.path.join(HERE, 'mmkit.py'), encoding='utf-8').read()",
 "    if 'a.cmd == \"contract\"' not in m:",
 "        return False, 'contract not wired'",
 "    return True, 'mmkit contract: validate proposals, reject empty/same-structure batches'",
 "",
 "",
 "def _p109_wired():",
 "    import os as _o",
 "    v = open(_o.path.join(HERE, 'verify.py'), encoding='utf-8').read()",
 "    if 'def main(argv=None)' not in v:",
 "        return False, 'verify.py still selftest-only'",
 "    return True, 'verify.py has CLI: check a real paper, not just selftest'",
 "",
 "",
 "def _p110_wired():",
 "    import os as _o",
 "    import sys as _s",
 "    _s.path.insert(0, HERE)",
 "    import verify as _v",
 "    bad = []",
 "    if _v._near(0.9999, 1.0):",
 "        bad.append('0.9999 still matched by 1.0')",
 "    if _v._near(0.9999, 0.9975):",
 "        bad.append('0.9999 still matched by 0.9975')",
 "    if not _v._near(0.00743, 0.0074342):",
 "        bad.append('legit rounding rejected')",
 "    if bad:",
 "        return False, '; '.join(bad)",
 "    return True, 'a must be round(b, decimals(a)); fabricated digits now caught'",
 "",
 ""])

if "_p107_wired" not in s:
    k = s.find("def _p105_wired")
    assert k > 0
    s = s[:k] + F + s[k:]
    for pid, cat, title, why in (
        ("P107", "① 知识", "试错循环接入主入口",
         "orchestrate.py 625 行、selftest 15/15，但 mmkit 里出现 0 次"),
        ("P108", "① 知识", "提案契约接入",
         "contract.py 能挡空话提案，但没接进主入口；LLM 的空话无人拦"),
        ("P109", "④ 验证", "verify 可查真实论文",
         "__main__ 原来只跑 selftest，新会话没法用自己的论文"),
        ("P110", "④ 验证", "数字溯源防编造",
         "1.0 能匹配 0.9999（相对差 0.01%），编一个高分轻松溜过"),
    ):
        anchor = '    Patch("P105",'
        entry = ('    Patch("' + pid + '", "' + cat + '", "' + title + '",\n'
                 '          "' + why + '",\n'
                 '          _' + pid.lower() + '_wired,\n'
                 '          tags=["done"]),\n' + anchor)
        s = s.replace(anchor, entry, 1)
    ast.parse(s); compile(s, P, "exec")
    open(P, "w", encoding="utf-8", newline="\n").write(s)
    print("  added P107-P110")

import subprocess, sys
r = subprocess.run([sys.executable, "patches.py", "verify"],
                   capture_output=True, text=True, encoding="utf-8",
                   errors="replace", cwd=HERE)
for ln in (r.stdout or "").splitlines():
    if "P10" in ln or "已落实" in ln:
        print("  " + ln.strip()[:94])