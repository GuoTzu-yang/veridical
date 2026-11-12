# Q2 大纲 · v5：路 B 的论文实际长什么样

> v4 判了「X = 4，按路 B 写（6 项经证 + 29 项实现）」。
> **但 v4 没说清路 B 写完的论文是什么形状。** 这一版只做这一件事。

---

## 1. 先回答一个关键问题：6 项够不够 Q2

**Q2 不看项数，看单项深度。** 把 6 项各拆开看：

| 项 | 它自己就能支撑什么 | 已有的证据 | 深度评价 |
|---|---|---|---|
| **`numbers`** | 五类数字分解 + 冻结表 + **精度感知相等（命题+证明）+ 消融 + 变异测试** | 399 个数字实测；删表后 90%→10%；`fence_acceptance` S1–S5；`fence_mutation` 1/4 | **单独够一篇 workshop，够半个 Q2 章节** |
| **`proof`** | 关键推导必须是命题且证明非空 | 本论文的命题 1（459 字符）；**构造样本未做** | **只有判据，缺证据** |
| **`iterlog`** | 过程必须逐轮记「不信判据」 | 6 轮迭代表；**构造样本未做** | **同上** |
| **`figures`** | 孤立图 + 图内标题与 caption 重复 | `fig_visual` + S6 + i12 变异 | 中等 |
| **`redteam`** | 板数 = `\section` 数；一条 finding 一个关闭 | S9–S12 四个样本 + 变异 | 较强 |
| **`stamp`** | 判决绑定文件摘要 | S8 | 弱（一项检查） |

**结论**：

> **`numbers` 一项就占了论文一半的分量。**
> **`proof` 和 `iterlog` 现在是「有判据无证据」——补两个样本后才有资格进正文。**
> **`figures`、`redteam`、`stamp` 是配套，不是主张。**

**所以路 B 的论文实质是**：

> **一篇以「数值谱系」为核心（`numbers`）、以「推导与过程各一道门」为延伸（`proof` / `iterlog`）、以「审核的可靠性」为元层的论文。**

**这个结构能投 Q2，但必须把 `numbers` 写到最深，把 `proof`/`iterlog` 只当「延伸」而不是「并列的贡献」。**

---

## 2. 收窄后的标题与主张

### 标题

**不用** v1 的 *Beyond Factual Support: Verifying the Computational Provenance of Numbers...*（太大）

**改用**：

> **Number provenance, not factuality: what a frozen table can verify that a knowledge source cannot**

**理由**：
- 「not factuality」明确划界，不是否定 FActScore，是说**维度不同**
- 「what a frozen table can verify」把方法说清（一个表，不是 35 道门）
- 「that a knowledge source cannot」是可证伪的（FActScore 跑出来就知道）

### 一句话主张

> **技术报告里近一半的数字是计算值，它们在知识源里不存在。一个冻结表能把这类数字变成可机械核对的，而现有的「查知识源」评测覆盖不了它们。我们用 399 个数字、一次消融和一次 A/B 对照量化了这件事，并指出这个判据的已知失效边界。**

**注意最后半句**：「并指出已知失效边界」——**这是这篇论文与其他工具论文的区别**。

---

## 3. 论文骨架（6 项版）

### §1 Introduction（2 页）

| 段 | 内容 | 证据 |
|---|---|---|
| 1 | 场景：LLM 写的报告，算术对，数字没有回到计算的路径 | 现稿 Restatement 开头（写得好，直接搬） |
| 2 | **现有评测的边界**：FActScore 问「是否被知识源支持」 | FActScore 原文定义 |
| 3 | **前置事实**：23 篇 9337 个数字，**47.3% 是计算值，知识源覆盖上界 35.1%** | `out/数字类别分布.md` |
| 4 | **本文贡献三条**（见下） | — |

**贡献三条（只三条，不多）**：

1. **一个分解**：数字分五类，只有「计算值」必须溯源；统一正则会误判结构整数。
2. **一个判据**：精度感知相等（命题 1 + 证明），把「合法舍入」与「伪造」分开。
3. **一个量化**：399 个数字实测 + 消融（删表 90%→10%）+ **A/B 对照揭示「数字对 ≠ 推导对 ≠ 过程诚实」**。

**第 3 条里的 A/B 是「三个不等式」**——**这是把三层讲清的最短路径**，比「三层」这个词更硬。

### §2 Related work（2 页，4 子节，v2 已定）

保持不变：2.1 factuality evaluation / 2.2 provenance / 2.3 reproducibility standards / 2.4 LLM verification in SE。

