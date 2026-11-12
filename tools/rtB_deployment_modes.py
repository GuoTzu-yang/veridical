# -*- coding: utf-8 -*-
"""rtB deployment board - probe 1: are the three run modes actually given?

Read-only. Prints facts only; no writes, no imports of the plugin modules
(only source text is examined).
"""
import io
import os
import re
import json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAPER = os.path.join(ROOT, "out", "final", "paper.tex")

SEC_START = 1001
SEC_END = 1118


def read_lines(path):
    with io.open(path, encoding="utf-8") as fh:
        return fh.read().splitlines()


def main():
    lines = read_lines(PAPER)
    sec = lines[SEC_START - 1:SEC_END]
    print("=== A. section extent check ===")
    print("L%d == %r" % (SEC_START, lines[SEC_START - 1]))
    print("L%d == %r" % (SEC_END, lines[SEC_END - 1]))

    print("\n=== B. any executable invocation inside the section? ===")
    pats = {
        "python_script": re.compile(r"python[ _]?[A-Za-z0-9_\\]*\.py"),
        "code_macro": re.compile(r"\\code\{[^}]*\}"),
        "dash_flag": re.compile(r"--[a-z][a-z0-9-]*"),
        "shell_prompt": re.compile(r"(?m)^\s*\$ "),
    }
    for name, pat in pats.items():
        hits = []
        for idx, txt in enumerate(sec):
            for m in pat.finditer(txt):
                hits.append((SEC_START + idx, m.group(0)))
        print("  %-14s hits=%d %s" % (name, len(hits), hits[:12]))

    print("\n=== C. the forward promise 'written down (below)' ===")
    for idx, txt in enumerate(sec):
        if "(below)" in txt:
            print("  L%d: %s" % (SEC_START + idx, txt.strip()))
    print("  -> where the nine-step order actually lives:")
    for i, txt in enumerate(lines, start=1):
        if "nine verified commands" in txt or "tab:timing" in txt:
            print("     L%d: %s" % (i, txt.strip()))

    print("\n=== D. is the order 'verified by a script'? ===")
    cand = []
    for base, _dirs, files in os.walk(ROOT):
        if any(skip in base for skip in ("__pycache__", ".git")):
            continue
        for f in files:
            if f.endswith(".py") and ("runbook" in f or "order" in f):
                cand.append(os.path.relpath(os.path.join(base, f), ROOT))
    print("  runbook/order scripts on disk: %s" % sorted(cand))
    for rel in sorted(cand):
        txt = io.open(os.path.join(ROOT, rel), encoding="utf-8", errors="replace").read()
        named = ("tab_timing" in txt) or ("nine" in txt) or ("order" in txt.lower())
        print("  %-40s mentions nine/order/tab_timing=%s len=%d" % (rel, named, len(txt)))
    print("  paper mentions a runbook verifier?")
    for i, txt in enumerate(lines, start=1):
        if "runbook" in txt.lower():
            print("     L%d: %s" % (i, txt.strip()))

    print("\n=== E. mode 2: does the MCP service expose the SAME subcommands? ===")
    schema_path = os.path.join(ROOT, "schema.json")
    cmds = []
    if os.path.exists(schema_path):
        data = json.load(io.open(schema_path, encoding="utf-8"))
        if isinstance(data, dict):
            for key in ("commands", "cmds"):
                if key in data and isinstance(data[key], dict):
                    cmds = sorted(data[key].keys())
                    break
            if not cmds and all(isinstance(v, dict) for v in data.values()):
                cmds = sorted(data.keys())
        elif isinstance(data, list):
            cmds = sorted(x.get("name", "") for x in data if isinstance(x, dict))
    print("  schema.json commands (%d): %s" % (len(cmds), cmds))

    mcp_path = os.path.join(ROOT, "mcp_server.py")
    mcp_txt = io.open(mcp_path, encoding="utf-8", errors="replace").read() if os.path.exists(mcp_path) else ""
    tool_names = sorted(set(re.findall(r"name\s*=\s*[\"']([a-z_0-9]+)[\"']", mcp_txt)))
    listed = sorted(set(re.findall(r"[\"']([a-z][a-z_0-9]{2,})[\"']\s*:", mcp_txt)))
    print("  mcp_server.py exists=%s len=%d" % (os.path.exists(mcp_path), len(mcp_txt)))
    print("  mcp name= literals: %s" % tool_names[:40])
    print("  mcp dict-key literals (first 40): %s" % listed[:40])
    covered = [c for c in cmds if c in mcp_txt]
    missing = [c for c in cmds if c not in mcp_txt]
    print("  schema commands named anywhere in mcp_server.py: %d/%d" % (len(covered), len(cmds)))
    print("  commands absent from mcp_server.py: %s" % missing)

    print("\n=== F. mode 3: any CI configuration in the section or repo? ===")
    for i, txt in enumerate(sec, start=SEC_START):
        if re.search(r"\bCI\b|commit|stamp", txt):
            print("  L%d: %s" % (i, txt.strip()))
    ci_files = []
    for base, _dirs, files in os.walk(ROOT):
        if any(skip in base for skip in ("__pycache__", ".git", "_removed")):
            continue
        for f in files:
            if f in (".gitlab-ci.yml", "azure-pipelines.yml", "Jenkinsfile") or (
                f.endswith(".yml") and "ci" in f.lower()
            ):
                ci_files.append(os.path.relpath(os.path.join(base, f), ROOT))
    print("  CI definition files found: %s" % ci_files)


if __name__ == "__main__":
    main()
