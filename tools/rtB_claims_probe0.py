# 只读：调用论文自己的 freeze.check_paper，看「每个数字都有出处」这句话的分母
import io, json, os, sys
root = r"C:\Users\21246\Documents\deepseek-harness\default-workspace\model1-arch"
os.chdir(root); sys.path.insert(0, root)
import freeze
tex = io.open(os.path.join(root, "out", "final", "paper.tex"), encoding="utf-8").read()
fz = json.load(io.open(os.path.join(root, "out", "final", "冻结数字.json"), encoding="utf-8"))
r = freeze.check_paper(tex, fz)
for k in ("ok","reasons","n_numbers","n_traced","untraced_ratio","untraced",
          "high_precision_untraced","n_int_not_judged","few_numbers",
          "frozen_has_source","frozen_self_proving","n_from_data"):
    print(k, "=", r.get(k))
print()
print("frozen items:", len(fz["items"]))
# 冻结表里有多少条是**脚本里手打的常数**（不是从工件展平出来的）
hand = [it for it in fz["items"] if str(it["path"]).startswith("derived.")]
print("derived items:", len(hand))
for it in hand:
    if it["path"] in ("derived.dpi_floor","derived.historic_claim_low",
                      "derived.historic_claim_high","derived.name_sha256_bits",
                      "derived.alpha","derived.r_crit_84","derived.nflis_table_rows"):
        print("  HAND-TYPED:", it)