**唯一要改的**：2.1 必须能说「FActScore 在计算值上怎么失败」。**这依赖那一次真跑**。

### §3 The object: five kinds of numbers（2 页）

现稿 Analysis 的 Step 1 已经写了，**只要加一件事**：

> 五类的实测分布（47.3 / 27.1 / 17.6 / 8.0）。
> **并说明「这个比例不是普适常数，是一个领域的函数」**（v2 批判 1 的降级）。

### §4 The criterion: precision-aware equality（3 页，**全文最重的一节**）

| 小节 | 内容 | 状态 |
|---|---|---|
| 4.1 为什么容差不行 | 两条：绝对地板 → 5 个假阳性；相对 2% → 假数字藏在真数字旁边 | ✅ 现稿有 |
| 4.2 **命题 1 + 证明** | 舍入等价 | ✅ 459 字符 |
| 4.3 实现与陷阱 | 相对余量 vs 绝对地板；容差由**论文写出的位数**决定 | ✅ 现稿有 |
| 4.4 **这一节能抓什么、抓不到什么** | 抓不到「形状像结构值的计算值」 | ⚠️ **有承认，无量化的漏检率** |

**4.4 是最大的残余风险**（v3 第 6 节点过）。**`[需补]`：构造一批「形状像结构值」的样本，报漏检率。**

### §5 Two extensions: derivation and process（2 页）

**这一节是「延伸」，不是「并列贡献」**——**标题用 extensions 而不是 layers**。

| 小节 | 内容 | 状态 |
|---|---|---|
| 5.1 `proof` 门 | 命题必须非空证明（≥60 有效字符）；本论文自己的命题 1 是它的第一个实例 | ⚠️ **需补构造样本** |
| 5.2 `iterlog` 门 | 六轮迭代表：轮/现象/诊断/修正 + 不信判据 | ⚠️ **同上** |

**写法**：不要写成「我们有第二层第三层」，写成「**我们发现第一层不够，于是加了两个延伸，各自有自己的失败模式**」。

### §6 Evaluation（3 页）

| 小节 | 内容 | 状态 |
|---|---|---|
| 6.1 语料 | 23 题，每题规模 | ✅ |
| 6.2 数字类别分布 | 47.3 / 27.1 / 17.6 / 8.0 | ✅ |
| 6.3 **消融** | 删表后 81.7–94.9% → 10.4–12.2% | ✅ |
| 6.4 **A/B 对照** | 94 vs 90；**三个不等式**：数字对 ≠ 推导对 ≠ 过程诚实 | ✅（n=1，要扩） |
| 6.5 对检查器的压力测试 | `fence_acceptance` 12/12、`fence_mutation` 假测试 0/4 | ✅ |
| 6.6 **逐层消融 C0–C3** | 加一层能否抓上一层抓不到的 | ❌ **未做** |
| 6.7 baseline 对拍 | FActScore / HaluEval | ❌ **未跑** |

### §7 Threats（1.5 页）

**这一节要写得比多数论文长**，因为它是这篇论文的护城河。

| 威胁 | 内容 | 状态 |
|---|---|---|
| 构造效度 | 分类器是形状规则；漏检率未量化 | ⚠️ |
| 内部效度 | 门与语料共同设计；30/30 seeded defect 由作者设计 | ✅ 已承认 |
| 外部效度 | 单语料、n=1、单评分者 | ✅ 已承认 |
| **元层** | **L3 也抓不到伪造的迭代史**（v2 批判 2） | **必须写** |
| **项数** | **35 项里只有 6 项经证**（v4 实测） | **必须写** |

**最后两条是这篇论文最诚实的地方，也是它区别于「35 项全绿」类工具论文的地方。**

### §8 Appendix：the other 29 checks

**不删，进附录**，写成一张表：

| 门 | 判据 | 有没有独立样本 |
|---|---|---|
| `compile` | LaTeX 无错 | 无 |
| ... | ... | ... |

**加一句**：

> 这些检查有判据实现，**但没有构造出的缺陷证明它们抓得住**。我们把它们列在这里，**不作为本文的论证依据**。

### §9 Conclusion（0.5 页）

**要答**：这个判据的边界在哪、下一个问题是什么。

**下一个问题**：**「结论是否被证据支持」能不能也机械判？** 我们怀疑不能（`blackbox2020` 的不可能性结果）。

---

## 4. Abstract 重写（只提 6 项，不提 35）

