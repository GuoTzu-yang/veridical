import os
import warnings
warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
L = pd.read_excel(os.path.join(HERE, "out", "data", "dwts2026c_long.xlsx"))
W = pd.read_excel(os.path.join(HERE, "out", "data", "dwts2026c.xlsx"))

# 每人：淘汰周（0=决赛选手）与最终名次
info = W[["celebrity_name", "season", "eliminated_week", "placement",
           "withdrew", "last_week"]].copy()
info["exit_week"] = np.where(info.eliminated_week > 0, info.eliminated_week,
                             info.last_week)
info["exit_order"] = 0
# 每季内：按 exit_week 排序，同周用 placement 排
info["exit_order"] = info.groupby("season")["exit_week"].rank(
    ascending=True, method="first").astype(int)
# 同一周退出的多个（Withdrew）按 placement 靠前
info.loc[info.eliminated_week == 0, "exit_order"] = (
    info[info.eliminated_week == 0].groupby("season")["placement"]
    .rank(ascending=True, method="first").astype(int)
    + info[info.eliminated_week == 0].groupby("season")["exit_week"]
    .transform("max") - info[info.eliminated_week == 0].groupby("season")["exit_week"]
    .transform("max"))
info.to_excel(os.path.join(HERE, "out", "data", "dwts_exit.xlsx"), index=False)
print("  每人退出序（每季内）已算")
print("  校验：季 1 前 6 名的 exit_week / placement")
s1 = info[info.season == 1].sort_values("placement")[
    ["celebrity_name", "eliminated_week", "placement", "exit_week", "exit_order"]]
print(s1.to_string(index=False))