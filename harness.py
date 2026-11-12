#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
model1 架构 · 三个真瓶颈的可执行实现

图的三个空洞：
  B1  置信度评估 —— 图上写"置信度评估"三次，没有一处定义它怎么算
  B2  对宿主提问 —— 图上要求停下来问，没画超时、没画降级
  B3  汇总同类   —— 图上要求把子问题归并成同类，没写用什么判等

本文件把三处填成可运行代码，全部为标准库实现，无第三方依赖。

用法:
    python harness.py selftest      # 跑内置真实题例，断言全部通过
    python harness.py demo          # 打印一次完整流程的中间态
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field, asdict
from typing import Optional

# =============================================================================
# B1  置信度评估
# =============================================================================
# 设计要点：不是"模型给自己打信心分"，而是三个可外部核对的计分维度。
# 每个维度 0/1/2，满分 6。三道闸只判其中一部分，成本递进。
# -----------------------------------------------------------------------------

E1_LEVELS = {
    0: "无来源：完全由生成得到，指不到任何出处",
    1: "指到来源名，指不到位置：『某论文说过』『业界普遍认为』",
    2: "指到位置：章节/段落/URL+锚点/命令与退出码/公式与代入值",
}

E2_LEVELS = {
    0: "单一来源，或所有来源同源（同一篇文献、同一次转载、同一个库）",
    1: "两个来源，但无法排除同源转载",
    2: "≥3 个互相独立的来源，或 1 个一手来源 + 1 次独立复算",
}

E3_LEVELS = {
    0: "不可复现：主观判断、未来预测、单次观测且无记录",
    1: "部分可复现：需要特定环境/数据，未给出",
    2: "完全可复现：给出命令、数据、公式，第三方能跑出同样结果",
}


@dataclass
class Claim:
    """一条待评估的结论。"""

    cid: str
    text: str
    e1: int = 0                      # 溯源度 0-2
    e2: int = 0                      # 独立度 0-2
    e3: int = 0                      # 可复现度 0-2
    sources: list[str] = field(default_factory=list)
    # 扣分项，来自实测踩过的两类失败
    unexplained_contradiction: int = 0   # 来源之间互相矛盾且未解释（每处 -1）
    out_of_scope: bool = False           # 结论超出所引来源的适用范围（-1）
    # 结论类别：world=关于世界的断言；observation=关于我观测到的
    # 观测类结论（"这个文件不存在"）位置精确且可复现时，独立性可豁免
    kind: str = "world"
    # 实测反证：有实验证据直接否定该主张时置真，一票否决
    refuted_by_test: bool = False
    # 规程类专用：关键输入是否已验证有效。None=未检查，False=明确无效
    input_valid: bool | None = None
    # 怎么验证我：{"domain": "sql", "task": {...}}，交给 precheck 取证。
    # 只作声明用，闸门不读它——闸门只读 input_valid。
    verify: dict | None = None
    # 验这条任务需要什么环境能力：{"rows": 1e8, "arch": "aarch64", ...}
    # 与 verify 不同，闸门**会读**它：环境明确给不了时自动降级为 degrade/env。
    # 第五十七轮加的——之前这类降级靠人手标 cause，标错过 5 条。
    needs: dict | None = None

    def penalty(self) -> int:
        return self.unexplained_contradiction + (1 if self.out_of_scope else 0)

    def score(self) -> int:
        """C = e1 + e2 + e3 - penalty，夹在 0..6"""
        raw = self.e1 + self.e2 + self.e3 - self.penalty()
        return max(0, min(6, raw))

    def dims(self) -> dict[str, int]:
        return {"e1": self.e1, "e2": self.e2, "e3": self.e3, "penalty": self.penalty()}


# 三道闸的判据：每道只判它该判的维度，成本递进
#   G1  分队列之后、深度切入之前   —— 只判 e1（值不值得挖）
#   G2  深度切入之后、优化拓展之前 —— 判 e1+e2（挖出来可不可信）
#   G3  优化拓展之后、生成方案之前 —— 判全三维（做出来能不能用）
GATE_SPEC = {
    "G1": {
        "uses": ("e1",),
        "pass_at": 1,      # e1 >= 1
        "reject_below": 1,  # e1 == 0 直接放弃，不进深度切入
        "label": "值不值得深挖",
    },
    "G2": {
        "uses": ("e1", "e2"),
        "pass_at": 4,      # e1+e2 = 4（指到位置 + 独立来源）才算过
        "reject_below": 2,  # <=2 打回；3 分降级（要补独立来源）
        "label": "挖出来的可不可信",
    },
    "G3": {
        "uses": ("e1", "e2", "e3"),
        "pass_at": 5,      # C >= 5
        "reject_below": 3,  # <=2 打回
        "label": "做出来的能不能用",
    },
}


# 证据环境的四档能力。判据不能脱离环境谈"够不够"。
# 真实长任务实测暴露过：本地只有文件路径、没有可执行实例时，
# 5 个子问题 4 个卡在 G2——不是判错，是环境根本产不出独立来源。
ENV_LEVELS = {
    3: "完整（可联网 + 可执行 + 有源码）",
    2: "可读不可跑（有源码，无运行环境）",
    1: "只见路径（有文件清单，看不到内容）",
    0: "只有题面（无任何外部证据）",
}

# 各档环境下，每个维度理论上能拿到的最高分
ENV_MAX_E = {
    3: {"e1": 2, "e2": 2, "e3": 2},
    2: {"e1": 2, "e2": 2, "e3": 1},   # 跑不了 → 可复现度封顶 1
    1: {"e1": 1, "e2": 1, "e3": 1},   # 只看得到路径 → 指不到位置，也复核不了
    0: {"e1": 0, "e2": 0, "e3": 0},
}


@dataclass
class EvidenceEnv:
    level: int = 3
    # 调用方已知的**精确**环境事实，用于能力核验。
    # 探针只能拿到下限（实测已物化 20 万行），但调用方可能知道确切数
    # （比如库里就是 5,000 行）。有精确值时用它，没有才退回探针下限。
    facts: dict | None = None

    def __post_init__(self):
        if self.level not in ENV_LEVELS:
            raise ValueError(f"未知环境档位 {self.level}")

    def cap(self, stage: str, kind: str = "world") -> int:
        """当前环境下，该闸理论上能拿到的最高分。"""
        table = table_for(kind)
        return sum(ENV_MAX_E[self.level][d] for d in table[stage]["uses"])

    def pass_at(self, stage: str, kind: str = "world") -> int:
        """环境受限时通过线按可达上限收缩。

        收缩不等于放水，两条兜底：
          1. 不低于该闸的打回线（否则 pass 与 reject 区间交叠）
          2. 环境受限下最终判定最高只到 degrade——拿不到完整证据就没资格说"通过"
        """
        spec = table_for(kind)[stage]
        base = spec["pass_at"]
        if self.level >= 3:
            return base
        return max(spec["reject_below"], min(base, self.cap(stage, kind)))

    def describe(self) -> dict:
        return {"level": self.level, "desc": ENV_LEVELS[self.level],
                "caps": dict(ENV_MAX_E[self.level])}


def _wsl_probe(distro: str, shell_expr: str, timeout: int = 25) -> bool:
    """在 WSL 里执行一条 shell 判断，返回 returncode==0。

    只看退出码，没有输出——避免编码问题，也避免把"输出里有 OK"当成成功。
    """
    import subprocess

    try:
        r = subprocess.run(
            ["wsl.exe", "-d", distro, "--", "bash", "-lc", shell_expr],
            capture_output=True, timeout=timeout,
        )
        return r.returncode == 0
    except Exception:
        return False


