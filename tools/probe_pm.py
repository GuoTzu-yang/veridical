import os
import sys
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import verify
print("  PLAUSIBLE_META 大小:", len(verify.PLAUSIBLE_META))
pm = sorted(verify.PLAUSIBLE_META)
print("  前 30 个:", pm[:30])
print("  含 0.9999:", 0.9999 in verify.PLAUSIBLE_META)
print("  含 0.000123:", 0.000123 in verify.PLAUSIBLE_META)
# 直接测
line = "The model achieves an R-squared of 0.9999 and a cross-validated RMSE of 0.000123, which is unprecedented. "
print("  单行提取:", verify.extract_numbers(line))