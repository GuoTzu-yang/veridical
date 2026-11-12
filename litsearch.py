"""litsearch.py —— 文献检索 + 多源核验 + 绑定（第 116 轮）。

为什么不是「装个 MCP 就行了」
----------------------------
本机实测（第 116 轮）：Crossref 200、arXiv 200；OpenAlex 与 Semantic Scholar
返回 429（匿名被限流）。所以可用的组合是 Crossref + arXiv，不需要 key。

但「搜到有用的文献」不是检索问题，是**过滤与绑定**问题。一条文献只有同时满足
四条才算「有用」：

  ① 真     —— DOI 能解析，或两条以上独立源的标题/年份一致；
  ② 相关   —— 命中查询词且标题里出现主题词（下面有判据）；
  ③ 被用   —— 在正文里被 \\cite 过，且不是凑数（同一段里连甩 3 条以上没有
              具体主张的，记为 decoration）；
  ④ 可追   —— 每条 \\bibitem 绑定一条已核验记录（DOI 或 arXiv id）。

这就是「每个数字必须绑定冻结表 key」的文献版：不信任任何未绑定外部标识符的
声明。`check` 就是那条硬检查，`search` 只是入口。

用法
----
  python litsearch.py search "provenance of machine-generated text"
  python litsearch.py check out/final          # 核验论文里全部 bibitem
  python litsearch.py selftest                 # 离线自检（不联网）
"""
import io
import json
import os
import re
import sys
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
UA = "model1-litsearch/1.0 (mailto:noreply@example.com)"
CACHE = os.path.join(HERE, "out", "lit_cache.json")


# ── HTTP ───────────────────────────────────────────────────────────
def _get(url: str, timeout: int = 25):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def _norm(s: str) -> str:
    """归一化标题：先去 LaTeX 数学与命令，再去标点。

    `$p$-Values` 里的 `$p$` 会被切成 'p'、'values'，与清洗后的
    'p values' 对不上 —— ASA 那条真 DOI 因此只拿到 0.57 未绑定（第 118 轮）。
    """
    s = (s or "").lower()
    s = re.sub(r"\$[^$]*\$", " ", s)          # $p$ -> 空格
    s = re.sub(r"\\[a-z]+", " ", s)           # \emph 之类
    s = s.replace("{", " ").replace("}", " ").replace("'", "")
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _sim(a: str, b: str) -> float:
    """标题是否同一篇：Jaccard 与**包含度**取大。

    为什么：书目里的标题经常是截短的（我的 \\bibitem 就写到 90 字符），
    纯 Jaccard 会因为长度差把正确记录判成不匹配（第 117 轮实测：
    FAIR 那条真记录在库里，sim 只有 0.71）。包含度 = 交集 / 较短者。
    """
    STOP = {"a", "an", "the", "of", "for", "and", "in", "on", "with",
            "to", "what", "how", "why", "is", "are", "can", "be"}
    A = {w for w in _norm(a).split() if w not in STOP}
    B = {w for w in _norm(b).split() if w not in STOP}
    if not A or not B:
        return 0.0
    # 截断词的容错："Ste" 与 "Stewardship" 应视为同词（书目标题被截在词中间）。
    def _hits(X, Y):
        n = 0
        for x in X:
            if any(x == y or (len(x) >= 3 and y.startswith(x))
                   or (len(y) >= 3 and x.startswith(y)) for y in Y):
                n += 1
        return n
    inter = _hits(A, B)
    # 子集判定：一篇标题的词基本被另一篇包含 → 同一篇。
    # 互不包含时只认 Jaccard，防止 "QuickCheck ..." 绑到 "MuCheck ..."。
    if inter >= 0.9 * min(len(A), len(B)):
        return 1.0
    return inter / max(1, len(A) + len(B) - inter)


def _same_work(mine: str, theirs: str, y1=None, y2=None,
               threshold: float = 0.60) -> tuple:
    """两条记录是否同一篇：包含度达标 **且** 年份不矛盾。"""
    sc = _sim(mine, theirs)
    if sc < threshold:
        return False, sc, "标题不够像"
    if y1 and y2 and abs(int(y1) - int(y2)) > 1:
        return False, sc, "年份相差 %d" % abs(int(y1) - int(y2))
    return True, sc, "ok"


