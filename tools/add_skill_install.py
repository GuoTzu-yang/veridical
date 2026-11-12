import io
import os

f = os.path.expanduser("~/.dsh/plugins/sample/lib/index.js")
s = io.open(f, encoding="utf-8").read()

# 1) 引入 readdirSync / cpSync
old_imp = 'import { existsSync } from "node:fs";'
new_imp = 'import { cpSync, existsSync, readdirSync } from "node:fs";'
if old_imp in s:
    s = s.replace(old_imp, new_imp, 1)

# 2) 插入 skill 自安装函数（放在 apply 之前，不带多余的尾部换行）
old_apply = 'function apply(ctx, config = {}) {'
new_apply = '''/**
 * 把插件自带的技能装到用户级技能目录。
 *
 * DSH 的技能扫描根只有这几个：
 *   <project>/.dsh/skills、<project>/.agents/skills、
 *   $DSH_HOME/skills、$AGENTS_HOME/skills
 * 插件包内的 skills/ 不在扫描范围，所以技能必须复制过去才能被发现。
 * 手抄一次能生效，换机器或重装就失效，因此放在插件加载时自动做。
 */
function ensureSkillsInstalled() {
  try {
    const here = dirname(new URL(import.meta.url).pathname.replace(/^\\/([A-Za-z]:)/, "$1"));
    const src = join(here, "..", "skills");
    if (!existsSync(src)) return;
    const dstRoot = join(homedir(), ".dsh", "skills");
    for (const name of readdirSync(src)) {
      const dst = join(dstRoot, name);
      if (existsSync(dst)) continue;
      cpSync(join(src, name), dst, { recursive: true });
    }
  } catch {
    /* 装技能失败不该阻断工具注册 */
  }
}

function apply(ctx, config = {}) {'''
assert old_apply in s, "apply anchor"
s = s.replace(old_apply, new_apply, 1)

# 3) 调用点：直接锚在 cfg 那一行，避开空行差异
old_cfg = '  const cfg = config || {};'
new_cfg = '  ensureSkillsInstalled();\n  const cfg = config || {};'
assert old_cfg in s, "cfg anchor"
s = s.replace(old_cfg, new_cfg, 1)

io.open(f, "w", encoding="utf-8", newline="\n").write(s)
print("已加 skill 自安装")
print("  cpSync =", s.count("cpSync"))
print("  ensureSkillsInstalled =", s.count("ensureSkillsInstalled"))
