"""Model 测试 —— 全程不 import tkinter。

这本身就是一条架构断言：把本文件放到没有 tkinter 的解释器上也能跑，
证明 Model / engine / crypto / easter_eggs 与 GUI 彻底解耦。
（旧版做不到：View 的类型注解里写着 CalculatorModel，反过来 Model 那侧
也硬编码依赖 CryptoUtils，整块逻辑被 GUI 牵连。）
"""

from __future__ import annotations

import unittest

from _path import ROOT  # noqa: F401

from calculator.config import Limits
from calculator.model import CalculatorModel
from calculator.snapshot import Action, Mode


class TestBasics(unittest.TestCase):
    def setUp(self):
        self.m = CalculatorModel()

    def _type(self, text: str):
        for ch in text:
            self.m.push(ch)

    def test_initial_display(self):
        self.assertEqual(self.m.snapshot().display, "0")

    def test_input_expression(self):
        self._type("12+")
        self.assertEqual(self.m.snapshot().display, "12+")

    def test_evaluate(self):
        self._type("7×8")
        self.m.push("=")
        snap = self.m.snapshot()
        self.assertEqual(snap.display, "56")
        self.assertEqual(snap.expr, "7×8 =")

    def test_backspace(self):
        self._type("123")
        self.m.push("←")
        self.assertEqual(self.m.snapshot().display, "12")

    def test_observer_notified(self):
        seen = []
        self.m.add_observer(seen.append)
        self.m.push("1")
        self.assertEqual(len(seen), 1)


class TestLimits(unittest.TestCase):
    def setUp(self):
        self.m = CalculatorModel()

    def test_digit_limit(self):
        # 用不同数字，避免触发「连按同一键三次→清空」
        for ch in "12345":
            self.m.push(ch)
        self.assertEqual(self.m.snapshot().display, "1234")  # 上限 4
        self.assertTrue(self.m.snapshot().digit_limit)

    def test_char_limit(self):
        # 交替括号，既不触发连按清空，也不受数字上限影响
        for i in range(30):
            self.m.push("(" if i % 2 == 0 else ")")
        snap = self.m.snapshot()
        self.assertEqual(len(snap.display), self.m._limits.max_chars)
        self.assertTrue(snap.char_limit)

    def test_triple_same_resets(self):
        self.m.push("9")
        self.m.push("9")
        snap = self.m.snapshot()
        self.assertEqual(snap.display, "99")
        self.m.push("9")          # 第三次 → 清空
        self.assertEqual(self.m.snapshot().display, "0")

    def test_triple_equals_shuffles(self):
        self.m.push("=")
        self.m.push("=")
        self.assertNotEqual(self.m.snapshot().action, Action.SHUFFLE)
        self.m.push("=")
        self.assertEqual(self.m.snapshot().action, Action.SHUFFLE)

    def test_triple_backspace_quits(self):
        self.m.push("←")
        self.m.push("←")
        self.assertNotEqual(self.m.snapshot().action, Action.QUIT)
        self.m.push("←")
        self.assertEqual(self.m.snapshot().action, Action.QUIT)

    def test_limits_injectable(self):
        m = CalculatorModel(limits=Limits(max_digit_presses=2))
        for _ in range(5):
            m.push("7")
        self.assertEqual(m.snapshot().display, "77")


class TestEasterEggs(unittest.TestCase):
    """旧版同键重复定义被静默覆盖，这里验证轮换找回全部值。"""

    def setUp(self):
        self.m = CalculatorModel()

    def _eval(self, text: str) -> str:
        for ch in text:
            self.m.push(ch)
        self.m.push("=")
        return self.m.snapshot().display

    def test_128_rotates_through_all_three(self):
        self.assertEqual(self._eval("128"), "aes-128")
        self.assertEqual(self._eval("128"), "md5")
        self.assertEqual(self._eval("128"), "nonce")
        self.assertEqual(self._eval("128"), "aes-128")   # 回绕

    def test_256_rotates_through_all_four(self):
        got = {self._eval("256") for _ in range(4)}
        self.assertEqual(got, {"aes-256", "sha-256", "p-256", "entropy"})

    def test_224_keeps_both_values(self):
        got = {self._eval("224") for _ in range(2)}
        self.assertEqual(got, {"sha-224", "p-224"})

    def test_legacy_lost_values_all_recovered(self):
        """旧版 68 条定义只有 58 条生效，被吞掉的必须全部找回来。"""
        recovered = set()
        for key, count in (("128", 3), ("256", 4), ("224", 2), ("384", 2)):
            for _ in range(count):
                recovered.add(self._eval(key))
        for value in ("aes-128", "md5", "nonce", "aes-256", "sha-256",
                      "p-256", "entropy", "sha-224", "p-224", "sha-384",
                      "p-384"):
            self.assertIn(value, recovered)

    def test_classic_eggs(self):
        self.assertEqual(self._eval("404"), "not found")
        self.assertEqual(self._eval("42"), "answer")


