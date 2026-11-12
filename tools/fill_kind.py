import ast
import json
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "kb", "methods", "index.json")
d = json.load(open(P, encoding="utf-8"))

# ① 补英文触发词。mechanism 原来 4 个全是热沉专属
#    (differential/dynamic/heat/thermal)，英文机制题同样含这些词，
#    但那 4 个词本身不该当成机理的判据 —— 机理由 data_features 判。
ADD_TRIG = {
    "optimization": ["minimise", "maximise", "allocation", "schedule",
                     "scheduling", "allocation", "under constraint",
                     "constrained", "maximum", "minimum"],
    "multiobjective": ["trade off", "multi objective", "competing",
                       "conflicting objective", "objective function"],
    "prediction": ["estimate", "estimation", "projection", "project",
                   "time series", "extrapolat", "forecasting", "forecast",
                   "predicting", "predict", "predictive"],
    "evaluation": ["score", "scoring", "rate", "rating", "index",
                   "compare", "comparison", "rank", "assess", "assessment",
                   "which product", "which option", "value"],
    "regression": ["predict", "response variable", "explanatory",
                   "dependent variable", "independent variable",
                   "affect", "affects", "determine", "determines",
                   "how does", "what drives", "which feature"],
    "clustering": ["segment", "segmentation", "group", "grouping",
                   "k means", "kmeans", "clustering", "typology",
                   "partition", "similar customer", "customer group"],
    "mechanism": ["physics", "physical", "mechanism", "law", "conservation",
                  "energy", "momentum", "fluid", "governing"],
    "simulation": ["simulate", "simulated", "montecarlo", "random draw",
                   "stochastic", "agent based", "discrete event"],
    "network": ["network", "graph", "routing", "shortest path", "flow",
                "transport", "logistics", "supply chain", "supplychain",
                "connected"],
}

# ② data_features：从列名/结构本身判断，与题面文字无关。
#    这是「换一道题也能判对类型」的关键 —— 之前全是空的。
#    匹配的是列名里的词（大小写不敏感的子串）。
ADD_FEAT = {
    "optimization": ["cost", "price", "profit", "yield", "capacity",
                      "budget", "revenue", "weight"],
    "multiobjective": ["cost", "price", "profit", "quality", "time",
                       "energy", "risk", "emission"],
    "prediction": ["date", "year", "month", "week", "day", "time",
                   "period", "quarter", "forecast", "future"],
    "evaluation": ["score", "rating", "rank", "quality", "index",
                   "grade", "level", "weight"],
    "regression": ["population", "revenue", "temperature", "pressure",
                   "population_", "size", "amount", "rate", "level"],
    "clustering": ["age", "income", "frequency", "segment", "spend",
                   "purchase", "membership", "category"],
    "mechanism": ["temperature", "pressure", "velocity", "flow", "heat",
                  "current", "concentration"],
    "simulation": ["replication", "seed", "round", "iteration", "trial",
                   "sim"],
    "network": ["node", "edge", "distance", "capacity", "origin",
                "destination", "route", "supplier", "plant", "warehouse"],
}

for kid, spec in d["kinds"].items():
    tr = list(spec.get("triggers") or [])
    have = {t.lower() for t in tr}
    for t in ADD_TRIG.get(kid, []):
        if t.lower() not in have:
            tr.append(t)
    spec["triggers"] = tr
    ft = list(spec.get("data_features") or [])
    havef = {f.lower() for f in ft}
    for f in ADD_FEAT.get(kid, []):
        if f.lower() not in havef:
            ft.append(f)
    spec["data_features"] = ft

d["version"] = 6
json.dump(d, open(P, "w", encoding="utf-8", newline="\n"),
          ensure_ascii=False, indent=1)
print("  triggers + data_features filled for %d kinds" % len(d["kinds"]))