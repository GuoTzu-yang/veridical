import os, sys
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import mm
cand = [x for x in dir(mm) if "corr" in x.lower() or "partial" in x.lower()]
print("  mm 里带 corr/partial 的:", cand)