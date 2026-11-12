"""修 redteam 自检：样本的 pass 探针要写 tried，钉数 7 -> 9（第 121 轮）。

第 121 轮新增两条规则后，自检样本本身不合规：
  · pass 探针必须写 tried（>=30 字）
  · finding 必须带 where/evidence
所以样本要补齐，并把回归链的钉数改成实际条数。
"""
import io
import re

HERE = r"C:\Users\21246\Documents\deepseek-harness\default-workspace\model1-arch"
p = HERE + r"\redteam.py"
s = io.open(p, encoding="utf-8").read()

# 给自检里所有 verdict="pass" 的样本探针补 tried
old_pass = 'dict(probe=spec["probes"][1], verdict="pass", note="")'
new_pass = ('dict(probe=spec["probes"][1], verdict="pass", note="",\n'
            '                             tried="查过了这一板对应的工件与代码：'
            '跑了该板的自检、看了相关实现，没有发现问题。")')
if old_pass in s:
    s = s.replace(old_pass, new_pass, 1)
    print("样本 pass 探针已补 tried")

# 若样本里还有别的 pass 写法（单引号/多行），再兜一层
s = s.replace('verdict="pass", note="")',
              'verdict="pass", note="",\n'
              '                             tried="查过了这一板对应的工件与代码：'
              '跑了该板的自检、看了相关实现，没有发现问题。")')
io.open(p, "w", encoding="utf-8", newline="\n").write(s)

# 钉数：数一下实际断言条数
m = re.search(r"def selftest\(\).*?\n(.*?)\n    print\(", s, re.S)
n_ck = len(re.findall(r"\bck\(", m.group(1))) if m else 0
q = HERE + r"\tests\run_all.py"
t = io.open(q, encoding="utf-8").read()
t = t.replace('("redteam.py", ["selftest"], 7)', '("redteam.py", ["selftest"], %d)' % n_ck)
io.open(q, "w", encoding="utf-8", newline="\n").write(t)
print("redteam 自检断言数 =", n_ck, "（钉数已同步）")
