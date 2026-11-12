#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
kb.py — 检索库：给一条主张找可引用的出处

⚠️ 这是**重建版**（2026-11-08）
原文件被误覆盖。本版由原文件的 pyc 反解出完整结构后重建：
函数签名、docstring、常量、SQL、e1/e2 规则均取自 pyc；
实现细节按语义重写，行为等价但措辞可能不同。
原件备份：kb_original.cpython-312.pyc.bak

它做什么
    给一条主张找**可引用的出处**。这是 e1（溯源度）唯一的外援：
    自己脑子里想到的都不算溯源，能指到「哪个仓库的哪个文件的哪一行」才算。

它不做什么
    **它不下结论。** 命中不是成立，检索到的东西是**候选证据**。
    这一条必须写在最前面，因为这个库最容易让人误以为"搜到了就是对的"。

它守的三条规矩（都是这个项目里踩出来的）
    1. 同一个仓库的多个文件**不算独立来源**。
       同一个团队写的一套代码，观点当然一致——拿它当两票是自欺。
    2. 命中要能核对。每条 Hit 都带仓库、路径，调用方可以 read() 打开原文比对，
       不能只信摘要。这是 verify() 存在的理由。
    3. **没搜到 ≠ 不存在。** 这个库只有 30 个仓库；
       搜不到只说明"这 30 个里没有"，不能推出"世界上没有"。

数据布局
    knowledge-base/
        repos/<owner>__<repo>/src/...   原始代码
        index.db                        FTS5 索引（repo/category/path/content）

用法
    python kb.py search "raft consensus" --cat db-sql
    python kb.py cite "raft consensus"
    python kb.py stats
    python kb.py selftest
