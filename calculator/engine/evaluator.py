"""求值：对 RPN 序列做栈式计算，并格式化结果。

护栏（旧实现统统没有）：
  * ``max_result_abs`` —— 结果规模上限，防止超大数把显示区撑爆；
  * NaN / inf 显式判为错误（旧版只判了 NaN）；
  * 除零独立错误码。
"""

from __future__ import annotations

import math

from ..config import LIMITS
from .errors import ERROR_LABELS, CalcError
from .parser import to_rpn
from .tokenizer import NUM, OP, Token, tokenize


def _apply(op: str, a: float, b: float) -> float:
    """执行二元运算。``a`` 是先弹出的右操作数。"""
    if op == "+":
        return b + a
    if op == "-":
        return b - a
    if op == "×":
        return b * a
    if op == "÷":
        if a == 0:
            raise CalcError("div0", "除数为零")
        return b / a
    raise CalcError("syntax", f"未知运算符 {op!r}")  # pragma: no cover


def eval_rpn(rpn: list[Token]) -> float:
    """对 RPN 序列求值，返回 float。"""
    stack: list[float] = []

    for tok in rpn:
        if tok.kind == NUM:
            stack.append(float(tok.value))
            continue

        if tok.kind == OP:
            if tok.value == "u-":
                if not stack:
                    raise CalcError("syntax", "一元负号缺少操作数")
                stack.append(-stack.pop())
                continue
            if len(stack) < 2:
                raise CalcError("syntax", f"运算符 {tok.value!r} 缺少操作数")
            a = stack.pop()
            b = stack.pop()
            stack.append(_apply(tok.value, a, b))
            continue

        raise CalcError("syntax", f"RPN 中出现非法 Token {tok!r}")  # pragma: no cover

    if len(stack) != 1:
        raise CalcError("syntax", "表达式不完整")

    value = stack[0]
    if math.isnan(value) or math.isinf(value):
        raise CalcError("nan", "结果非有限数")
    if abs(value) > LIMITS.max_result_abs:
        raise CalcError("overflow", "结果超出可表示范围")
    return value


def format_result(value: float) -> str:
    """按旧版观感格式化：整数不带小数点，浮点最多 6 位小数。"""
    if value == int(value) and abs(value) < 1e15:
        return str(int(value))
    text = f"{value:{LIMITS.float_format}}".rstrip("0").rstrip(".")
    if len(text) > LIMITS.max_result_digits:
        raise CalcError("too_long", "结果过长")
    return text or "0"


def evaluate(expr: str) -> str:
    """端到端求值入口：字符串 → 结果字符串。

    永不抛异常；失败时返回错误文案（默认 ``"fool"``，与旧版一致）。
    """
    stripped = expr.strip()
    if not stripped:
        return ERROR_LABELS["empty"]

    try:
        rpn = to_rpn(tokenize(stripped))
        return format_result(eval_rpn(rpn))
    except CalcError as exc:
        return ERROR_LABELS.get(exc.code, "fool")
    except (ValueError, OverflowError, ZeroDivisionError):
        return ERROR_LABELS["syntax"]
