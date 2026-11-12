#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""redteam_orchestrate.py —— 把「一板一审」变成两条可执行命令。

问题（第 123 轮）：`redteam.py roster` 能告诉你「有几板、每板什么角色」，
但从「名单」到「真的各派一个独立审核者」之间，原来全靠 agent 手工拼 prompt。
新会话不知道怎么写、写几个、怎么收 —— 于是又回到凭记忆建 7 个。

分工：
  · 本脚本（Python）做它擅长的：**切正文、拼 prompt、收结果、写 JSON**
  · agent 做它擅长的：**真的派 subagent、真的读文件、真的判断**

两条命令：

    python tools/redteam_orchestrate.py prompts out/d2026c
        为每一板生成一个自足的 prompt 文件（out/<dir>/红队/prompts/NN-<key>.md），
        内含：该板正文、角色、4 条探针、禁止读别板报告的硬约束、输出 JSON 形状。
        同时写一份 index.md 列出「要派几个、每个叫什么」。

    python tools/redteam_orchestrate.py collect out/d2026c
        读 out/<dir>/红队/results/*.json（每个审核者交一份），
        合并成 redteam.json 的 reviews 数组。缺哪个就点名。

**为什么不让脚本自己派 agent**：Python 进程没有 subagent 能力。
硬要在脚本里「模拟」派，只能造假数据 —— 那正是本项目一路在防的事。

**一一对应**：板数从 `paper.tex` 的 `\\section` 解析，4 板就 4 个 prompt，
20 板就 20 个，没有「固定 12」。
"""
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import redteam as R


def _section_bodies(tex):
    """把正文按 \\section 切开，返回 {title: body}。"""
    parts = re.split(r"\\section\*?\{([^{}]*)\}", tex)
    out = {}
    for i in range(1, len(parts), 2):
        title = parts[i].strip()
        body = parts[i + 1] if i + 1 < len(parts) else ""
        out[title] = body
    return out


def cmd_prompts(figdir):
    tex_path = os.path.join(figdir, "paper.tex")
    if not os.path.exists(tex_path):
        print("没有 %s" % tex_path)
        return 1
    tex = io.open(tex_path, encoding="utf-8", errors="replace").read()
    bodies = _section_bodies(tex)
    rows = R.paper_sections(figdir)
    if not rows:
        print("解析不到 \\section —— 论文没有板块，无从一一对应")
        return 1

    pdir = os.path.join(figdir, "红队", "prompts")
    rdir = os.path.join(figdir, "红队", "results")
    os.makedirs(pdir, exist_ok=True)
    os.makedirs(rdir, exist_ok=True)

    index = ["# 红队派工单", "",
             "论文 `%s` 共 **%d 个板块**，因此要派 **%d 个独立审核者**。"
             % (figdir, len(rows), len(rows)),
             "", "一板一人，**不许一人审两板**，**不许读别板报告**。", "",
             "| # | 板块 | 角色 | 探针 | prompt 文件 | 交付到 |",
             "|---|---|---|---|---|---|"]
    for i, (key, title) in enumerate(rows, 1):
        spec = R.spec_for(key)
        role = spec["role"]
        probes = spec.get("probes") or []
        body = bodies.get(title, "")
        fn = "%02d-%s.md" % (i, key[:40])
        res = "%02d-%s.json" % (i, key[:40])

        md = [
            "# 你是 %s，只审《%s》这一板" % (role, title), "",
            "## 硬约束", "",
            "1. **只审这一板**。不评价别的板块，不提「建议补充第 N 节」。",
            "2. **不许读** `红队/results/` 下任何其它文件，也不许读 `redteam.json`。",
            "   独立性靠这个，不靠角色名不同。",
            "3. 每条探针要么 `pass`，要么 `finding`。**不许写「看着还行」**。",
            "4. `pass` 必须写 `tried`（≥30 字），说明你**具体查了什么**、查了哪些行。",
            "   「没找到」和「根本没查」必须可区分。",
            "5. `finding` 必须写 `where`（文件路径）+ `evidence`（该文件里**逐字存在**的"
            "标记，≥3 字符）。gate 会亲自 grep，对不上就判假证据。",
            "", "## 这一板的正文", "", "```latex", body.strip()[:6000], "```", "",
            "## 四条探针（逐条回答）", "",
        ]
        for j, p in enumerate(probes, 1):
            md.append("%d. %s" % (j, p))
        md += [
            "", "## 交付格式（写成 `%s`，放 `%s/`）" % (res, rdir), "",
            "```json",
            json.dumps({
                "section": key,
                "title": title,
                "role": role,
                "probes": [
                    {"probe": "<第 1 条探针原文>", "verdict": "pass|finding",
                     "tried": "<查了什么，≥30 字>",
                     "where": "<仅 finding：文件路径>",
                     "evidence": "<仅 finding：逐字存在的标记>",
                     "finding": "<仅 finding：缺陷是什么>",
                     "disposition": "<fixed|blocked|rejected|open>",
                     "falsifier": "<blocked/rejected 必填：什么证据会推翻你>"}
                ],
            }, ensure_ascii=False, indent=1),
            "```", "",
            "**没有 `disposition` 的 finding 一律按 `open` 计**，open 会让 gate 变红。",
            "这是有意的：账面上「已关闭」而正文没改，比没审更糟。", "",
        ]
        io.open(os.path.join(pdir, fn), "w", encoding="utf-8",
                newline="\n").write("\n".join(md))
        index.append("| %d | `%s` | %s | %d | `%s` | `%s` |"
                     % (i, key, role, len(probes), fn, res))

    index += ["", "## 派发方式", "",
              "板数 ≤ 8：可以直接 `spawn_teammate` 逐个派（团队上限 8）。",
              "板数 > 8：用 `workflow` 并行派，或**分批**——上一批 inactive 后再派下一批，",
              "**同一 agent 不许同时审两板**。", "",
              "全部交齐后运行：",
              "",
              "```",
              "python tools/redteam_orchestrate.py collect %s" % figdir,
              "```", ""]
    io.open(os.path.join(pdir, "index.md"), "w", encoding="utf-8",
            newline="\n").write("\n".join(index))

    print("板块数 %d → 生成 %d 份 prompt" % (len(rows), len(rows)))
    print("  prompts: %s" % pdir)
    print("  results: %s" % rdir)
    print("  派工单 : %s" % os.path.join(pdir, "index.md"))
    print()
    print("下一步（agent 做，脚本做不了）：按 index.md 逐个派独立审核者，")
    print("每人只拿自己那份 prompt，产出写到 results/ 下同名 .json。")
    return 0


def cmd_collect(figdir):
    pdir = os.path.join(figdir, "红队", "prompts")
    rdir = os.path.join(figdir, "红队", "results")
    rows = R.paper_sections(figdir)
    if not rows:
        print("解析不到板块")
        return 1
    have, missing, bad = {}, [], []
    for d in sorted(os.listdir(rdir)) if os.path.isdir(rdir) else []:
        if not d.endswith(".json"):
            continue
        try:
            j = json.load(io.open(os.path.join(rdir, d), encoding="utf-8"))
        except Exception as e:                          # noqa: BLE001
            bad.append("%s: %s" % (d, e))
            continue
        s = str(j.get("section") or "").strip()
        if not s:
            bad.append("%s: 没有 section 字段" % d)
            continue
        have[s] = j
    for key, title in rows:
        if key not in have:
            missing.append(key)

    if missing or bad:
        print("交齐情况：%d/%d" % (len(have), len(rows)))
        if missing:
            print("  **缺**：%s" % ", ".join(missing))
        for b in bad:
            print("  **坏文件**：%s" % b)
        print()
        print("缺的不能补假数据 —— 要么真派一个审核者，要么在交接文件里写「未审」。")
        return 1

    out = os.path.join(figdir, "redteam.json")
    reviews = [have[k] for k, _t in rows]
    payload = {"paper": figdir, "n_boards": len(rows), "reviews": reviews}
    io.open(out, "w", encoding="utf-8", newline="\n").write(
        json.dumps(payload, ensure_ascii=False, indent=1))
    print("已合并 %d 板 → %s" % (len(reviews), out))
    print("跑 `python redteam.py %s` 与 `python gate.py %s` 验判决。" % (figdir, figdir))
    return 0


def cmd_auto(figdir):
    """一条命令：看名单 → 生成任务书 → 打印「你现在必须做什么」。

    为什么要有 auto：新会话开插件时，它可能没读 AGENTS，也不会主动想到
    「先 roster 再派」。所以入口必须只有一个，而且它自己会说话。
    """
    rows = R.paper_sections(figdir)
    if not rows:
        print("【红队】%s 没有 \\section —— 无从一一对应" % figdir)
        return 1
    print("【红队】%s 共 %d 个板块 → 需要 %d 个独立审核者（几板几审）"
          % (figdir, len(rows), len(rows)))
    print()
    rc = cmd_prompts(figdir)
    if rc != 0:
        return rc
    rdir = os.path.join(figdir, "红队", "results")
    done = len([f for f in os.listdir(rdir) if f.endswith(".json")]) \
        if os.path.isdir(rdir) else 0
    print()
    if done >= len(rows):
        print("【状态】results 已齐（%d/%d）→ 现在合并：" % (done, len(rows)))
        print("    python tools/redteam_orchestrate.py collect %s" % figdir)
        return 0
    n = len(rows) - done
    print("【状态】还差 %d 份（%d/%d）" % (n, done, len(rows)))
    print()
    print("【你现在必须做】按派工单派 %d 个独立 subagent：" % n)
    print("    %s" % os.path.join(figdir, "红队", "prompts", "index.md"))
    print()
    if n > 8:
        batches = [8] * (n // 8) + ([n % 8] if n % 8 else [])
        print("  **并行上限是 8**，所以要分 %d 批：%s"
              % (len(batches), " + ".join(str(b) for b in batches)))
    else:
        print("  一次可以并行派 %d 个（上限 8）" % n)
    print("  每人只拿自己那份 prompt，产出写到 红队/results/ 下同名 .json")
    print("  不许读别板报告；pass 要写 tried（>=30 字）；finding 要写")
    print("  where + evidence（逐字存在）+ disposition（缺省按 open 计）")
    print()
    print("  派完再跑：python tools/redteam_orchestrate.py collect %s" % figdir)
    return 0


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    cmd, figdir = argv[1], argv[2]
    if cmd == "auto":
        return cmd_auto(figdir)
    if cmd == "prompts":
        return cmd_prompts(figdir)
    if cmd == "collect":
        return cmd_collect(figdir)
    print("未知子命令：%s" % cmd)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
