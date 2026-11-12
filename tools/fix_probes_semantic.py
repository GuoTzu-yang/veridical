import json, os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "kb", "methods", "checks.json")
d = json.load(open(P, encoding="utf-8"))
k = d["kinds"]["network"]
k[0]["probes"] = ["algorithmic complexity", "time complexity",
                  "polynomial time", "np-hard", "o(n", "o(n log",
                  "asymptotic complexity"]
k[0]["note"] = ("model complexity (a goodness-of-fit notion) is NOT "
                "algorithmic complexity; the probe must say which")
k[1]["probes"] = ["optimality gap", "duality gap", "proven optimal",
                  "lower bound", "certificate", "optimal solution",
                  "not a heuristic"]
k[1]["note"] = ("'optimal design' means a good design, not a proof of "
                "optimality; the probe must say 'optimality'")
k[2]["probes"] = ["scalab", "large instance", "runtime", "wall-clock",
                  "instance size"]
k[2]["note"] = ("a sensitivity analysis is not a scale test; drop "
                "the generic word")
# evaluation 的 weight 也太宽：'weighted sum' 与权重来源无关
e = d["kinds"]["evaluation"]
for it in e:
    if it["name"].startswith("weight provenance"):
        it["probes"] = ["weight provenance", "entropy weight",
                        "ahp", "delphi", "weight sensitiv",
                        "weights are", "assigned weight"]
        it["note"] = ("a weighted sum is arithmetic, not a justification "
                      "of where the weights came from")
d["version"] = 3
json.dump(d, open(P, "w", encoding="utf-8", newline="\n"),
          ensure_ascii=False, indent=1)
print("  fixed network x3 + evaluation weight")