# ── 两个源 ─────────────────────────────────────────────────────────
def crossref(query: str, rows: int = 8):
    u = ("https://api.crossref.org/works?rows=%d&query.bibliographic=%s"
         % (rows, urllib.parse.quote(query)))
    try:
        d = _get(u)
    except Exception:                                   # noqa: BLE001
        return []
    out = []
    for it in (d.get("message") or {}).get("items", []):
        title = (it.get("title") or [""])[0]
        yr = None
        for k in ("published-print", "published-online", "issued"):
            p = (it.get(k) or {}).get("date-parts") or [[None]]
            if p and p[0] and p[0][0]:
                yr = p[0][0]
                break
        out.append(dict(source="crossref", title=title, year=yr,
                        doi=it.get("DOI"),
                        venue=(it.get("container-title") or [""])[0],
                        authors=[(a.get("family") or "") for a in
                                 (it.get("author") or [])][:6]))
    return out


def arxiv(query: str, rows: int = 8):
    u = ("http://export.arxiv.org/api/query?search_query=all:%s&max_results=%d"
         % (urllib.parse.quote(query), rows))
    try:
        req = urllib.request.Request(u, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=25) as r:
            xml = r.read().decode("utf-8", "replace")
    except Exception:                                   # noqa: BLE001
        return []
    out = []
    for m in re.finditer(r"<entry>(.*?)</entry>", xml, re.S):
        e = m.group(1)
        t = re.search(r"<title>(.*?)</title>", e, re.S)
        i = re.search(r"<id>(.*?)</id>", e)
        p = re.search(r"<published>(\d{4})", e)
        out.append(dict(source="arxiv",
                        title=re.sub(r"\s+", " ", t.group(1)).strip() if t else "",
                        year=int(p.group(1)) if p else None,
                        arxiv=(i.group(1).rsplit("/", 1)[-1] if i else None),
                        venue="arXiv",
                        authors=[]))
    return out


# ── 交叉核验 ───────────────────────────────────────────────────────
def merge(cands, threshold: float = 0.62):
    """把两个源的候选按标题相似度合并，标出被几个独立源命中。"""
    groups = []
    for c in cands:
        if not c.get("title"):
            continue
        for g in groups:
            if _sim(g["title"], c["title"]) >= threshold:
                g["sources"].add(c["source"])
                g.setdefault("ids", {})
                for k in ("doi", "arxiv"):
                    if c.get(k):
                        g["ids"][k] = c[k]
                if not g.get("year") and c.get("year"):
                    g["year"] = c["year"]
                break
        else:
            groups.append(dict(title=c["title"], year=c.get("year"),
                               venue=c.get("venue"),
                               sources={c["source"]},
                               ids={k: c[k] for k in ("doi", "arxiv")
                                    if c.get(k)},
                               authors=c.get("authors") or []))
    for g in groups:
        g["n_sources"] = len(g["sources"])
        g["verified"] = g["n_sources"] >= 2 or bool(g["ids"].get("doi"))
        g["sources"] = sorted(g["sources"])
    return groups


def search(query: str, rows: int = 8, topic_words=None):
    """检索 → 合并 → 按「验证优先、相关次之」排序。"""
    cands = crossref(query, rows) + arxiv(query, rows)
    groups = merge(cands)
    tw = [w.lower() for w in (topic_words or query.split()) if len(w) > 3]
    for g in groups:
        t = _norm(g["title"])
        g["topic_hits"] = sum(1 for w in tw if _norm(w) in t)
        g["useful"] = g["verified"] and g["topic_hits"] >= 1
    groups.sort(key=lambda g: (-int(g["useful"]), -g["n_sources"],
                               -g["topic_hits"]))
    return groups


