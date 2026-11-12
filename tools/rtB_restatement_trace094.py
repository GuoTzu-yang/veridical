# -*- coding: utf-8 -*-
"""restatement 板 · 只读探针 2：0.94 到底"溯源"到了什么。

只读 out/final/ 下的 json+csv，只打印。
"""
from __future__ import annotations

import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import verify  # noqa: E402

OUT = os.path.join(ROOT, "out", "final")


def rd(p):
    with io.open(p, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def main():
    tex = rd(os.path.join(OUT, "paper.tex"))
    sec = "\n".join(tex.splitlines()[74:170])
    toks = verify.extract_numbers(sec, skip_meta=True)
    outs = verify.load_outputs(OUT)

    print("=" * 72)
    print("[A] 本板候选数字：%s" % toks)
    print("[B] 溯源池文件数（json+csv，已剔自证 json）：%d" % len(outs))

    for tk, _ln in toks:
        v = float(tk)
        dec = verify._written_decimals(tk)
        print("\n[C] token=%s 精度=%d 判定式 = round(pool, %d) == %s" % (tk, dec, dec, tk))

        # 复刻 verify.trace 的匹配，并记录命中的那个池值
        hits = []
        pool = verify.collect_output_numbers(outs)
        print("    池内数值总数 %d" % len(pool))
        for p in pool:
            if verify._near(v, p, dec):
                hits.append(p)
        uniq = sorted(set(hits))
        print("    命中 %d 次 / %d 个不同值：%s" % (len(hits), len(uniq), uniq[:12]))

        # 命中的值来自哪个文件（逐文件定位）
        for name in sorted(os.listdir(OUT)):
            p = os.path.join(OUT, name)
            if not os.path.isfile(p):
                continue
            if name.endswith(".json"):
                try:
                    import json
                    obj = json.loads(rd(p))
                except Exception:
                    continue
                if verify._looks_self_proved(obj):
                    continue
                nums = verify.collect_output_numbers(obj)
            elif name.endswith(".csv"):
                nums = verify.collect_output_numbers(rd(p))
            else:
                continue
            mine = [x for x in nums if verify._near(v, x, dec)]
            if mine:
                print("    来源文件 %-22s 命中 %d 个，样本值 %s"
                      % (name, len(mine), sorted(set(mine))[:6]))

    print("\n" + "=" * 72)
    print("[D] 冻结表里有没有 0.94 这一项（items 全扫）")
    import json
    fz = json.loads(rd(os.path.join(OUT, "冻结数字.json")))
    cnt = 0
    for it in fz.get("items") or []:
        vv = it.get("value")
        if isinstance(vv, (int, float)) and abs(float(vv) - 0.94) < 1e-12:
            print("    命中: %s" % it)
            cnt += 1
    print("    精确等于 0.94 的冻结项: %d" % cnt)


if __name__ == "__main__":
    main()
