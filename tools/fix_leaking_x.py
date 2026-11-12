"""第 4 轮：修掉 4 处「把响应的组成部分当自变量」的配置错误，并重跑这 4 题。

依据（gate.chk_leakage 在正确的表上跑出来的）：
  clustering        消费金额 → 客户价值  +0.995   ← 消费金额是客户价值的组成部分
  mcm2020c          total_votes → helpful_votes +0.997
  review_microwave  helpful_votes → total_votes +0.997
  review_pacifier   helpful_votes → total_votes +0.985

修法：从 x 里删掉那一列，并按可用列补齐有意义的预测变量。
  clustering 剩 购买频次/最近购买天数，补 品类数/年龄/会员等级（RFM + 属性）
  mcm2020c   删 total_votes，保留 star_rating/review_*_len/body_len
  review_*   只剩 star_rating 可用 —— 弱就弱，不编列

旧产物已备份到 out/runs_backup_r4/。
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNS = os.path.join(HERE, "runs.json")

NEW_X = {
    "clustering": "购买频次,最近购买天数,品类数,年龄,会员等级",
    "mcm2020c": "star_rating,review_headline_len,body_len",
    "review_microwave": "star_rating",
    "review_pacifier": "star_rating",
}


def main():
    cfg = json.load(io.open(RUNS, encoding="utf-8"))
    changed = []
    for k, x in NEW_X.items():
        if k not in cfg:
            print("MISS: %s 不在 runs.json" % k)
            return 2
        old = cfg[k].get("x")
        if old == x:
            print("SKIP %s 已是新值" % k)
            continue
        cfg[k]["x"] = x
        changed.append((k, old, x))
    if changed:
        io.open(RUNS, "w", encoding="utf-8").write(
            json.dumps(cfg, ensure_ascii=False, indent=2) + "\n")
        for k, old, new in changed:
            print("OK %-18s\n     old x = %s\n     new x = %s" % (k, old, new))
    else:
        print("NO CHANGE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
