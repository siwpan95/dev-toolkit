"""密码学工具 —— 纯函数集合，零 GUI 依赖，可独立单测。

相对旧 ``CryptoUtils`` 的修正：

1. **随机数改用 ``secrets``**。旧代码用 ``random``（Mersenne Twister，
   非密码学安全）生成密钥和盐值——这是实打实的安全缺陷，不是风格问题。
2. **命名纠偏**：``encode_fernet`` / ``decode_fernet`` 实际做的是 Base64，
   与 Fernet（一种带认证加密的方案）毫无关系，改名避免误导。
3. **XOR 输出改为十六进制**。旧实现逐字节 ``chr()`` 拼接，产物含不可见
   字符和控制字符，既没法显示也没法回传解密；改成 hex 后可打印且可逆。
4. **统一执行入口** :func:`run`，供密码学菜单驱动，不再让 Model
   写一大串 if/elif 去分发。

定位说明：凯撒 / ROT13 / 维吉尼亚 是**教学演示**，不具备任何实际机密性，
仅用于本计算器的解密终端玩法。
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import string
from dataclasses import dataclass
from typing import Callable

# ─────────────────────────────────────────────────────────────
#  经典密码（教学演示）
# ─────────────────────────────────────────────────────────────

def caesar_cipher(text: str, shift: int = 3) -> str:
    """凯撒密码加密（仅移字母，其余原样保留）。"""
    return _shift_alpha(text, shift)


def caesar_decipher(text: str, shift: int = 3) -> str:
    """凯撒密码解密。"""
    return _shift_alpha(text, -shift)


def rot13(text: str) -> str:
    """ROT13 —— 凯撒密码 shift=13 的自反特例。"""
    return _shift_alpha(text, 13)


def _shift_alpha(text: str, shift: int) -> str:
    out: list[str] = []
    for ch in text:
        if ch.isascii() and ch.isalpha():
            base = ord("a") if ch.islower() else ord("A")
            out.append(chr((ord(ch) - base + shift) % 26 + base))
        else:
            out.append(ch)
    return "".join(out)


def vigenere_encrypt(text: str, key: str) -> str:
    """维吉尼亚密码加密。密钥中的非字母字符会被忽略。"""
    shifts = [ord(c) - ord("a") for c in key.lower() if c.isalpha()]
    if not shifts:
        return text
    out: list[str] = []
    i = 0
    for ch in text:
        if ch.isascii() and ch.isalpha():
            base = ord("a") if ch.islower() else ord("A")
            out.append(chr((ord(ch) - base + shifts[i % len(shifts)]) % 26 + base))
            i += 1
        else:
            out.append(ch)
    return "".join(out)


def vigenere_decrypt(text: str, key: str) -> str:
    """维吉尼亚密码解密。"""
    shifts = [ord(c) - ord("a") for c in key.lower() if c.isalpha()]
    if not shifts:
        return text
    return vigenere_encrypt(text, "".join(
        chr(-s % 26 + ord("a")) for s in shifts
    ))


# ─────────────────────────────────────────────────────────────
#  编码 / 异或
# ─────────────────────────────────────────────────────────────

def b64_encode(text: str) -> str:
    """Base64 编码。（旧名 ``encode_fernet``，名不副实，已纠正）"""
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


def b64_decode(text: str) -> str:
    """Base64 解码。失败时抛 ``ValueError``，由调用方转成提示文案。"""
    return base64.b64decode(text.encode("ascii"), validate=True).decode("utf-8")


def xor_encrypt(text: str, key: str) -> str:
    """XOR 加密，输出十六进制串（可打印、可用 :func:`xor_decrypt` 还原）。"""
    if not key:
        raise ValueError("XOR 密钥不能为空")
    data = text.encode("utf-8")
    k = key.encode("utf-8")
    return bytes(b ^ k[i % len(k)] for i, b in enumerate(data)).hex()


def xor_decrypt(hex_text: str, key: str) -> str:
    """XOR 解密（与加密同构，接受十六进制串）。"""
    if not key:
        raise ValueError("XOR 密钥不能为空")
    try:
        data = bytes.fromhex(hex_text)
    except ValueError as exc:
        raise ValueError("密文必须是十六进制串") from exc
    k = key.encode("utf-8")
    return bytes(b ^ k[i % len(k)] for i, b in enumerate(data)).decode(
        "utf-8", errors="replace"
    )


# ─────────────────────────────────────────────────────────────
#  哈希 / 密钥派生 / 随机
# ─────────────────────────────────────────────────────────────

#: 支持的摘要算法。``truncate`` 是为了适配 13 字符的显示区——
#: 注意这是**显示截断**，不是安全强度声明。
DIGESTS: dict[str, tuple[Callable[[bytes], "hashlib._Hash"], int]] = {
    "md5":    (hashlib.md5, 16),
    "sha1":   (hashlib.sha1, 20),
    "sha224": (hashlib.sha224, 28),
    "sha256": (hashlib.sha256, 32),
    "sha384": (hashlib.sha384, 48),
    "sha512": (hashlib.sha512, 64),
}


def digest(text: str, algorithm: str = "sha256") -> str:
    """计算摘要，默认截断到 32 个十六进制字符以适配显示区。"""
    algo = algorithm.lower().replace("-", "")
    fn, _ = DIGESTS.get(algo, DIGESTS["sha256"])
    return fn(text.encode("utf-8")).hexdigest()[:32]


def generate_key(bits: int = 256) -> str:
    """生成随机密钥（十六进制），输出恒为 32 个十六进制字符。

    下限取 128 bit 是为了让输出宽度稳定——低于 128 bit 时
    ``token_hex`` 本身就不足 32 字符，显示区宽窄不一。上限 4096 bit
    防止用户传入天文数字导致无谓的大内存分配。

    随机源用 ``secrets``，旧实现用的 ``random`` 模块不具备密码学安全性。
    """
    bits = max(128, min(bits, 4096))
    return secrets.token_hex(bits // 8)[:32]


def generate_salt(length: int = 16) -> str:
    """生成可打印盐值。同样改用 ``secrets``。"""
    length = max(4, min(length, 64))
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def derive_password(password: str, salt: str | None = None) -> tuple[str, str]:
    """PBKDF2-HMAC-SHA256 派生口令哈希，返回 ``(hash, salt)``。"""
    if salt is None:
        salt = generate_salt(16)
    raw = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000
    )
    return raw.hex()[:32], salt


def check_password(password: str, expected: str, salt: str) -> bool:
    """常数时间比对口令哈希，避免时序侧信道。"""
    actual, _ = derive_password(password, salt)
    return hmac.compare_digest(actual, expected)


# ─────────────────────────────────────────────────────────────
#  模式注册表 —— 密码学菜单的驱动数据
# ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class CryptoMode:
    """一个密码学模式：显示名、说明、以及执行函数。"""

    key: str
    label: str
    hint: str          # 输入框提示，告诉用户该输什么
    run: Callable[[str], str]


def _run_caesar(text: str) -> str:
    """``文本 位移``，如 ``hello 3``；省略位移则默认 3。"""
    parts = text.split()
    if len(parts) >= 2 and parts[-1].lstrip("-").isdigit():
        return caesar_cipher(" ".join(parts[:-1]), int(parts[-1]) % 26)
    return caesar_cipher(text, 3)


def _run_rot13(text: str) -> str:
    return rot13(text)


def _run_hash(text: str) -> str:
    parts = text.split()
    if len(parts) >= 2:
        return digest(parts[0], parts[-1])
    return digest(text)


def _run_key(text: str) -> str:
    bits = int(text) if text.strip().isdigit() else 256
    return generate_key(bits)


def _run_xor(text: str) -> str:
    """``明文:密钥``，缺省密钥用 ``key``。"""
    if ":" in text:
        plain, _, key = text.partition(":")
        return xor_encrypt(plain.strip(), key.strip())
    return xor_encrypt(text, "key")


def _run_vig(text: str) -> str:
    parts = text.split()
    if len(parts) < 2:
        raise ValueError("需要：文本 密钥")
    return vigenere_encrypt(parts[0], parts[-1])


def _run_b64(text: str) -> str:
    return b64_encode(text)


def _run_salt(text: str) -> str:
    length = int(text) if text.strip().isdigit() else 16
    return generate_salt(length)


def _run_pwd(text: str) -> str:
    parts = text.split()
    if not parts:
        raise ValueError("需要：密码 [盐值]")
    pwd = parts[0]
    salt = parts[1] if len(parts) >= 2 else generate_salt(16)
    h, salt = derive_password(pwd, salt)
    return f"{h[:16]}·{salt[:8]}"


#: 菜单顺序即 :data:`calculator.config.CRYPTO_MENU_LAYOUT` 的顺序。
MODES: dict[str, CryptoMode] = {
    m.key: m
    for m in (
        CryptoMode("caesar", "caesar", "文本 位移", _run_caesar),
        CryptoMode("hash",   "hash",   "文本 算法", _run_hash),
        CryptoMode("key",    "key",    "位数",     _run_key),
        CryptoMode("xor",    "xor",    "文本:密钥", _run_xor),
        CryptoMode("vig",    "vig",    "文本 密钥", _run_vig),
        CryptoMode("rot13",  "rot13",  "文本",     _run_rot13),
        CryptoMode("b64",    "b64",    "文本",     _run_b64),
        CryptoMode("salt",   "salt",   "长度",     _run_salt),
        CryptoMode("pwd",    "pwd",    "密码 盐值", _run_pwd),
    )
}


def normalize(text: str) -> str:
    """把输入缓冲规范成各执行器期望的形态。

    字母键盘没有空格键（网格已被字母和数字占满），用 ``_`` 充当分隔符。
    这里统一把它还原成真正的空格，各模式的 ``split()`` 才能正确切分
    ``文本 密钥`` 这类双参数输入。
    """
    return text.replace("_", " ").strip()


def run(mode: str, text: str) -> str:
    """执行一个密码学模式。失败时返回人类可读的提示，不抛异常。"""
    spec = MODES.get(mode)
    if spec is None:
        return "unknown crypto"
    try:
        return spec.run(normalize(text))
    except ValueError as exc:
        return str(exc)
    except Exception:  # pragma: no cover - 兜底，保证 UI 不崩
        return "crypto error"
