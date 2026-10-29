"""表达式引擎：词法 → 语法 → 求值 三段式，取代旧的 ``eval()``。

对外只需 :func:`evaluate`：

    >>> from calculator.engine import evaluate
    >>> evaluate("2+3×4")
    '14'

设计取舍见各子模块 docstring。选择 Shunting-yard 而非 AST：
本计算器语法极简（二元运算 + 括号 + 一元负号），RPN 足够，
且比递归下降少一层结构，单测写起来更直接。
"""

from __future__ import annotations

from .errors import CalcError, ERROR_LABELS
from .evaluator import evaluate, eval_rpn, format_result
from .parser import to_rpn
from .tokenizer import Token, tokenize

__all__ = [
    "CalcError",
    "ERROR_LABELS",
    "Token",
    "evaluate",
    "eval_rpn",
    "format_result",
    "to_rpn",
    "tokenize",
]
