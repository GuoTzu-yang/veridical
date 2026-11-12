#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""批量拉取用户列出的全部 GitHub 仓库（走镜像站）。

原则：不再替我判断「有没有用」——先全部落地，之后再评估。
每个仓库记录：成功/失败、大小、文件数。
"""
import os
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MIRROR = "http://82.156.194.197/5219426"
OUT = os.path.join(HERE, "external", "github")
TMP = os.path.join(os.environ.get("TEMP", "/tmp"), "gh_batch")

REPOS = [
    # 第 5 批：流程框架与方法论
    "ZSLlearn/my-math-modeling-skill",
    "logic1241/xiaohudie-math-modeling",
    "jiangkaiqi2005/math-cumcm-modeler",
    "AR-firefly/math-modeling-skill",
    "skillforCUMCM/math-modeling-skill-pro",
    "XiucuiGuan/shumo-expert",
    "LEEHAHAHAHA/math-modeling-skill",
    "jihe520/MathModelAgent",
    "luoluo13/math-modeling",
    "li1408/MathModelHub",
    "Rzna-5559/Mrite",
    "LanFeng-git/MathModelPro",
    "FuInSure/MMA",
    "Hyde-yd/MathModeling-AI-Agent",
    "qiancheng0/ModelingAgent",
    # 第 3/4 批里点到的 GitHub 项目
    "usail-hkust/LLM-MM-Agent",
    "RealSeaberry/AutoMCM-Pro",
    "sweetcornna/mathodology",
    "yushui2022/liuhuan-mathmodel-skills",
    "han69611/math-modeling-skills",
]

os.makedirs(OUT, exist_ok=True)
os.makedirs(TMP, exist_ok=True)

ok, fail = [], []
for full in REPOS:
    owner, repo = full.split("/")
    dst = os.path.join(OUT, f"{owner}__{repo}")
    if os.path.isdir(dst) and os.listdir(dst):
        print(f"  SKIP {full}（已存在）")
        ok.append((full, "已存在", 0, 0))
        continue
    got = False
    for br in ("main", "master"):
        zp = os.path.join(TMP, f"{repo}-{br}.zip")
        url = f"{MIRROR}/zip/{owner}/{repo}/{br}"
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             f"$ProgressPreference='SilentlyContinue'; "
             f"try{{Invoke-WebRequest -Uri '{url}' -OutFile '{zp}' "
             f"-TimeoutSec 90 -UseBasicParsing; exit 0}}catch{{exit 1}}"],
            capture_output=True, text=True)
        if r.returncode != 0 or not os.path.exists(zp):
            continue
        if os.path.getsize(zp) < 500:
            continue
        try:
            with zipfile.ZipFile(zp) as z:
                z.extractall(dst)
        except Exception:                       # noqa: BLE001
            continue
        # 展平：解压出来通常多一层 repo-main/
        subs = [d for d in os.listdir(dst)
                if os.path.isdir(os.path.join(dst, d))]
        if len(subs) == 1 and subs[0].lower().startswith(repo.lower()):
            inner = os.path.join(dst, subs[0])
            for f in os.listdir(inner):
                os.replace(os.path.join(inner, f), os.path.join(dst, f))
            os.rmdir(inner)
        nf = sum(len(fs) for _, _, fs in os.walk(dst))
        sz = sum(os.path.getsize(os.path.join(r_, f))
                 for r_, _, fs in os.walk(dst) for f in fs)
        ok.append((full, br, sz, nf))
        print(f"  OK   {full} ({br}) {sz // 1024} KB / {nf} 文件")
        got = True
        break
    if not got:
        fail.append(full)
        print(f"  FAIL {full}")

print()
print(f"  成功 {len(ok)} / 失败 {len(fail)}")
if fail:
    print("  失败清单：")
    for f in fail:
        print("    " + f)
