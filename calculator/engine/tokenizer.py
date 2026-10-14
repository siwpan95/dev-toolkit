"""词法分析：把中缀表达式字符串切成 Token 序列。

编译前端第一阶段。只做「认字」，不判断结构是否合法
（结构问题交给 :mod:`parser`）。

关键安全设计：本 tokenizer **不认识** ``**``。
旧实现用 eval() 加字符白名单，白名单里含 ``*``，于是 ``9**9**9``
能一路通过校验并交给解释器——那是货真价实的 CPU/内存炸弹。
这里从词法层面直接拒掉，炸弹根本构造不出来。
"""

from __future__ import annotations

from dataclasses import dataclass

from .errors import CalcError

NUM = "NUM"
OP = "OP"
LPAREN = "LPAREN"
RPAREN = "RPAREN"

#: 支持的二元运算符。（注意：没有 "^" 也没有 "**"）
BINARY_OPS: frozenset[str] = frozenset({"+", "-", "×", "÷"})


@dataclass(frozen=True)
class Token:
    """一个词法单元。``pos`` 用于报错定位。"""

    kind: str
    value: str
    pos: int = 0

    def __repr__(self) -> str:  # pragma: no cover - 调试辅助
        return f"Token({self.kind}, {self.value!r})"


def _is_unary_position(tokens: list[Token]) -> bool:
    """判断即将读入的 '-' 是否为一元负号。

    一元：表达式开头、紧跟在 '(' 之后、或紧跟在另一个运算符之后。
    其余情况（前面是数字或 ')'）都是二元减号。
    """
    if not tokens:
        return True
    prev = tokens[-1]
    return prev.kind in (OP, LPAREN)


def tokenize(expr: str) -> list[Token]:
    """把表达式切成 Token 列表。

    :raises CalcError: 遇到非法字符或不支持的运算符（含 ``**``）。
    """
    tokens: list[Token] = []
    i = 0
    n = len(expr)

    while i < n:
        ch = expr[i]

        if ch.isspace():
            i += 1
            continue

        # ── 数字（含小数） ──
        if ch.isdigit() or ch == ".":
            start = i
            seen_dot = False
            while i < n and (expr[i].isdigit() or expr[i] == "."):
                if expr[i] == ".":
                    if seen_dot:
                        raise CalcError("syntax", f"多余的小数点 @ {i}")
                    seen_dot = True
                i += 1
            literal = expr[start:i]
            if literal == ".":
                raise CalcError("syntax", "孤立的小数点")
            tokens.append(Token(NUM, literal, start))
            continue

        # ── 括号 ──
        if ch == "(":
            tokens.append(Token(LPAREN, ch, i))
            i += 1
            continue
        if ch == ")":
            tokens.append(Token(RPAREN, ch, i))
            i += 1
            continue

        # ── 运算符 ──
        # 显式拦截 ** —— 幂运算不在本计算器的语法内，
        # 且是旧 eval 实现的主要拒绝服务入口。
        if ch == "*" and i + 1 < n and expr[i + 1] == "*":
            raise CalcError("power", "不支持幂运算 **")

        if ch in BINARY_OPS:
            # 旧表达式用 "×" "÷"，同时兼容 ASCII 的 "*" "/"
            if ch == "-":
                kind = OP
                value = "u-" if _is_unary_position(tokens) else "-"
            else:
                kind, value = OP, ch
            tokens.append(Token(kind, value, i))
            i += 1
            continue

        if ch in "*/":
            # ASCII 别名：统一成显示符号
            if ch == "*" and i + 1 < n and expr[i + 1] == "*":
                raise CalcError("power", "不支持幂运算 **")
            tokens.append(Token(OP, "×" if ch == "*" else "÷", i))
            i += 1
            continue

        raise CalcError("char", f"非法字符 {ch!r} @ {i}")

    return tokens
