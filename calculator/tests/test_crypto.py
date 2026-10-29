"""密码学模块测试。

重点：随机源必须是 ``secrets``（旧版用 ``random``，非密码学安全），
以及各算法本身的正确性 / 可逆性。
"""

from __future__ import annotations

import unittest

from _path import ROOT  # noqa: F401

from calculator import crypto


class TestClassicCiphers(unittest.TestCase):
    def test_caesar_roundtrip(self):
        self.assertEqual(crypto.caesar_cipher("abc", 3), "def")
        self.assertEqual(crypto.caesar_decipher("def", 3), "abc")
        self.assertEqual(crypto.caesar_cipher("xyz", 3), "abc")

    def test_caesar_preserves_case_and_non_alpha(self):
        self.assertEqual(crypto.caesar_cipher("Hello, World!", 1), "Ifmmp, Xpsme!")

    def test_rot13_is_involution(self):
        self.assertEqual(crypto.rot13("hello"), "uryyb")
        self.assertEqual(crypto.rot13(crypto.rot13("hello")), "hello")

    def test_rot13_digits_untouched(self):
        self.assertEqual(crypto.rot13("abc123"), "nop123")

    def test_vigenere_known_vector(self):
        self.assertEqual(crypto.vigenere_encrypt("hello", "key"), "rijvs")
        self.assertEqual(crypto.vigenere_decrypt("rijvs", "key"), "hello")

    def test_vigenere_without_alpha_key_is_identity(self):
        self.assertEqual(crypto.vigenere_encrypt("hello", "123"), "hello")


class TestEncoding(unittest.TestCase):
    def test_base64_roundtrip(self):
        self.assertEqual(crypto.b64_encode("hi"), "aGk=")
        self.assertEqual(crypto.b64_decode("aGk="), "hi")

    def test_xor_roundtrip(self):
        cipher = crypto.xor_encrypt("hello", "key")
        self.assertEqual(crypto.xor_decrypt(cipher, "key"), "hello")

    def test_xor_output_is_printable_hex(self):
        cipher = crypto.xor_encrypt("hello", "key")
        self.assertTrue(all(c in "0123456789abcdef" for c in cipher))

    def test_xor_empty_key_rejected(self):
        with self.assertRaises(ValueError):
            crypto.xor_encrypt("hello", "")

    def test_xor_decrypt_bad_hex(self):
        with self.assertRaises(ValueError):
            crypto.xor_decrypt("zzzz", "key")


class TestDigest(unittest.TestCase):
    def test_known_sha256_prefix(self):
        """sha256("abc") 前 32 位十六进制。"""
        self.assertEqual(
            crypto.digest("abc", "sha256"),
            "ba7816bf8f01cfea414140de5dae2223",
        )

    def test_unknown_algorithm_falls_back_to_sha256(self):
        self.assertEqual(crypto.digest("abc", "nope"), crypto.digest("abc", "sha256"))

    def test_algorithm_alias_with_dash(self):
        self.assertEqual(crypto.digest("abc", "sha-1"), crypto.digest("abc", "sha1"))


class TestRandomSource(unittest.TestCase):
    """旧版用 random（Mersenne Twister）生成密钥/盐值，不安全。"""

    def test_keys_are_distinct(self):
        self.assertNotEqual(crypto.generate_key(128), crypto.generate_key(128))

    def test_salts_are_distinct(self):
        self.assertNotEqual(crypto.generate_salt(16), crypto.generate_salt(16))

    def test_key_length_clamped(self):
        # 下限 128 bit（保证输出恒 32 hex），上限 4096 bit（防天文数字）
        self.assertEqual(len(crypto.generate_key(1)), 32)
        self.assertEqual(len(crypto.generate_key(99999)), 32)
        self.assertEqual(len(crypto.generate_key(256)), 32)

    def test_salt_length_clamped(self):
        self.assertEqual(len(crypto.generate_salt(1)), 4)
        self.assertEqual(len(crypto.generate_salt(999)), 64)

    def test_uses_secrets_module(self):
        """源码层面确认：密钥/盐值不再依赖 random 模块。"""
        import inspect

        src = inspect.getsource(crypto)
        self.assertNotIn("import random", src)
        self.assertIn("import secrets", src)


class TestPasswordDerivation(unittest.TestCase):
    def test_derive_is_salted(self):
        h1, s1 = crypto.derive_password("pw")
        h2, s2 = crypto.derive_password("pw")
        self.assertNotEqual(s1, s2)
        self.assertNotEqual(h1, h2)

    def test_check_password(self):
        h, s = crypto.derive_password("pw")
        self.assertTrue(crypto.check_password("pw", h, s))
        self.assertFalse(crypto.check_password("wrong", h, s))


class TestRunDispatcher(unittest.TestCase):
    def test_normalize_underscore_to_space(self):
        """字母键盘用 '_' 当分隔符，执行前还原为空格。"""
        self.assertEqual(crypto.normalize("hello_key"), "hello key")

    def test_all_modes_executable(self):
        for mode in crypto.MODES:
            with self.subTest(mode=mode):
                out = crypto.run(mode, "abc")
                self.assertNotIn(out, ("unknown crypto", "crypto error"))

    def test_unknown_mode(self):
        self.assertEqual(crypto.run("nope", "x"), "unknown crypto")

    def test_vig_requires_key(self):
        self.assertIn("需要", crypto.run("vig", "hello"))

    def test_bad_input_returns_message_not_raise(self):
        self.assertIsInstance(crypto.run("xor", ""), str)


if __name__ == "__main__":
    unittest.main()
