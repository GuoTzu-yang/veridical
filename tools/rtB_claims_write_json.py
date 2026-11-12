# -*- coding: utf-8 -*-
import io, json, os
root = r"C:\Users\21246\Documents\deepseek-harness\default-workspace\model1-arch"
out = os.path.join(root, "out", "红队七板")
os.makedirs(out, exist_ok=True)

doc = {
  "section": "claims",
  "role": "overclaim-auditor",
  "probes": [
    {
      "probe": "每条主张是否都有证据指针",
      "verdict": "finding",
      "note": ("L1229「every numeric token in it is resolved against the frozen table … the verifier reports "
               "no untraced token at all」的唯一支撑物是冻结表，但论文全文 0 次点名该文件（'冻结数字' 0 次、"
               "'freeze_paper_numbers' 0 次），六步复现清单 L1210-L1224 里也没有任何一步生成它："
               "tools/verify_all.py 全文不含冻结表字样，gate.py:286 在缺表时把 numbers 直接判 N/A。"
               "照本节清单复现，能证明「零未溯源」的那件工件不会被造出来，指针是悬空的。"
               "同段 L1205-1206 还写「one collection script … a single JSON artifact」，紧接着的 L1214 就列出"
               "collect_paper_data2.py，out/final 下 data.json 与 data2.json 两件并存。"
               "另：fig:densitynum 的图注（L1259-L1261）把自己 \\ref 到自身（\\ref{fig:densitynum} 写在 "
               "fig:densitynum 自己的 caption 里）并夹带 fig:sections 的图注句，指针指向自己而不是证据。"
               "声明表 6 行本身的指针是齐的（都指到 Section/Table/ledger），缺的是表外这几句。"),
      "tried": ("逐行读 paper.tex L1166-L1272；把 claims 表 6 行拆成 Claim/Evidence/NotSupported 三列逐格看指针；"
                "把六步复现清单里的脚本名抽出来与 tools/ 目录对账；UTF-8 全仓扫 '冻结数字'/'freeze_paper_numbers' "
                "的引用点共 156 处；读 verify_all.py 全文与 gate.py 的 chk_numbers 实现。"),
      "where": "out/final/paper.tex",
      "evidence": "frozen table"
    },
    {
      "probe": "每条主张是否写明「哪里没支撑」",
      "verdict": "finding",
      "note": ("声明表 6 行确实每行都有第三列，这点作者的 pass 站得住；但本节正文的 8 个全称句"
               "（L1203、1205、1206、1207、1217、1229、1241、1244）逐句查过，邻域 ±4 行内没有一处 "
               "Not supported / limitation / weak / cannot 字样。最硬的一处是 L1268-L1270 的图注："
               "「the balance is deliberate: the mechanism and its validation carry most of the length」，"
               "而它的数据源 data2.json['sections'] 是空列表（len=0），画图脚本 make_final_figs2.py:155 "
               "遇到空表直接 return，fig16_sections.pdf 停在 22:02 再没重画——这张图承载的量化主张既不可复现，"
               "图注里也没有一句「这里没支撑」。"),
      "tried": ("按全称量词正则扫 L1201-L1271，得 8 个全称句并逐个取 ±4 行邻域查局限字样；"
                "把图注 L1256-L1263 与 data2.json 的 sections/paper_words 对账；读 make_final_figs2.py 的 "
                "fig16_sections 函数确认空表分支；比对 fig16_sections.pdf 与 paper.tex 的 mtime。"),
      "where": "tools/make_final_figs2.py",
      "evidence": "if not S"
    },
    {
      "probe": "有没有把「未见反例」写成「已证明」",
      "verdict": "finding",
      "note": ("跑论文自己的 freeze.check_paper(paper.tex, out/final/冻结数字.json)：ok=True、n_numbers=37、"
               "n_traced=37、untraced_ratio=0.0——表面是零反例。但同一份返回值里 n_int_not_judged=147："
               "freeze.py:209 只把含小数点的 token 纳入判决，147 个整数 token（23 题、29 检查、51 of 51、"
               "1,027 行、129 kB 全在里面）没进分母，真正被核的是 37/184≈20.1%。而且「命中」是 715 值袋子匹配"
               "（原值、×100、÷100、按书写精度取整）：0.0 命中 229 条，等于没证据也过；0.2146 只命中一条——"
               "tools/freeze_paper_numbers.py:111 手打的 derived.r_crit_84=0.2146。把「检查器没报反例」"
               "写成「no untraced token at all」，就是把没被检的那 80% 当成了已证明。"),
      "tried": ("在 root 下 import freeze/verify 复跑 check_paper 并打印全部返回字段；把 37 个被判 token 逐个用 "
                "freeze._match_written 反查命中的冻结项路径，按命中条数与是否命中手打常数分组；读 freeze.py:182-309 "
                "的判决代码，确认整数被 'if \".\" in t' 过滤；读 freeze_paper_numbers.py 的 derived 段确认哪些值是"
                "脚本里写死的常数。"),
      "where": "tools/freeze_paper_numbers.py",
      "evidence": "derived.r_crit_84"
    },
    {
      "probe": "有没有主张超出语料范围而没说明边界",
      "verdict": "finding",
      "note": ("语料边界（一个语料、一个作者、一种日志口径）在第 1128-1134 行是写了的，声明表第 1、6 行也各写了"
               "「One corpus」「One project」；缺的是对象/版本这一层边界。L1205 说「one collection script that "
               "reads the repository state」，把采集工件当成与成稿同一状态，但实测：paper.tex 65235 B、写于 "
               "11-11 01:34；data2.json 写于 11-10 22:05，里面 paper_bytes=54778（差 10.5 kB）；"
               "fig16_sections.pdf 写于 11-10 22:02。本节只给 gate 判决做了摘要绑定（L1251-L1253「stored with "
               "the digests of the files it judged」），没有给 data.json/data2.json/图 做任何版本绑定，"
               "也没写一句它们的口径是对哪一版成稿。"),
      "tried": ("比对 paper.tex / data.json / data2.json / fig16_sections.pdf 的大小与 mtime；把 data2.paper_bytes "
                "与成稿实际字节数对账；读 L1201-L1255 全部句子，按 corpus/one author/different object/outside/"
                "generalise 关键词抓边界声明，确认只有语料层声明、没有版本层声明；核对 L1251-L1253 的摘要绑定只覆盖 gate 判决。"),
      "where": "out/final/data2.json",
      "evidence": "paper_bytes"
    }
  ],
  "resolved": ("未处理。四条 finding 正文一条都没处理：L1229 的冻结表仍未点名文件、也未进六步复现清单；"
               "L1268-L1270 图注的量化主张仍无「未支撑」说明，data2.json['sections'] 仍为空；"
               "「no untraced token at all」仍按 37/184 的口径写，147 个整数仍免检；"
               "采集工件与成稿的版本边界仍无一字。"
               "另：out/final/redteam.json 里作者自评 probe1/probe2/probe4 判 pass、probe3 的 finding 只针对"
               "分类器召回（agreement=97.5），与本轮三条 finding 不是同一件事——本轮三条 finding 都落在作者判 pass 的探针上。"),
  "verdict": "revise"
}
p = os.path.join(out, "claims-overclaim-auditor.json")
io.open(p, "w", encoding="utf-8", newline="\n").write(json.dumps(doc, ensure_ascii=False, indent=1))
print("wrote", p, os.path.getsize(p), "bytes")
# 自检
d = json.load(io.open(p, encoding="utf-8"))
print("probes:", len(d["probes"]), "verdicts:", [x["verdict"] for x in d["probes"]])
for x in d["probes"]:
    print("  where exists:", os.path.exists(os.path.join(root, x["where"])),
          "| evidence in file:",
          x["evidence"] in io.open(os.path.join(root, x["where"]), encoding="utf-8").read())