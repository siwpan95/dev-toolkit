"""语法分析：调度场算法（Shunting-yard），中缀 → 逆波兰式（RPN）。

选它而不是直接 eval 的理由：
  * 明确的运算符优先级与结合律，行为可预测、可单测；
  * 词法层已收紧，**不存在任意代码执行面**；
  * 递归下降/AST 对本计算器属于过度设计，RPN 足够且更快。

一元负号（``u-``）优先级高于乘除、右结合，因此 ``-2×3`` 得 ``-6``，
``-3+1`` 得 ``-2``，与直觉一致。
"""

from __future__ import annotations

from .errors import CalcError
from .tokenizer import LPAREN, NUM, OP, RPAREN, Token

#: 运算符优先级（越大越紧）
PRECEDENCE: dict[str, int] = {
    "+": 1,
    "-": 1,
    "×": 2,
    "÷": 2,
    "u-": 3,
}

#: 结合律
RIGHT_ASSOC: frozenset[str] = frozenset({"u-"})


def to_rpn(tokens: list[Token]) -> list[Token]:
    """把中缀 Token 序列转换为 RPN（逆波兰）序列。

    :raises CalcError: 括号不匹配，或表达式结构非法。
    """
    if not tokens:
        raise CalcError("empty", "空表达式")

    output: list[Token] = []
    stack: list[Token] = []

    for tok in tokens:
        if tok.kind == NUM:
            output.append(tok)
            continue

        if tok.kind == OP:
            prec = PRECEDENCE.get(tok.value)
            if prec is None:
                raise CalcError("syntax", f"未知运算符 {tok.value!r}")
            while stack:
                top = stack[-1]
                if top.kind != OP:
                    break
                top_prec = PRECEDENCE.get(top.value, 0)
                # 右结合时用严格大于，保证同优先级不弹出
                if top_prec > prec or (
                    top_prec == prec and tok.value not in RIGHT_ASSOC
                ):
                    output.append(stack.pop())
                else:
                    break
            stack.append(tok)
            continue

        if tok.kind == LPAREN:
            stack.append(tok)
            continue

        if tok.kind == RPAREN:
            # 弹出直到遇到左括号
            matched = False
            while stack:
                top = stack.pop()
                if top.kind == LPAREN:
                    matched = True
                    break
                output.append(top)
            if not matched:
                raise CalcError("syntax", "括号不匹配（多余的右括号）")
            continue

        raise CalcError("syntax", f"无法处理的 Token {tok!r}")

    # 收尾：弹出剩余运算符
    while stack:
        top = stack.pop()
        if top.kind == LPAREN:
            raise CalcError("syntax", "括号不匹配（缺少右括号）")
        output.append(top)

    # 有输入却没产出，典型如 "()" —— 那是语法错误，不是空表达式
    if not output:
        raise CalcError("syntax", "表达式为空（如空括号）")

    return output
