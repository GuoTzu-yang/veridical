"""修 caption 里的 $[ ... ]$。

caption 宏包在扫描参数时会把 `[` 当成「可选短标题」的开始，所以
`\caption{... $[0.202, ...]$.}` 直接报 "File ended while scanning use of
\\caption@xdblarg"。正文中同样的写法没有问题，只有 caption 里出错。

修法：caption 内的数学方括号换成圆括号，语义不变。
"""
import os
import re

P = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 "out", "arch", "paper.tex")


def main():
    t = open(P, encoding="utf-8").read()
    n_before = 0

    def repl(m):
        global n_before
        n_before += 1
        return m.group(0).replace("$[", "$(").replace("]$", ")$")

    # caption 可能跨行，用 DOTALL 匹配到第一个未嵌套的 }
    t2 = re.sub(r"\\caption\{(?:[^{}]|\{[^{}]*\})*\}", repl, t, flags=re.S)
    open(P, "w", encoding="utf-8", newline="\n").write(t2)
    print("caption 内替换 %d 处" % n_before)
    for l in t2.split("\n"):
        if "Entropy weights" in l or "captionsetup" in l:
            print("  ", l.strip()[:120])


if __name__ == "__main__":
    main()