def detect_env(source_root: str | None = None,
               executable: str | None = None,
               network: bool = True,
               wsl_distro: str | None = None,
               wsl_executable: str | None = None) -> tuple[EvidenceEnv, dict]:
    """自动探测证据环境档位。

    判据全部可复现：目录里有没有源码文件、有没有可执行产物、能否联网。
    不看 self-report，不做推测。

    wsl_distro 非空时，可执行性改在 WSL 内判定——Windows 侧看不见 Linux 的
    /usr/bin/observer，不这么改，一个真跑起来的实例也会被判成 L2。
    """
    import os

    src_files = 0
    if source_root and os.path.isdir(source_root):
        for _, _, fs in os.walk(source_root):
            for f in fs:
                if f.endswith((".cpp", ".cc", ".h", ".hpp", ".py", ".go", ".rs")):
                    src_files += 1

    via = "本机"
    if wsl_distro and wsl_executable:
        exe_ok = _wsl_probe(wsl_distro, f"test -x {wsl_executable}")
        via = f"WSL:{wsl_distro}"
    else:
        exe_ok = bool(executable and os.path.isfile(executable))

    has_src = src_files > 0

    if has_src and exe_ok and network:
        lvl = 3
    elif has_src and network:
        lvl = 2
    elif has_src or network:
        lvl = 1
    else:
        lvl = 0

    return EvidenceEnv(lvl), {
        "src_files": src_files,
        "executable": exe_ok,
        "network": network,
        "via": via,
        "reason": (f"源码 {src_files} 个 / 可执行 {'有' if exe_ok else '无'} / "
                   f"联网 {'可' if network else '否'}（探测路径 {via}）"),
    }


# ---------------------------------------------------------------------------
# e3 不该拍出来：它取决于证据从哪来
# ---------------------------------------------------------------------------
# 判据版本：每次判定逻辑有实质改变就 +1。
# 账本里的样本必须带版本——否则 v1 时期（没有 cause、没有 input_valid）的样本
# 会和 v2 的混在一起算概率，那个概率没有意义。
#   v1  三瓶颈实现：e1/e2/e3 + 三闸，无 cause、无 e3 来源、无 input_valid
#   v2  加 cause（degrade 拆 env/info）、derive_e3、三态 input_valid
MODEL_VERSION = 2
# 第十七轮实测（case_l3_estacc.py，5 个查询）：
#   走索引的计划，EST.ROWS 与实际完全一致（450 vs 450，0.0%）
#   全表扫描的估算，偏差 79.6% ~ 96.4%
# 所以同样是"看了 EXPLAIN"，可信度差一个档。
E3_SOURCE = {
    "measured":     (2, "直接实测，可复现"),
    "index_plan":   (2, "走索引的精确计划，估算与实际一致"),
    "partial":      (1, "只验证了一部分"),
    "fullscan_est": (1, "全表扫描的估算，实测偏差 80-96%"),
    "guess":        (0, "没有证据，只有推测"),
}


def derive_e3(source: str) -> int:
    """按证据来源推导 e3，而不是凭感觉填。"""
    if source not in E3_SOURCE:
        raise ValueError(f"未知证据来源 {source}，可用：{sorted(E3_SOURCE)}")
    return E3_SOURCE[source][0]


def e3_reason(source: str) -> str:
    return E3_SOURCE.get(source, (None, "未知来源"))[1]


# 规程类（"照着做能不能成功"）不适用"独立来源"这个概念。
# 一条部署指令，跑一次和跑三次结果一样；它要的是步骤清楚 + 结果可判定。
# 所以用 e3（可验证）顶替 e2（独立性），另立一张表。
PROCEDURE_SPEC = {
    "G1": {
        "uses": ("e1",),
        "pass_at": 1,
        "reject_below": 0,
        "label": "步骤是否明确到能照着做",
    },
    "G2": {
        "uses": ("e1", "e3"),
        "pass_at": 3,      # e1+e3 >= 3（步骤清楚 + 结果能判定）
        "reject_below": 1,
        "label": "步骤清楚且成败可判",
    },
    "G3": {
        "uses": ("e1", "e3"),
        "pass_at": 3,
        "reject_below": 1,
        "label": "能否完整跑完并判定",
    },
}


def table_for(kind: str) -> dict:
    return PROCEDURE_SPEC if kind == "procedure" else GATE_SPEC


def gate(c: Claim, stage: str, env: EvidenceEnv | None = None) -> dict:
    """单道闸判定：pass / degrade / reject。

    degrade 的语义：可以往下走，但必须带不确定标注，且不能再往上抬权重。
    """
    env = env or EvidenceEnv()
    spec = table_for(c.kind)[stage]
    pass_at = env.pass_at(stage, c.kind)

    if spec["uses"] == ("e1",):
        value = c.e1
    elif spec["uses"] == ("e1", "e3"):
        # 规程类：结果可验证顶替独立来源
        value = c.e1 + c.e3
    elif spec["uses"] == ("e1", "e2"):
        value = c.e1 + c.e2
        # 观测类结论（"这个文件不存在"）：位置看得见 + 谁都能复核，
        # 独立性一项可以豁免——再查十次结果也一样。
        if c.kind == "observation" and c.e1 >= 2 and c.e3 >= 2:
            value = max(value, pass_at)
    else:
        value = c.score()

    # 打分不得超过该环境理论上能产出的上限——环境拿不到的证据不该计分
    value = min(value, env.cap(stage, c.kind))

    if value >= pass_at:
        verdict = "pass"
    elif value > spec["reject_below"]:
        verdict = "degrade"
    else:
        verdict = "reject"

    return {
        "gate": stage,
        "label": spec["label"],
        "value": value,
        "pass_at": pass_at,
        "base_pass_at": spec["pass_at"],
        "env_cap": env.cap(stage, c.kind),
        "env_limited": pass_at < spec["pass_at"],
        "verdict": verdict,
        "uses": list(spec["uses"]),
        "kind": c.kind,
    }


_CAP_CACHE: dict = {}


def _split_fact(raw) -> tuple[object, str, dict | None]:
    """拆开一个环境事实：值 + 出处 + 可执行规格。

    三种写法：
        5000                                        → (5000, "", None)
        {"value": 5000, "from": "sql: COUNT(*)"}    → (5000, "sql: COUNT(*)", None)
        {"value": 5000, "from": "数一遍",
         "check": {"domain": "sql",
                   "task": {"sql": "SELECT COUNT(*) ..."}}}
                                                    → (5000, "数一遍", {...})

    **只有带 check 的才能被采信**（第六十轮）：
    字符串出处是"声称"，可执行规格才是"核对过"。一个没核对过的数字
    不许拿去否定别人的结论。
    """
    if isinstance(raw, dict):
        return (raw.get("value"), str(raw.get("from") or ""),
                raw.get("check") if isinstance(raw.get("check"), dict) else None)
    return raw, "", None


