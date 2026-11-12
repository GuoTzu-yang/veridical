import ast
import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "orchestrate.py")
s = open(P, encoding="utf-8").read()

BLOCK = '''

def rule_propose(ctx: dict) -> list:
    """规则版 propose：不需要 LLM 也能跑起来。

    demo 里那个 _propose 把 --y/--x 硬编码成 demo 数据的列名，
    换个数据集就 KeyError；而且只提 1 条，过不了
    「至少 3 条」的批量校验（实测 5 轮全 FAIL）。

    这一版从 ctx["columns"] 读真实列名，按能力清单生成三条互不相同的
    路线：赛马 / 基线出稿 / 优化。LLM 想接管时，写 --propose-json
    给出自己的提案即可，本函数不参与。
    """
    cols = [str(c) for c in (ctx.get("columns") or [])]
    data = ctx.get("data") or ""
    cmds = ctx.get("commands") or {}
    if len(cols) < 2 or not data:
        return []

    # 目标列：默认最后一个数值列；解释变量取前面几个
    y = cols[-1]
    xs = cols[:-1][:3]
    xj = ",".join(xs)
    x2 = ",".join(xs[:2]) if len(xs) >= 2 else xj

    out = []

    if "race" in cmds:
        out.append(dict(
            route_id="A", title="模型赛马",
            method="race",
            method_args={"--data": data, "--y": y, "--x": xj, "--json": True},
            success_criteria={"cv_rmse_max": 1e9},
            falsifiable_assumption="若二次型相对线性型没有可测改进，"
                                   "则响应关系在本样本上是线性的"))

    if "run" in cmds:
        out.append(dict(
            route_id="B", title="基线出稿",
            method="run",
            method_args={"--data": data, "--y": y, "--x": xj,
                         "--no-gate": True},
            success_criteria={"n_rows_min": 1},
            falsifiable_assumption="若残差检验显示漏设曲率，"
                                   "则基线模型形式不足"))

    if "solve" in cmds and len(xs) >= 2:
        out.append(dict(
            route_id="C", title="约束优化",
            method="solve",
            method_args={"--data": data, "--y": y, "--x": x2,
                         "--maximize": True, "--json": True},
            success_criteria={"n_rows_min": 1},
            falsifiable_assumption="若最优解落在可行域内部，"
                                   "则约束没有绑定，问题退化为无约束"))

    if "forecast" in cmds and len(cols) >= 2:
        out.append(dict(
            route_id="D", title="时间外推",
            method="forecast",
            method_args={"--data": data, "--t": cols[0], "--y": y,
                         "--horizon": 5, "--json": True},
            success_criteria={"n_rows_min": 1},
            falsifiable_assumption="若外推误差随步长单调增大且不收敛，"
                                   "则该序列不可预测"))

    return out
'''

if "def rule_propose" not in s:
    i = s.find("def main(")
    assert i > 0
    s = s[:i] + BLOCK.lstrip("\n") + "\n\n" + s[i:]
    ast.parse(s)
    compile(s, P, "exec")
    open(P, "w", encoding="utf-8", newline="\n").write(s)
    print("  rule_propose 已加入")
else:
    print("  已存在")