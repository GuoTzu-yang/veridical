import os
import sys
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import orchestrate

st = orchestrate.run_loop("out/data/scope_test.xlsx",
                          orchestrate.rule_propose,
                          max_rounds=2, routes_per_round=3,
                          budget_min=5.0)
print(orchestrate.report(st)[:2000])