import io, os
root = r"C:\Users\21246\Documents\deepseek-harness\default-workspace\model1-arch"
checks = [
    ("out/final/paper.tex", "frozen table"),
    ("out/final/paper.tex", "from nothing else"),
    ("out/final/paper.tex", "carry most of the length"),
    ("tools/make_final_figs2.py", "if not S"),
    ("tools/freeze_paper_numbers.py", "derived.r_crit_84"),
    ("out/final/data2.json", "paper_bytes"),
    ("out/final/data2.json", "\"sections\": []"),
    ("freeze.py", "n_int_not_judged"),
]
for rel, mark in checks:
    p = os.path.join(root, rel)
    t = io.open(p, encoding="utf-8").read()
    print(f"{rel:<38} {mark!r:<28} exists={mark in t} count={t.count(mark)}")