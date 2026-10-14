"""View —— 纯渲染层。

相对旧版的实质变化：

1. **不再认识 Model**。旧签名是 ``on_model_change(self, model: "CalculatorModel")``，
   类型注解里就写着 Model；现在只接收 :class:`Snapshot`（见 :mod:`calculator.snapshot`），
   与 Model 零 import 关系。
2. **按键通过统一回调上报**，而不是「Controller 遍历 View 的常量逐个绑定」。
   旧版 Controller 写 ``for token in BUTTON_TOKENS`` —— 那是 View 层的布局数据，
   Controller 本不该知道；现在 Controller 只注册一个 ``on_press(token)``。
3. **支持运行时切换键盘布局**（四则 / 密码学菜单 / 字母输入），
   这是让密码学功能真正可达的前提。
4. 配色从 View 抽到 :class:`calculator.config.Theme`，支持换肤。
"""

from __future__ import annotations

import random
import tkinter as tk
from typing import Callable

from .config import (
    ALWAYS_ACTIVE,
    ALPHA_LAYOUT,
    BTN_FONT,
    BTN_FONT_SMALL,
    CRYPTO_MENU_LAYOUT,
    DISPLAY_FONT_MIN,
    DISPLAY_FONT_TIERS,
    EMPTY,
    EXPR_FONT,
    NUMPAD_LAYOUT,
    OPERATORS,
    Layout,
    Theme,
    THEME,
)
from .snapshot import Mode, Snapshot

#: 密码学相关按键（用命令色区分）
CRYPTO_KEYS = frozenset({"#", "ESC", "EXE"})


