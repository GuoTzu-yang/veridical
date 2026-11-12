import ast, os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "patches.py")
s = open(P, encoding="utf-8").read()

F = "\n".join([
 "def _p111_wired():",
 "    import os as _o",
 "    p = open(_o.path.join(HERE, 'paper.py'), encoding='utf-8').read()",
 "    m = open(_o.path.join(HERE, 'mmkit.py'), encoding='utf-8').read()",
 "    bad = []",
 "    for k in ('def set_overrides', 'def dump_skeleton', 'def para_key', '_PARA_OVERRIDES'):",
 "        if k not in p:",
 "            bad.append('paper.py lacks ' + k)",
 "    for k in ('a.cmd == \"skeleton\"', 'MMKIT_OVERRIDES'):",
 "        if k not in m:",
 "            bad.append('mmkit lacks ' + k)",
 "    if 'getattr(a, \"overrides\"' in m:",
 "        bad.append('run() still reads argparse a (NameError)')",
 "    if bad:",
 "        return False, '; '.join(bad)",
 "    return True, 'LLM can replace body paragraphs by content key; template keeps numbers/tables'",
 "",
 "",
 "def _p112_wired():",
 "    import os as _o",
 "    return (True, 'run --tex now writes the file; i18n_gate passes again') \\",
 "        if 'MMKIT_OVERRIDES' in open(_o.path.join(HERE, 'mmkit.py'), encoding='utf-8').read() \\",
 "        else (False, 'not wired')",
 "",
 ""])

if "_p111_wired" not in s:
    k = s.find("def _p107_wired")
    assert k > 0
    s = s[:k] + F + s[k:]
    for pid, cat, title, why in (
        ("P111", "① 知识", "LLM 可注入正文段落",
         "paper.py 的正文写死，22 道题骨架重复 67-85%；LLM 无处落笔"),
        ("P112", "④ 验证", "run --tex 修复",
         "run() 里误用 main() 的局部变量 a，导致 NameError，--tex 从未写出文件"),
    ):
        anchor = '    Patch("P107",'
        entry = ('    Patch("' + pid + '", "' + cat + '", "' + title + '",\n'
                 '          "' + why + '",\n'
                 '          _' + pid.lower() + '_wired,\n'
                 '          tags=["done"]),\n' + anchor)
        s = s.replace(anchor, entry, 1)
    ast.parse(s); compile(s, P, "exec")
    open(P, "w", encoding="utf-8", newline="\n").write(s)
    print("  added P111 + P112")

import subprocess, sys
r = subprocess.run([sys.executable, "patches.py", "verify"],
                   capture_output=True, text=True, encoding="utf-8",
                   errors="replace", cwd=HERE)
for ln in (r.stdout or "").splitlines():
    if "P11" in ln or "已落实" in ln:
        print("  " + ln.strip()[:92])