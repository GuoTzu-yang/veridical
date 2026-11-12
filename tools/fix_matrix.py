import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
p = os.path.join(HERE, "插件速查.md")
s = open(p, encoding="utf-8").read()
reps = [
 ('& $py falsify.py --data X.xlsx --claim "A:正,B:负"',
  '& $py falsify.py counter --data X.xlsx --y Y --x A --sign 1   # 1=正 -1=负'),
 ('& $py mmkit.py ahp     --ahp "1,3,5;1/3,1,3;1/5,1/3,1" --names "指标1,指标2,指标3" --json',
  '& $py mmkit.py ahp     --ahp "1,3,5|1/3,1,3|1/5,1/3,1" --names "指标1,指标2,指标3" --json'),
 ('& $py mmkit.py greyrel --data X.xlsx --directions "1,-1,1" --normalize range --json',
  '& $py mmkit.py greyrel --matrix "3,2,1|2,3,4|3,4,5" --directions "1,-1,1" --json'),
]
n = 0
for a, b in reps:
    if a in s:
        s = s.replace(a, b); n += 1
open(p, "w", encoding="utf-8", newline="\n").write(s)
print("  速查修正 %d 处" % n)

# verify_matrix.py 同步
p2 = os.path.join(HERE, "tools", "verify_matrix.py")
s2 = open(p2, encoding="utf-8").read()
s2 = s2.replace('["falsify.py","--data",D,"--claim","反应温度:正,操作压力:负"]',
                '["falsify.py","counter","--data",D,"--y","产量","--x","反应温度","--sign","1"]')
s2 = s2.replace('["mmkit.py","ahp","--ahp","1,3,5;1/3,1,3;1/5,1/3,1","--names","温度,压力,时间","--json"]',
                '["mmkit.py","ahp","--ahp","1,3,5|1/3,1,3|1/5,1/3,1","--names","温度,压力,时间","--json"]')
s2 = s2.replace('["mmkit.py","greyrel","--data",D,"--directions","1,-1,1","--normalize","range","--json"]',
                '["mmkit.py","greyrel","--matrix","3,2,1|2,3,4|3,4,5","--directions","1,-1,1","--json"]')
open(p2, "w", encoding="utf-8", newline="\n").write(s2)
print("  verify_matrix 同步")