class CalculatorView(tk.Frame):
    """计算器界面。只做渲染与事件上报，不含任何业务判断。"""

    def __init__(self, master: tk.Misc, theme: Theme = THEME) -> None:
        super().__init__(master, bg=theme.bg)
        self._theme = theme
        self._press_cb: Callable[[str], None] | None = None
        self._buttons: dict[str, tk.Button] = {}
        self._order: list[str] = []
        self._mode: Mode | None = None

        self._disp_var = tk.StringVar(value="0")
        self._expr_var = tk.StringVar(value="")
        self._hint_var = tk.StringVar(value="")

        self._build_display()
        self.apply_layout(NUMPAD_LAYOUT)

    # ── 事件注册 ──────────────────────────────────────────────
    def set_press_handler(self, cb: Callable[[str], None]) -> None:
        """Controller 注册唯一的按键回调。View 不关心谁来接。"""
        self._press_cb = cb

    # ── 显示区 ────────────────────────────────────────────────
    def _build_display(self) -> None:
        t = self._theme
        disp = tk.Frame(self, bg=t.display_bg)
        disp.grid(row=0, column=0, columnspan=8, sticky="ew", padx=10, pady=10)

        self._expr_label = tk.Label(
            disp, textvariable=self._expr_var, bg=t.display_bg, fg=t.expr_fg,
            font=EXPR_FONT, anchor="e", padx=16,
        )
        self._expr_label.pack(fill="x", pady=(12, 0))

        self._disp_label = tk.Label(
            disp, textvariable=self._disp_var, bg=t.display_bg, fg=t.display_fg,
            font=DISPLAY_FONT_TIERS[0][1], anchor="e", padx=16,
        )
        self._disp_label.pack(fill="x", pady=(2, 6))

        self._hint_label = tk.Label(
            disp, textvariable=self._hint_var, bg=t.display_bg, fg=t.expr_fg,
            font=EXPR_FONT, anchor="e", padx=16,
        )
        self._hint_label.pack(fill="x", pady=(0, 12))

        sep = tk.Frame(self, bg=t.sep_color, height=1)
        sep.grid(row=1, column=0, columnspan=8, sticky="ew", padx=10, pady=6)

    def _font_for(self, text: str) -> tuple:
        for max_len, font in DISPLAY_FONT_TIERS:
            if len(text) <= max_len:
                return font
        return DISPLAY_FONT_MIN

    # ── 键盘布局 ──────────────────────────────────────────────
    def apply_layout(self, layout: Layout, shuffle: bool = False) -> None:
        """按给定布局重建键盘。``shuffle=True`` 时打乱顺序。"""
        for btn in self._buttons.values():
            btn.destroy()
        self._buttons.clear()

        self._order = list(layout.tokens)
        if shuffle:
            movable = [t for t in self._order if t != EMPTY]
            random.shuffle(movable)
            it = iter(movable)
            self._order = [EMPTY if t == EMPTY else next(it) for t in self._order]

        cols = layout.cols
        for idx, token in enumerate(self._order):
            r, c = divmod(idx, cols)
            bg, fg = self._normal_colors(token)
            is_empty = token == EMPTY
            font = BTN_FONT if len(token) <= 2 else BTN_FONT_SMALL

            btn = tk.Button(
                self,
                text="" if is_empty else token,
                bg=bg, fg=fg,
                activebackground=bg if is_empty else fg,
                activeforeground=fg if is_empty else bg,
                font=font,
                width=5, height=2,
                relief="flat", borderwidth=0,
                cursor="arrow" if is_empty else "hand2",
                takefocus=0,
                state="disabled" if is_empty else "normal",
            )
            btn.grid(row=r + 2, column=c, padx=4, pady=4, sticky="nsew")
            if not is_empty:
                btn.config(command=lambda t=token: self._press(t))
                btn.bind("<Enter>", lambda e, b=btn, t=token: self._hover(b, t, True))
                btn.bind("<Leave>", lambda e, b=btn, t=token: self._hover(b, t, False))
            self._buttons[token] = btn

        rows = 2 + (len(self._order) + cols - 1) // cols
        for r in range(2, rows + 1):
            self.rowconfigure(r, weight=1)
        for c in range(8):
            self.columnconfigure(c, weight=1 if c < cols else 0)

    def layout_for(self, mode: Mode) -> Layout:
        """模式 → 布局。View 自己知道该画什么键盘。"""
        if mode is Mode.CRYPTO_MENU:
            return CRYPTO_MENU_LAYOUT
        if mode is Mode.CRYPTO_INPUT:
            return ALPHA_LAYOUT
        return NUMPAD_LAYOUT

    def shuffle_current(self) -> None:
        """打乱当前键盘（连按三次等号的彩蛋）。"""
        self.apply_layout(self.layout_for(self._mode or Mode.CALC), shuffle=True)

    # ── 配色 ──────────────────────────────────────────────────
    def _normal_colors(self, token: str) -> tuple[str, str]:
        t = self._theme
        if token == EMPTY:
            return t.bg, t.bg
        if token == "=" or token == "EXE":
            return t.btn_eq, t.btn_eq_fg
        if token == "←":
            return t.btn_back, t.btn_fg
        if token in CRYPTO_KEYS or token in CRYPTO_MENU_LAYOUT.tokens:
            return t.btn_cmd, t.btn_fg
        if token in OPERATORS:
            return t.btn_op, t.btn_fg
        return t.btn_num, t.btn_fg

    def _hover_colors(self, token: str) -> tuple[str, str]:
        t = self._theme
        if token == EMPTY:
            return t.bg, t.bg
        if token == "=" or token == "EXE":
            return t.btn_eq_hv, t.btn_eq_fg
        if token == "←":
            return t.btn_back_hv, t.btn_fg
        if token in CRYPTO_KEYS or token in CRYPTO_MENU_LAYOUT.tokens:
            return t.btn_cmd_hv, t.btn_fg
        if token in OPERATORS:
            return t.btn_op_hv, t.btn_fg
        return t.btn_num_hv, t.btn_fg

    def _hover(self, btn: tk.Button, token: str, entering: bool) -> None:
        if token == EMPTY:
            return
        if str(btn.cget("state")) == "disabled":
            return
        bg, _ = self._hover_colors(token) if entering else self._normal_colors(token)
        btn.config(bg=bg)

    # ── 渲染 ──────────────────────────────────────────────────
    def render(self, snap: Snapshot) -> None:
        """把快照画出来。这是 View 唯一的入口。"""
        if snap.mode is not self._mode:
            self._mode = snap.mode
            self.apply_layout(self.layout_for(snap.mode))

        text = snap.display
        self._disp_var.set(text)
        self._disp_label.config(font=self._font_for(text))
        self._expr_var.set(snap.expr)
        self._hint_var.set(snap.hint)

        self._apply_enabled(snap)

    def _apply_enabled(self, snap: Snapshot) -> None:
        """按快照里的上限标志置灰按键。密码学面板不设限。"""
        t = self._theme
        limited = snap.mode is Mode.CALC and (snap.char_limit or snap.digit_limit)

        for token, btn in self._buttons.items():
            if token == EMPTY:
                continue
            if not limited or token in ALWAYS_ACTIVE:
                bg, fg = self._normal_colors(token)
                btn.config(bg=bg, fg=fg, state="normal", cursor="hand2")
                continue

            disabled = snap.char_limit or (
                snap.digit_limit and (token.isdigit() or token == ".")
            )
            if disabled:
                btn.config(
                    bg=t.btn_dis, fg=t.btn_dis_fg,
                    state="disabled", cursor="arrow",
                )
            else:
                bg, fg = self._normal_colors(token)
                btn.config(bg=bg, fg=fg, state="normal", cursor="hand2")

    # ── 事件上报 ──────────────────────────────────────────────
    def _press(self, token: str) -> None:
        if self._press_cb is not None:
            self._press_cb(token)
