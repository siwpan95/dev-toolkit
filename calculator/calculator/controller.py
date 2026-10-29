"""Controller —— 把 Model 与 View 接起来，并承担副作用。

职责边界（这次拆分明确了）：

* 把按键从 View 转交给 Model；
* 处理 Model 表达不了、View 不该做的副作用：退出进程、打乱键盘；
* **不再引用任何布局常量**——旧版写 ``for token in BUTTON_TOKENS``
  去逐个绑定按钮，等于 Controller 依赖了 View 的内部数据；
  现在只向 View 注册一个回调，布局怎么排是 View 自己的事。
"""

from __future__ import annotations

import tkinter as tk
from typing import Callable

from .model import CalculatorModel
from .snapshot import Action, Snapshot
from .view import CalculatorView


class CalculatorController:
    """Model ↔ View 的接线器。"""

    def __init__(
        self,
        model: CalculatorModel,
        view: CalculatorView,
        root: tk.Misc,
        on_quit: Callable[[], None] | None = None,
    ) -> None:
        self._model = model
        self._view = view
        self._root = root
        self._on_quit = on_quit

        model.add_observer(self._on_model_change)
        view.set_press_handler(self._on_press)

        # 首帧：把初始状态画出来
        view.render(model.snapshot())

    # ── 只读访问器（供组合根做开场动画等，避免外部摸私有成员） ──
    @property
    def model(self) -> CalculatorModel:
        return self._model

    @property
    def view(self) -> CalculatorView:
        return self._view

    def shuffle(self) -> None:
        """打乱键盘并重画。连按三次等号时由本类自动调用，也可外部触发。"""
        self._view.shuffle_current()
        self._view.render(self._model.snapshot())

    # ── View → Model ──────────────────────────────────────────
    def _on_press(self, token: str) -> None:
        self._model.push(token)
        self._handle_side_effects(self._model.snapshot())

    # ── Model → View ──────────────────────────────────────────
    def _on_model_change(self, snap: Snapshot) -> None:
        self._view.render(snap)

    # ── 副作用 ────────────────────────────────────────────────
    def _handle_side_effects(self, snap: Snapshot) -> None:
        if snap.action is Action.QUIT:
            if self._on_quit is not None:
                self._on_quit()
            else:
                self._root.destroy()
            return

        if snap.action is Action.SHUFFLE:
            self._view.shuffle_current()
            # 打乱后重画一次，确保按键状态与当前快照一致
            self._view.render(self._model.snapshot())
