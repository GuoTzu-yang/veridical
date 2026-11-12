#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把建模插件整套代码打包到桌面。

包含：能跑出这篇论文所需的全部源码 + 知识库 + 测试 + 工具 + 数据
排除：生成的产物(out/)、字节码(__pycache__)、账本历史(ledger-history/)
     以及与建模无关的数据库/账本模块的中间文件
"""
import os
import shutil
import zipfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DESK = os.path.join(os.path.expanduser("~"), "Desktop")
STAGE = os.path.join(DESK, "_mmpack_tmp")
ZIP = os.path.join(DESK, "建模插件-完整代码.zip")

# 根目录要带走的扩展名
KEEP_EXT = (".py", ".md", ".json")
# 根目录明确排除
DROP_NAMES = {
    "schema.json",  # 29KB 的配置，可选；保留也行，这里保留
}
DROP_PREFIX = ("_", "ledger.jsonl", "plot_box", "plot_corr",
               "kb_original")

if os.path.isdir(STAGE):
    shutil.rmtree(STAGE, ignore_errors=True)
os.makedirs(STAGE)

n_file = 0
n_byte = 0


def copy(src, dst_rel):
    global n_file, n_byte
    dst = os.path.join(STAGE, dst_rel)
    os.makedirs(os.path.dirname(dst) or STAGE, exist_ok=True)
    shutil.copy2(src, dst)
    n_file += 1
    n_byte += os.path.getsize(src)


# ── ① 根目录源码与文档 ──
for f in sorted(os.listdir(HERE)):
    p = os.path.join(HERE, f)
    if not os.path.isfile(p):
        continue
    if not f.endswith(KEEP_EXT):
        continue
    if f.startswith(DROP_PREFIX):
        continue
    copy(p, f)

# ── ② 三个目录 ──
for d in ("kb", "tests", "tools"):
    src = os.path.join(HERE, d)
    if not os.path.isdir(src):
        continue
    for r, _, fs in os.walk(src):
        if "__pycache__" in r:
            continue
        for f in fs:
            if f.endswith(".pyc"):
                continue
            fp = os.path.join(r, f)
            copy(fp, os.path.join(os.path.relpath(r, HERE), f))

# ── ②b 数据集（out/data）──
# runs.json 里 14 道题都指向这里。上一版整段漏掉，实测冷启动
# 报「数据缺失」、14 道题一道都跑不了。
_dd = os.path.join(HERE, "out", "data")
if os.path.isdir(_dd):
    for _f in sorted(os.listdir(_dd)):
        if _f.lower().endswith((".xlsx", ".xls", ".csv")):
            copy(os.path.join(_dd, _f), os.path.join("out", "data", _f))
    print("  数据集已带入: %d 个" % len([
        x for x in os.listdir(_dd)
        if x.lower().endswith((".xlsx", ".xls", ".csv"))]))

# ── ③ 数据文件（在项目外的题库目录）──
data = ("C:\\Users\\21246\\Documents\\deepseek-harness\\default-workspace\\"
        "apmcm2026\\题库\\2026中文-A_B_C三题\\"
        "B题 高性能芯片热管理系统的优化问题\\附件\\"
        "附件 2：不同结构参数下无量纲的热阻、压降和温度非均匀性结果数据.xlsx")
os.makedirs(os.path.join(STAGE, "data"), exist_ok=True)
if os.path.exists(data):
    shutil.copy2(data, os.path.join(STAGE, "data", os.path.basename(data)))
    n_file += 1
    n_byte += os.path.getsize(data)
    print("  数据已带入: " + os.path.basename(data))

# ── ④ 运行说明 ──
README = """# 建模插件 · 完整代码

## 这是什么

一套「数据 → 模型赛马 → 多目标优化 → 鲁棒设计 → 制造误差 → 排版出稿」的
建模流水线，附带 15 项质量门与数字溯源。

## 环境

Python 3.12（本机路径示例）
```
C:\\Users\\21246\\.dsh\\dsh-runtimes\\dsh-primary-runtime\\dependencies\\python\\python.exe
```
依赖：numpy / pandas / openpyxl / matplotlib / pypdf / scienceplots
```
pip install numpy pandas openpyxl matplotlib pypdf scienceplots
```
LaTeX：MiKTeX（需要 pdflatex）

## 跑出论文（一条命令）

```bash
# 跑全部 14 道题（含出图、编译、过 gate）
python tools/battle.py

# 只跑某几道
python tools/battle.py chemical real_c2023

# 验收藏（逐题过 gate + 回归 + 补丁）
python tools/verify_all.py
```

题目配置在 `runs.json`（数据 / y / x / min / 题面 / 产物目录）。
`mmkit run --compile` 会**自动出图**（12 张），不需要单独跑 genfigs。
产物：`out/fig/` 下 12 张图（PNG 预览 + PDF 矢量）

**第二步：出稿并编译**
```bash
python mmkit.py run \\
  --data "data/附件 2：不同结构参数下无量纲的热阻、压降和温度非均匀性结果数据.xlsx" \\
  --y 热阻 --x 宽度,深高,排数 --min 热阻,压降,温度 \\
  --tex out/fig/paper.tex --team 你的队号 --problem "heat sink" \\
  --compile
```
产物：`out/fig/paper.pdf`、`paper.tex`、`冻结数字.json`

> 顺序不能反：先有图，`paper.py` 才会写图注。
> 没图时它会跳过整段图注，出稿只有 46 KB 而不是 57 KB。

## 质量门

```bash
python gate.py out/fig      # 15 项，全绿才算出稿
```

## 自测

```bash
python tests/run_all.py     # 24 个模块的 selftest
```

## 目录

| 路径 | 内容 |
|---|---|
| `mmkit.py` | 主编排：读数据 → EDA → 模型 → 优化 → 出稿 |
| `mm.py` | 统计核心：拟合、交叉验证、Pareto、预测区间、残差诊断 |
| `paper.py` | 论文生成（LaTeX） |
| `q4.py` / `q5.py` / `multimodel.py` | 权重鲁棒 / 制造误差 / 三指标分建 |
| `gate.py` | 15 项质量门 |
| `freeze.py` | 数字冻结与溯源 |
| `cards.py` / `innovation.py` / `abstract.py` | 假设卡 / 创新审计 / 摘要审计 |
| `plot_mpl.py` | 绘图后端（scienceplots 主题） |
| `kb/` | 知识库（假设卡、不变量、方法映射） |
| `tests/` | 各模块 selftest |
| `tools/` | 开发期检查脚本 |
| `data/` | 附件数据 |

## 已知边界

- **物理叙事层不可移植**：机理节与符号检验是热沉题目专用。
  换一道题，数据/优化/排版/溯源全通用，但 `paper.py` 的
  Mechanistic basis 一节会输出错误内容，必须改。
- 样本 84 行，所有区间基于此。
"""
open(os.path.join(STAGE, "README-如何运行.md"), "w",
     encoding="utf-8", newline="\n").write(README)
n_file += 1

# ── ⑤ 压缩 ──
if os.path.exists(ZIP):
    os.remove(ZIP)
with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    for r, _, fs in os.walk(STAGE):
        for f in fs:
            fp = os.path.join(r, f)
            z.write(fp, os.path.relpath(fp, STAGE))

shutil.rmtree(STAGE, ignore_errors=True)
print(f"  打包 {n_file} 个文件 / 原始 {n_byte} 字节")
print(f"  ZIP  {os.path.getsize(ZIP)} 字节")
print(f"  桌面: {ZIP}")
