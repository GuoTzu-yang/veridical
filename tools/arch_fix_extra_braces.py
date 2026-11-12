"""按编译错误逐个删除多余的右花括号，直到 paper.tex 编译干净。

背景
----
修 TOPSIS caption 时，我给**所有跨行 caption** 都补了一个行尾 `}`，把 8 个本来
正确的 caption 弄坏了（编译报 "Extra }, or forgotten \\endgroup"）。手工数不可靠，
因为「行尾的 `}` 原本就在」和「是我补的」在文本上完全一样。

做法
----
让编译器当裁判：编译 -> 从 log 里读出报错的**文件行号** -> 若该行是 caption 行，
删掉它行尾的 `}` -> 再编译。重复直到无错。每一步都只删一个，因此不会误删。
"""
import os
import re
import subprocess

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(HERE, "out", "arch")
P = os.path.join(D, "paper.tex")
TEX = r"C:\Users\21246\AppData\Local\Programs\MiKTeX\miktex\bin\x64\pdflatex.exe"


def compile_once():
    subprocess.run([TEX, "-interaction=nonstopmode", "paper.tex"], cwd=D,
                   capture_output=True, text=True, encoding="utf-8",
                   errors="replace")
    log = os.path.join(D, "paper.log")
    return open(log, encoding="utf-8", errors="replace").read() if os.path.exists(log) else ""


def main():
    for it in range(20):
        log = compile_once()
        if "! " not in log:
            print("第 %d 轮：编译干净" % (it + 1))
            break
        m = re.search(r"Extra \}, or forgotten \\endgroup.*?on input line (\d+)",
                      log, re.S)
        if not m:
            m = re.search(r"on input line (\d+)", log)
            if not m:
                print("无法定位错误，log 前 30 行：")
                print("\n".join(log.split("\n")[:30]))
                return 1
        ln = int(m.group(1))
        lines = open(P, encoding="utf-8").read().split("\n")
        if ln < 1 or ln > len(lines):
            print("行号越界 %d" % ln)
            return 1
        idx = ln - 1
        txt = lines[idx]
        if "\\caption" not in txt:
            # 错误行不是 caption，但多余 } 可能在其上方最近的 caption 行
            j = idx
            while j >= 0 and "\\caption" not in lines[j]:
                j -= 1
            if j < 0:
                print("找不到相关 caption 行（报在 L%d）" % ln)
                return 1
            idx = j
            txt = lines[idx]
        new = txt.rstrip()
        if not new.endswith("}"):
            print("L%d 不是以 } 结尾，无法处理：%s" % (idx + 1, txt[:80]))
            return 1
        lines[idx] = new[:-1].rstrip()
        print("  删除 L%d 行尾的多余 }：…%s" % (idx + 1, lines[idx][-50:]))
        open(P, "w", encoding="utf-8", newline="\n").write("\n".join(lines))
    else:
        print("迭代次数用尽")
        return 1
    # 最终确认
    log = compile_once()
    print("最终：", "OK" if "! " not in log else "仍有错误")
    return 0 if "! " not in log else 1


if __name__ == "__main__":
    raise SystemExit(main())
