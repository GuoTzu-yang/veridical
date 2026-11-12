#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""paper_pipeline.py —— 改完论文后的固定链路，一条命令跑完（第 123 轮）。

为什么需要它：改一个数字，要连着跑七步，**每一步漏掉都会产生静默过时**。
这几轮我把七步漏过至少四次，每次都是同一个症状：
「文件改了，但派生物还是旧的，gate 报绿」。

七步与漏掉的后果：

  1. pdflatex ×2            漏 → PDF 是旧的，pdf 页数/字节数对不上
  2. collect_paper_data2    漏 → data2.paper_bytes 过时 → fence_acceptance 的 S8 报「工件过期」
  3. context_metrics        漏 → n_frozen / paper_tokens 停在生成时的值（实测停在 713，实际 792）
  4. make_final_figs ×2     漏 → 图是旧数据画的（实测 fig16 画了两版之前的数据）
  5. remake_fig14b          漏 → 同上
  6. freeze_paper_numbers   漏 → 冻结表不含新数 → numbers 门报未溯源
  7. gate --stamp（两遍）   第一遍必然报 stale（它盖的是上一次的摘要），第二遍才干净

用法：
    python tools/paper_pipeline.py out/final
    python tools/paper_pipeline.py out/d2026c --skip-figs
    python tools/paper_pipeline.py out/final --dry      # 只打印将执行的命令

**它不做判断**，只保证顺序与「不漏步」。判断仍然交给 gate / verify。
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable


def _run(cmd, cwd, dry=False):
    line = " ".join(cmd)
    print("  → %s" % line[:150])
    if dry:
        return 0, ""
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    out = (p.stdout or "") + (p.stderr or "")
    return p.returncode, out


def main(argv):
    dirs = [a for a in argv[1:] if not a.startswith("-")]
    figdir = dirs[0] if dirs else os.path.join(HERE, "out", "final")
    dry = "--dry" in argv
    skip_figs = "--skip-figs" in argv
    is_final = os.path.basename(os.path.normpath(figdir)) == "final"

    steps = []
    # 1) 编译两遍（引用/目录需要第二遍）
    steps.append(([ "pdflatex", "-interaction=nonstopmode", "paper.tex"], figdir))
    steps.append(([ "pdflatex", "-interaction=nonstopmode", "paper.tex"], figdir))
    # 2) 采集论文侧数据（写 data2.paper_bytes）
    if is_final:
        steps.append(([PY, "tools/collect_paper_data2.py"], HERE))
        steps.append(([PY, "tools/context_metrics.py"], HERE))
    if not skip_figs and is_final:
        steps.append(([PY, "tools/make_final_figs.py"], HERE))
        steps.append(([PY, "tools/make_final_figs2.py"], HERE))
        steps.append(([PY, "tools/remake_fig14b.py"], HERE))
        # 第 124 轮：A/B 四图必须在 make_final_figs 之后重画。
        # 否则 pipeline 每次更新 data2.json 都会让它们变旧，I12 报「图旧于数据」。
        steps.append(([PY, "tools/make_ab_figs.py"], HERE))
    if is_final:
        steps.append(([PY, "tools/freeze_paper_numbers.py"], HERE))
    # 7) 盖章两遍：第一遍盖的是旧摘要，第二遍才干净
    #    **第一遍非零退出是正常的**：`--stamp` 的职责就是「先报 stale，再盖章」，
    #    它报 stale 时返回 1。原来把它当失败，pipeline 每次都判红（实测踩到）。
    steps.append(([PY, "gate.py", figdir, "--stamp"], HERE, True))   # allow_fail
    steps.append(([PY, "gate.py", figdir], HERE, False))

    print("改论文后的固定链路：%s（%d 步）" % (figdir, len(steps)))
    if not is_final:
        print("  注意：非 out/final 目录跳过 collect/context/figs/freeze —— "
              "那些是工具论文专用的派生物")
    print()
    fail = []
    for step in steps:
        cmd, cwd = step[0], step[1]
        allow = step[2] if len(step) > 2 else False
        rc, out = _run(cmd, cwd, dry)
        if rc != 0 and not allow:
            fail.append((" ".join(cmd), rc, out[-400:]))
        elif rc != 0 and allow:
            print("    （这一步非零是预期的：--stamp 先报 stale 再盖章）")
    print()
    if dry:
        print("（--dry：只打印，未执行）")
        return 0
    if fail:
        print("**%d 步失败**：" % len(fail))
        for c, rc, tail in fail:
            print("  ✗ %s (exit %d)" % (c[:110], rc))
            print("    %s" % tail.replace("\n", "\n    ")[:360])
        return 1
    print("七步全过。别忘了单独跑：")
    print("  python verify.py %s/paper.tex" % figdir)
    print("  python tools/paper_hygiene.py %s" % figdir)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
