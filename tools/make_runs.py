import json
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "runs.json")

CFG = {
  "heat_sink": {
    "data": None, "y": "热阻", "x": "宽度,深高,排数",
    "min": "热阻,压降,温度", "problem": "heat sink",
    "out": "out/runs/heat_sink"},
  "evaluation": {
    "data": "evaluation.xlsx", "y": "综合得分",
    "x": "采购成本,质量评分,交付周期",
    "min": "综合得分,客户满意度,售后成本",
    "problem": "supplier evaluation by weighted scoring",
    "out": "out/runs/evaluation"},
  "prediction": {
    "data": "prediction.xlsx", "y": "销量",
    "x": "月份,单价,广告投入", "min": "销量,库存,退货量",
    "problem": "forecast monthly sales from price and advertising",
    "out": "out/runs/prediction"},
  "network": {
    "data": "network.xlsx", "y": "运输量",
    "x": "距离,容量,单位成本", "min": "运输量,距离,单位成本",
    "problem": "transport network flow under capacity constraints",
    "out": "out/runs/network"},
  "queueing": {
    "data": "queueing.xlsx", "y": "等待时间",
    "x": "到达人数,服务台数", "min": "等待时间,人工成本,客户流失",
    "problem": "simulation of queueing waiting time vs staffing cost",
    "out": "out/runs/queueing"},
  "population": {
    "data": "population.xlsx", "y": "人口",
    "x": "年份,食物供给", "min": "人口,资源消耗,城市化率",
    "problem": "population growth projection under resource limits",
    "out": "out/runs/population"},
  "clustering": {
    "data": "clustering.xlsx", "y": "客户价值",
    "x": "消费金额,购买频次,最近购买天数",
    "min": "客户价值,消费金额,最近购买天数",
    "problem": "customer segmentation by clustering",
    "out": "out/runs/clustering"},
  "multiobjective": {
    "data": "multiobjective.xlsx", "y": "综合效益",
    "x": "产量,单位成本,能耗", "min": "产量,单位成本,能耗",
    "problem": "production planning with conflicting objectives",
    "out": "out/runs/multiobjective"},
  "simulation": {
    "data": "simulation.xlsx", "y": "平均队长",
    "x": "到达率,服务率,服务台数", "min": "平均队长,平均等待,系统利用率",
    "problem": "monte carlo simulation of queue length under random arrivals",
    "out": "out/runs/simulation"},
  "chemical": {
    "data": "scope_test.xlsx", "y": "产量",
    "x": "反应温度,操作压力,停留时间", "min": "产量,能耗,次品率",
    "problem": "chemical reactor yield against operating conditions",
    "out": "out/runs/chemical"},
  "real_c2023": {
    "data": "real_hs.xlsx", "y": "CBTS",
    "x": "母亲年龄,妊娠时间（周数）,睡醒次数", "min": "CBTS,EPDS,HADS",
    "problem": "infant sleep quality and maternal mood regression",
    "out": "out/runs/real_c2023"},
  "real_c2024": {
    "data": "real_hs2024.xlsx", "y": "yield_per_mu",
    "x": "cost_per_mu", "min": "yield_per_mu,cost_per_mu",
    "problem": "crop yield against planting cost",
    "out": "out/runs/real_c2024"},
  "icm2006c": {
    "data": "icm2006c.xlsx", "y": "pop2005",
    "x": "pop1950,pop1980,pop1990,pop2000,life1995,life2005",
    "min": "pop2005,life2005",
    "problem": "population growth and life expectancy across countries",
    "out": "out/runs/icm2006c"},
  "mcm2020c": {
    "data": "mcm2020c.xlsx", "y": "helpful_votes",
    "x": "star_rating,total_votes,review_headline_len,body_len",
    "min": "helpful_votes,total_votes,star_rating",
    "problem": "which review features drive helpfulness votes",
    "out": "out/runs/mcm2020c"},
}

json.dump(CFG, open(P, "w", encoding="utf-8", newline="\n"),
          ensure_ascii=False, indent=1)
print("  写出 %s：%d 道题" % (os.path.basename(P), len(CFG)))
for k, v in CFG.items():
    print("    %-16s y=%-14s x=%-32s min=%s"
          % (k, v["y"][:14], v["x"][:32], v["min"][:30]))