import ast
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "mmkit.py")
s = open(P, encoding="utf-8").read()

OLD = ('        if _re_cjk.search(tex):\n'
       '            tex = _re_cjk.sub("variable", tex)')
assert OLD in s, "no cjk gate"
NEW = ('        # 这道总闸只对英文模式成立。\n'
       '        # 之前它无条件生效，结果 --lang zh 的章节标题刚被 _localize\n'
       '        # 换成中文，下一行就被替成 variable —— 多语言功能被自己\n'
       '        # 加的安全网闷死了，产出的是「英文论文 + 两个 variable 标题」。\n'
       '        _lang_now = str(ctx.get("lang") or "en").lower()\n'
       '        if _lang_now.startswith("en"):\n'
       '            if _re_cjk.search(tex):\n'
       '                tex = _re_cjk.sub("variable", tex)\n'
       '        else:\n'
       '            # 非英文：中文是预期的，不许替。但要用中文排版就得有\n'
       '            # ctex/xeCJK，缺了会编出一堆问号 —— 说清楚，别静默。\n'
       '            try:\n'
       '                _need = list(_i18n.LANGS.get(_lang_now[:2], {})\n'
       '                              .get("needs") or [])\n'
       '            except Exception:\n'
       '                _need = []\n'
       '            if _need:\n'
       '                print(f"  ⚠ 语言 {_lang_now} 需要宏包 "\n'
       '                      f"{\', \'.join(_need)}；本机 MiKTeX 若未安装，"\n'
       '                      f"中文会排成问号。")\n')
s = s.replace(OLD, NEW, 1)
ast.parse(s)
compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  cjk gate now language-aware")