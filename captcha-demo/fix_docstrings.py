#!/usr/bin/env python3
"""
修复 captcha_model.py 中的文档字符串问题
将 \"\"\" ... \"\"\" 替换为三重引号文档字符串

用法:
    python fix_docstrings.py                    # 默认处理本仓 model/captcha_model.py
    python fix_docstrings.py <captcha_model.py 路径>   # 指定其它副本
"""

import sys
import os
from pathlib import Path

# 目标文件解析：命令行参数 → 本文件同级的 model/captcha_model.py → fail-loud
DEFAULT_TARGET = Path(__file__).resolve().parent / "model" / "captcha_model.py"


def resolve_target():
    if len(sys.argv) > 1:
        return Path(sys.argv[1])
    if DEFAULT_TARGET.is_file():
        return DEFAULT_TARGET
    raise SystemExit(
        f"[fix_docstrings] 找不到目标文件：{DEFAULT_TARGET}\n"
        f"  用法：python {Path(__file__).name} <captcha_model.py 路径>"
    )


file_path = resolve_target()

# 读取文件
with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# 修复每一行
fixed_count = 0
for i, line in enumerate(lines):
    if '\\"\\"\\"' in line:
        lines[i] = line.replace('\\"\\"\\"', '"""')
        fixed_count += 1

# 写回文件
with open(file_path, 'w', encoding='utf-8') as f:
    f.writelines(lines)

print(f"已修复: {file_path}")
print(f"修复了 {fixed_count} 行")
