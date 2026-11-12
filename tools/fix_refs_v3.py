"""修 chapters 的引用绑定：只认 table/figure 环境里的标签（第 121 轮，第三版）。

上一版把 \\section{...} 的 \\label{sec:wrong} 也当成"表的标签"，
于是纠错节（本来没有表）被判成"表没被引用"。
"""
import io

HERE = r"C:\Users\21246\Documents\deepseek-harness\default-workspace\model1-arch"
q = HERE + r"\chapters.py"
t = io.open(q, encoding="utf-8").read()

old = (
    '    _defined = set(re.findall(r"\\\\label\\{([^}]*)\\}", body))\n'
    '    for _txt in _table_texts(body, figdir)[1:]:\n'
    '        _defined |= set(re.findall(r"\\\\label\\{([^}]*)\\}", _txt))\n'
    '    _refs = set(re.findall(r"\\\\ref\\{([^}]*)\\}", body))\n'
    '    if _defined and not (_defined & _refs):\n'
    '        return False, ("本节的表没有被本节正文引用（\\ref）"\n'
    '                       "—— 这张表不属于这一节")\n'
)
new = (
    '    # 只认 table/figure 环境里的标签 —— \\section 的 \\label 不是表的标签\n'
    '    # （第 121 轮第三版：曾把 sec:wrong 当表标签，误判了纠错节）\n'
    '    _defined = set()\n'
    '    for _m in re.finditer(\n'
    '            r"\\\\begin\\{(?:table|longtable|figure)\\}(.*?)\\\\end\\{(?:table|longtable|figure)\\}",\n'
    '            body, re.S):\n'
    '        _defined |= set(re.findall(r"\\\\label\\{([^}]*)\\}", _m.group(1)))\n'
    '    for _txt in _table_texts(body, figdir)[1:]:\n'
    '        _defined |= set(re.findall(r"\\\\label\\{([^}]*)\\}", _txt))\n'
    '    _refs = set(re.findall(r"\\\\ref\\{([^}]*)\\}", body))\n'
    '    if _defined and not (_defined & _refs):\n'
    '        return False, ("本节的表没有被本节正文引用（\\ref）"\n'
    '                       "—— 这张表不属于这一节")\n'
)
assert old in t, "引用绑定块未匹配"
t = t.replace(old, new, 1)
io.open(q, "w", encoding="utf-8", newline="\n").write(t)
print("chapters：只认表/图环境里的标签")