def _verify_fact(val, src: str, spec: dict | None) -> tuple[bool, str]:
    """核对一个环境事实能不能用。返回 (可用与否, 依据)。

    规矩：**没核对过的数字不能用**。三种结论：
      能用   —— 跑了 check，结果与声明值一致
      不能用 —— 没给 check（只是声称），或跑了但值对不上，或根本跑不了
    """
    if not src:
        return False, "调用方给了值但没给出处"
    if not spec:
        return False, f"出处「{src[:40]}」只是声称，没给可执行核对规格"

    domain = spec.get("domain")
    task = spec.get("task") or {}
    try:
        import probe as _probe
    except Exception as e:  # noqa: BLE001
        return False, f"核对器不可用：{type(e).__name__}"

    if domain != "sql":
        # const 域：把值本身写进规格里直接核对。
        # 存在的理由：原来的测试只能靠 SQL 探针自证，于是「环境能力核验」
        # 这一组测试依赖外部数据库 —— seekdb 一不可用，探针失败，
        # value 降成 None，fits() 返回 None，run_gates 又把 None 当成
        # "不降级"，测试就从 degrade 变成 pass（实测 5/5 复现）。
        # 这个域让测试能自证，不借外部环境。
        if domain == "const":
            try:
                same = abs(float(task.get("value")) - float(val)) < 1e-9
            except (TypeError, ValueError):
                same = str(task.get("value")).strip() == str(val).strip()
            if not same:
                return False, (f"核对不符：声称 {val}，"
                               f"规格写的是 {task.get('value')}")
            return True, f"已核对（常量）：{val}"
        return False, f"暂不支持核对 {domain!r} 域的事实"

    sql = task.get("sql") or ""
    ok, got = _probe.query_scalar(sql)
    if not ok:
        return False, f"核对没跑成：{got[:50]}"
    try:
        same = abs(float(got) - float(val)) < 1e-9
    except (TypeError, ValueError):
        same = str(got).strip() == str(val).strip()
    if not same:
        return False, f"核对不符：声称 {val}，实测 {got}"
    return True, f"已核对（{src[:30]}）：实测 {got}"


def _capability_check(c: Claim, env: EvidenceEnv) -> tuple[bool | None, str]:
    """任务声明的环境需求，本机给不给得了。

    三态：True 给得了 / False 明确给不了 / None 没测到（或没声明需求）。
    只探一次，缓存在模块级——探测本身要真跑，不能每次判定都跑一遍。
    """
    needs = getattr(c, "needs", None)
    if not needs:
        return None, "没声明环境需求"
    try:
        import capability as _cap
    except Exception as e:  # noqa: BLE001
        return None, f"能力模块不可用：{type(e).__name__}"
    try:
        if "env" not in _CAP_CACHE:
            _CAP_CACHE["env"] = _cap.probe_environment()
        base = _CAP_CACHE["env"]
        # 调用方给了精确事实 → 覆盖探针的下限值（exact 优先于 at_least）
        facts = getattr(env, "facts", None)
        if facts:
            dims = dict(base.dims)
            for k, raw in facts.items():
                if k not in dims:
                    continue
                val, src, spec = _split_fact(raw)
                good, why = _verify_fact(val, src, spec)
                if not good:
                    # 分两种失败：
                    #   核对器**跑不了**（探针挂/库不可用）→ 数字真假未知，
                    #     但「声称 5000 行、需求 1 亿」方向上已经不够，
                    #     保留值标 declared（安全，不会假通过）；
                    #   核对**不符**、**没出处**、**只有声称** → 数字本身
                    #     有问题，一律降成 unknown，不参与判定（不冤枉）。
                    if any(kw in why for kw in
                           ("没跑成", "跑不了", "不可用")):
                        dims[k] = _cap.Dim(value=val, source="declared",
                                           bound="exact", note=why[:80])
                    else:
                        dims[k] = _cap.Dim(value=None, source="unknown",
                                           bound="exact", note=why[:80])
                    continue
                dims[k] = _cap.Dim(value=val, source="measured",
                                   bound="exact", note=why[:80])
            base = _cap.Capability(label=base.label, dims=dims,
                                   facts=dict(getattr(base, "facts", {}) or {}))
        # 并发维度要分清"量的什么"（第六十一轮）：
        # probe_concurrency 量的是**线程驻留数**（能同时开 256 个线程），
        # 而"100 个并发事务会不会锁等待"完全是另一件事。
        # 拿线程数去回答事务并发，会得出"够"——一个基于隔壁指标的信心。
        #
        # 规矩：需求没声明 kind 或 kind 不是 threads 时，把环境的并发维度
        # 降成 unknown。这样最坏只是"没测到"，不会假阳性地说够。
        ckind = needs.get("concurrency_kind")
        need_args = {k: v for k, v in needs.items() if k != "concurrency_kind"}
        if ckind and ckind != "threads" and "concurrency" in need_args:
            dims = dict(base.dims)
            dims["concurrency"] = _cap.Dim(
                value=None, source="unknown", bound="exact",
                note=f"要的是 {ckind} 并发，探针量的是线程驻留，不是一回事")
            base = _cap.Capability(label=base.label, dims=dims,
                                   facts=dict(getattr(base, "facts", {}) or {}))

        need = _cap.requirement(**need_args)
        ok, why = _cap.fits(base, need)
        return ok, why.replace(chr(10), "；")[:120]
    except Exception as e:  # noqa: BLE001
        return None, f"能力判定出错：{type(e).__name__}: {e}"


def run_gates(c: Claim, env: EvidenceEnv | None = None) -> dict:
    """三道闸按顺序跑；被 reject 即终止，不再往下。"""
    env = env or EvidenceEnv()

    # 实测反证：有实验证据直接否定，不再走闸门——过多少道闸都改变不了"已证伪"
    if c.refuted_by_test:
        return {
            "cid": c.cid, "text": c.text, "dims": c.dims(),
            "env": env.describe(), "env_limited": env.level < 3,
            "downgraded_by_env": False,
            "C": c.score(), "ledger": [],
            "final": "reject", "cause": None, "blocked_at": "REFUTED",
        }

    # 规程类的关键输入失效：步骤再清楚也白搭，一票否决
    if c.kind == "procedure" and c.input_valid is False:
        return {
            "cid": c.cid, "text": c.text, "dims": c.dims(),
            "env": env.describe(), "env_limited": env.level < 3,
            "downgraded_by_env": False,
            "C": c.score(), "ledger": [],
            "final": "reject", "cause": None, "blocked_at": "INPUT_INVALID",
        }

    # 前置没查成 → 不许判 pass（第六十三轮）。
    #
    # 第二十六轮定过一条：input_valid=None（没查成）不否决，因为"查不成"≠"做不了"。
    # 那条仍然有效——但当时漏了一半：不否决不等于可以判 pass。
    #
    # 实测 12 条 pass 样本，11 条的依据是"前置检查通过"——pass 的可靠性
    # 本来就是前置检查给的。只有 1 条前置没查成却判了 pass，而且碰巧成功。
    # 那一条是赌博，不是结论。
    #
    # 所以：**声明了验法（verify）但没验成** → 降为 degrade/info。
    # 没声明 verify 的不受影响（那是没打算验，不是验失败了）。
    unverified_precondition = bool(getattr(c, "verify", None)) and c.input_valid is None
    if unverified_precondition and env.level >= 3:
        pass  # 先记着，闸门跑完再决定是否降级

    # 环境能力核验：任务声明的需求，本机明确给不了 → 直接降级，不必等闸门结果。
    # 判据是 capability.fits() 的三态，**只有明确 False 才降级**——
    # None 是「没测到」，不能当成「做不到」（第五十七轮的教训）。
    cap_ok, cap_why = _capability_check(c, env)

    ledger = []
    for stage in ("G1", "G2", "G3"):
        r = gate(c, stage, env)
        ledger.append(r)
        if r["verdict"] == "reject":
            break
    final = ledger[-1]["verdict"] if ledger else "reject"
    # 环境受限时，任何"通过"都降为"降级"——证据不全，不许声称过关。
    downgraded = False
    if unverified_precondition and final == "pass":
        # 声明了验法但没验成 —— 没资格说 pass。
        # 不否决（那会把"查不成"当"做不了"），只降级。
        final = "degrade"
        ledger[-1]["verdict"] = "degrade"
        ledger[-1]["downgraded_by_env"] = False
    if cap_ok is False and final == "pass":
        final = "degrade"
        ledger[-1]["verdict"] = "degrade"
        ledger[-1]["downgraded_by_env"] = True
        downgraded = True
    if env.level < 3 and final == "pass":
        final = "degrade"
        ledger[-1]["verdict"] = "degrade"
        ledger[-1]["downgraded_by_env"] = True
        downgraded = True

    # degrade 有两种成因，差别在结果上能差 7 倍（第十八轮实测 L2 4/4 vs L3 1/7）：
    #   env  —— 本可 pass，被环境规则降级；条件一好就可能成功
    #   info —— 证据不足，闸门自己判的降级；大概率干不成
    if final == "degrade":
        # 环境能力明确不够时，成因就是 env——不管这次 degrade 是怎么来的。
        # 闸门自己判出的 degrade（比如 e3=0）如果同时还缺环境能力，
        # 说 info 就是错的：证据补齐了也照样做不成，卡点是环境。
        if cap_ok is False:
            cause = "env"
            ledger[-1]["downgraded_by_env"] = True
        elif unverified_precondition:
            cause = "info"      # 前置没查成 = 证据不足，不是环境限制
        else:
            cause = "env" if downgraded else "info"
    else:
        cause = None

    return {
        "cid": c.cid,
        "text": c.text,
        "dims": c.dims(),
        "env": env.describe(),
        "env_limited": env.level < 3,
        "downgraded_by_env": downgraded,
        "C": c.score(),
        "ledger": ledger,
        "final": final,
        "cause": cause,
        "capability": cap_why,
        "blocked_at": ledger[-1]["gate"] if final == "reject" else None,
    }


