import ast, os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "paper.py")
s = open(P, encoding="utf-8").read()
ADD = {
    "队长": "queue length",
    "等待": "waiting",
    "利用率": "utilisation",
    "到达": "arrival",
    "服务": "service",
    "台数": "server count",
    "重复": "replication",
    "批次": "batch",
    "合格率": "pass rate",
    "交付": "delivery",
    "周期": "cycle",
    "消费": "spending",
    "频次": "frequency",
    "品类": "category",
    "会员": "membership",
    "等级": "tier",
    "客户": "customer",
    "价值": "value",
    "年龄": "age",
    "销量": "sales volume",
    "单价": "unit price",
    "广告": "advertising",
    "库存": "inventory",
    "退货": "returns",
    "距离": "distance",
    "容量": "capacity",
    "运输": "transport",
    "起点": "origin",
    "终点": "destination",
    "评分": "score",
    "采购": "procurement",
    "质量": "quality",
    "满意度": "satisfaction",
    "售后": "after-sales",
    "年份": "year",
    "人口": "population",
    "食物": "food",
    "供给": "supply",
    "资源": "resource",
    "消耗": "consumption",
    "城市化": "urbanisation",
}
if '"队长": "queue length"' not in s:
    anchor = '    "热阻": "thermal resistance",'
    assert anchor in s, "no TERMS anchor"
    lines = "".join('    "%s": "%s",\n' % (k, v) for k, v in ADD.items())
    s = s.replace(anchor, lines + anchor, 1)
    ast.parse(s)
    compile(s, P, "exec")
    open(P, "w", encoding="utf-8", newline="\n").write(s)
    print("  added %d terms" % len(ADD))