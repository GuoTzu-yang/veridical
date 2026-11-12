import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import kind

CASES = [
    ("ICM2006C", "population growth and life expectancy across countries"),
    ("MCM2020C", "which review features drive helpfulness votes"),
    ("heat sink", "heat sink"),
    ("网络流", "network flow optimisation of a transport network"),
    ("预测", "forecast monthly demand for the next quarter"),
]
for n, p in CASES:
    r = kind.detect(p, [], None)
    print("  %-10s %-52s -> %s   scores=%s"
          % (n, p[:52], r["kinds"], r["scores"]))