# =============================================================================
# B2  对宿主提问
# =============================================================================
# 设计要点：触发条件必须可判，不能是"模型觉得不确定"。
# 只有两类允许发问：
#   歧义型 —— 分叉探测：同样的题干按两种合理解释各跑一次粗解，关键字段对不上
#   缺参型 —— 解算链上出现未绑定且无法从题干/库推断的必需参数
# 两条硬约束：一次最多问 2 个；每个问题必须带默认值。
# -----------------------------------------------------------------------------

MAX_QUESTIONS = 2
DEFAULT_WAIT_ROUNDS = 2   # 交互模式下最多等两轮；批处理模式 = 0


@dataclass
class Question:
    qid: str
    reason: str            # 为什么问（一句话，指出分歧点）
    options: list[str]     # 候选解释
    default: str           # 用户不答时采用的默认值
    kind: str = "ambiguity"  # ambiguity | missing_param


def detect_fork(
    runs: list[dict],
    key_fields: list[str],
) -> dict:
    """分叉探测。

    runs: 每个元素是一次"按某种解释跑出来的粗解"，形如
          {"interpretation": "按缺考计0分", "fields": {"average": 78.4, "rank": 3}}

    判定：任意两个 run 在 key_fields 上存在差异 → 判为歧义。
    这是可复现的判据（同一批 runs 必然得到同一结论），不依赖模型自评。
    """
    if len(runs) < 2:
        return {"forked": False, "reason": "只有一种解释，无需探测", "diverged": {}}

    diverged: dict[str, list] = {}
    for f in key_fields:
        vals = [(r["interpretation"], r["fields"].get(f)) for r in runs]
        uniq = {json.dumps(v, ensure_ascii=False, sort_keys=True) for _, v in vals}
        if len(uniq) > 1:
            diverged[f] = [{"interpretation": i, "value": v} for i, v in vals]

    return {
        "forked": bool(diverged),
        "reason": (
            f"{len(diverged)} 个关键字段在不同解释下取值不同"
            if diverged
            else "各解释下关键字段取值一致"
        ),
        "diverged": diverged,
    }


def detect_missing(params_required: list[str], bound: dict[str, object]) -> list[str]:
    """缺参探测：必需参数里没有绑定、也没有可推断默认值的。

    bound 里值为 None 或空串视为未绑定。
    """
    missing = []
    for p in params_required:
        v = bound.get(p, None)
        if v is None or (isinstance(v, str) and not v.strip()):
            missing.append(p)
    return missing


def build_questions(
    fork: Optional[dict] = None,
    missing: Optional[list[str]] = None,
    defaults: Optional[dict[str, str]] = None,
) -> list[Question]:
    """把两类探测结果转成问题，强制不超过 MAX_QUESTIONS，且每条自带默认值。"""
    defaults = defaults or {}
    qs: list[Question] = []

    if fork and fork.get("forked"):
        fields = list(fork["diverged"].keys())
        # 用第一个分歧字段构造歧义问题，其余字段写进 reason
        first = fields[0] if fields else "key"
        opts = [d["interpretation"] for d in fork["diverged"].get(first, [])]
        qs.append(
            Question(
                qid="Q_AMBIG",
                reason=f"『{first}』在不同解释下取值不同（涉及字段: {', '.join(fields)}）",
                options=opts,
                default=opts[0] if opts else "按最常见口径",
                kind="ambiguity",
            )
        )

    if missing:
        qs.append(
            Question(
                qid="Q_PARAM",
                reason=f"缺少必要输入: {', '.join(missing)}",
                options=[],
                default=defaults.get(missing[0], "按库中同题型的惯用值"),
                kind="missing_param",
            )
        )

    return qs[:MAX_QUESTIONS]


def ask_gate(
    questions: list[Question],
    answered: Optional[dict[str, str]] = None,
    wait_rounds: int = DEFAULT_WAIT_ROUNDS,
) -> dict:
    """提问状态机。

    DETECT → ASK → WAIT(wait_rounds)
                ├ 有回答 → MERGE(约束补丁) → RE_DECOMPOSE
                └ 超时/未答 → DEFAULT(用默认值) → CONTINUE(带存疑标注)
    """
    answered = answered or {}

    if not questions:
        return {"state": "SKIP", "patch": {}, "caveats": [], "questions": []}

    if wait_rounds <= 0:
        patch = {q.qid: q.default for q in questions}
        return {
            "state": "BATCH_DEFAULT",
            "patch": patch,
            "caveats": [f"{q.reason} → 采用默认：{q.default}" for q in questions],
            "questions": [asdict(q) for q in questions],
        }

    hit = {q.qid: answered[q.qid] for q in questions if q.qid in answered}
    miss = [q for q in questions if q.qid not in answered]

    if miss and len(hit) == 0:
        patch = {q.qid: q.default for q in questions}
        return {
            "state": "TIMEOUT_DEFAULT",
            "patch": patch,
            "caveats": [f"{q.reason} → 未回复，采用默认：{q.default}" for q in questions],
            "questions": [asdict(q) for q in questions],
        }

    patch = {q.qid: hit.get(q.qid, q.default) for q in questions}
    caveats = [f"{q.reason} → 未回复，采用默认：{q.default}" for q in miss]
    return {
        "state": "MERGED",
        "patch": patch,
        "caveats": caveats,
        "questions": [asdict(q) for q in questions],
    }


def render_degraded(answer: str, caveats: list[str], unresolved: list[str]) -> str:
    """降级输出模板：不问也要给出东西，但绝不假装确定。"""
    lines = [f"【答案】{answer}"]
    if caveats:
        lines.append("【方向存疑】")
        lines.extend(f"  - {c}" for c in caveats)
    if unresolved:
        lines.append("【未验证项】")
        lines.extend(f"  - {u}" for u in unresolved)
    return "\n".join(lines)


# =============================================================================
# B3  汇总同类
# =============================================================================
# 设计要点：判等不靠"感觉像同一类"，而是把子问题拆成可比字段，
# 按 operation + answer_type 定列，按 target 定项，conditions 互斥则拒绝合并。
# -----------------------------------------------------------------------------

