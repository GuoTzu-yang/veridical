import io
import os

f = os.path.expanduser("~/.dsh/plugins/sample/lib/index.js")
s = io.open(f, encoding="utf-8").read()

old1 = '''        return {
          ok: r.code === 0 && parsed !== null,
          exitCode: r.code,
          data: parsed ? safeJson(parsed) : undefined,
          text: parsed ? undefined : clean((r.stdout || r.stderr || "").slice(0, 40000)),
        };'''
new1 = '''        const body = parsed
          ? safeJson(parsed)
          : clean((r.stdout || r.stderr || "").slice(0, 40000));
        return {
          text: (r.code === 0 ? "" : "[exit " + r.code + "] ") + body,
        };'''

old2 = '''        return {
          ok: r.code === 0,
          exitCode: r.code,
          text: clean(((r.stdout || "") + (r.stderr ? "\\n" + r.stderr : "")).slice(0, 60000)),
        };'''
new2 = '''        return {
          text: (r.code === 0 ? "" : "[exit " + r.code + "] ")
            + clean(((r.stdout || "") + (r.stderr ? "\\n" + r.stderr : "")).slice(0, 60000)),
        };'''

n = 0
if old1 in s:
    s = s.replace(old1, new1, 1)
    n += 1
if old2 in s:
    s = s.replace(old2, new2, 1)
    n += 1

io.open(f, "w", encoding="utf-8", newline="\n").write(s)
print("替换 %d 处" % n)
print("剩余 ok: r.code =", s.count("ok: r.code"))
print("text-only 返回 =", s.count("text: (r.code === 0"))
