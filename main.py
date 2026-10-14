#!/usr/bin/env python3
"""入口 —— ``python main.py``。

Python 运行脚本时会把脚本所在目录放进 ``sys.path[0]``，
因此无论当前工作目录在哪，同级的 ``calculator`` 包都能被导入，
不需要任何 sys.path 操作。

等价写法：``python -m calculator``（见 ``calculator/__main__.py``）。
"""

from __future__ import annotations

from calculator.app import run

if __name__ == "__main__":
    run()