# ── 绑定检查：论文里的每条 bibitem 是否核验过 ────────────────────────
def parse_bib(tex: str):
    out = []
    for m in re.finditer(r"\\bibitem\{([^}]*)\}(.*?)(?=\\bibitem\{|\\end\{thebibliography)",
                         tex, re.S):
        key, body = m.group(1), re.sub(r"\s+", " ", m.group(2)).strip()
        # DOI 内部本来就有句点（10.1145/355604.361591），不能把 `.` 当终止符；
        # 只排除空白与逗号，尾部标点交给 rstrip（第 117 轮踩过：截成 /355604）
        doi = re.search(r"10\.\d{4,9}/[^\s,]+", body)
        arx = re.search(r"arXiv:(\d{4}\.\d{4,5})", body)
        # 标题 = 第一个 \emph 之前的部分，去掉作者前缀。
        # 原来直接取第一个 \emph{...}，抓到的是**期刊名**（第 116 轮自检发现）。
        # bibitem 有两种写法：
        #   (a) Author. Title. \emph{Journal}, year.   ← 标题在 \emph 之前
        #   (b) Author. \emph{Title}. \emph{Journal}.  ← 标题就是第一个 \emph
        # 解析器无法可靠区分，所以保留两个假设，由核验环节选能对上的那个。
        # 标题解析前先把标识符从正文里剥掉：把 DOI 写在标题后面会让
        # "Promoting an Open Research Culture. doi:10.1126/..." 的标题
        # 变成那串 DOI（第 118 轮实测）。
        _body_nt = body
        if doi:
            _body_nt = _body_nt.replace("doi:" + doi.group(0), " ")
            _body_nt = _body_nt.replace(doi.group(0), " ")
            # 剥掉 'doi:' 残壳：否则 "... 标题. doi: 10.x" 会剩 "doi:" 当标题
            _body_nt = re.sub(r"\bdoi:\s*", " ", _body_nt)
        if arx:
            _body_nt = _body_nt.replace("arXiv:" + arx.group(1), " ")
        head = _body_nt.split("\\emph{", 1)[0]
        _parts = [x.strip() for x in head.split(". ") if x.strip()]
        cand_a = (_parts[-1].rstrip(".") if _parts else head.strip())
        # 注意：原始串里要写 `\\emph\{`（一个反斜杠 + emph），写成 `\\emph\\{`
        # 会匹配 "\\emph\" —— 于是 cand_b 恒为空，标题永远抓错（第 117 轮）。
        _em = re.search(r"\\emph\{([^}]*)\}", _body_nt)
        cand_b = _em.group(1).strip() if _em else ""
        _JOURNALISH = ("journal", "proceedings", "transactions", "review",
                       "annals", "arxiv", "conference", "letters", "bulletin",
                       "communications", "magazine", "press", "wiley")
        def _ok(t):
            low = t.lower()
            return bool(t) and not any(w in low for w in _JOURNALISH)
        # 先排除期刊名，再在剩下的里取**词数最多**的（标题通常比作者名长）：
        # "A. Author. \\emph{Title One}" 里 cand_a="Author" 会被误选。
        _cands = [c for c in (cand_a, cand_b) if _ok(c)]
        title = max(_cands, key=lambda t: len(t.split())) if _cands else cand_a
        alt_title = cand_b if title == cand_a else cand_a
        year = re.search(r"(19|20)\d{2}", body)
        out.append(dict(key=key, doi=doi.group(0).rstrip(".") if doi else None,
                        arxiv=arx.group(1) if arx else None,
                        title=re.sub(r"\\[a-z]+\{[^}]*\}", "", title).strip(),
                        year=int(year.group(0)) if year else None))
    return out


def cite_usage(tex: str):
    """每条 key 被引用几次，以及是否有「连甩」凑数段。"""
    counts = {}
    for m in re.finditer(r"\\cite\{([^}]*)\}", tex):
        for k in [x.strip() for x in m.group(1).split(",")]:
            counts[k] = counts.get(k, 0) + 1
    decoration = 0
    for m in re.finditer(r"\\cite\{([^}]*)\}", tex):
        keys = [x.strip() for x in m.group(1).split(",")]
        if len(keys) < 3:
            continue
        # 只看**这一句**：上一个句号到下一个句号。用 ±200 字符会把邻居句的
        # 数字算进来，于是「凑数」永远判不出来（第 116 轮自检抓到）。
        a0 = max(tex.rfind(".", 0, m.start()),
                 tex.rfind("\n\n", 0, m.start())) + 1
        b0 = tex.find(".", m.end())
        seg = tex[a0:b0 if b0 > 0 else m.end() + 120].lower()
        if not re.search(r"\d|we show|we find|reports|measured|demonstrat",
                         seg):
            decoration += 1
    return counts, decoration