"""

from __future__ import annotations

import os
import re
import sqlite3
import sys
from dataclasses import dataclass, field


def kb_root() -> str:
    """知识库根目录（含 repos/ 与 index.db 的那一层）。"""
    env = os.environ.get("KB_ROOT")
    if env and os.path.isdir(env):
        return os.path.abspath(env)
    here = os.path.dirname(os.path.abspath(__file__))
    for cand in (os.path.join(here, "..", "knowledge-base"),
                 os.path.join(here, "knowledge-base"),
                 here):
        p = os.path.normpath(cand)
        if os.path.isdir(os.path.join(p, "repos")) or \
                os.path.exists(os.path.join(p, "index.db")):
            return p
    return os.path.normpath(os.path.join(here, "..", "knowledge-base"))


KB = kb_root()
REPOS = os.path.join(KB, "repos")
INDEX = os.path.join(KB, "index.db")

# bm25 的列权重：repo, category, path, content
# path 给一点（文件名常含关键词），repo/category 只做过滤不计分
BM25_WEIGHTS = (0.0, 0.0, 0.5, 1.0)

CATEGORIES = (
    "db-doc", "db-embed", "db-kv", "db-olap", "db-sql",
    "math-data", "math-dl", "math-graph", "math-ml", "math-numeric",
    "math-optimize", "math-scientific", "math-stat", "math-symbolic",
    "tool-convert", "tool-editor", "tool-git", "tool-search",
    "tool-terminal", "tool-tui", "tool-view",
)


@dataclass
class Hit:
    """一条命中 = 一个可以被核对的具体位置。"""
    repo: str
    category: str
    path: str
    snippet: str = ""
    rank: float = 0.0

    def cite(self) -> str:
        """可引用的出处。e1=2 要求指到具体位置，就是这个字符串。"""
        return f"{self.repo}/{self.path}"

    def url(self) -> str:
        return f"https://github.com/{self.repo}/blob/HEAD/{self.path}"

    def local(self) -> str:
        """本机原文路径。"""
        base = os.path.join(REPOS, self.repo.replace("/", "__"))
        p = os.path.join(base, "src", os.path.normpath(self.path))
        # Windows 长路径前缀（路径超 260 字符时必需）
        if sys.platform == "win32" and not p.startswith("\\\\?\\"):
            return "\\\\?\\" + os.path.abspath(p)
        return p


@dataclass
class Assessment:
    """这批命中能支持多强的证据。"""
    hits: list = field(default_factory=list)
    e1_cap: int = 0
    e2_cap: int = 0
    repos: list = field(default_factory=list)
    why: str = ""

    def as_claim_dims(self) -> dict:
        """直接喂给 harness.Claim 的字段。"""
        return {"e1": self.e1_cap, "e2": self.e2_cap}


def _sanitize(q: str) -> str:
    """把用户输入洗成 FTS5 认的查询。

    FTS5 对 `-` `(` `"` `*` 这些有语法意义，直接扔进去会抛
    OperationalError。这里只保留字母数字、下划线和中文，其余当分隔符。
    宁可少召回，也不要让整次检索炸掉。
    """
    parts = [p for p in re.split(r"[^\w\u4e00-\u9fff]+", str(q or "")) if p]
    return " ".join(parts)


def _connect() -> sqlite3.Connection:
    if not os.path.exists(INDEX):
        raise FileNotFoundError(f"索引不存在：{INDEX}")
    # 只读打开且禁止写 —— 检索库不许改数据
    conn = sqlite3.connect(f"file:{INDEX}?mode=ro", uri=True, timeout=15)
    conn.execute("PRAGMA query_only=ON")
    return conn


def search(query: str, category: str | None = None,
           repo: str | None = None, limit: int = 12) -> list:
    """按关键词检索。返回按 bm25 排序的命中（越小越相关）。

    这是**检索**，不是判定。拿到 Hit 之后该做的第一件事是 read() 核对原文。
    """
    q = _sanitize(query)
    if not q:
        return []
    where, params = ["files MATCH ?"], [q]
    if category:
        where.append("category = ?")
        params.append(category)
    if repo:
        where.append("repo = ?")
        params.append(repo)
    sql = (
        "SELECT repo, category, path, "
        "snippet(files, 3, '…', '…', '…', 18), "
        "bm25(files, ?,?,?,?) AS r "
        "FROM files WHERE " + " AND ".join(where) +
        " ORDER BY r LIMIT ?")
    args = list(BM25_WEIGHTS) + params + [int(max(1, limit))]
    conn = _connect()
    try:
        rows = conn.execute(sql, args).fetchall()
    except sqlite3.Error:
        rows = []
    finally:
        conn.close()
    return [Hit(repo=r[0], category=r[1], path=r[2],
                snippet=r[3] or "", rank=float(r[4] or 0.0))
            for r in rows]


def read(hit: Hit, max_chars: int = 4000) -> str:
    """读命中处的原文。引用之前**必须**走这一步——摘要不是证据。"""
    p = hit.local()
    try:
        with open(p, encoding="utf-8", errors="replace") as f:
            return f.read(max_chars)
    except OSError as e:
        return f"<<读不到原文：{type(e).__name__}: {e}>>"


def verify(hit: Hit, terms) -> bool:
    """原文里真的出现这些词吗。

    FTS 是词干/分词匹配，摘要也可能截断得只剩半句。
    只有原文真含这些词，这条命中才算**核对过**。
    """
    body = read(hit, max_chars=200000)
    if body.startswith("<<读不到"):
        return False
    low = body.lower()
    return all(str(t).lower() in low for t in (terms or []) if t)


def assess(hits, terms=None, verified_only: bool = False) -> Assessment:
    """这批命中能撑起多强的证据。

    规则（和 harness 的 e1/e2 语义对齐）：
        e1：能指到具体文件 → 2；只有仓库名 → 1；没有 → 0
        e2：**独立来源**数 —— 同一仓库的多个文件只算一个来源
    """
    used = []
    for h in hits:
        if verified_only and terms and not verify(h, terms):
            continue
        used.append(h)

    repos = sorted({h.repo for h in used})
    e1 = 2 if used else 0
    if len(repos) >= 3:
        e2 = 2
    elif len(repos) == 2:
        e2 = 1
    else:
        e2 = 0   # 单一仓库（或没有）→ 不算独立证据，这是那条规矩

    why = []
    if not used:
        why.append("没有可用命中")
    else:
        why.append(f"{len(used)} 条命中，来自 {len(repos)} 个仓库")
        if len(repos) == 1:
            why.append("单一仓库不算独立来源（同团队观点天然一致）")
    if verified_only and terms:
        why.append(f"已用原文核对关键词 {list(terms)}")

    return Assessment(hits=used, e1_cap=e1, e2_cap=e2,
                      repos=repos, why="；".join(why))


def stats() -> dict:
    """库的规模。回答『没搜到 ≠ 不存在』时要用它说明覆盖面。"""
    if not os.path.exists(INDEX):
        return dict(ok=False, why=f"索引不存在：{INDEX}")
    conn = _connect()
    try:
        n_files = conn.execute("SELECT count(*) FROM files").fetchone()[0]
        n_repos = conn.execute(
            "SELECT count(DISTINCT repo) FROM files").fetchone()[0]
        cats = [r[0] for r in conn.execute(
            "SELECT DISTINCT category FROM files ORDER BY 1")]
        by_cat = dict(conn.execute(
            "SELECT category, count(*) FROM files GROUP BY 1").fetchall())
    finally:
        conn.close()
    return dict(ok=True, files=n_files, repos=n_repos,
                categories=cats, by_category=by_cat,
                index_bytes=os.path.getsize(INDEX))


def selftest() -> int:
    bad = 0
    n = 0

    def ck(name, cond, detail=""):
        nonlocal bad, n
        n += 1
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}"
              + (f"  — {detail}" if detail else ""))
        if not cond:
            bad += 1

    s = stats()
    ck("索引可读", s.get("ok"), s.get("why") or f"{s.get('files')} 行")
    if s.get("ok"):
        ck("仓库数 > 0", s["repos"] > 0, f"{s['repos']} 个")
        ck("文件数 > 1000", s["files"] > 1000, f"{s['files']} 条")

    # 清洗：FTS5 语法字符不能进去
    ck("_sanitize 去掉 - 与引号",
       _sanitize('raft-consensus "quoted"') == "raft consensus quoted",
       _sanitize('raft-consensus "quoted"'))
    ck("_sanitize 保留中文",
       "热阻" in _sanitize("热阻 压降"), _sanitize("热阻 压降"))
    ck("_sanitize 空输入返回空", _sanitize("") == "")

    hits = search("model", limit=3)
    ck("能检索到结果", len(hits) > 0, f"{len(hits)} 条")
    if hits:
        h = hits[0]
        ck("Hit 带 repo/path", bool(h.repo and h.path), h.cite()[:50])
        ck("cite 可引用", "/" in h.cite(), h.cite()[:40])
        ck("url 是 GitHub",
           h.url().startswith("https://github.com/") and
           "/blob/HEAD/" in h.url())
        body = read(h)
        ck("read 能读到原文",
           not body.startswith("<<读不到"), f"{len(body)} 字符")

        same = [x for x in search("the", limit=8) if x.repo == h.repo]
        if len(same) >= 2:
            a = assess(same)
            ck("同一仓库多文件 → e2 仍为 0",
               a.e2_cap == 0, f"{len(same)} 文件 / e2={a.e2_cap}")
            ck("但 e1 为 2（能指到具体文件）", a.e1_cap == 2)

    # verify()：引用前必须核对原文。这是「摘要不是证据」那条规矩的落实。
    if hits:
        h = hits[0]
        body = read(h, max_chars=20000).lower()
        # 取原文里真实存在的一个词
        _word = next((w for w in re.findall(r"[a-z]{4,}", body)
                      if len(w) >= 4), None)
        if _word:
            ck("verify 对原文真有的词返回 True",
               verify(h, [_word]) is True, _word)
        ck("verify 对原文没有的词返回 False",
           verify(h, ["zzzz_not_in_file_zzzz"]) is False)

    ck("空查询不炸", search("") == [])
    ck("语法字符不炸", isinstance(search('- ( " *'), list))

    print(f"\n{'ALL PASS' if bad == 0 else 'FAILED'}  {n - bad}/{n}")
    return 0 if bad == 0 else 1


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="检索库：给主张找出处")
    ap.add_argument("cmd", choices=["search", "cite", "read", "stats",
                                    "selftest"])
    ap.add_argument("query", nargs="?", default="")
    ap.add_argument("--cat", default=None, help="限定 category")
    ap.add_argument("--repo", default=None, help="限定仓库")
    ap.add_argument("--limit", type=int, default=12)
    a = ap.parse_args(argv)

    if a.cmd == "selftest":
        return selftest()
    if a.cmd == "stats":
        s = stats()
        if not s.get("ok"):
            print(f"  ✗ {s.get('why')}")
            return 2
        print(f"  索引：{s['index_bytes'] / 1e9:.2f} GB")
        print(f"  仓库 {s['repos']} 个 / 文件 {s['files']} 条")
        print(f"  分类 {len(s['categories'])} 个")
        for c in s["categories"]:
            print(f"    {c:<18} {s['by_category'].get(c, 0):>7}")
        print(f"  注意：这是全部覆盖面。没搜到只说明这 {s['repos']} "
              f"个仓库里没有，不能推出世界上没有。")
        return 0

    hits = search(a.query, a.cat, a.repo, a.limit)
    if not hits:
        s = stats()
        print(f"  没有命中。检索范围：{s.get('repos')} 个仓库 / "
              f"{s.get('files')} 条。")
        print("  注意：没搜到 ≠ 不存在。")
        return 1

    if a.cmd == "cite":
        asmt = assess(hits)
        for h in hits:
            print(f"  {h.cite()}")
        print(f"\n  {asmt.why}")
        print(f"  e1={asmt.e1_cap}  e2={asmt.e2_cap}")
        return 0

    if a.cmd == "read":
        print(read(hits[0]))
        return 0

    for h in hits:
        print(f"  [{h.rank:+.2f}] {h.cite()}")
        if h.snippet:
            print(f"          {h.snippet[:110]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