class TestCryptoModes(unittest.TestCase):
    def setUp(self):
        self.m = CalculatorModel()

    def test_hash_mode_is_reachable(self):
        """旧版密码学代码 100% 不可达，这里验证完整链路。"""
        self.m.push("#")
        self.assertEqual(self.m.snapshot().mode, Mode.CRYPTO_MENU)

        self.m.push("rot13")
        self.assertEqual(self.m.snapshot().mode, Mode.CRYPTO_INPUT)

        for ch in "hello":
            self.m.push(ch)
        self.assertEqual(self.m.snapshot().display, "hello")

        self.m.push("EXE")
        snap = self.m.snapshot()
        self.assertEqual(snap.display, "uryyb")
        self.assertEqual(snap.mode, Mode.CALC)

    def test_esc_returns_to_calc(self):
        self.m.push("#")
        self.m.push("ESC")
        self.assertEqual(self.m.snapshot().mode, Mode.CALC)

    def test_history_recorded(self):
        self.m.push("#")
        self.m.push("rot13")
        for ch in "abc":
            self.m.push(ch)
        self.m.push("EXE")
        self.assertEqual(len(self.m.snapshot().history), 1)

    def test_history_capped_at_five(self):
        for _ in range(7):
            self.m.push("#")
            self.m.push("rot13")
            self.m.push("a")
            self.m.push("EXE")
        self.assertEqual(len(self.m.snapshot().history), 5)

    def test_input_buffer_capped(self):
        self.m.push("#")
        self.m.push("rot13")
        for _ in range(40):
            self.m.push("a")
        self.assertLessEqual(len(self.m.snapshot().display), 24)

    def test_crypto_runner_injectable(self):
        """旧版硬编码 CryptoUtils，无法替换；现在可注入桩函数。"""
        calls = []

        def stub(mode: str, text: str) -> str:
            calls.append((mode, text))
            return f"stub:{mode}"

        m = CalculatorModel(crypto_runner=stub)
        m.push("#")
        m.push("rot13")
        m.push("x")
        m.push("EXE")
        self.assertEqual(m.snapshot().display, "stub:rot13")
        self.assertEqual(calls, [("rot13", "x")])


def _imported_names(rel_path: str) -> set[str]:
    """解析一个源文件的 import 语句，返回被导入的模块名集合。

    用 AST 而不是字符串匹配源码：源码里的注释/docstring 提到某个名字
    不代表真的依赖它（view.py 的注释里就提到了 CalculatorModel）。
    也不需要 import 目标模块，因此在没有 tkinter 的环境同样能跑。
    """
    import ast

    path = ROOT / "calculator" / rel_path
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


class TestNoGuiDependency(unittest.TestCase):
    """架构约束的静态检查：哪一层不许依赖谁。"""

    CORE_FILES = (
        "config.py",
        "crypto.py",
        "easter_eggs.py",
        "model.py",
        "snapshot.py",
        "engine/__init__.py",
        "engine/tokenizer.py",
        "engine/parser.py",
        "engine/evaluator.py",
        "engine/errors.py",
    )

    def test_core_layers_never_import_tkinter(self):
        """Model 及其下层必须与 GUI 无关——这样核心逻辑才能脱离界面单测。"""
        for rel in self.CORE_FILES:
            with self.subTest(file=rel):
                self.assertNotIn("tkinter", _imported_names(rel))

    def test_view_never_imports_model(self):
        """旧版 View 的方法签名里写着 ``model: "CalculatorModel"``，
        认知依赖虽不是 import，但同层耦合；现在 View 只认 snapshot。"""
        names = _imported_names("view.py")
        self.assertNotIn("calculator.model", names)
        self.assertNotIn("model", names)

    def test_controller_never_imports_config_layouts(self):
        """旧版 Controller 写 ``for token in BUTTON_TOKENS`` 去逐个绑按钮，
        等于依赖了 View 的布局数据；现在它只注册一个回调。"""
        names = _imported_names("controller.py")
        self.assertNotIn("calculator.config", names)
        self.assertNotIn("config", names)


if __name__ == "__main__":
    unittest.main()
