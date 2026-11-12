import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import kind

CASES = [
    ("ICM2006C", "population growth and life expectancy across countries",
     ["pop1950", "pop1980", "pop1990", "pop2000", "pop2005",
      "life1995", "life2005", "life2010"], "pop2005"),
    ("MCM2020C", "which review features drive helpfulness votes",
     ["star_rating", "helpful_votes", "total_votes",
      "review_headline_len", "body_len", "product_parent"], "helpful_votes"),
    ("heatmap", "heat sink", ["width", "depth", "rows", "thermal"], "thermal"),
    ("forecast", "forecast monthly demand",
     ["date", "month", "sales", "ad_spend"], "sales"),
    ("cluster", "customer segmentation",
     ["age", "income", "frequency", "spend"], "spend"),
]
for n, p, cols, y in CASES:
    r = kind.detect(p, cols, y)
    print("  %-10s -> %-34s scores=%s"
          % (n, str(r["kinds"])[:34], r["scores"]))