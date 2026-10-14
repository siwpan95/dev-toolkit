"""表达式引擎测试。

重点覆盖旧 ``eval`` 实现的两类问题：
  * 四则运算行为不得回归（与旧实现对拍过 10 组，见提交说明）；
  * ``**`` 幂炸弹必须被拒（旧版白名单放行，可把 UI 算死）。
"""

from __future__ import annotations

import unittest

from _path import ROOT  # noqa: F401  确保 src 在 sys.path

from calculator.engine import CalcError, evaluate, to_rpn, tokenize


class TestEvaluate(unittest.TestCase):
    def test_basic_arithmetic(self):
        self.assertEqual(evaluate("2+3"), "5")
        self.assertEqual(evaluate("2+3×4"), "14")      # 优先级
        self.assertEqual(evaluate("(1+2)×3"), "9")     # 括号
        self.assertEqual(evaluate("10÷4"), "2.5")
        self.assertEqual(evaluate("10-2-3"), "5")      # 左结合
        self.assertEqual(evaluate("8÷2÷2"), "2")

    def test_unary_minus(self):
        self.assertEqual(evaluate("-3+1"), "-2")
        self.assertEqual(evaluate("2-(-3)"), "5")
        self.assertEqual(evaluate("-(2+3)"), "-5")

    def test_empty(self):
        self.assertEqual(evaluate(""), "0")
        self.assertEqual(evaluate("   "), "0")

    def test_division_by_zero(self):
        self.assertEqual(evaluate("1÷0"), "fool")
        self.assertEqual(evaluate("5÷(3-3)"), "fool")

    def test_float_format_matches_legacy(self):
        """与旧实现 f"{v:.6f}".rstrip("0").rstrip(".") 保持一致。"""
        self.assertEqual(evaluate("100÷3"), "33.333333")
        self.assertEqual(evaluate("7÷2"), "3.5")
        self.assertEqual(evaluate("1÷8"), "0.125")

    def test_integer_result_has_no_decimal_point(self):
        self.assertEqual(evaluate("4÷2"), "2")
        self.assertEqual(evaluate("1.5+1.5"), "3")


class TestSafety(unittest.TestCase):
    """旧 eval 实现的攻击面，这里必须全部封死。"""

    def test_power_operator_rejected(self):
        """9**9**9 是旧版的 CPU/内存炸弹，必须拒绝。"""
        for attack in ("9**9**9", "2**99999", "(9**9)**9", "2**2"):
            with self.subTest(attack=attack):
                self.assertEqual(evaluate(attack), "fool")

    def test_code_injection_rejected(self):
        for attack in (
            "__import__('os')",
            "(1).__class__",
            "().__class__.__bases__[0]",
            "open('x')",
        ):
            with self.subTest(attack=attack):
                self.assertEqual(evaluate(attack), "fool")

    def test_syntax_errors(self):
        for bad in ("(((", "1+", "+", "1..2", "1 2", "()", "÷"):
            with self.subTest(bad=bad):
                self.assertEqual(evaluate(bad), "fool")

    def test_illegal_characters(self):
        self.assertEqual(evaluate("abc"), "fool")
        self.assertEqual(evaluate("1;a"), "fool")

    def test_overflow_guard(self):
        """结果超上限视为溢出，而不是慢慢算出一个天文数字。"""
        self.assertEqual(evaluate("9999999×9999999×9999999"), "fool")


class TestTokenizer(unittest.TestCase):
    def test_tokenize_mixed(self):
        kinds = [(t.kind, t.value) for t in tokenize("1+23×(4.5)")]
        self.assertEqual(
            kinds,
            [
                ("NUM", "1"), ("OP", "+"), ("NUM", "23"), ("OP", "×"),
                ("LPAREN", "("), ("NUM", "4.5"), ("RPAREN", ")"),
            ],
        )

    def test_unary_minus_marked(self):
        values = [t.value for t in tokenize("-3+1")]
        self.assertEqual(values[0], "u-")

    def test_double_dot_rejected(self):
        with self.assertRaises(CalcError):
            tokenize("1..2")

    def test_power_rejected_at_lexer(self):
        with self.assertRaises(CalcError) as ctx:
            tokenize("2**9")
        self.assertEqual(ctx.exception.code, "power")


class TestParser(unittest.TestCase):
    def test_rpn_precedence(self):
        rpn = [t.value for t in to_rpn(tokenize("3+4×2"))]
        # 3 4 2 × +
        self.assertEqual(rpn, ["3", "4", "2", "×", "+"])

    def test_unbalanced_parens(self):
        with self.assertRaises(CalcError):
            to_rpn(tokenize("(1+2"))
        with self.assertRaises(CalcError):
            to_rpn(tokenize("1+2)"))


if __name__ == "__main__":
    unittest.main()
