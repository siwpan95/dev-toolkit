"""Model —— 全部状态与业务规则。

硬性约束：**本模块不 import tkinter**。因此可在无 GUI 环境下完整单测
（旧版 Model 虽也号称无 GUI 依赖，但它硬编码调用 ``CryptoUtils``，
无法替换、无法打桩，测试只能走真实加密路径）。

改进点：

* ``crypto_runner`` 通过构造函数注入，测试可传桩函数；
* 彩蛋命中改为**轮换**（见 :mod:`calculator.easter_eggs`），旧版同键只认一个值；
* 密码学结果写入 ``history`` 并随快照暴露——旧版存了却从不展示；
* 状态以 :class:`Snapshot` 外发，View 不需要认识本类。
"""

from __future__ import annotations

from typing import Callable

from .config import LIMITS, Limits
from .crypto import MODES
from .crypto import run as default_crypto_run
from .easter_eggs import lookup
from .engine import evaluate
from .snapshot import Action, Mode, Snapshot

#: 密码学执行器签名：``(mode, text) -> 结果字符串``
CryptoRunner = Callable[[str, str], str]

MAX_CRYPTO_INPUT = 24   # 密码学输入缓冲上限（显示区只有 13 字符宽）


class CalculatorModel:
    """计算器状态机。三个模式：四则运算 / 密码学菜单 / 密码学文本输入。"""

    def __init__(
        self,
        limits: Limits | None = None,
        crypto_runner: CryptoRunner | None = None,
    ) -> None:
        self._limits: Limits = limits or LIMITS
        self._crypto_runner: CryptoRunner = crypto_runner or default_crypto_run

        self._observers: list[Callable[[Snapshot], None]] = []

        # ── 四则运算状态 ──
        self._expression: str = ""
        self._display: str | None = None   # 求值/彩蛋结果，优先于表达式显示
        self._last_token: str = ""
        self._same_count: int = 0
        self._digit_presses: int = 0
        self._backspace_streak: int = 0
        self._equals_streak: int = 0
        self._last_eval_expr: str = ""

        # ── 彩蛋轮换游标：同一键第 n 次命中取第 n 个值 ──
        self._egg_rotation: dict[str, int] = {}

        # ── 模式与密码学状态 ──
        self._mode: Mode = Mode.CALC
        self._crypto_mode: str = ""
        self._crypto_buffer: str = ""
        self._history: list[str] = []

        self._action: Action = Action.NONE

    # ── 观察者 ────────────────────────────────────────────────
    def add_observer(self, cb: Callable[[Snapshot], None]) -> None:
        self._observers.append(cb)

    def _notify(self) -> None:
        snap = self.snapshot()
        for cb in self._observers:
            cb(snap)

    # ── 对外只读快照 ──────────────────────────────────────────
    def snapshot(self) -> Snapshot:
        """产出当前视图快照。View 只认这个，不认 Model。"""
        if self._mode is Mode.CRYPTO_INPUT:
            display = self._crypto_buffer or "_"
            spec = MODES.get(self._crypto_mode)
            spec_hint = spec.hint if spec else ""
            hint = f"{spec_hint} · _ 代表空格 · EXE 执行"
        elif self._mode is Mode.CRYPTO_MENU:
            display = "🔐"
            hint = "选择密码学模式"
        else:
            display = self._display if self._display is not None else (
                self._expression or "0"
            )
            hint = ""

        return Snapshot(
            display=display,
            expr=self._expr_line(),
            hint=hint,
            mode=self._mode,
            action=self._action,
            char_limit=self._char_limit(),
            digit_limit=self._digit_limit(),
            crypto_mode=self._crypto_mode,
            history=tuple(self._history),
        )

    def _expr_line(self) -> str:
        """小号表达式行。仅在刚求值完时回显 ``原式 =``，与旧版一致。"""
        if self._mode is not Mode.CALC:
            return ""
        if self._action is Action.NONE and self._last_eval_expr:
            return f"{self._last_eval_expr} ="
        return ""

    # ── 上限 ──────────────────────────────────────────────────
    def _char_limit(self) -> bool:
        return len(self._expression) >= self._limits.max_chars

    def _digit_limit(self) -> bool:
        return self._digit_presses >= self._limits.max_digit_presses

    def _reset_expression(self) -> None:
        self._expression = ""
        self._last_token = ""
        self._same_count = 0
        self._digit_presses = 0

    def _recalc_digit_presses(self) -> None:
        self._digit_presses = sum(
            1 for ch in self._expression if ch.isdigit() or ch == "."
        )

    # ── 主入口 ────────────────────────────────────────────────
    def push(self, token: str) -> None:
        """处理一个按键，更新状态并通知观察者。"""
        self._action = Action.NONE

        if self._mode is Mode.CRYPTO_MENU:
            self._push_menu(token)
        elif self._mode is Mode.CRYPTO_INPUT:
            self._push_input(token)
        else:
            self._push_calc(token)

        self._notify()

    # ── 模式一：四则运算 ──────────────────────────────────────
    def _push_calc(self, token: str) -> None:
        self._last_eval_expr = ""

        if token == "#":
            self._mode = Mode.CRYPTO_MENU
            self._action = Action.LAYOUT_CHANGED
            return

        if token == "←":
            self._equals_streak = 0
            self._backspace_streak += 1
            if self._backspace_streak >= self._limits.triple_backspace_quit:
                self._action = Action.QUIT
                return
            self._display = None
            if self._expression:
                self._expression = self._expression[:-1]
                self._recalc_digit_presses()
            self._last_token = ""
            self._same_count = 0
            return

        if token == "=":
            self._backspace_streak = 0
            self._equals_streak += 1
            if self._equals_streak >= self._limits.triple_equals_shuffle:
                self._equals_streak = 0
                self._reset_expression()
                self._display = None
                self._action = Action.SHUFFLE
                return
            expr = self._expression
            self._evaluate(expr)
            self._last_eval_expr = expr
            self._reset_expression()
            return

        self._backspace_streak = 0
        self._equals_streak = 0

        # 连按同一键 N 次 → 清空
        if token == self._last_token:
            self._same_count += 1
        else:
            self._same_count = 1
            self._last_token = token

        if self._same_count >= self._limits.triple_same_reset:
            self._reset_expression()
            self._display = None
            return

        # 上限：静默忽略（沿用旧行为）
        if self._char_limit():
            return
        if (token.isdigit() or token == ".") and self._digit_limit():
            return

        self._display = None
        if token.isdigit() or token == ".":
            self._digit_presses += 1

        self._expression += token

    def _evaluate(self, expr: str) -> None:
        """求值并把结果写入 ``_display``。命中彩蛋时展示彩蛋文案。"""
        stripped = expr.strip()
        if not stripped:
            self._display = "0"
            return

        egg = lookup(stripped, self._egg_rotation.get(stripped, 0))
        if egg is not None:
            self._egg_rotation[stripped] = self._egg_rotation.get(stripped, 0) + 1
            self._display = egg
            return

        self._display = evaluate(stripped)

    # ── 模式二：密码学菜单 ────────────────────────────────────
    def _push_menu(self, token: str) -> None:
        if token == "ESC":
            self._mode = Mode.CALC
            self._action = Action.LAYOUT_CHANGED
            return
        if token in MODES:
            self._crypto_mode = token
            self._crypto_buffer = ""
            self._mode = Mode.CRYPTO_INPUT
            self._action = Action.LAYOUT_CHANGED

    # ── 模式三：密码学文本输入 ────────────────────────────────
    def _push_input(self, token: str) -> None:
        if token == "ESC":
            self._mode = Mode.CRYPTO_MENU
            self._crypto_mode = ""
            self._crypto_buffer = ""
            self._action = Action.LAYOUT_CHANGED
            return

        if token == "EXE":
            text = self._crypto_buffer
            result = self._crypto_runner(self._crypto_mode, text)
            self._remember(self._crypto_mode, text, result)
            self._display = result
            self._expression = ""
            self._last_eval_expr = ""
            self._crypto_mode = ""
            self._crypto_buffer = ""
            self._mode = Mode.CALC
            self._action = Action.LAYOUT_CHANGED
            return

        if token == "←":
            self._crypto_buffer = self._crypto_buffer[:-1]
            return

        if len(self._crypto_buffer) >= MAX_CRYPTO_INPUT:
            return

        self._crypto_buffer += token

    def _remember(self, mode: str, text: str, result: str) -> None:
        self._history.append(f"{mode}: {text} → {result}")
        if len(self._history) > 5:
            self._history.pop(0)
