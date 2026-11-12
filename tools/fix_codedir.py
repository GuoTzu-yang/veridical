import io
import os

f = os.path.expanduser("~/.dsh/plugins/sample/lib/index.js")
s = io.open(f, encoding="utf-8").read()

# 1) resolveCodeDir 接受显式 cwd，并用它替代 process.cwd()
old = '''function resolveCodeDir(config) {
  const cands = [];
  if (config && config.codeDir) cands.push(config.codeDir);
  const here = dirname(new URL(import.meta.url).pathname.replace(/^\\/([A-Za-z]:)/, "$1"));
  cands.push(join(here, "..", "python")); // 插件内自带
  // 从当前工作目录往上找 model1-arch
  let cur = process.cwd();'''
new = '''function resolveCodeDir(config, cwd) {
  const cands = [];
  if (config && config.codeDir) cands.push(config.codeDir);
  const here = dirname(new URL(import.meta.url).pathname.replace(/^\\/([A-Za-z]:)/, "$1"));
  cands.push(join(here, "..", "python")); // 插件内自带
  // 优先用调用方给的 cwd（工具参数），否则退回进程 cwd。
  // 只用 process.cwd() 时，GUI 里调用会因为宿主目录不是工程目录而找不到代码。
  let cur = cwd || process.cwd();'''
assert old in s, "resolveCodeDir anchor"
s = s.replace(old, new, 1)

# 2) runPy 把 cwd 传下去
old2 = '''  const codeDir = resolveCodeDir(config);'''
new2 = '''  const codeDir = resolveCodeDir(config, cwd);'''
assert old2 in s, "runPy anchor"
s = s.replace(old2, new2, 1)

# 3) runPy 里若 cwd 未给，补一个默认
old3 = '''async function runPy(config, script, args, cwd) {'''
new3 = '''async function runPy(config, script, args, cwd) {'''
s = s.replace(old3, new3, 1)

io.open(f, "w", encoding="utf-8", newline="\n").write(s)
print("已改 resolveCodeDir(config, cwd)")
print("  resolveCodeDir(config, cwd) =", s.count("resolveCodeDir(config, cwd)"))
print("  cwd || process.cwd() =", s.count("cwd || process.cwd()"))
