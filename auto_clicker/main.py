"""连点器入口。

项目已拆分：core(点击引擎/配置) + input(热键) + ui(界面)，本文件只负责拉起界面。
运行：  python main.py        （带控制台，方便看报错）
或：    python main.pyw       （无控制台，日常使用）
"""

from ui.app import main

if __name__ == "__main__":
    main()
