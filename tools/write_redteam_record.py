"""把红队那 20 条攻击，按板块归档成 redteam.json（七板七角色）。

不是重新编，而是把 `redteam-report.md` 里已经提出的攻击**映射**到七个板块，
并补上处理方式。没被攻击到的板也必须写一条探针结论（pass），否则等于没查。
"""
import io
import json
import os

OUT = r"C:\Users\21246\Documents\deepseek-harness\default-workspace\model1-arch\out\final"

REVIEWS = [
    dict(section="analysis", role="decomposition-auditor",
         probes=[
             dict(probe="分类是否互斥（一个对象不会同时属于两类）",
                  verdict="pass", note="五类按取值形态判定，rule 表见 untraced.py"),
             dict(probe="分类是否穷尽（有没有不属于任何一类的对象被悄悄丢掉）",
                  verdict="finding",
                  note="红队 F1：首版只分类了打印出来的前 15 条（199/1293），"
                       "85% 的对象未被归档；已改为直接取 verify.trace 的完整集合"),
             dict(probe="每一类是否改变了「检查器能问什么」",
                  verdict="pass", note="只有 D_computed 必须追计算出处"),
             dict(probe="分母是否完整（有没有只统计了打印出来的前 N 条）",
                  verdict="finding",
                  note="已加断言：各类之和必须等于未溯源总数（untraced.py 自检）"),
         ],
         resolved="重写 tools/anatomy_tokens.py 走 trace() API；新增 untraced.py 模块，"
                  "把「分母完整」钉成自检断言",
         verdict="revise"),

    dict(section="method_argument", role="alternative-auditor",
         probes=[
             dict(probe="每个方法是否都配了被否掉的替代方案", verdict="pass",
                  note="Table 2 六行方法/替代/理由"),
             dict(probe="否决理由是否可证伪（什么证据会让我们改主意）",
                  verdict="pass", note="每行有 Would change if"),
             dict(probe="有没有把「实现方便」写成「方法更优」", verdict="pass",
                  note="成本一栏给了实测秒数"),
             dict(probe="方法的成本是否给了实测值而非形容词", verdict="finding",
                  note="红队 H7：附录声称账本会在数字失效前变红，但 verify_all.py "
                       "并不读论文；已把论文自身溯源与计数一致两道加进账本"),
         ],
         resolved="在 Method 节补一段散文式论证；账本加两道检查",
         verdict="revise"),

    dict(section="validation", role="statistics-auditor",
         probes=[
             dict(probe="样本量 n 是否与结论强度匹配", verdict="pass",
                  note="23 题全量，不是抽样"),
             dict(probe="多重比较/窗口数是否交代并处理", verdict="finding",
                  note="红队 F5：窗口搜索的窗口数与多重比较未交代；已在局限里写明"),
             dict(probe="效应量是否给了区间而不只是点估计", verdict="finding",
                  note="红队 M1：临界值 0.218 算错，实为 0.2146；已改"),
             dict(probe="消融是否非平凡（删掉机制后是否只得到 0 或 1）", verdict="finding",
                  note="红队 F4：首版消融删了全部 json，0.0% 是算术；"
                       "改为只删冻结表后为 10.4–12.2%（非平凡）"),
         ],
         resolved="消融只删冻结表并重跑；临界值重算；窗口多重比较写进局限",
         verdict="revise"),

    dict(section="results", role="reproducibility-auditor",
         probes=[
             dict(probe="每个数字是否能追到工件", verdict="finding",
                  note="红队 F2：论文自身溯源仅 69.7%，两个摘要数字被判无源；"
                       "已为重采工件建冻结表，并修 verify 退出码键名"),
             dict(probe="口径是否写明（gate 口径 vs 全量口径）", verdict="finding",
                  note="红队 H3：正文写「99% 以上」与数据不符；已改为 94.1–100%"),
             dict(probe="图表是否都被正文引用且图注与内容一致", verdict="finding",
                  note="红队 M4：每稿有 5–6 张图从未被正文引用；已补引用与图注"),
             dict(probe="计数是否与工件同源（不手抄）", verdict="finding",
                  note="红队 H1：22/23 项两种说法并存；已全部由脚本生成并同步"),
         ],
         resolved="建 out/final/冻结数字.json；加 tools/refresh_paper_numbers.py "
                  "与 sync_counts.py 统一刷新；图注与引用补齐",
         verdict="revise"),

    dict(section="self_correction", role="confession-auditor",
         probes=[
             dict(probe="每条是否写清「错在哪」", verdict="pass", note="七例各有 Wrong 段"),
             dict(probe="每条是否写清「怎么发现的」（哪个测量暴露的）",
                  verdict="pass", note="七例各有 How found，且指出是哪个工具抓的"),
             dict(probe="每条是否写清「改了什么」", verdict="pass", note="七例各有 Change"),
             dict(probe="每条是否给出「为什么这个改法是对的」（不是「现在绿了」）",
                  verdict="finding",
                  note="红队 F3：论文声称 N/A 不能判绿，而代码把 N/A 一律判绿；"
                       "已改为 fail-closed，并加声明文件机制"),
         ],
         resolved="修 gate 的 hard_ok：只有 na_kind=ABSENT 才算过；"
                  "新增 declaration.json 显式豁免并打印",
         verdict="revise"),

    dict(section="deployment", role="operations-auditor",
         probes=[
             dict(probe="运行方式是否给全（单机/服务/CI）", verdict="pass",
                  note="Table 三种模式"),
             dict(probe="时间预算是否用实测秒数", verdict="pass",
                  note="0.43/0.40/0.37/1.61/0.12/0.31/0.46/2.25 s"),
             dict(probe="失败处置是否可执行（症状→第一步→不许做什么）",
                  verdict="pass", note="处置表五行，含「不许把 N/A 当通过」"),
             dict(probe="成本是否区分机器时间与编辑时间", verdict="finding",
                  note="红队指出成本段把两者混说；已改写为「机器时间可忽略，"
                       "编辑纪律不可」"),
         ],
         resolved="成本段重写；处置表补「不许」一列",
         verdict="revise"),

    dict(section="claims", role="overclaim-auditor",
         probes=[
             dict(probe="每条主张是否都有证据指针", verdict="pass",
                  note="claims 表六行都指到章节/图"),
             dict(probe="每条主张是否写明「哪里没支撑」", verdict="pass",
                  note="第三列 Not supported"),
             dict(probe="有没有把「未见反例」写成「已证明」", verdict="finding",
                  note="红队 F6：题型覆盖 15/22 是纯召回，恒输出七标签的平凡基线更高；"
                       "已在正文承认这是低于基线的成绩"),
             dict(probe="有没有主张超出语料范围而没说明边界", verdict="pass",
                  note="局限一节明确「一个语料、一个作者、一种日志口径」"),
         ],
         resolved="在 Results 明确写出「过度报告 optimization（21 vs 6）」与"
                  "「低于平凡基线」，并把召回口径写进 claims 表",
         verdict="revise"),
]

p = os.path.join(OUT, "redteam.json")
json.dump(dict(reviews=REVIEWS),
          io.open(p, "w", encoding="utf-8", newline="\n"),
          ensure_ascii=False, indent=1)
print("已写 redteam.json：%d 个板块，%d 条探针，%d 条 finding"
      % (len(REVIEWS), sum(len(r["probes"]) for r in REVIEWS),
         sum(1 for r in REVIEWS for q in r["probes"] if q["verdict"] == "finding")))
