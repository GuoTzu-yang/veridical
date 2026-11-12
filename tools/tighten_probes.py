import json, os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "kb", "methods", "checks.json")
d = json.load(open(P, encoding="utf-8"))
e = d["kinds"]["evaluation"]
for it in e:
    if it["name"].startswith("normalisation"):
        it["probes"] = ["normalised indicator", "normalisation of the",
                        "normalised value", "min-max", "benefit indicator",
                        "cost indicator", "direction of the indicator"]
        it["note"] = ("a 'normalised gap' is a regret measure, not indicator "
                      "normalisation; 'direction of association' is not "
                      "indicator direction")
    if it["name"].startswith("agreement"):
        it["probes"] = ["rank correlation", "spearman", "kendall",
                        "two methods agree", "methods agree",
                        "ranking agree", "consistency check between"]
        it["note"] = ("'the relation stays consistent with theory' is not "
                      "agreement between two evaluation methods")
# prediction 的 residual 也收紧：热沉题的残差诊断不该算预测题的
p = d["kinds"]["prediction"]
for it in p:
    if it["name"].startswith("residual diagnostics"):
        it["probes"] = ["residual autocorrelation", "ljung", "durbin",
                        "acf of the residual", "residuals are white"]
        it["note"] = ("plain residual diagnostics belong to regression; "
                      "this check is about structure *left in* them over time")
d["version"] = 4
json.dump(d, open(P, "w", encoding="utf-8", newline="\n"),
          ensure_ascii=False, indent=1)
print("  tightened evaluation x2 + prediction x1")