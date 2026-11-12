# -*- coding: utf-8 -*-
"""rtB deployment board - probe 1 (part 2): what mode 2/3 actually expose.

Read-only. Extracts the MCP tool registry from mcp_server.py and compares it
with schema.json's subcommand list, then looks for any CI/hook wiring.
"""
import io
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def rd(p):
    return io.open(p, encoding="utf-8", errors="replace").read()


def main():
    print("=== A. mcp_server.py TOOLS registry ===")
    src = rd(os.path.join(ROOT, "mcp_server.py"))
    block = re.search(r"TOOLS\s*=\s*\[(.*?)\n\]", src, re.S)
    names = []
    if block:
        names = re.findall(r'"name"\s*:\s*"([^"]+)"', block.group(1))
    print("  tool names (%d): %s" % (len(names), names))
    print("  any tool named after a schema subcommand? %s"
          % [n for n in names if not n.startswith("model1_")])
    print("  docstring says:")
    for ln in src.splitlines()[:16]:
        if "model1_" in ln or "MCP" in ln:
            print("    " + ln.strip())

    print("\n=== B. schema.json subcommands ===")
    data = json.load(io.open(os.path.join(ROOT, "schema.json"), encoding="utf-8"))
    cmds = sorted(data["commands"].keys()) if "commands" in data else sorted(data.keys())
    print("  n=%d" % len(cmds))
    print("  %s" % cmds)
    print("  paper L32 claim: exposes 23 subcommands over one entry point -> n==23? %s"
          % (len(cmds) == 23))

    print("\n=== C. does mmkit.py itself serve MCP? ===")
    mm = rd(os.path.join(ROOT, "mmkit.py"))
    for i, ln in enumerate(mm.splitlines(), start=1):
        if re.search(r"\bmcp\b|tools/list|jsonrpc", ln, re.I):
            print("  mmkit.py L%d: %s" % (i, ln.strip()))
    print("  (empty above = mmkit has no MCP transport of its own)")

    print("\n=== D. how a human is supposed to invoke one step ===")
    runbook = os.path.join(ROOT, "问题到手时的操作手册.md")
    print("  runbook md exists: %s" % os.path.exists(runbook))
    if os.path.exists(runbook):
        txt = rd(runbook)
        inv = re.findall(r"mmkit\.py\s+([a-z]+)", txt)
        print("  runbook invokes mmkit.py %d times, subcommands: %s"
              % (len(inv), sorted(set(inv))))
        print("  runbook len=%d lines=%d" % (len(txt), txt.count("\n")))
    paper = rd(os.path.join(ROOT, "out", "final", "paper.tex"))
    print("  paper names 'mmkit.py': %s" % ("mmkit.py" in paper))
    print("  paper names 'verify_runbook': %s" % ("verify_runbook" in paper))
    print("  paper names '问题到手时的操作手册': %s" % ("问题到手时的操作手册" in paper))

    print("\n=== E. mode 3 wiring: any hook or CI file? ===")
    found = []
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in ("__pycache__", "_removed_20261108", ".git")]
        for f in files:
            low = f.lower()
            if low in ("pre-commit", "pre-push") or low.endswith(
                (".yml", ".yaml")
            ) and ("ci" in low or "workflow" in low or "hook" in low):
                found.append(os.path.relpath(os.path.join(base, f), ROOT))
            if low.startswith("jenkins"):
                found.append(os.path.relpath(os.path.join(base, f), ROOT))
    print("  hook/CI files: %s" % (found if found else "none"))
    print("  .git exists: %s" % os.path.exists(os.path.join(ROOT, ".git")))


if __name__ == "__main__":
    main()
