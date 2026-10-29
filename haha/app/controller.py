"""Controller 层 — 控制逻辑。

连接 Model 与 View：把视图发出的用户交互事件转换为对模型的
状态变更，并驱动视图更新。本层不持有任何界面控件，也不直接读写数据文件。
"""

from .model import MessageModel
from .view import MainView


class ApplicationController:
    def __init__(self, model: MessageModel, view: MainView):
        self.model = model
        self.view = view

        # 连接视图的事件到控制器方法
        self.view.set_start_command(self.handle_start_click)
        self.view.set_message_click(self.handle_message_click)

    def handle_start_click(self) -> None:
        """处理START按钮点击"""
        if not self.model.is_displayed:
            self.model.random_helloworld()
            self.model.toggle_display()
            self.view.start_countdown(3, self._show_after_countdown)

    def _show_after_countdown(self) -> None:
        """倒计时结束后显示消息"""
        self.view.show_message(self.model.language, self.model.message, self.model.metadata)

    def handle_message_click(self, event=None) -> None:
        """点击消息后隐藏"""
        if self.model.is_displayed:
            self.model.toggle_display()
            self.view.hide_message()

    def run(self) -> None:
        """运行应用程序"""
        self.view.master.mainloop()
