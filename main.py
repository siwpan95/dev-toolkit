"""程序入口 — 组装 MVC 并启动应用。

按 Model → View → Controller 的顺序实例化各层，
由控制器负责把视图事件与模型状态连接起来，最后进入主事件循环。
"""

import tkinter as tk

from app.model import MessageModel
from app.view import MainView
from app.controller import ApplicationController


def main():
    root = tk.Tk()
    model = MessageModel()
    view = MainView(root)
    controller = ApplicationController(model, view)
    controller.run()


if __name__ == "__main__":
    main()
