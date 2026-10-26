# -*- coding: utf-8 -*-
"""无头自检（不开窗口）：四则运算状态机 + 除零彩蛋。

用法：python selfcheck.py    （退出 0 = 通过）
GUI 入口仍是 `python main.py`。
"""
from __future__ import annotations

from calculator.model import CalculatorModel


def press(tokens: list[str]) -> str:
    model = CalculatorModel()
    for token in tokens:
        model.push(token)
    return model.snapshot().display


def main() -> int:
    cases = {
        ("1", "+", "2", "="): "3",
        ("8", "/", "2", "="): "4",
        ("9", "*", "9", "="): "81",
        ("1", "/", "0", "="): "fool",  # 除零彩蛋，与旧版一致
    }
    for tokens, expected in cases.items():
        got = press(list(tokens))
        if got != expected:
            print(f"FAIL {' '.join(tokens)} -> {got!r}, expected {expected!r}")
            return 1

    # 表达式行长：刚求值完应回显「原式 =」
    model = CalculatorModel()
    for token in ("1", "+", "2", "="):
        model.push(token)
    if model.snapshot().expr != "1+2 =":
        print(f"FAIL expression line: {model.snapshot().expr!r}")
        return 1

    print("calculator selfcheck ok: 4 arithmetic cases + expression line")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
