"""组合根 —— 组装 Model / View / Controller 并启动主循环。

单独成模块的意义：依赖关系在**这一个文件**里一次性决定，其它模块不负责
构造彼此。想换主题、放宽求值上限、给密码学执行器打桩，都只改这里。
"""

from __future__ import annotations

import sys
import tkinter as tk
from typing import Callable

from .config import Limits, Theme, THEME
from .controller import CalculatorController
from .model import CalculatorModel, CryptoRunner
from .view import CalculatorView


def _center(root: tk.Tk) -> None:
    """窗口居中。"""
    root.update_idletasks()
    w = root.winfo_width()
    h = root.winfo_height()
    x = (root.winfo_screenwidth() - w) // 2
    y = (root.winfo_screenheight() - h) // 2
    root.geometry(f"+{x}+{y}")


def build(
    root: tk.Tk,
    theme: Theme = THEME,
    limits: Limits | None = None,
    crypto_runner: CryptoRunner | None = None,
    on_quit: Callable[[], None] | None = None,
) -> CalculatorController:
    """在给定 root 上组装整个应用，返回 Controller（调用方需持有引用防 GC）。"""
    root.title("Calculator ∞ Alchemia")
    root.resizable(False, False)
    root.configure(bg=theme.bg)

    model = CalculatorModel(limits=limits, crypto_runner=crypto_runner)
    view = CalculatorView(root, theme=theme)
    view.pack(padx=10, pady=10, fill="both", expand=True)

    return CalculatorController(model, view, root, on_quit=on_quit)


def run(
    theme: Theme = THEME,
    limits: Limits | None = None,
    crypto_runner: CryptoRunner | None = None,
) -> None:
    """启动计算器并进入主循环。"""
    root = tk.Tk()

    def _quit() -> None:
        root.destroy()
        sys.exit(0)

    controller = build(
        root, theme=theme, limits=limits,
        crypto_runner=crypto_runner, on_quit=_quit,
    )

    # 开场打乱键盘（沿用旧版行为）
    controller.shuffle()
    _center(root)

    root.mainloop()


if __name__ == "__main__":
    run()