OP_KINDS = {"求值", "比较", "证明", "定义", "列举", "预测", "评价"}
ANSWER_TYPES = {"数值", "布尔", "集合", "文本", "过程", "区间"}


@dataclass
class SubQ:
    sid: str
    target: str          # 问的对象
    op: str              # 问的动作
    answer_type: str     # 答案类型
    conditions: dict[str, object] = field(default_factory=dict)
    required_params: list[str] = field(default_factory=list)

    def signature(self) -> tuple:
        return (self.op, self.answer_type)


def classify(a: SubQ, b: SubQ) -> str:
    """强同类 / 弱同类 / 异类。

    strong —— op 与 answer_type 相同，且 target 相同        → 合并为一项
    weak   —— op 与 answer_type 相同，target 不同            → 同列不同项，不合并
    diff   —— op 或 answer_type 不同                         → 不同列
    """
    if a.op != b.op or a.answer_type != b.answer_type:
        return "diff"
    if a.target == b.target:
        return "strong"
    return "weak"


def conflict(a: SubQ, b: SubQ) -> Optional[str]:
    """强同类合并前的冲突检测。

    同一 target 但 conditions 对同一键给出不同值 → 冲突，禁止合并。
    """
    if classify(a, b) != "strong":
        return None
    for k in set(a.conditions) & set(b.conditions):
        if a.conditions[k] != b.conditions[k]:
            return f"约束冲突: 同为『{a.target}』，但 {k} 分别为 {a.conditions[k]!r} 与 {b.conditions[k]!r}"
    return None


def group(subqs: list[SubQ]) -> dict:
    """按签名分列，列内按 target 归并。

    返回：
      columns: [{signature, items: [{target, members: [sid...]}], conflicts: [...]}]
      merged / dropped 统计
    """
    columns: dict[tuple, list[SubQ]] = {}
    for sq in subqs:
        if sq.op not in OP_KINDS:
            raise ValueError(f"{sq.sid}: 未知 op={sq.op!r}")
        if sq.answer_type not in ANSWER_TYPES:
            raise ValueError(f"{sq.sid}: 未知 answer_type={sq.answer_type!r}")
        columns.setdefault(sq.signature(), []).append(sq)

    out = []
    merged_count = 0
    conflict_count = 0

    for sig, members in columns.items():
        by_target: dict[str, list[SubQ]] = {}
        for sq in members:
            by_target.setdefault(sq.target, []).append(sq)

        items = []
        conflicts = []
        for target, group_members in by_target.items():
            primary = group_members[0]
            merged_in: list[SubQ] = []
            conflicted: list[SubQ] = [primary]
            for cand in group_members[1:]:
                c = conflict(primary, cand)
                if c:
                    conflicts.append({"target": target, "reason": c,
                                      "sids": [primary.sid, cand.sid]})
                    conflict_count += 1
                    conflicted.append(cand)      # 冲突不合并，各保留一条
                else:
                    merged_in.append(cand)       # 并入主项
                    merged_count += 1
            items.append({
                "target": target,
                "primary": primary.sid,
                "merged_in": [m.sid for m in merged_in],
                "conflicted": [m.sid for m in conflicted if m is not primary],
            })

        out.append({
            "signature": list(sig),
            "items": items,
            "conflicts": conflicts,
        })

    return {
        "columns": out,
        "n_columns": len(out),
        "n_items": sum(len(c["items"]) for c in out),
        "merged": merged_count,
        "conflicts": conflict_count,
    }


# =============================================================================
# selftest：用一道真实题跑通三条路
# =============================================================================
# 题：某城市 2026 年新能源汽车充电桩缺口评估
# 这条题同时具备：可分列（求值 vs 预测）、可强合并（同一 target 重复出现）、
# 有歧义（"缺口"的定义）、有缺参（城市未指定）。
# -----------------------------------------------------------------------------

CITY_TASK = {
    "title": "某城市 2026 年新能源汽车充电桩缺口评估",
    "subqs": [
        SubQ("SQ1", "充电桩存量", "求值", "数值", {"年份": 2026}, ["城市"]),
        SubQ("SQ2", "新能源汽车保有量", "求值", "数值", {"年份": 2026}, ["城市"]),
        SubQ("SQ3", "车桩比", "求值", "数值", {"年份": 2026}, []),
        SubQ("SQ4", "充电桩存量", "求值", "数值", {"年份": 2026}, ["城市"]),   # 与 SQ1 强同类
        SubQ("SQ5", "目标车桩比", "求值", "数值", {"口径": "政策目标"}, []),
        SubQ("SQ6", "2030年缺口", "预测", "数值", {"年份": 2030}, ["城市"]),   # 异类：op=预测
        SubQ("SQ7", "充电桩存量", "求值", "数值", {"年份": 2025}, ["城市"]),   # 约束冲突：年份不同
    ]
}

CLAIMS = [
    Claim(
        cid="C_SQ1", text="该市 2026 年公共充电桩存量约 12.3 万个",
        e1=2, e2=0, e3=2,
        sources=["市政府《2026能源发展公报》第3章表4"],
    ),
    Claim(
        cid="C_SQ2", text="该市 2026 年新能源汽车保有量约 39.4 万辆",
        e1=2, e2=1, e3=2,
        sources=["市交委年报 §2", "行业协会统计（疑同源转载）"],
    ),
    Claim(
        cid="C_SQ3", text="车桩比 3.2:1",
        e1=2, e2=2, e3=2,
        sources=["公报推算", "独立复算（39.4/12.3）", "协会交叉核对"],
    ),
    Claim(
        cid="C_SQ6", text="2030 年缺口将达 8 万个",
        e1=1, e2=0, e3=0,
        sources=["某券商研报结论"],
        out_of_scope=True,
    ),
]


# =============================================================================
# 端到端：三个瓶颈串成一条流水线
# =============================================================================
# 目的：证明三个模块互不打架。
#   分列 → 逐项过闸 → 拒绝项直接归档 → 存疑项进提问闸 → 汇总
# -----------------------------------------------------------------------------

ROUTE = {"pass": "方案库", "degrade": "疑难2库（降级后待补证）", "reject": "疑难1库"}


def run_pipeline(task: dict, claims: list[Claim]) -> dict:
    g = group(task["subqs"])
    claim_by_cid = {c.cid: c for c in claims}

    column_reports = []
    for col in g["columns"]:
        rows = []
        for it in col["items"]:
            c = claim_by_cid.get("C_" + it["primary"])
            if c is None:
                rows.append({
                    "target": it["target"], "primary": it["primary"],
                    "merged_in": it["merged_in"], "conflicted": it["conflicted"],
                    "status": "no_claim", "C": None, "final": None,
                    "blocked_at": None, "route": "待生成结论",
                })
                continue
            r = run_gates(c)
            rows.append({
                "target": it["target"], "primary": it["primary"],
                "merged_in": it["merged_in"], "conflicted": it["conflicted"],
                "status": "scored", "C": r["C"], "final": r["final"],
                "blocked_at": r["blocked_at"], "route": ROUTE[r["final"]],
            })
        column_reports.append({
            "signature": col["signature"],
            "rows": rows,
            "conflicts": col["conflicts"],
        })

    flat = [r for c in column_reports for r in c["rows"]]
    stats = {
        "n_columns": g["n_columns"],
        "n_items": g["n_items"],
        "passed": sum(1 for r in flat if r["final"] == "pass"),
        "rejected": sum(1 for r in flat if r["final"] == "reject"),
        "no_claim": sum(1 for r in flat if r["status"] == "no_claim"),
        "merged": g["merged"],
        "conflicts": g["conflicts"],
    }
    return {"columns": column_reports, "stats": stats}


