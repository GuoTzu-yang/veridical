#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第二批：npm 包、pip 包、以及重试失败的 GitHub 仓库。

用户要求：不挑，全都拿来。所以这里不再判断「有没有用」，
只记录拿到没拿到。
"""
import glob
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MIRROR = "http://82.156.194.197/5219426"
NPM_DIR = os.path.join(HERE, "external", "npm")
PIP_DIR = os.path.join(HERE, "external", "pip")
GH_DIR = os.path.join(HERE, "external", "github")
TMP = os.path.join(os.environ.get("TEMP", "/tmp"))

os.makedirs(NPM_DIR, exist_ok=True)
os.makedirs(PIP_DIR, exist_ok=True)

# ── ① 把 TEMP 里已经下载过的挪进来 ──
moved = 0
for pat, dest in (("wg_inspect", "dsh-plugin-writing-guard"),
                  ("um_inspect", "dsh-ultramath"),
                  ("gc_inspect", "gatecraft"),
                  ("danus_inspect", "dsh-danus")):
    tgzs = glob.glob(os.path.join(TMP, pat, "*.tgz"))
    for t in tgzs:
        d = os.path.join(NPM_DIR, dest)
        os.makedirs(d, exist_ok=True)
        shutil.copy2(t, os.path.join(d, os.path.basename(t)))
        # 已解压的也带上
        src_pkg = os.path.join(TMP, pat, "package")
        if os.path.isdir(src_pkg):
            shutil.copytree(src_pkg, os.path.join(d, "package"),
                            dirs_exist_ok=True)
        moved += 1
        print(f"  移入 {dest}")
print(f"  从 TEMP 移入 {moved} 个包")

# ── ② 补拉其余 npm 包 ──
NPM = [
    "dsh-alphasolve", "dsh-writing-style-learner", "dsh-research-suite",
    "dsh-plugin-academic-writing", "dsh-academic-skills", "paperlab",
    "model-designer",
    # 之前 404 的再试一次（可能已发布）
    "dsh-math-rigor", "dsh-math-agent", "dsh-math-team",
    "dsh-mathmodel-v7", "no-ai-style", "dsh-research-paper-mode",
    "dsh-scholar-suite", "dsh-math-modeling-skills-gatecraft",
]
ok_npm, fail_npm = [], []
for p in NPM:
    d = os.path.join(NPM_DIR, p)
    if os.path.isdir(d) and os.listdir(d):
        ok_npm.append((p, "已存在"))
        continue
    os.makedirs(d, exist_ok=True)
    NPM = r"C:\\Program Files\\nodejs\\npm.cmd"
    r = subprocess.run([NPM, "pack", p, "--silent"],
                       capture_output=True, text=True, cwd=d)
    tgzs = glob.glob(os.path.join(d, "*.tgz"))
    if tgzs:
        ok_npm.append((p, os.path.basename(tgzs[0])))
        # 解压
        subprocess.run(["tar", "-xzf", tgzs[0], "-C", d],
                       capture_output=True)
        print(f"  OK   npm {p}")
    else:
        fail_npm.append(p)
        os.rmdir(d)
        print(f"  FAIL npm {p}")

# ── ③ pip 包 ──
PIP = ["mathlas-mcp", "ai4math", "luma-mcp",
       "ortools", "pyomo", "statsforecast"]
ok_pip, fail_pip = [], []
for p in PIP:
    r = subprocess.run(
        [sys.executable, "-m", "pip", "download", p, "--no-deps",
         "-d", os.path.join(PIP_DIR, p), "--quiet",
         "--disable-pip-version-check"],
        capture_output=True, text=True)
    files = glob.glob(os.path.join(PIP_DIR, p, "*"))
    if files:
        sz = sum(os.path.getsize(f) for f in files)
        ok_pip.append((p, sz))
        print(f"  OK   pip {p} {sz // 1024} KB")
    else:
        fail_pip.append(p)
        print(f"  FAIL pip {p}")

# ── ④ 重试失败的 GitHub ──
RETRY = [
    ("usail-hkust", "LLM-MM-Agent", ["main", "master"]),
    ("yushui2022", "liuhuan-mathmodel-skills", ["main", "master"]),
    ("USail-HKUST", "LLM-MM-Agent", ["main", "master"]),
    ("yushui2022", "liuhuan-mathmodel-skill", ["main", "master"]),
]
import zipfile
retry_ok = []
for owner, repo, brs in RETRY:
    dst = os.path.join(GH_DIR, f"{owner}__{repo}")
    if os.path.isdir(dst) and os.listdir(dst):
        continue
    for br in brs:
        zp = os.path.join(TMP, f"{repo}-{br}-r.zip")
        url = f"{MIRROR}/zip/{owner}/{repo}/{br}"
        subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             f"$ProgressPreference='SilentlyContinue'; "
             f"try{{Invoke-WebRequest -Uri '{url}' -OutFile '{zp}' "
             f"-TimeoutSec 60 -UseBasicParsing; exit 0}}catch{{exit 1}}"],
            capture_output=True, text=True)
        if not os.path.exists(zp) or os.path.getsize(zp) < 500:
            continue
        try:
            os.makedirs(dst, exist_ok=True)
            with zipfile.ZipFile(zp) as z:
                z.extractall(dst)
            retry_ok.append(f"{owner}/{repo}")
            print(f"  OK   重试 {owner}/{repo} ({br})")
            break
        except Exception:                       # noqa: BLE001
            continue

print()
print(f"  npm 成功 {len(ok_npm)} / 失败 {len(fail_npm)}")
if fail_npm:
    print("    npm 拿不到: " + ", ".join(fail_npm))
print(f"  pip 成功 {len(ok_pip)} / 失败 {len(fail_pip)}")
if fail_pip:
    print("    pip 拿不到: " + ", ".join(fail_pip))
print(f"  GitHub 重试成功 {len(retry_ok)}")
