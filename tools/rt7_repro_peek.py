import io, json
s = json.load(io.open("schema.json", encoding="utf-8"))
print(list(s.keys())[:12])
print("n_commands =", s.get("n_commands"))
cmds = s.get("commands") or s.get("cmds") or []
print("len(commands) =", len(cmds))
if cmds:
    print("cmd0 keys:", list(cmds[0].keys())[:14])
    tot = 0
    for c in cmds:
        par = c.get("params") or c.get("args") or {}
        tot += len(par) if hasattr(par, "__len__") else 0
    print("sum(len(params)) =", tot)
