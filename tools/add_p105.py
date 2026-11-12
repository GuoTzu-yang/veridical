import ast
import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "patches.py")
s = open(P, encoding="utf-8").read()

F = "\n".join([
 "def _p105_wired():",
 "    import json as _j",
 "    import os as _o",
 "    p = _o.path.join(HERE, 'schema.json')",
 "    if not _o.path.exists(p):",
 "        return False, 'no schema.json'",
 "    d = _j.load(open(p, encoding='utf-8'))",
 "    bad = []",
 "    miss = [k for k, v in d['commands'].items() if not v.get('desc')]",
 "    if miss:",
 "        bad.append('no desc: ' + ','.join(miss[:4]))",
 "    if len(d['commands']) < 19:",
 "        bad.append('only %d commands' % len(d['commands']))",
 "    if bad:",
 "        return False, '; '.join(bad)",
 "    return True, '%d commands all carry desc' % len(d['commands'])",
 "",
 "",
 "def _p106_wired():",
 "    import os as _o",
 "    import re as _re",
 "    m = open(_o.path.join(HERE, 'mmkit.py'), encoding='utf-8').read()",
 "    bad = []",
 "    if 'def _emit(' not in m:",
 "        bad.append('no _emit')",
 "    if 'sys.stdout = sys.stderr' not in m:",
 "        bad.append('json mode not redirecting')",
 "    if 'print(json.dumps(' in m:",
 "        bad.append('raw print(json.dumps) still present')",
 "    if bad:",
 "        return False, '; '.join(bad)",
 "    return True, '--json: prompts to stderr, JSON via sys.__stdout__'",
 "",
 ""])

if "_p105_wired" not in s:
    k = s.find("def _p101_wired")
    assert k > 0
    s = s[:k] + F + s[k:]
    for pid, cat, title, why in (
        ("P105", "① 知识", "命令能力可发现（schema desc）",
         "22 个命令的 --help 输出完全一样（参数全挂顶层），LLM 分不出 race 和 run，只能退回 run"),
        ("P106", "④ 验证", "--json 输出净化",
         "提示与 JSON 混在 stdout，LLM 解析前得剥皮；剥皮一脆就退回一条龙"),
    ):
        anchor = '    Patch("P101",'
        entry = ('    Patch("' + pid + '", "' + cat + '", "' + title + '",\n'
                 '          "' + why + '",\n'
                 '          _' + pid.lower() + '_wired,\n'
                 '          tags=["done"]),\n' + anchor)
        s = s.replace(anchor, entry, 1)
    ast.parse(s)
    compile(s, P, "exec")
    open(P, "w", encoding="utf-8", newline="\n").write(s)
    print("  added P105 + P106")

import subprocess, sys
r = subprocess.run([sys.executable, "patches.py", "verify"],
                   capture_output=True, text=True, encoding="utf-8",
                   errors="replace", cwd=HERE)
for ln in (r.stdout or "").splitlines():
    if "P105" in ln or "P106" in ln or "已落实" in ln:
        print("  " + ln.strip()[:96])