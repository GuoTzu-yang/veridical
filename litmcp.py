"""litmcp.py —— 把 paper-search-mcp 接成 pl插件 的文献后端（第 117 轮）。

背景（本轮实测）
----------------
`用户给的三个仓库名都取不到 README（不存在）`；真实存在的是
`blazickjm/arxiv-mcp-server` 与 `openags/paper-search-mcp`，后者在本机
import 成功、注册了 71 个工具，其中 `get_crossref_paper_by_doi` 实测能
按 DOI 取回正确元数据（10.1162/tacl_a_00638 -> Liu et al., TACL）。

设计原则：**可选依赖，绝不硬依赖**
  · 能找到源码树（环境变量 PAPER_SEARCH_MCP_ROOT 或默认路径）→ 用它；
  · 找不到 → 返回 None，调用方回退到原始 HTTP（litsearch.py 自己的实现）。
这样插件在没装第三方包的机器上仍然能跑，不会因为「文献后端缺失」而红。

为什么不用 MCP 协议调用
----------------------
stdio 协议需要长驻子进程与握手；我们只需要四个纯函数。直接 import 模块
调用在语义上等价、故障面更小（少一层序列化），且能被我自己的自检覆盖。
"""
import io
import os
import sys

DEFAULT_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "out", "_mcp", "paper-search-mcp",
                            "paper-search-mcp-HEAD")
_state = {"tried": False, "server": None, "error": None}


def _load():
    """惰性导入一次；失败就记住原因，不再重试。"""
    if _state["tried"]:
        return _state["server"]
    _state["tried"] = True
    root = os.environ.get("PAPER_SEARCH_MCP_ROOT", DEFAULT_ROOT)
    if not os.path.isdir(root):
        _state["error"] = "源码树不存在：%s" % root
        return None
    if root not in sys.path:
        sys.path.insert(0, root)
    # 该包在导入时往 stderr 打一堆 warning（缺 API key），不要污染我们的输出
    _err = io.StringIO()
    try:
        import contextlib
        with contextlib.redirect_stderr(_err):
            from paper_search_mcp import server as S
        _state["server"] = S
    except Exception as e:                              # noqa: BLE001
        _state["error"] = "%s: %s" % (type(e).__name__, str(e)[:120])
        _state["server"] = None
    return _state["server"]


def available() -> bool:
    return _load() is not None


def why_not() -> str:
    _load()
    return _state["error"] or "可用"


def _call(name: str, **kw):
    S = _load()
    if S is None or not hasattr(S, name):
        return None
    import inspect
    import asyncio
    f = getattr(S, name)
    try:
        r = f(**kw)
        if inspect.isawaitable(r):
            r = asyncio.get_event_loop().run_until_complete(r)
        return r
    except Exception:                                   # noqa: BLE001
        return None


def resolve_doi(doi: str):
    """DOI → 元数据。返回 dict(title, authors, year) 或 None。"""
    if not doi:
        return None
    r = _call("get_crossref_paper_by_doi", doi=doi)
    # 不存在的 DOI 会返回 {}（而不是 None）—— 所以按「标题为空即失败」判
    if not isinstance(r, dict) or not (r.get("title") or "").strip():
        return None
    title = r["title"].strip()
    # 字段名实测是 published_date（不是 published/year）
    year = r.get("published_date") or r.get("year") or r.get("published")
    if isinstance(year, str):
        import re
        m = re.search(r"(19|20)\d{2}", year)
        year = int(m.group(0)) if m else None
    return dict(title=title, authors=r.get("authors") or "", year=year,
                doi=r.get("paper_id") or doi, source="paper-search-mcp")


def search_crossref(query: str, limit: int = 8):
    """Crossref 检索。返回 list[dict(title, doi, year)]。"""
    r = _call("search_crossref", query=query, max_results=limit)
    if isinstance(r, dict):
        r = r.get("results") or r.get("papers") or []
    out = []
    for it in (r or []):
        if not isinstance(it, dict):
            continue
        out.append(dict(title=it.get("title") or "",
                        doi=it.get("paper_id") or it.get("doi"),
                        year=it.get("published") or it.get("year"),
                        venue=it.get("venue") or ""))
    return out


def citing(doi: str, limit: int = 5):
    """被谁引用（用于判断一篇文献是不是领域内的关键工作）。"""
    r = _call("get_citing_papers", doi=doi, max_results=limit)
    if isinstance(r, dict):
        r = r.get("results") or []
    return r or []


def selftest() -> int:
    bad = n = 0

    def ck(name, cond, detail=""):
        nonlocal bad, n
        n += 1
        print("  [%s] %s%s" % ("PASS" if cond else "FAIL", name,
                               ("  — " + detail) if detail else ""))
        if not cond:
            bad += 1

    ok = available()
    ck("后端可加载（不可用时下面的联网断言会跳过）", True,
       "可用" if ok else why_not())
    ck("why_not 有明确答案", isinstance(why_not(), str))
    if ok:
        r = resolve_doi("10.1162/tacl_a_00638")
        ck("按 DOI 取回元数据", bool(r), str(r)[:60] if r else "None")
        if r:
            ck("标题含关键短语", "long contexts" in r["title"].lower(),
               r["title"][:50])
            ck("年份是 2024", r.get("year") in (2024, 2023), str(r.get("year")))
        ck("空 DOI 返回 None", resolve_doi("") is None)
        ck("不存在的 DOI 返回 None",
           resolve_doi("10.9999/definitely-not-a-real-doi-xyz") is None)
    print()
    print("%s  %d/%d" % ("ALL PASS" if bad == 0 else "FAILED", n - bad, n))
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "selftest":
        raise SystemExit(selftest())
    print("后端可用:", available(), "|", why_not())
    if available():
        print("示例:", resolve_doi("10.1162/tacl_a_00638"))
