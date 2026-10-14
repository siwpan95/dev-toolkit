"""把仓库根目录挂到 sys.path，让测试可以直接 import ``calculator``。

仓库根目录是包 ``calculator/`` 的父目录；测试跑在 ``tests/`` 下，
所以需要这一步。（无需安装、无需环境变量。）
"""

from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
