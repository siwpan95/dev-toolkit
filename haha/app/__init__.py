"""haha 应用包 — 按 MVC 架构拆分的 Hello World 展示程序。

包结构:
- config:      语言映射表与路径常量 (Model/View/Controller 共享)
- model:       MessageModel — 数据与业务逻辑
- view:        MainView — 用户界面 (tkinter)
- controller:  ApplicationController — 控制逻辑

入口见顶层 main.py。
"""

__version__ = "1.0.0"
