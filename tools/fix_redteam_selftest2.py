"""修 redteam 自检的最后一条：零 finding 的样本也要给 pass 探针写 tried。

第 121 轮新增「pass 必须写 tried」后，这个样本（全部 pass）因缺 tried
被判 FAIL，而不是预期的 WARN。
"""
import io

HERE = r"C:\Users\21246\Documents\deepseek-harness\default-workspace\model1-arch"
p = HERE + r"\redteam.py"
s = io.open(p, encoding="utf-8").read()

old = 'probes=[dict(probe=p, verdict="pass") for p in spec["probes"]],'
new = ('probes=[dict(probe=p, verdict="pass",\n'
       '                        tried="查过了这一板对应的工件与代码：跑了该板的自检、"\n'
       '                        "看了相关实现，没有发现问题。")\n'
       '                for p in spec["probes"]],')
assert old in s, "零 finding 样本块未匹配"
s = s.replace(old, new, 1)
io.open(p, "w", encoding="utf-8", newline="\n").write(s)
print("零 finding 样本已补 tried")