def verify_paper(figdir: str, do_network: bool = True):
    tex = io.open(os.path.join(figdir, "paper.tex"), encoding="utf-8").read()
    bib = parse_bib(tex)
    counts, decoration = cite_usage(tex)
    cache = {}
    if os.path.exists(CACHE):
        try:
            cache = json.load(io.open(CACHE, encoding="utf-8"))
        except Exception:                               # noqa: BLE001
            cache = {}
    for b in bib:
        b["cited"] = counts.get(b["key"], 0)
        hit = None
        if b["doi"]:
            hit = cache.get(b["doi"])
            if hit is None and do_network:
                # 优先用已接好的文献后端（71 个工具，实测可用）
                try:
                    import litmcp
                    mr = litmcp.resolve_doi(b["doi"])
                    if mr:
                        hit = dict(title=mr["title"], doi=mr.get("doi"))
                        cache[b["doi"]] = hit
                except Exception:                       # noqa: BLE001
                    pass
            if hit is None and do_network:
                try:
                    d = _get("https://api.crossref.org/works/" +
                             urllib.parse.quote(b["doi"]))
                    it = d.get("message") or {}
                    hit = dict(title=(it.get("title") or [""])[0],
                               doi=it.get("DOI"))
                    cache[b["doi"]] = hit
                except Exception:                       # noqa: BLE001
                    hit = None
        b["resolved"] = bool(hit)
        if hit:
            b["title_sim"] = round(_sim(b["title"], hit.get("title") or ""), 2)
            b["bound"] = b["resolved"] and b["title_sim"] >= 0.45
        elif do_network and b.get("title"):
            # 没有 DOI 时按**精确标题**反查 —— 这是核验「我凭记忆写下的一条
            # 引用」的正确方式（第 116 轮：只走 DOI 路径时 25 条只绑上 1 条）。
            f = find(b["title"])
            if b.get("alt_title") and not f["found"]:
                f2 = find(b["alt_title"])
                if f2["best_sim"] > f["best_sim"]:
                    f = f2
            b["found_sim"] = f["best_sim"]
            rec = f.get("record") or {}
            if f["found"] and (rec.get("doi") or rec.get("arxiv")):
                b["resolved"] = True
                b["bound"] = True
                b["doi"] = rec.get("doi") or b.get("doi")
                b["arxiv"] = rec.get("arxiv") or b.get("arxiv")
                cache.setdefault("by_title", {})[b["title"]] = rec
            else:
                b["bound"] = bool(b["arxiv"])
        else:
            b["bound"] = bool(b["arxiv"])
    if cache and do_network:
        json.dump(cache, io.open(CACHE, "w", encoding="utf-8", newline="\n"),
                  ensure_ascii=False, indent=1)
    unbound = [b for b in bib if not b["bound"]]
    uncited = [b for b in bib if b["cited"] == 0]
    return dict(n=len(bib), bound=len(bib) - len(unbound),
                unbound=[b["key"] for b in unbound],
                uncited=[b["key"] for b in uncited],
                decoration=decoration, entries=bib)


EVALSET = [
    ("Lost in the Middle: How Language Models Use Long Contexts", "liu2023"),
    ("Literate Programming", "knuth1984"),
    ("Bootstrap Methods: Another Look at the Jackknife", "efron1979"),
    ("Why Most Published Research Findings Are False", "ioannidis2005"),
    ("Tests for Parameter Instability and Structural Change with Unknown Change Point",
     "andrews1993"),
]


def find(title: str, rows: int = 10, threshold: float = 0.80):
    """已知标题 → 该标题是否真有对应记录（高相似度才算命中）。

    为什么需要它：模糊查询会返回同名不同文（实测 arXiv 对 "lost in the middle"
    返回 "Lost in the Middle at Birth"）。核验一条**已有**引用时不能用模糊查询，
    必须按标题精确比对。
    """
    cands = crossref(title, rows) + arxiv(title, rows)
    best = None
    for c in cands:
        sc = _sim(title, c.get("title") or "")
        if best is None or sc > best[0]:
            best = (sc, c)
    if not best:
        return dict(found=False, best_sim=0.0, record=None)
    return dict(found=best[0] >= threshold, best_sim=round(best[0], 3),
                record=best[1])


def evalset(threshold: float = 0.80) -> int:
    """已知答案集：衡量「能不能找到那篇」而不是「搜出一堆东西」。"""
    hit = 0
    print("命中测试（hit@1，标题相似度 >= %.2f 才算命中）" % threshold)
    for title, key in EVALSET:
        r = find(title, threshold=threshold)
        ok = bool(r["found"])
        hit += 1 if ok else 0
        rec = r.get("record") or {}
        print("  [%s] %-52s sim=%.2f  %s" % (
            "命中" if ok else "未命中", title[:52], r["best_sim"],
            (rec.get("doi") or rec.get("arxiv") or "无标识")[:34]))
    print()
    print("hit@1 = %d/%d = %.0f%%" % (hit, len(EVALSET), 100.0 * hit / len(EVALSET)))
    return 0 if hit == len(EVALSET) else 1


