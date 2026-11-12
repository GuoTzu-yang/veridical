import os
import warnings
warnings.filterwarnings("ignore")
import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.path.join(HERE, "external", "github",
                    "usail-hkust__LLM-MM-Agent", "LLM-MM-Agent-main",
                    "MMBench", "dataset", "2020_C")
OUT = os.path.join(HERE, "out", "data")
d = pd.read_csv(os.path.join(BASE, "hair_dryer.tsv"), sep="\t",
                low_memory=False, encoding_errors="replace")
# 2020 C 的核心问题：一条评论的「有用票」与评分的关系。
# 数值列：star_rating / helpful_votes / total_votes / customer_id
keep = ["star_rating", "helpful_votes", "total_votes",
        "review_headline_len", "body_len", "product_parent"]
d["review_headline_len"] = d["review_headline"].fillna("").astype(str).str.len()
d["body_len"] = d["review_body"].fillna("").astype(str).str.len()
out = d[keep].copy()
# customer_id 是标识符，降采样到合理规模（1.1 万行 × 一次回归太慢）
out = out.iloc[::7].reset_index(drop=True)
p = os.path.join(OUT, "mcm2020c.xlsx")
out.to_excel(p, index=False, sheet_name="Sheet1")
print("  写出 %s: %d 行 x %d 列" % (os.path.basename(p), len(out), out.shape[1]))
print("  列: %s" % list(out.columns))
print(out.head(3).to_string())