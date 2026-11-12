# 探针3：有没有把「未见反例」写成「已证明」 —— 只读，跑论文自己的 freeze.check_paper
import io, json, os, sys
root = r"C:\Users\21246\Documents\deepseek-harness\default-workspace\model1-arch"
os.chdir(root); sys.path.insert(0, root)
import freeze, verify
tex = io.open(os.path.join(root, "out", "final", "paper.tex"), encoding="utf-8").read()
fz = json.load(io.open(os.path.join(root, "out", "final", "冻结数字.json"), encoding="utf-8"))
r = freeze.check_paper(tex, fz)
print("### A. 论文自我核对的真实分母")
for k in ("ok", "n_numbers", "n_traced", "untraced_ratio", "untraced",
          "high_precision_untraced", "n_int_not_judged", "n_from_data"):
    print(f"  {k} = {r[k]}")
tot = r["n_numbers"] + r["n_int_not_judged"]
print(f"  被判的带小数 token = {r['n_numbers']}；被判之外被跳过的整数 token = {r['n_int_not_judged']}")
print(f"  全体数字 token ≈ {tot}；「每个数字都被核过」实际覆盖 {r['n_numbers']/tot:.1%}")

print()
print("### B. 判决规则里整数为什么不可能失败（源码原文）")
src = io.open(os.path.join(root, "freeze.py"), encoding="utf-8").read().splitlines()
for i, ln in enumerate(src, 1):
    if 'toks = [t for t, _line in _all if "." in t]' in ln or "n_int_skipped" in ln or "n_int_not_judged" in ln:
        print(f"  freeze.py:{i}: {ln.strip()}")

print()
print("### C. 37 个被判 token 分别被哪条冻结项「接住」")
items = fz["items"]
vals = [(it["path"], it["value"]) for it in items]
all_toks = verify.extract_numbers(tex, skip_meta=False)
dec_toks = [t for t, _l in all_toks if "." in t]
seen = set()
hand_paths = {"derived.dpi_floor", "derived.historic_claim_low", "derived.historic_claim_high",
              "derived.name_sha256_bits", "derived.alpha", "derived.r_crit_84",
              "derived.nflis_table_rows"}
for tok in dec_toks:
    try:
        v = float(tok)
    except ValueError:
        continue
    dec = freeze._decimals(tok)
    key = (round(v, 6), dec)
    if key in seen:
        continue
    seen.add(key)
    matched = [p for p, f in vals if freeze._match_written(v, dec, [f])]
    hand = [p for p in matched if p in hand_paths]
    print(f"  {tok:<12} dec={dec:<3} 命中={len(matched):<3} 手打常数命中={hand}")