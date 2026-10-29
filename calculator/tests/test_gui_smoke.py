"""GUI 冒烟测试 —— 真建窗口、真点按钮（``Button.invoke()``）。

与单元测试的区别：这里验证的是**接线**是否正确，即
Controller 有没有把 Model 和 View 接起来、布局切换有没有生效。
纯逻辑正确性由 test_engine / test_crypto / test_model 覆盖。

需要 tkinter；没有 tkinter 的解释器会自动整体跳过。
"""

from __future__ import annotations

import sys
import unittest

from _path import ROOT  # noqa: F401

try:
    import tkinter as tk

    from calculator.app import build
    from calculator.snapshot import Mode

    HAS_TK = True
except ModuleNotFoundError:  # pragma: no cover - 无 tkinter 环境
    HAS_TK = False


@unittest.skipUnless(HAS_TK, "需要 tkinter")
class TestGuiSmoke(unittest.TestCase):
    def setUp(self):
        self.quit_calls: list[int] = []
        self.root = tk.Tk()
        self.ctrl = build(self.root, on_quit=lambda: self.quit_calls.append(1))
        self.view = self.ctrl.view
        self.model = self.ctrl.model

    def tearDown(self):
        self.root.destroy()

    def press(self, token: str) -> bool:
        """点击按钮；若按钮被置灰则返回 False（点击本就无效果）。"""
        btn = self.view._buttons.get(token)
        if btn is None:
            raise AssertionError(f"按钮 {token!r} 不在当前布局")
        if str(btn.cget("state")) == "disabled":
            return False
        btn.invoke()
        return True

    def display(self) -> str:
        return self.view._disp_var.get()

    def test_arithmetic_end_to_end(self):
        for t in ("7", "×", "8"):
            self.press(t)
        self.press("=")
        self.assertEqual(self.display(), "56")
        self.assertEqual(self.view._expr_var.get(), "7×8 =")

    def test_division_by_zero(self):
        for t in ("1", "÷", "0"):
            self.press(t)
        self.press("=")
        self.assertEqual(self.display(), "fool")

    def test_easter_egg_rotates_on_screen(self):
        """旧版 128 恒显示 nonce，现在应轮换。"""
        seen = []
        for _ in range(3):
            for t in ("1", "2", "8"):
                self.press(t)
            self.press("=")
            seen.append(self.display())
        self.assertEqual(seen, ["aes-128", "md5", "nonce"])

    def test_crypto_path_is_reachable(self):
        """旧版密码学功能 100% 不可达（无 # 键、无字母键）。"""
        self.press("#")
        self.assertEqual(self.model.snapshot().mode, Mode.CRYPTO_MENU)

        self.press("rot13")
        self.assertEqual(self.model.snapshot().mode, Mode.CRYPTO_INPUT)

        for ch in "hello":
            self.press(ch)
        self.assertEqual(self.display(), "hello")

        self.press("EXE")
        self.assertEqual(self.display(), "uryyb")
        self.assertEqual(self.model.snapshot().mode, Mode.CALC)

    def test_alpha_keyboard_has_letters_and_digits(self):
        self.press("#")
        self.press("xor")
        tokens = set(self.view._buttons)
        for ch in "abcdefghijklmnopqrstuvwxyz0123456789":
            self.assertIn(ch, tokens)

    def test_digit_limit_greys_out_digits(self):
        for ch in "1234":
            self.press(ch)
        self.assertEqual(self.display(), "1234")
        self.assertEqual(str(self.view._buttons["5"].cget("state")), "disabled")
        self.assertFalse(self.press("5"))   # 点击无效
        self.assertEqual(self.display(), "1234")

    def test_triple_backspace_triggers_quit(self):
        for _ in range(3):
            self.press("←")
        self.assertEqual(len(self.quit_calls), 1)

    def test_esc_returns_from_menu(self):
        self.press("#")
        self.press("ESC")
        self.assertEqual(self.model.snapshot().mode, Mode.CALC)

    def test_shuffle_keeps_all_buttons(self):
        self.ctrl.shuffle()
        self.assertEqual(len(self.view._buttons), 20)


if __name__ == "__main__":
    unittest.main()
