#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
前置检查的可插拔接口：判据通用，检测器分领域

前十几轮里，「这一步现在做得了吗」这件事一直是硬编码在 sqlcheck.py 里的。
判据框架（e1/e3/input_valid + 三道闸）本身不分领域，但检测器绑死在 SQL 上。

这个文件把接口抽出来：

    Precheck.domain      领域名
    Precheck.check(task) → CheckResult(ok, reason)

已实现三个领域：
    sql   查表/列/维度/语法（走 WSL 里的 seekdb）
    file  查路径存在/类型/权限（本机）
    http  查 URL 格式/可达/状态码（本机）

新增领域只需要继承 Precheck 并在 REGISTRY 里注册，判据代码一行不用改。

跑法：python precheck.py
"""

from __future__ import annotations

import os
import re
import socket
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass


@dataclass
class CheckResult:
    """三态，对应 input_valid 的 True / False / None。

    ok    —— 查了，做得了
    fail  —— 查了，做不了
    unknown —— 没查成（检查器本身不可用：连不上库、没有权限、环境缺失）

    unknown 不是 fail。把「没查」写成「不行」，等于凭空否定一个可能成立的任务。

    mechanism / mechanism_reason 是第三十五轮加的第二问：
    「这件事原理上成不成立」——和「现在做得了吗」是两回事。
      mechanism=True   原理上成立
      mechanism=False  原理上不成立（做得了，但做了没用）
      mechanism=None   没查这一问
    """
    status: str          # "ok" | "fail" | "unknown"
    reason: str
    mechanism: bool | None = None
    mechanism_reason: str = ""

    def __post_init__(self):
        if self.status not in ("ok", "fail", "unknown"):
            raise ValueError(f"未知状态 {self.status}")

    @property
    def ok(self) -> bool | None:
        return {"ok": True, "fail": False, "unknown": None}[self.status]

    @property
    def decided(self) -> bool:
        """是否做出了确定判断（ok 或 fail）；unknown 为 False。"""
        return self.status != "unknown"

    def __bool__(self) -> bool:
        # unknown 不能当成 True，不能谎报通过
        return self.status == "ok"


def OK(reason: str) -> CheckResult:
    return CheckResult("ok", reason)


def FAIL(reason: str) -> CheckResult:
    return CheckResult("fail", reason)


def UNKNOWN(reason: str) -> CheckResult:
    return CheckResult("unknown", reason)


def OK_BUT(reason: str, mechanism: bool | None, mechanism_reason: str = "") -> CheckResult:
    """前置通过，但机制适用性另有结论。"""
    return CheckResult("ok", reason, mechanism, mechanism_reason)


class Precheck:
    """前置检查的基类。每个领域一个子类。"""

    domain = "base"

    def check(self, task: dict) -> CheckResult:
        raise NotImplementedError

    # 子类可以提供更具体的说明
    def describe(self) -> str:
        return f"{self.domain} 前置检查"


# ---------------------------------------------------------------------------
# 文件操作
# ---------------------------------------------------------------------------
class FilePrecheck(Precheck):
    domain = "file"

    def describe(self) -> str:
        return "路径存在性 + 类型 + 读写权限"

    def check(self, task: dict) -> CheckResult:
        path = task.get("path")
        op = task.get("op", "read")
        if not path:
            return FAIL("没有给 path")

        if op == "create":
            parent = os.path.dirname(os.path.abspath(path)) or "."
            if not os.path.isdir(parent):
                return FAIL(f"父目录不存在：{parent}")
            if os.path.exists(path):
                return OK("目标已存在，create 会覆盖（可能不是预期）")
            if not os.access(parent, os.W_OK):
                return FAIL(f"父目录不可写：{parent}")
            return OK("父目录可写，可以创建")

        if not os.path.exists(path):
            return FAIL(f"路径不存在：{path}")

        if op == "dir":
            if not os.path.isdir(path):
                return FAIL(f"不是目录：{path}")
            return OK("存在且是目录")
        if op == "read":
            if os.path.isdir(path):
                return FAIL(f"是目录不是文件：{path}")
            if not os.access(path, os.R_OK):
                return FAIL(f"不可读：{path}")
            return OK("存在且可读")
        if op == "write":
            if not os.access(path, os.W_OK):
                return FAIL(f"不可写：{path}")
            return OK("存在且可写")

        return OK(f"exists（op={op} 未特判）")


# ---------------------------------------------------------------------------
# HTTP 请求
# ---------------------------------------------------------------------------
_DNS_ALIVE_CACHE: bool | None = None

# 只用来探测「本机 DNS 通不通」，不访问目标域名
_DNS_PROBES = ("github.com", "example.com", "baidu.com")


def dns_alive() -> bool:
    """本机 DNS 是否可用。

    上一版是靠 `strerror` 里有没有 "unknown" 来判断，换个系统 / 换个 libc
    就失效了。改成**先探一个已知能解析的域名**：
      探针能解析 → DNS 是通的，那么其余解析失败就是目标域名的问题（fail）
      探针也失败 → 本机 DNS 坏了，什么域名都查不了（unknown）
    """
    global _DNS_ALIVE_CACHE
    if _DNS_ALIVE_CACHE is not None:
        return _DNS_ALIVE_CACHE
    for host in _DNS_PROBES:
        try:
            socket.getaddrinfo(host, 443)
            _DNS_ALIVE_CACHE = True
            return True
        except Exception:
            continue
    _DNS_ALIVE_CACHE = False
    return False


class HttpPrecheck(Precheck):
    domain = "http"

    def describe(self) -> str:
        return "URL 格式 + DNS 可解析 + TCP 可连接（先探本机 DNS 是否可用）"

    def check(self, task: dict) -> CheckResult:
        url = task.get("url", "")
        if not url:
            return FAIL("没有给 url")

        u = urllib.parse.urlparse(url)
        if u.scheme not in ("http", "https"):
            return FAIL(f"协议不支持：{u.scheme or '（空）'}")
        if not u.hostname:
            return FAIL(f"没有主机名：{url}")

        port = u.port or (443 if u.scheme == "https" else 80)

        # 第一关：DNS。只解析，不发 HTTP 请求
        try:
            socket.getaddrinfo(u.hostname, port)
        except socket.gaierror:
            if dns_alive():
                return FAIL(f"域名不存在：{u.hostname}（本机 DNS 正常，探针可解析）")
            return UNKNOWN(f"本机 DNS 不可用，查不了 {u.hostname}")
        except Exception as e:
            return UNKNOWN(f"解析器异常：{type(e).__name__}: {e}")

        # 第二关：TCP。
        # 第二十九轮实测：github.com 的 DNS 正常，但 443 端口连接被拒
        # （WinError 10061），precheck 只查 DNS 就会把它判成可行。
        # DNS 通过 ≠ 服务可达。
        try:
            with socket.create_connection((u.hostname, port), timeout=3):
                pass
        except socket.timeout:
            return UNKNOWN(f"{u.hostname}:{port} 连接超时（可能被拦，也可能只是慢）")
        except OSError as e:
            return FAIL(f"{u.hostname}:{port} 连不上（{e.strerror or e}）")

        # 第三关：资源本身在不在。
        # 第四十五轮加：TCP 通 ≠ 资源存在。
        # 实测 `https://github.com/oceanbase/no-such-repo-xyz-999` 端口连得上，
        # 但请求返回 404——判 pass 就是假阳性。
        # 前两关只能证明"服务器在"，这一关才回答"这东西在不在"。
        try:
            req = urllib.request.Request(url, method="HEAD",
                                         headers={"User-Agent": "model1-precheck/1.0"})
            with urllib.request.urlopen(req, timeout=8) as r:
                code = r.status
            if code >= 400:
                return FAIL(f"{url} 返回 HTTP {code}")
            return OK(f"{u.hostname}:{port} 可解析、可连接、资源可访问（HTTP {code}）")
        except urllib.error.HTTPError as e:
            # 405 = 服务器不接受 HEAD，不代表资源不存在 → 不下结论
            if e.code == 405:
                return UNKNOWN(f"{url} 不支持 HEAD（HTTP 405），资源存在性查不了")
            return FAIL(f"{url} 返回 HTTP {e.code}")
        except urllib.error.URLError as e:
            reason = e.reason
            # 分清"查不成"和"查到了，是不行"：
            #   超时            → 可能只是慢，不下结论
            #   连接被重置/拒绝  → 明确的否定响应，判 FAIL
            if isinstance(reason, (ConnectionResetError, ConnectionRefusedError)) or \
                    "10054" in str(reason) or "10061" in str(reason):
                return FAIL(f"{url} 连接被拒/重置（{reason}）")
            if "timed out" in str(reason).lower() or "timeout" in str(reason).lower():
                return UNKNOWN(f"{url} 请求超时（可能只是慢）")
            return UNKNOWN(f"{url} 请求失败：{reason}")
        except Exception as e:
            return UNKNOWN(f"{url} 请求异常：{type(e).__name__}: {e}")


# ---------------------------------------------------------------------------
# SQL（复用 sqlcheck 的实现）
# ---------------------------------------------------------------------------
def _sql_mechanism(sql: str, columns_fn=None) -> tuple[bool | None, str]:
    """SQL 的机制适用性：谓词里的索引列能不能用上索引。

    「现在做得了吗」（表在不在、语法对不对）是第一问；
    「做了有没有用」（索引原理上用得上吗）是第二问。
    第三十五轮实测：age+0=42 跑得动但走全表扫描——第二问才拦得住它。
    """
    import re

    try:
        from sargable import sargable
    except Exception:
        return None, "sargable 模块不可用"

    m = re.search(r"\bfrom\s+([A-Za-z_][A-Za-z0-9_.]*)", sql, re.I)
    if not m:
        return None, "没有 FROM 子句，无从判断索引可用性"
    table = m.group(1).split(".")[-1]

    try:
        from sqlcheck import _indexed_columns
        indexed = _indexed_columns(table)
    except Exception:
        return None, f"取 {table} 的索引信息失败"
    if not indexed:
        return None, f"表 {table} 上没有索引，走全表扫描是合理的"

    try:
        return sargable(sql, indexed)
    except Exception as e:
        return None, f"机制检查异常：{type(e).__name__}: {e}"


class SqlPrecheck(Precheck):
    domain = "sql"

    def describe(self) -> str:
        return "表/列存在性 + 向量维度 + 语法（走 WSL seekdb）"

    def check(self, task: dict) -> CheckResult:
        sql = task.get("sql", "")
        if not sql:
            return FAIL("没有给 sql")

        # 先确认检查器本身可用——连不上库是「查不了」，不是「做不了」
        try:
            from sqlcheck import _wsl_mysql
        except Exception as e:
            return UNKNOWN(f"检查器导入失败：{type(e).__name__}: {e}")

        code, out = _wsl_mysql("SELECT 1")
        if code != 0:
            first = (out or "").splitlines()[0][:60] if out else "无输出"
            return UNKNOWN(f"连不上 seekdb，无法检查（{first}）")

        try:
            from sqlcheck import precheck as sql_precheck, _tables, _columns
            ok, reason = sql_precheck(sql, _tables())
        except Exception as e:
            return UNKNOWN(f"检查器异常：{type(e).__name__}: {e}")

        if not ok:
            return FAIL(reason)

        # 第二问：机制适用性。
        # 「现在做得了吗」和「做了有没有用」是两回事——
        # `WHERE age + 0 = 42` 跑得动，但索引原理上用不上，做了也没用。
        mech, mech_reason = _sql_mechanism(sql, _columns)
        return OK_BUT(reason, mech, mech_reason)


# ---------------------------------------------------------------------------
# 数据表断言（真题投喂用）
# ---------------------------------------------------------------------------
class DataPrecheck(Precheck):
    """前置检查：这份数据现在能不能断言。

    只回答「做得了吗」——文件在不在、读不读得开、断言需要的列在不在。
    **不断言真假**，那是执行器（probe._do_data）的事。
    两件事分开，是因为「能验」和「验出来为真」必须能被分别表述。
    """
    domain = "data"

    def describe(self) -> str:
        return "数据文件存在 + 可读 + 断言所需列存在"

    def check(self, task: dict) -> CheckResult:
        path = task.get("file")
        if not path:
            return FAIL("没有给 file")
        if not os.path.exists(path):
            return FAIL(f"数据文件不存在：{path}")
        if os.path.isdir(path):
            return FAIL(f"是目录不是文件：{path}")
        if not os.access(path, os.R_OK):
            return FAIL(f"不可读：{path}")

        kind = task.get("assert")
        if not kind:
            return OK("文件可读（没指定断言）")

        try:
            from probe import DATA_ASSERTS, _read_table
            if kind not in DATA_ASSERTS:
                return FAIL(f"未知断言 {kind!r}；支持 {DATA_ASSERTS}")
            cols, rows = _read_table(path, task.get("sheet"),
                                     int(task.get("header_row", 1)))
        except Exception as e:
            return UNKNOWN(f"读表失败（读不了 ≠ 断言不成立）：{type(e).__name__}: {e}")

        if not cols:
            return FAIL(f"表是空的或表头没读到：{path}")

        low = {str(c).lower().strip() for c in cols}
        p = task.get("params") or {}
        need = [x for x in (p.get("column"), p.get("x"), p.get("y")) if x]
        missing = [c for c in need if c.lower() not in low]
        if missing:
            return FAIL(f"列不存在：{missing}；表里有 {[str(c)[:12] for c in cols[:8]]}")

        return OK(f"数据可读（{len(cols)} 列 / {len(rows)} 行），断言所需列都在")


# ---------------------------------------------------------------------------
# 图像断言（真题投喂用）
# ---------------------------------------------------------------------------
class ImagePrecheck(Precheck):
    """前置检查：这张图现在能不能断言。

    只回答「打得开吗、断言认不认」——**不断言图片内容符合什么**。
    """
    domain = "image"

    def describe(self) -> str:
        return "图像文件存在 + 可被 PIL 打开 + 断言名受支持"

    def check(self, task: dict) -> CheckResult:
        path = task.get("file")
        if not path:
            return FAIL("没有给 file")
        if not os.path.exists(path):
            return FAIL(f"图像不存在：{path}")
        if os.path.isdir(path):
            return FAIL(f"是目录不是文件：{path}")

        kind = task.get("assert")
        try:
            from probe import IMAGE_ASSERTS
            if kind and kind not in IMAGE_ASSERTS:
                return FAIL(f"未知图像断言 {kind!r}；支持 {IMAGE_ASSERTS}")
        except Exception as e:
            return UNKNOWN(f"取断言清单失败：{type(e).__name__}: {e}")

        try:
            from PIL import Image
            with Image.open(path) as im:
                w, h = im.size
                mode = im.mode
        except Exception as e:
            return UNKNOWN(f"打不开图像（打不开 ≠ 断言不成立）：{type(e).__name__}: {e}")

        return OK(f"图像可读（{w}x{h} / {mode}）")


# ---------------------------------------------------------------------------
# 注册表
# ---------------------------------------------------------------------------
REGISTRY: dict[str, Precheck] = {}


def register(p: Precheck) -> None:
    if p.domain in REGISTRY:
        raise ValueError(f"领域重复注册：{p.domain}")
    REGISTRY[p.domain] = p


register(FilePrecheck())
register(HttpPrecheck())
register(SqlPrecheck())
register(DataPrecheck())
register(ImagePrecheck())


def precheck_for(domain: str) -> Precheck:
    if domain not in REGISTRY:
        raise KeyError(f"未注册的领域 {domain}，可用：{sorted(REGISTRY)}")
    return REGISTRY[domain]


def check_task(domain: str, task: dict) -> CheckResult:
    return precheck_for(domain).check(task)


# ---------------------------------------------------------------------------
# 演示
# ---------------------------------------------------------------------------
CASES = [
    ("file", {"path": r"C:\Windows\System32\drivers\etc\hosts", "op": "read"}, "ok"),
    ("file", {"path": r"C:\no\such\dir\x.txt", "op": "read"}, "fail"),
    ("file", {"path": r"C:\Windows", "op": "dir"}, "ok"),
    ("file", {"path": r"C:\no\such\dir\new.txt", "op": "create"}, "fail"),
    ("http", {"url": "https://github.com/oceanbase/seekdb"}, "ok"),
    ("http", {"url": "https://no-such-host-xyz-12345.invalid/"}, "fail"),
    ("http", {"url": "ftp://example.com/x"}, "fail"),
    ("http", {"url": "not-a-url"}, "fail"),
    ("sql", {"sql": "SELECT * FROM bench_l3.no_such_table"}, "fail"),   # seekdb 在跑时
]

LABEL = {"ok": "可行", "fail": "不可行", "unknown": "没查成"}


def main() -> int:
    print("=" * 82)
    print("前置检查 · 可插拔接口（三态）")
    print("=" * 82)
    print(f"已注册领域：{sorted(REGISTRY)}")
    for d, p in sorted(REGISTRY.items()):
        print(f"  {d:6s} {p.describe()}")

    print()
    print(f"  {'领域':<6}{'任务':<44}{'期望':>8}{'实际':>8}  理由")
    print("  " + "-" * 96)
    hit = 0
    unknown_n = 0
    for domain, task, want in CASES:
        try:
            r = check_task(domain, task)
        except Exception as e:
            print(f"  {domain:<6}{str(task)[:42]:<44}{'-':>8}{'ERR':>8}  {e}")
            continue
        if r.status == "unknown":
            unknown_n += 1
        good = r.status == want
        hit += 1 if good else 0
        label = task.get("path") or task.get("url") or task.get("sql")
        print(f"  {domain:<6}{str(label)[:42]:<44}"
              f"{LABEL[want]:>8}{LABEL[r.status]:>8}"
              f"  {'✓' if good else '✗'} {r.reason[:38]}")

    print()
    print("=" * 82)
    print(f"准确率: {hit}/{len(CASES)}    其中 unknown: {unknown_n}")

    # 故意让检查器不可用，验证它会说"没查成"而不是"做不了"
    print()
    print("【对照 A】把 sql 检查器的 WSL 发行版指向一个不存在的地方：")
    try:
        import sqlcheck
        saved = sqlcheck.DISTRO
        sqlcheck.DISTRO = "NoSuchDistro-XYZ"
        r = check_task("sql", {"sql": "SELECT 1"})
        sqlcheck.DISTRO = saved
        print(f"  状态 = {r.status}（{LABEL[r.status]}）")
        print(f"  理由 = {r.reason[:70]}")
        print(f"  → input_valid = {r.ok}  （None 表示未检查，不是 False）")
        if r.status == "unknown" and r.ok is None:
            print("  ✓ 正确区分了「没查成」和「做不了」")
        else:
            print("  ✗ 没能区分")
    except Exception as e:
        print(f"  对照失败：{type(e).__name__}: {e}")

    print()
    print("【对照 B】伪造本机 DNS 挂掉：")
    # 注意：不能用 `import precheck as _self`——脚本本身的模块名是 __main__，
    # import 会得到**第二份**模块对象，改的是副本，主模块的缓存纹丝不动。
    global _DNS_ALIVE_CACHE
    saved_cache = _DNS_ALIVE_CACHE
    _DNS_ALIVE_CACHE = False          # 假装探针也失败
    try:
        r = check_task("http", {"url": "https://totally-made-up-host-abc.xyz/"})
        print(f"  状态 = {r.status}（{LABEL[r.status]}）")
        print(f"  理由 = {r.reason}")
        print(f"  → input_valid = {r.ok}")
        if r.status == "unknown":
            print("  ✓ DNS 挂了 → unknown，不会误判成「域名不存在」")
        else:
            print("  ✗ 应该 unknown")
    finally:
        _DNS_ALIVE_CACHE = saved_cache

    print()
    print("【对照 C】DNS 正常时，真不存在的域名应判 fail：")
    r = check_task("http", {"url": "https://totally-made-up-host-abc.xyz/"})
    print(f"  状态 = {r.status}（{LABEL[r.status]}）")
    print(f"  理由 = {r.reason}")
    print(f"  → input_valid = {r.ok}")
    if r.status == "fail":
        print("  ✓ DNS 正常 → fail，不会含混成 unknown")
    else:
        print("  ✗ 应该 fail")

    print()
    print("判据框架不认领域：它只要一个 True / False / None。")
    print("  True    查了，做得了")
    print("  False   查了，做不了")
    print("  None    没查成（检查器不可用）——不是「做不了」")
    print("=" * 82)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
