import os
import warnings

warnings.filterwarnings("ignore")
import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.path.join(HERE, "external", "github",
                    "usail-hkust__LLM-MM-Agent", "LLM-MM-Agent-main",
                    "MMBench", "dataset", "2006_C")
OUT = os.path.join(HERE, "out", "data")
os.makedirs(OUT, exist_ok=True)

pop = pd.read_excel(os.path.join(BASE, "population_data.xls"))
life = pd.read_excel(os.path.join(BASE, "life_expectancy_0_data.xls"))

pop = pop.rename(columns={c: "pop_" + str(c) for c in pop.columns})
life = life.rename(columns={c: "life_" + str(c) for c in life.columns})
key = "pop_Country code"
life_key = "life_Country code"
m = pop.merge(life, left_on=key, right_on=life_key, how="inner")
print("  合并后 %d 行 x %d 列" % m.shape)

cols = (["pop_Major area, region", "pop_2000", "pop_2005",
         "life_1990-1995", "life_2000-2005", "life_2005-2010"]
        + ["pop_1950", "pop_1980", "pop_1990"])
cols = [c for c in cols if c in m.columns]
out = m[cols].rename(columns={
    "pop_Major area, region": "region",
    "pop_2000": "pop2000", "pop_2005": "pop2005",
    "life_1990-1995": "life1995", "life_2000-2005": "life2005",
    "life_2005-2010": "life2010",
    "pop_1950": "pop1950", "pop_1980": "pop1980", "pop_1990": "pop1990"})
p = os.path.join(OUT, "icm2006c.xlsx")
out.to_excel(p, index=False, sheet_name="Sheet1")
print("  写出 %s" % os.path.basename(p))
print("  列: %s" % list(out.columns))
print(out.head(4).to_string())