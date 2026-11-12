"""一次性核对：schema.build() 的命令集 vs argparse 的 choices。

只在开发时手动跑，不属于交付物。
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import schema  # noqa: E402

src = io.open(os.path.join(HERE, "mmkit.py"), encoding="utf-8").read()
m = re.search(r'ap\.add_argument\("cmd".*?choices=\[(.*?)\]', src, re.S)
choices = sorted(set(re.findall(r'"([^"]+)"', m.group(1))))

sc = schema.build()
names = sorted(sc["commands"])

print("schema 命令数:", len(names))
print("argparse choices 数:", len(choices))
print("只在 choices 不在 schema:", sorted(set(choices) - set(names)))
print("只在 schema 不在 choices:", sorted(set(names) - set(choices)))
print("含 fuzzy:", "fuzzy" in names)
print("含 cand/surface/formula:",
      [n for n in names if n in ("cand", "surface", "formula")])
print()
print("全部:", names)
