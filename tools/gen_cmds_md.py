import json
import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
d = json.load(open(os.path.join(HERE, "schema.json"), encoding="utf-8"))
L = []
L.append("| 命令 | 干什么 | 关键参数 |")
L.append("|---|---|---|")
KEY = {
    "--data": "数据", "--y": "目标列", "--x": "解释变量",
    "--min": "多目标列", "--constraint": "约束", "--maximize": "最大化",
    "--obj": "目标列", "--k": "簇数", "--horizon": "预测步数",
    "--t": "时间轴", "--op": "算法", "--edges": "边", "--nodes": "点",
    "--matrix": "邻接矩阵", "--rhs": "右端式", "--t0": "起点",
    "--t1": "终点", "--y0": "初值", "--method": "方法", "--var": "变量",
    "--kind": "图型", "--out-png": "输出图", "--ahp": "判断矩阵",
    "--weights": "权重", "--directions": "方向", "--grades": "等级",
    "--membership": "隶属度", "--normalize": "归一化", "--operator": "算子",
    "--series": "序列", "--out-gif": "GIF", "--claim": "主张",
    "--compile": "编译", "--lang": "语言", "--team": "队号",
    "--problem": "题面", "--tex": "tex 路径", "--sheet": "工作表",
}
for name, c in d["commands"].items():
    desc = (c.get("desc") or "").split("。")[0][:52]
    args = list((c.get("args") or {}).keys())
    keys = [a for a in args if a in KEY][:4]
    kt = " ".join("%s(%s)" % (a, KEY[a]) for a in keys) or "—"
    L.append("| `%s` | %s | %s |" % (name, desc, kt))
open(os.path.join(HERE, "_cmds_table.md"), "w", encoding="utf-8",
     newline="\n").write("\n".join(L) + "\n")
print("  已生成命令表 %d 行" % len(L))