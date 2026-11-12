import json, os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ov = {
 "This report models chemical reactor yiel":
   "We model this reactor as a two-input response surface and hold every "
   "claim to one standard: error measured on data the fit never saw.",
 "Four candidate model structures -- linea":
   "Six candidate structures were compared under repeated k-fold. The linear "
   "and quadratic forms are separated by less than one tenth of a percent, "
   "so the data do not justify the extra curvature.",
}
p = os.path.join(HERE, "out", "ov.json")
json.dump(ov, open(p, "w", encoding="utf-8", newline="\n"),
          ensure_ascii=False, indent=1)
print("  写出 %s（%d 段）" % (os.path.basename(p), len(ov)))