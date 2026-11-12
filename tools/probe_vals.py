import os
import warnings
warnings.filterwarnings("ignore")
import pandas as pd
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src = os.path.join(HERE, "external", "github", "li1408__MathModelHub",
                   "competitions", "2026_MCM_Problem_C_Data.csv")
d = pd.read_csv(src)
print("  赛季: %d 个（%d - %d），每季选手数 %d-%d"
      % (d.season.nunique(), d.season.min(), d.season.max(),
         d.groupby("season").size().min(), d.groupby("season").size().max()))
print()
print("  results 取值:", d.results.value_counts().to_dict())
print()
print("  industry 取值（%d 类）:" % d.celebrity_industry.nunique())
for k, v in d.celebrity_industry.value_counts().items():
    print("    %-24s %d" % (str(k)[:24], v))
print()
print("  pro dancer 数: %d" % d.ballroom_partner.nunique())
print("  age: %d - %d，均值 %.1f" % (d.celebrity_age_during_season.min(),
                                    d.celebrity_age_during_season.max(),
                                    d.celebrity_age_during_season.mean()))
print()
print("  placement 缺失: %d" % d.placement.isna().sum())
print("  有名次的行 placement 范围: %s - %s"
      % (d.placement.min(), d.placement.max()))