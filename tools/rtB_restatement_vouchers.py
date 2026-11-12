# -*- coding: utf-8 -*-
"""restatement 板 · 只读探针 5：vouching 值 93.9 / 94.0 / 94.1 的来处。

只读 out/final/*.json；只打印。
"""
from __future__ import annotations

import io
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "out", "final")


def rd(p):
    with io.open(p, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def walk(o, path=""):
    if isinstance(o, bool):
        return
    if isinstance(o, dict):
        for k, v in o.items():
            yield from walk(v, "%s.%s" % (path, k) if path else str(k))
    elif isinstance(o, (list, tuple)):
        for i, v in enumerate(o):
            yield from walk(v, "%s[%d]" % (path, i))
    elif isinstance(o, (int, float)):
        yield path, float(o)
    elif isinstance(o, str):
        pass


def main():
    targets = (93.9, 94.0, 94.1)
    print("=" * 72)
    print("[A] 冻结数字.json 里值为 93.9 / 94.0 / 94.1 的条目（就是给 0.94 背书的那几个）")
    fz = json.loads(rd(os.path.join(OUT, "冻结数字.json")))
    for it in fz.get("items") or []:
        v = it.get("value")
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            if any(abs(float(v) - t) < 1e-9 for t in targets):
                print("   %-42s = %s" % (it.get("path"), v))

    print("\n[B] data.json / ablation.json / meta_eval.json / redteam.json 里命中的路径")
    for name in ("data.json", "ablation.json", "meta_eval.json", "redteam.json"):
        p = os.path.join(OUT, name)
        if not os.path.exists(p):
            continue
        try:
            obj = json.loads(rd(p))
        except Exception as e:
            print("   %s 解析失败 %r" % (name, e))
            continue
        hits = [(k, v) for k, v in walk(obj)
                if any(abs(v - t) < 1e-9 for t in targets)]
        print("   --- %s: %d 个" % (name, len(hits)))
        for k, v in hits[:8]:
            print("        %-46s = %s" % (k, v))


if __name__ == "__main__":
    main()
