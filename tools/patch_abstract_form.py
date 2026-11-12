"""abstract.extract 放宽识别 + gate 把「找不到摘要」当失败。

问题（第 89 轮实测）：
  out/arch/paper.tex 用的是自定义环境 \\begin{abstractbox}，
  而 extract 只认 \\begin{abstract} 与 \\section{Summary}。
  于是 abstract 这条**硬门**返回 N/A —— 硬门算通过。
  一篇真有摘要的论文，因为环境名不叫 abstract，就绕过了摘要 8 项自检。

修法：
  1. extract 认三种形式：
     a) 任何名字里含 abstract 的环境（abstract / abstractbox / abstractenv）
     b) \\section{Abstract} / \\section*{Abstract} / 中文「摘要」
     c) 摘要关键字后再兜底
  2. gate.chk_abstract 找不到摘要时返回 **failed-N/A**（严格模式下计失败）：
     摘要是 CUMCM/APMCM 必交项，找不到不等于没有，但也不能算通过。
"""
import io
import sys

AB = r"C:\Users\21246\Documents\deepseek-harness\default-workspace\model1-arch\abstract.py"
GATE = r"C:\Users\21246\Documents\deepseek-harness\default-workspace\model1-arch\gate.py"

OLD_EXTRACT = '''def extract(tex: str) -> str:
    m = re.search(r"\\\\begin\\{abstract\\}(.*?)\\\\end\\{abstract\\}", tex, re.S)
    if m:
        return m.group(1).strip()
    m = re.search(r"\\\\section\\*?\\{Summary\\}(.*?)(?=\\\\section)", tex, re.S)
    return m.group(1).strip() if m else ""'''

NEW_EXTRACT = '''def extract(tex: str) -> str:
    """从 paper.tex 里取出摘要正文。

    认三种写法，顺序从最明确到最宽松：
      ① 名字里含 abstract 的环境 —— abstract / abstractbox / abstractenv …
         原来只认 `\\begin{abstract}`，于是自定义环境（例如本仓库技术报告用的
         `abstractbox`）会被判成「没有摘要」，硬门直接 N/A 放行。
      ② `\\section{Abstract}` / `\\section*{摘要}`，取到下一个 \\section 为止
      ③ `\\section{Summary}`，同上（旧行为，保留）
    """
    m = re.search(r"\\\\begin\\{(\\w*abstract\\w*)\\}(.*?)\\\\end\\{\\1\\}", tex, re.S)
    if m:
        return m.group(2).strip()
    for pat in (r"\\\\section\\*?\\{\\s*(?:Abstract|摘要)\\s*\\}",
                r"\\\\section\\*?\\{\\s*Summary\\s*\\}"):
        m = re.search(pat + r"(.*?)(?=\\\\section)", tex, re.S)
        if m:
            return m.group(1).strip()
    return ""'''

OLD_GATE = '''        r = ab.audit(open(tex, encoding="utf-8").read())
        if not r.get("items"):
            return _r("abstract", HARD, "N/A", r.get("why", "无摘要"))'''

NEW_GATE = '''        r = ab.audit(open(tex, encoding="utf-8").read())
        if not r.get("items"):
            # 找不到摘要不能算通过：摘要（含关键词）是竞赛必交项。
            # 原来返回裸 N/A，硬门按通过处理 —— 实测 out/arch 用自定义环境
            # abstractbox，真有摘要却因识别不到而放行。
            return _na("abstract", HARD,
                       r.get("why", "无摘要")
                       + "（已尝试 abstract 类环境 / \\\\section{Abstract|摘要|Summary}）",
                       kind=NA_FAILED)'''


def main():
    ab = io.open(AB, encoding="utf-8").read()
    g = io.open(GATE, encoding="utf-8").read()
    if "\\w*abstract\\w*" in ab:
        print("SKIP extract: already broadened")
    elif OLD_EXTRACT not in ab:
        print("FAIL: extract anchor not matched")
        return 2
    else:
        ab = ab.replace(OLD_EXTRACT, NEW_EXTRACT, 1)
        print("OK extract broadened")
    if "kind=NA_FAILED" in g and "已尝试 abstract 类环境" in g:
        print("SKIP gate: already failed-N/A")
    elif OLD_GATE not in g:
        print("FAIL: gate anchor not matched")
        return 3
    else:
        g = g.replace(OLD_GATE, NEW_GATE, 1)
        print("OK gate: missing abstract is failed-N/A")
    io.open(AB, "w", encoding="utf-8", newline="\n").write(ab)
    io.open(GATE, "w", encoding="utf-8", newline="\n").write(g)
    print("written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
