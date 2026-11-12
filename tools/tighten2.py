import json, os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "kb", "methods", "checks.json")
d = json.load(open(P, encoding="utf-8"))

# 1) simulation 的 randomness：删掉通用的 random，seed 已足够
for it in d["kinds"]["simulation"]:
    if it["name"].startswith("randomness"):
        it["probes"] = ["random seed", "seeds were", "seed the",
                        "stochastic simulation", "monte carlo"]
        it["note"] = ("the bare word 'random' appears in any paper that "
                      "mentions randomness at all; require the seed")

# 2) optimization 的 local-optimum：删掉通用的 global
for it in d["kinds"]["optimization"]:
    if it["name"].startswith("local-optimum"):
        it["probes"] = ["multi-start", "multiple starting", "restart",
                        "local optimum", "global optimum", "global minimum"]
        it["note"] = ("'global' alone matches 'global market'; require the "
                      "optimisation sense")

# 3) multiobjective 的 coverage：收紧到前沿语境
for it in d["kinds"]["multiobjective"]:
    if it["name"].startswith("coverage"):
        it["probes"] = ["hypervolume", "non-dominated", "pareto front",
                        "spread of the front", "front coverage",
                        "coverage of the front"]
        it["note"] = ("'coverage of the literature' is not front coverage")

d["version"] = 5
json.dump(d, open(P, "w", encoding="utf-8", newline="\n"),
          ensure_ascii=False, indent=1)
print("  tightened: random / global / coverage")