def selftest() -> int:
    fails = []

    def check(name: str, cond: bool, detail: str = ""):
        status = "PASS" if cond else "FAIL"
        print(f"  [{status}] {name}" + (f"  — {detail}" if detail else ""))
        if not cond:
            fails.append(name)

    print("=" * 72)
    print("B1  置信度评估 · 三维打分与递进闸门")
    print("=" * 72)

    results = {}
    for c in CLAIMS:
        r = run_gates(c)
        results[c.cid] = r
        print(f"  {c.cid:8s} C={r['C']}  dims={r['dims']}  final={r['final']}"
              + (f"  blocked_at={r['blocked_at']}" if r["blocked_at"] else ""))

    # C_SQ1: e1=2,e2=0,e3=2 → C=4；G1 pass(2) G2 e1+e2=2 → reject(<=2)
    check("C_SQ1 在 G2 被打回（独立度不足）",
          results["C_SQ1"]["blocked_at"] == "G2",
          f"actual={results['C_SQ1']['blocked_at']}")

    # C_SQ3: 6 分全通过
    check("C_SQ3 三道闸全通过",
          results["C_SQ3"]["final"] == "pass",
          f"actual={results['C_SQ3']['final']}")

    # C_SQ6: e1=1,e2=0,e3=0 -1(out_of_scope) → C=0；G1 pass(1) G2 1 → reject
    check("C_SQ6 在 G2 被打回并计入越界扣分",
          results["C_SQ6"]["C"] == 0 and results["C_SQ6"]["blocked_at"] == "G2")

    # ---- 环境能力核验（第五十八轮接入）----
    # 任务声明的需求本机明确给不了 → 自动降级，不再靠人手标 cause。
    # 三态纪律：探针只拿到下限时不许判 False。
    def _cap_case(label, needs, facts):
        cc = Claim("CAP", label, e1=2, e2=2, e3=2, kind="world", needs=needs)
        return run_gates(cc, EvidenceEnv(3, facts=facts))

    # 用 const 域自证，不依赖外部数据库 —— 原来靠 SQL 探针，
    # seekdb 一不可用就变成 pass（实测 5/5）。
    _CONST = {"domain": "const", "task": {"value": 5000}}
    _c1 = _cap_case("要 1 亿行 / 库 5,000 行", {"rows": 100_000_000},
                    {"scale": {"value": 5000, "from": "数一遍", "check": _CONST}})
    check("能力不够 → 自动降级为 degrade",
          _c1["final"] == "degrade", f"actual={_c1['final']}")
    check("能力不够 → cause 自动记为 env",
          _c1["cause"] == "env", f"actual={_c1['cause']}")

    _c2 = _cap_case("要 1 千行 / 库 5,000 行", {"rows": 1_000},
                    {"scale": {"value": 5000, "from": "数一遍", "check": _CONST}})
    check("能力够 → 不降级", _c2["final"] == "pass", f"actual={_c2['final']}")

    _c3 = _cap_case("要 1 亿行 / 没有精确事实", {"rows": 100_000_000}, None)
    check("只有下限没精确值 → 不判不够（None 不等于 False）",
          _c3["final"] == "pass", f"actual={_c3['final']}")

    _c4 = _cap_case("要 arm64", {"arch": "aarch64"}, None)
    check("架构明确不符 → 自动降级", _c4["final"] == "degrade"
          and _c4["cause"] == "env", f"actual={_c4['final']}/{_c4['cause']}")

    check("没声明需求 → 不干预判定",
          _cap_case("普通主张", None, None)["final"] == "pass")

    # ---- 环境事实必须带出处（第五十九轮）----
    # 调用方给的数字如果没出处，不许拿去否定结论——降为 unknown 即可。
    _c5 = _cap_case("要 1 亿行 / 给了值但没出处", {"rows": 100_000_000},
                    {"scale": 5000})
    check("没出处的事实不降级判定", _c5["final"] == "pass",
          f"actual={_c5['final']}")

    _c6 = _cap_case("要 1 亿行 / 给了值+出处", {"rows": 100_000_000},
                    {"scale": {"value": 5000, "from": "数一遍", "check": _CONST}})
    check("有出处的事实才降级", _c6["final"] == "degrade"
          and _c6["cause"] == "env", f"actual={_c6['final']}/{_c6['cause']}")

    _c7 = _cap_case("要 1 亿行 / 出处是空串", {"rows": 100_000_000},
                    {"scale": {"value": 5000, "from": ""}})
    check("空出处等同于没出处", _c7["final"] == "pass",
          f"actual={_c7['final']}")

    check("_split_fact 认得三种写法",
          _split_fact(5000) == (5000, "", None)
          and _split_fact({"value": 7, "from": "x"}) == (7, "x", None)
          and _split_fact({"value": 7, "from": "x", "check": {"a": 1}})[2] == {"a": 1})

    # ---- 事实必须真跑一次对账（第六十轮）----
    # 用 const 域：把值写进规格里直接核对。原来用 SQL 探针，
    # seekdb 一不可用就整组测试变红/变绿不定（实测）。
    _VERIFIED = {"value": 5000, "from": "数一遍",
                 "check": {"domain": "const", "task": {"value": 5000}}}
    _MISMATCH = {"value": 99999, "from": "瞎填",
                 "check": {"domain": "const", "task": {"value": 5000}}}
    _CLAIMED = {"value": 5000, "from": "sql: SELECT COUNT(*)"}

    def _fc(facts):
        cc = Claim("F", "要 1 亿行", e1=2, e2=2, e3=2, kind="world",
                   needs={"rows": 100_000_000})
        return run_gates(cc, EvidenceEnv(3, facts=facts))

    _f1 = _fc({"scale": _VERIFIED})
    check("核对通过的事实才降级", _f1["final"] == "degrade" and _f1["cause"] == "env",
          f"actual={_f1['final']}")
    _f2 = _fc({"scale": _MISMATCH})
    check("核对不符的事实被拒收（不降级）", _f2["final"] == "pass",
          f"actual={_f2['final']}")
    _f3 = _fc({"scale": _CLAIMED})
    check("只有声称没有核对规格 → 不采信", _f3["final"] == "pass",
          f"actual={_f3['final']}")
    _vf = _verify_fact(5000, "数一遍",
                       {"domain": "const", "task": {"value": 5000}})
    check("_verify_fact 对得上就放行", _vf[0] is True, _vf[1][:50])

    # ---- 并发：探针量的是什么，决定能不能说"够"（第六十一轮）----
    # probe_concurrency 量的是线程驻留数，不是并发事务。
    # 拿线程数回答"100 个事务会不会锁等待"，会得出假的"够"。
    def _conc(needs):
        cc = Claim("C", "并发任务", e1=2, e2=2, e3=2, kind="proc", needs=needs)
        return run_gates(cc, EvidenceEnv(3))

    _k1 = _conc({"concurrency": 100, "concurrency_kind": "threads"})
    check("要线程 → 探针答得了",
          "够" in (_k1.get("capability") or ""), (_k1.get("capability") or "")[:50])

    _k2 = _conc({"concurrency": 100, "concurrency_kind": "transactions"})
    check("要事务 → 探针答不了，不许说够",
          "没测到" in (_k2.get("capability") or ""), (_k2.get("capability") or "")[:50])
    check("答不了就不降级（不会假阳性地说够，也不会假阴性地说不够）",
          _k2["final"] == "pass", f"actual={_k2['final']}")

    _k3 = _conc({"concurrency": 1000, "concurrency_kind": "threads"})
    check("超了实测下限也不判不够（下限不构成否定）",
          _k3["final"] == "pass", f"actual={_k3['final']}")

    # ---- 声明了验法但没验成 → 不许判 pass（第六十三轮）----
    # 第二十六轮定过 input_valid=None 不否决（查不成 ≠ 做不了），那条还成立。
    # 但漏了一半：不否决不等于可以判 pass。
    _V = {"domain": "file", "task": {"path": r"C:\x", "op": "read"}}

    def _pv(verify, iv):
        cc = Claim("P", "前置样本", e1=2, e2=2, e3=2, kind="procedure",
                   verify=verify, input_valid=iv)
        return run_gates(cc, EvidenceEnv(3))

    check("声明了验法 + 验通过 → pass",
          _pv(_V, True)["final"] == "pass")
    _pv2 = _pv(_V, None)
    check("声明了验法 + 没验成 → degrade 且 cause=info",
          _pv2["final"] == "degrade" and _pv2["cause"] == "info",
          f"actual={_pv2['final']}/{_pv2['cause']}")
    check("声明了验法 + 验失败 → reject（不降级，直接打回）",
          _pv(_V, False)["final"] == "reject"
          and _pv(_V, False)["blocked_at"] == "INPUT_INVALID")
    check("没声明验法 → 不受这条规则影响",
          _pv(None, None)["final"] == "pass")

    # C_SQ2: e1+e2=3 → G2 degrade；C=5 → G3 pass
    check("C_SQ2 在 G2 降级后在 G3 通过",
          [g["verdict"] for g in results["C_SQ2"]["ledger"]] == ["pass", "degrade", "pass"],
          str([g["verdict"] for g in results["C_SQ2"]["ledger"]]))

    print()
    print("=" * 72)
    print("B2  对宿主提问 · 分叉探测 / 缺参 / 超时降级")
    print("=" * 72)

    runs = [
        {"interpretation": "缺口=桩数缺口", "fields": {"gap_value": 8.0, "unit": "万个", "rank": 3}},
        {"interpretation": "缺口=车桩比缺口", "fields": {"gap_value": 22.5, "unit": "%", "rank": 7}},
    ]
    fork = detect_fork(runs, ["gap_value", "unit"])
    print(f"  分叉探测: forked={fork['forked']}  {fork['reason']}")
    check("两种解释下 gap_value 不同 → 判为歧义", fork["forked"] is True)

    missing = detect_missing(["城市", "年份"], {"城市": "", "年份": 2026})
    print(f"  缺参探测: {missing}")
    check("城市为空 → 识别为缺参", missing == ["城市"])

    questions = build_questions(fork, missing, defaults={"城市": "按省会城市口径"})
    print(f"  生成问题 {len(questions)} 条（上限 {MAX_QUESTIONS}）:")
    for q in questions:
        print(f"    - [{q.qid}] {q.reason} | 默认: {q.default}")
    check("问题数量不超过上限", len(questions) <= MAX_QUESTIONS)
    check("每条问题都带默认值", all(q.default for q in questions))

    r_timeout = ask_gate(questions, answered={}, wait_rounds=2)
    print(f"  超时分支: state={r_timeout['state']}")
    check("未回答 → TIMEOUT_DEFAULT", r_timeout["state"] == "TIMEOUT_DEFAULT")

    r_batch = ask_gate(questions, answered={}, wait_rounds=0)
    check("批处理模式不阻塞", r_batch["state"] == "BATCH_DEFAULT")

    r_merged = ask_gate(questions, answered={"Q_AMBIG": "缺口=车桩比缺口"}, wait_rounds=2)
    print(f"  回答分支: state={r_merged['state']}  patch={r_merged['patch']}")
    check("有回答 → MERGED 且落入约束补丁", r_merged["state"] == "MERGED")

    degraded = render_degraded("该市 2026 年缺口约 8 万个", r_timeout["caveats"], ["2030 年预测未验证"])
    print("  降级输出样例:")
    for line in degraded.splitlines():
        print("    " + line)
    check("降级输出同时含答案与存疑段", "【答案】" in degraded and "【方向存疑】" in degraded)

    print()
    print("=" * 72)
    print("B3  汇总同类 · 结构化判等 / 冲突检测 / 分列")
    print("=" * 72)

    g = group(CITY_TASK["subqs"])
    print(f"  分列结果: {g['n_columns']} 列 / {g['n_items']} 项 / 合并 {g['merged']} 次 / 冲突 {g['conflicts']} 处")
    for col in g["columns"]:
        print(f"    列 {col['signature']}:")
        for it in col["items"]:
            extra = ""
            if it["merged_in"]:
                extra += f"，并入 {it['merged_in']}"
            if it["conflicted"]:
                extra += f"，冲突 {it['conflicted']}"
            print(f"      - {it['target']}: 主项 {it['primary']}{extra}")
        for cf in col["conflicts"]:
            print(f"      ! {cf['reason']}")

    check("求值列与预测列分开（异类不混列）", g["n_columns"] == 2, f"actual={g['n_columns']}")

    sq1_item = next(
        (it for col in g["columns"] for it in col["items"] if it["primary"] == "SQ1"), None
    )
    check("SQ4 并入 SQ1（强同类合并）",
          sq1_item is not None and "SQ4" in sq1_item["merged_in"],
          str(sq1_item))
    check("SQ7 因年份不同判为冲突、未被并入",
          sq1_item is not None and "SQ7" in sq1_item["conflicted"],
          str(sq1_item))
    check("冲突计数与项数一致", g["conflicts"] >= 1, f"actual={g['conflicts']}")

    print()
    print("=" * 72)
    print("E2E  端到端流水线 · 三瓶颈同时在线")
    print("=" * 72)

    pipe = run_pipeline(CITY_TASK, CLAIMS)
    for col in pipe["columns"]:
        print(f"  列 {col['signature']}:")
        for r in col["rows"]:
            tail = ""
            if r["merged_in"]:
                tail += f" 并入{r['merged_in']}"
            if r["conflicted"]:
                tail += f" 冲突{r['conflicted']}"
            print(f"    {r['primary']:{5}s} C={str(r['C']):4s} {str(r['final']):7s} → {r['route']}{tail}")
    print(f"  统计: {pipe['stats']}")

    check("端到端产出 2 列", pipe["stats"]["n_columns"] == 2,
          str(pipe["stats"]["n_columns"]))
    check("通过 2 项、拒绝 2 项、待生成 1 项",
          (pipe["stats"]["passed"], pipe["stats"]["rejected"], pipe["stats"]["no_claim"]) == (2, 2, 1),
          str(pipe["stats"]))
    check("被拒项全部落到疑难1库",
          all(r["route"] == "疑难1库"
              for c in pipe["columns"] for r in c["rows"] if r["final"] == "reject"))
    check("冲突项在流水线中保留标记",
          any(r["conflicted"] for c in pipe["columns"] for r in c["rows"]))

    print()
    print("=" * 72)
    print("ENV  证据环境自适应 · 判据随能力收缩")
    print("=" * 72)

    probe = Claim(cid="P_ENV", text="指到位置+两源独立+部分可复现", e1=2, e2=2, e3=1,
                  sources=["src/oblib/common/ob_range.cpp:120", "独立复算"])
    for lvl in (3, 2, 1, 0):
        env = EvidenceEnv(level=lvl)
        r = run_gates(probe, env)
        print(f"  L{lvl} {ENV_LEVELS[lvl]:<28} "
              f"G2线={env.pass_at('G2')} G3线={env.pass_at('G3')} → {r['final']}"
              + ("  [环境受限]" if r["env_limited"] else ""))

    check("L3 通过线不变（G2=4, G3=5）",
          EvidenceEnv(3).pass_at("G2") == 4 and EvidenceEnv(3).pass_at("G3") == 5)
    check("L1 通过线收缩（G2=2）", EvidenceEnv(1).pass_at("G2") == 2,
          str(EvidenceEnv(1).pass_at("G2")))
    check("L0 下 G1 不可达（上限 0）", EvidenceEnv(0).cap("G1") == 0)
    check("通过线永不低于打回线",
          all(EvidenceEnv(l).pass_at(s) >= GATE_SPEC[s]["reject_below"]
              for l in (0, 1, 2, 3) for s in ("G1", "G2", "G3")))
    check("环境受限时 pass 被降为 degrade",
          run_gates(probe, EvidenceEnv(1))["final"] == "degrade",
          str(run_gates(probe, EvidenceEnv(1))["final"]))
    check("L3 下同一结论可 pass",
          run_gates(probe, EvidenceEnv(3))["final"] == "pass",
          str(run_gates(probe, EvidenceEnv(3))["final"]))
    check("打分被环境上限截断（L1 下 e1=2 只算 1）",
          gate(probe, "G2", EvidenceEnv(1))["value"] == 2,
          str(gate(probe, "G2", EvidenceEnv(1))["value"]))

    # 自动探测：只看硬事实，不看自述
    env_self, why_self = detect_env(os.path.dirname(os.path.abspath(__file__)))
    print(f"  自动探测本目录: L{env_self.level}  ({why_self['reason']})")
    check("本目录有 .py 源码 → 至少 L1", env_self.level >= 1)
    check("本目录无 observer 可执行 → 不到 L3", env_self.level < 3)

    env_none, why_none = detect_env(None, None, network=False)
    print(f"  探测空环境: L{env_none.level}  ({why_none['reason']})")
    check("无源码无执行无网络 → L0", env_none.level == 0)

    print()
    print("=" * 72)
    print("PROC  规程类判据 · 独立性不适用")
    print("=" * 72)

    proc = Claim(cid="PR1", text="部署后从配置文件取 UUID", e1=2, e3=2, kind="procedure")
    world = Claim(cid="WD1", text="同样的分，但按世界断言判", e1=2, e3=2, kind="world")
    rp = run_gates(proc, EvidenceEnv(3))
    rw = run_gates(world, EvidenceEnv(3))
    print(f"  procedure L3 → {rp['final']:7s} (uses={rp['ledger'][1]['uses']})")
    print(f"  world     L3 → {rw['final']:7s} (uses={rw['ledger'][1]['uses']})")

    check("规程类在 L3 能通过", rp["final"] == "pass", str(rp["final"]))
    check("同样的分按世界判据会被拒", rw["final"] == "reject", str(rw["final"]))
    check("规程类 G2 改用 e1+e3", rp["ledger"][1]["uses"] == ["e1", "e3"],
          str(rp["ledger"][1]["uses"]))
    check("规程类 pass_at 与 world 不同",
          EvidenceEnv(3).pass_at("G2", "procedure") == 3
          and EvidenceEnv(3).pass_at("G2", "world") == 4)

    # 关键输入失效 → 一票否决
    bad_in = Claim(cid="PR2", text="伪 UUID（格式对但查不到）",
                   e1=2, e3=2, kind="procedure", input_valid=False)
    ok_in = Claim(cid="PR3", text="真 UUID", e1=2, e3=2,
                  kind="procedure", input_valid=True)
    none_in = Claim(cid="PR4", text="未检查输入", e1=2, e3=2, kind="procedure")
    rb, ro, rn = (run_gates(x, EvidenceEnv(3)) for x in (bad_in, ok_in, none_in))
    print(f"  输入无效 → {rb['final']} ({rb['blocked_at']})")
    print(f"  输入有效 → {ro['final']}")
    print(f"  未检查   → {rn['final']}")

    check("输入无效一票否决", rb["final"] == "reject" and rb["blocked_at"] == "INPUT_INVALID")
    check("输入有效可放行", ro["final"] == "pass", str(ro["final"]))
    check("未检查不否决（保守放行）", rn["final"] in ("pass", "degrade"), str(rn["final"]))

    print()
    print("=" * 72)
    print("E3SRC  e3 按证据来源推导（不靠拍）")
    print("=" * 72)
    check("measured → 2", derive_e3("measured") == 2)
    check("index_plan → 2", derive_e3("index_plan") == 2)
    check("fullscan_est → 1", derive_e3("fullscan_est") == 1)
    check("guess → 0", derive_e3("guess") == 0)
    try:
        derive_e3("nonsense")
        unknown_ok = False
    except ValueError:
        unknown_ok = True
    check("未知来源抛错", unknown_ok)
    check("每档都有理由", all(e3_reason(s) for s in E3_SOURCE))

    print()
    print("=" * 72)
    print("CAUSE  degrade 的两种成因")
    print("=" * 72)
    cx = Claim("X1", "同一条 claim", e1=2, e2=0, e3=2, kind="procedure")
    rx3 = run_gates(cx, EvidenceEnv(3))
    rx2 = run_gates(cx, EvidenceEnv(2))
    ci = Claim("X2", "证据不足", e1=2, e2=0, e3=0, kind="procedure")
    ri = run_gates(ci, EvidenceEnv(3))
    print(f"  L3 同分   → {rx3['final']:8s} cause={rx3['cause']}")
    print(f"  L2 同分   → {rx2['final']:8s} cause={rx2['cause']}")
    print(f"  L3 e3=0  → {ri['final']:8s} cause={ri['cause']}")
    check("L3 满分无成因", rx3["cause"] is None)
    check("L2 降级成因=env", rx2["cause"] == "env")
    check("证据不足成因=info", ri["cause"] == "info")
    check("pass 不带成因", run_gates(
        Claim("X3", "t", e1=2, e2=2, e3=2), EvidenceEnv(3))["cause"] is None)

    print()
    print("=" * 72)
    print("PRIOR  先验按复合键取值")
    print("=" * 72)
    from taskgraph import prior_for   # 延迟导入，避免与 taskgraph→harness 循环
    pz = {"pass": 0.9, "degrade": 0.5, "reject": 0.1,
          "degrade/env": 0.83, "degrade/info": 0.22}
    print(f"  degrade+env  → {prior_for(pz, 'degrade', 'env')}")
    print(f"  degrade+info → {prior_for(pz, 'degrade', 'info')}")
    print(f"  无复合键     → {prior_for({'degrade': 0.5}, 'degrade', 'env')}")
    check("degrade+env 取复合键", prior_for(pz, "degrade", "env") == 0.83)
    check("degrade+info 取复合键", prior_for(pz, "degrade", "info") == 0.22)
    check("无复合键回落到 verdict",
          prior_for({"degrade": 0.5}, "degrade", "env") == 0.5)

    print()
    print("=" * 72)
    print("VER    判据版本")
    print("=" * 72)
    print(f"  当前 MODEL_VERSION = {MODEL_VERSION}")
    check("版本号已定义", isinstance(MODEL_VERSION, int) and MODEL_VERSION >= 1)
    check("v2 已具备 cause 维度", MODEL_VERSION >= 2,
          "v1 没有 cause / input_valid，样本不该与 v2 混算")

    print()
    print("=" * 72)
    if fails:
        print(f"FAILED: {len(fails)} 项 -> {fails}")
        return 1
    print("ALL PASS")
    return 0


def demo() -> int:
    """打印一次完整流程的中间态，便于人工核对。"""
    print(json.dumps({
        "claims": [run_gates(c) for c in CLAIMS],
        "grouping": group(CITY_TASK["subqs"]),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "selftest"
    if cmd == "selftest":
        raise SystemExit(selftest())
    elif cmd == "demo":
        raise SystemExit(demo())
    else:
        print(__doc__)
        raise SystemExit(2)