> Large language models write technical reports whose arithmetic is usually correct and whose numbers have no path back to anything computed. Existing factuality evaluations ask whether a sentence is supported by a knowledge source. **We measured 9{,}337 numbers across 23 technical reports and found that 47.3\% of them are computed values, which a knowledge source cannot support by construction; the upper bound of knowledge-source coverage is 35.1\%.**
>
> We build and evaluate a criterion for that missing half: a frozen table plus **precision-aware equality**, in which a written value is accepted only if it rounds from the frozen one at the number of decimals the paper wrote. We prove the rounding equivalence that justifies it, and show two failure modes of the naive alternatives (an absolute floor produced five false positives; a 2\% relative tolerance let fabricated values hide next to true ones).
>
> Removing the table while leaving the prose untouched drops the traced fraction from 81.7--94.9\% to 10.4--12.2\%. A sealed A/B comparison with and without the tool layer shows 94 against 90 on a shared rubric, but the dimensions move in opposite directions: **the tool arm loses points on derivation and gains them on process**, which is why we added two extensions rather than claiming one criterion is enough.
>
> We report the criterion's known failure boundary: the classifier is a shape rule, and a computed value that looks like a structural index is excused. Of the 35 checks we implemented, **six have been validated by constructed defects and mutation testing**; the rest are listed in the appendix and are **not** used as evidence here.

**这段 Abstract 的每一句都能追到一个文件或一次运行。**

---

## 5. 这样写能到 Q2 吗（诚实评估）

| 门槛 | 路 B 之后 | 判断 |
|---|---|---|
| **有 baseline 对比** | ❌ 仍缺（FActScore 未跑） | **仍然是判负项** |
| 多语料 | ❌ | 硬伤 |
| 统计检验 | ⚠️ A/B 仍 n=1 | 硬伤 |
| **可复现** | ✅ 399/399 + 12/12 + 假测试 0/4 | **超标准** |
| **诚实边界** | ✅ **比多数论文更硬**（明说 6/35） | **超标准** |
| 单项深度 | ✅ `numbers` 一项足够深 | 达标 |

**结论**：

> **路 B 把论文从「工程报告」变成「一篇诚实的工具论文」，但还不足以让「有 baseline」这一项变绿。**
> **所以路 B 的产物最适合投 workshop 或 Q3；要到 Q2，`baseline` 那一步不能省。**

**而 `baseline` 卡在 API key 上——这是唯一一个「不是我不做，是做不了」的项。**

---

## 6. 降级路径（如果 baseline 永久做不了）

| 目标 | 条件 | 现在能做吗 |
|---|---|---|
| **workshop**（ICSE SE4ML / NeurIPS repro） | 路 B + 逐层消融 | ✅ **能** |
| **Q3 期刊**（*Science of Computer Programming* 等） | 路 B + 逐层消融 | ✅ **能** |
| **Q2** | 上面 + baseline | ❌ 卡 API |
| **arXiv 预印本** | 路 B | ✅ 能，且能引 FActScore 做「概念对比」而不做「实验对比」 |

**「引 FActScore 做概念对比而不做实验对比」是可行的**，但要写成：

> FActScore 的判据是「这句是否被知识源支持」。我们无法在本环境运行它（缺 LLM 依赖），**但它的判据定义本身就排除了计算值**——因为知识源不包含「这个数是通过某次计算得到的」。

**这是「定义层面的论证」，不是「实验层面的论证」。它能过 Q3，过不了 Q2。**

---

## 7. v5 净变化（相对 v4）

| # | v4 | v5 |
|---|---|---|
| 1 | 说「按路 B 写」 | **给出路 B 的完整骨架**（8 节，每节绑证据） |
| 2 | 6 项经证 | **拆开看：`numbers` 占一半分量，`proof`/`iterlog` 是「有判据无证据」，`figures`/`redteam`/`stamp` 是配套** |
| 3 | 未定标题 | **标题收窄**：*Number provenance, not factuality* |
| 4 | 「三层」 | **改成「一个判据 + 两个延伸」**（避免「并列贡献」的过度主张） |
| 5 | 未写 Abstract | **写了，每句可追** |
| 6 | 未评估路 B 的强度 | **诚实结论：路 B 够 Q3/workshop，不够 Q2（缺 baseline）** |

---

## 修订记录

| 版本 | 改了什么 |
|---|---|
| v1 | 骨架 |
| v2 | 七处批判 |
| v3 | 可执行化 + 四情形预案 |
| v4 | 判决第一项实测：X=4/35 |
| **v5** | **路 B 的完整论文骨架 + 收窄标题 + Abstract + 诚实评估（够 Q3，不够 Q2）** |
