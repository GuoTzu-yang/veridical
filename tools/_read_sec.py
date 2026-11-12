import io
import re

p = r"C:\Users\21246\Documents\deepseek-harness\default-workspace\aidc2026\big\main.tex"
L = io.open(p, encoding="utf-8", errors="replace").read().split("\n")


def show(a, b, label):
    print("=" * 70)
    print(label, "(L%d-L%d)" % (a, b))
    print("=" * 70)
    for i in range(a - 1, min(b, len(L))):
        print("%4d %s" % (i + 1, L[i][:118]))
    print()


show(187, 226, "2.3 演进分期 + 2.4 一次自欺的形状")
show(777, 812, "8.2 尚未做的六件事 + 8.3")
show(1103, 1130, "12.1 被证明的 / 12.2 没有被证明的")
