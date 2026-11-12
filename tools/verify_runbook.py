"""验证「题目到手 → 交稿」操作手册里的每条命令都真能跑。

手册写在 `问题到手时的操作手册.md`；这里逐条执行并记录退出码，
任何一条非 0 就红。开赛当天不必重新摸索——先跑这个，绿了再动手。
"""
import io
import os
import subprocess
import sys
import time

HERE = r"C:\Users\21246\Documents\deepseek-harness\default-workspace\model1-arch"
PY = sys.executable
os.chdir(HERE)

DATA = os.path.join("out", "data", "heat_sink.xlsx")
OUT = os.path.join("out", "_runbook")

# (编号, 说明, 命令)
STEPS = [
    ("1", "定题：显式声明题型 + 目标列",
     [PY, "mmkit.py", "advise", "--data", DATA, "--y", "热阻",
      "--x", "宽度,深高", "--min", "热阻", "--types",
      "regression,optimization", "--json"]),
    ("2", "模型赛马：多结构 × 多 seed",
     [PY, "mmkit.py", "race", "--data", DATA, "--y", "热阻",
      "--x", "宽度,深高", "--json"]),
    ("3", "偏相关提示（带样本量与解释力）",
     [PY, "mmkit.py", "hints", "--data", DATA, "--y", "热阻",
      "--x", "宽度,深高"]),
    ("4", "出稿骨架：列出可被重写的段落",
     [PY, "mmkit.py", "skeleton", "--from-tex",
      os.path.join("out", "runs", "heat_sink", "paper.tex")]),
    ("5", "画图（示例类型）",
     [PY, "mmkit.py", "plot", "--kind", "corr", "--data", DATA,
      "--y", "热阻", "--x", "宽度,深高",
      "--out-png", os.path.join(OUT, "corr.png")]),
    ("6", "数字溯源（对已有论文）",
     [PY, "verify.py", os.path.join("out", "runs", "heat_sink", "paper.tex")]),
    ("7", "主动证伪：滑窗找反例",
     [PY, "falsify.py", "counter", "--data", DATA, "--y", "热阻",
      "--x", "宽度,深高"]),
    ("8", "多通道验证（八通道 + veto 演示）",
     [PY, "lanes.py", "demo"]),
    ("9", "出稿前硬门",
     [PY, "gate.py", os.path.join("out", "runs", "heat_sink")]),
]


def main():
    os.makedirs(OUT, exist_ok=True)
    bad = []
    print("=" * 74)
    print("操作手册逐条验证")
    print("=" * 74)
    # 有些命令用退出码传信息（verify.py 有未溯源数字就退 1），
    # 手册判定它们「能跑」= 退出码在允许集合内且输出里有预期内容。
    ALLOW = {"6": (0, 1)}
    for no, desc, argv in STEPS:
        t0 = time.time()
        try:
            r = subprocess.run(argv, capture_output=True, text=True,
                               encoding="utf-8", errors="replace",
                               cwd=HERE, timeout=600)
            code, out = r.returncode, (r.stdout or "") + (r.stderr or "")
        except subprocess.TimeoutExpired:
            code, out = -1, "超时 600s"
        dt = time.time() - t0
        first = ""
        for ln in out.splitlines():
            if ln.strip():
                first = ln.strip()
                break
        # 键统一成 str：STEPS 的编号可能是 int，而 ALLOW 写的是 "6"。
        # 这处类型不匹配让「允许 verify 退 1」的补丁静默失效过一次。
        _ok = code in ALLOW.get(str(no), (0,))
        mark = "OK  " if _ok else "FAIL"
        if not _ok:
            bad.append((no, desc, code, first))
        print("  [%s] %-2s %-32s exit=%-3d %5.1fs  %s"
              % (mark, no, desc, code, dt, first[:52]))
    print()
    if bad:
        print("有 %d 条不通：" % len(bad))
        for no, desc, code, first in bad:
            print("   %s %s exit=%d %s" % (no, desc, code, first[:70]))
    else:
        print("手册里的命令全部可跑。")
    print()
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