def selftest() -> int:
    bad = n = 0

    def ck(name, cond, detail=""):
        nonlocal bad, n
        n += 1
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}"
              + (f"  — {detail}" if detail else ""))
        if not cond:
            bad += 1

    # ① 标题相似度
    ck("相同标题 sim=1", _sim("Lost in the Middle", "lost in the middle!") == 1.0)
    ck("无关标题 sim 低", _sim("Lost in the Middle", "Heat sink design") < 0.2)

    # ② 合并：两个源命中 → verified
    g = merge([dict(source="crossref", title="Lost in the Middle: How Language "
                                        "Models Use Long Contexts",
                    year=2024, doi="10.1/x", venue="TACL", authors=[]),
               dict(source="arxiv", title="Lost in the Middle: How Language "
                                         "Models Use Long Contexts", year=2023,
                    arxiv="2307.03172", venue="arXiv", authors=[])])
    ck("两源命中判 verified", g[0]["verified"] and g[0]["n_sources"] == 2,
       str(g[0]["sources"]))
    ck("合并后保留两个标识", bool(g[0]["ids"].get("doi")) and
       bool(g[0]["ids"].get("arxiv")))

    # ③ 单源且有 DOI 也算 verified（DOI 本身可解析）
    g2 = merge([dict(source="crossref", title="Some Real Paper", year=2020,
                     doi="10.2/y", venue="J", authors=[])])
    ck("单源+DOI 判 verified", g2[0]["verified"])

    # ④ 单源无标识 → 不 verified
    g3 = merge([dict(source="arxiv", title="Only Here", year=2020,
                     arxiv=None, venue="arXiv", authors=[])])
    ck("单源无标识不 verified", not g3[0]["verified"])

    # ⑤ 解析 bibitem
    tex = (r"\begin{thebibliography}{9}" "\n"
           r"\bibitem{a} A. Author. \emph{Title One}. \emph{Journal}, 2020." "\n"
           r"\bibitem{b} B. Author. \emph{Title Two}. doi:10.1234/abc. 2021." "\n"
           r"\end{thebibliography}")
    bib = parse_bib(tex)
    ck("解析出两条", len(bib) == 2, str([b["key"] for b in bib]))
    ck("抓到 DOI", bib[1]["doi"] == "10.1234/abc", str(bib[1]["doi"]))
    ck("抽到标题", "Title One" in bib[0]["title"], bib[0]["title"])

    # ⑥ 引用计数与凑数识别
    body = (r"See \cite{a}. " +
            r"Many works \cite{a,b,c} say so. " +      # 3 连甩、无数字 → 凑数
            r"We measured 0.42 \cite{a}.")
    counts, dec = cite_usage(body)
    ck("引用计数正确", counts.get("a") == 3 and counts.get("b") == 1, str(counts))
    ck("识别出凑数引用", dec == 1, f"decoration={dec}")

    print()
    print(f"{'ALL PASS' if bad == 0 else 'FAILED'}  {n - bad}/{n}")
    return 0 if bad == 0 else 1


def main(argv=None):
    a = argv or sys.argv[1:]
    if not a:
        print(__doc__)
        return 0
    if a[0] == "selftest":
        return selftest()
    if a[0] == "find":
        t = " ".join(a[1:])
        r = find(t)
        print("命中" if r["found"] else "未命中", "sim=%.2f" % r["best_sim"])
        if r.get("record"):
            print("  ", (r["record"].get("title") or "")[:80])
            print("   ", r["record"].get("doi") or r["record"].get("arxiv") or "无标识")
        return 0
    if a[0] == "evalset":
        return evalset()
    if a[0] == "search":
        q = " ".join(a[1:]) or "provenance of machine-generated text"
        g = search(q)
        print(f"查询：{q}\n")
        for x in g[:8]:
            mark = "有用" if x["useful"] else ("待核" if x["verified"] else "单源")
            ids = " ".join(f"{k}={v}" for k, v in x["ids"].items()) or "无标识"
            print("  [%s] %s" % (mark, x["title"][:78]))
            print("        %s %s | %s | 源 %s" % (x.get("year") or "?", ids,
                                                (x.get("venue") or "")[:28],
                                                "+".join(x["sources"])))
        return 0
    if a[0] == "check":
        d = a[1] if len(a) > 1 else os.path.join(HERE, "out", "final")
        r = verify_paper(d, do_network=("--offline" not in a))
        print("文献绑定：%d 条，已绑定 %d，未绑定 %s"
              % (r["n"], r["bound"], r["unbound"] or "无"))
        print("未被引用：%s" % (r["uncited"] or "无"))
        print("疑似凑数引用段：%d" % r["decoration"])
        json.dump(r, io.open(os.path.join(d, "lit_bound.json"), "w",
                             encoding="utf-8", newline="\n"),
                  ensure_ascii=False, indent=1)
        return 0
    print("未知子命令：", a[0])
    return 2


if __name__ == "__main__":
    sys.exit(main())
