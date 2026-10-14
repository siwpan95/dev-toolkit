"""彩蛋表 —— 特殊数字/术语组合触发的趣味输出。

旧实现是一个 ``dict[str, str]`` 字面量，里面 **有 10 个重复键**：

    "128": "aes-128",   ┐
    "128": "md5",       ├─ 同键三次，Python 只保留最后一个
    "128": "nonce",     ┘

字面量里重复键不会报错，只会静默覆盖。实测：68 条定义最终只有 58 条
生效，文档里写的 ``128 → aes-128`` 实际输出的是 ``nonce``。

本模块改用 ``dict[str, tuple[str, ...]]``：
一个键可挂多个值，**命中时轮换**，既不丢数据，也让同一个数字多按几次
能翻出不同彩蛋——比丢掉更有趣，也算把「重复」从缺陷转成特性。
"""

from __future__ import annotations

#: 键 → 彩蛋值（可多个，按顺序轮换）
EASTER_EGGS: dict[str, tuple[str, ...]] = {
    # ── 经典 ──
    "++--××÷÷()()": ("cool",),
    "110": ("warning",),
    "119": ("warning",),
    "120": ("warning",),
    "911": ("fbi warning",),
    "520": ("1314",),
    "1314": ("520",),

    # ── AES 密钥长度 / 摘要长度 / 椭圆曲线 / 熵：同一数字的多重身份 ──
    "128": ("aes-128", "md5", "nonce"),
    "160": ("sha-1",),
    "192": ("aes-192",),
    "224": ("sha-224", "p-224"),
    "256": ("aes-256", "sha-256", "p-256", "entropy"),
    "384": ("sha-384", "p-384"),
    "512": ("sha-512",),
    "521": ("p-521",),

    # ── RSA 密钥 ──
    "1024": ("rsa-1k",),
    "2048": ("rsa-2048",),
    "3072": ("rsa-3k",),
    "4096": ("rsa-4k",),

    # ── 密钥交换 ──
    "448": ("x448",),

    # ── 端口与协议 ──
    "443": ("https",),
    "22":  ("ssh",),
    "21":  ("ftp",),

    # ── 分组模式 ──
    "ecb": ("危险",),
    "cbc": ("安全",),
    "gcm": ("认证",),
    "ofb": ("流式",),

    # ── 填充 ──
    "pkcs7": ("padding",),
    "zero":  ("zero",),

    # ── 密钥派生 ──
    "1000": ("pbkdf2",),
    "10":   ("bcrypt",),

    # ── 二进制 / 十六进制 ──
    "101": ("matrix",),
    "010": ("binary",),
    "16":  ("hex",),
    "2":   ("binary",),
    "00":  ("null",),
    "ff":  ("0xff",),
    "0x":  ("hex",),
    "0b":  ("bin",),

    # ── 熵与随机 ──
    "64": ("salt",),

    # ── 数学常数 ──
    "314": ("pi",),
    "271": ("e",),
    "161": ("golden",),
    "618": ("phi",),

    # ── 安全术语 ──
    "xor": ("⊕",),
    "rnd": ("rand",),
    "key": ("🔐",),
    "enc": ("encrypt",),
    "dec": ("decrypt",),
    "sig": ("signature",),
    "pki": ("pki",),
    "ca":  ("certificate",),

    # ── 趣味 ──
    "42":  ("answer",),
    "007": ("bond",),
    "404": ("not found",),
    "666": ("beast",),
    "777": ("jackpot",),
    "000": ("void",),
}


def lookup(key: str, rotation: int = 0) -> str | None:
    """取第 ``rotation`` 个彩蛋值（超出长度则回绕）。无此键返回 ``None``。"""
    values = EASTER_EGGS.get(key)
    if not values:
        return None
    return values[rotation % len(values)]


def count(key: str) -> int:
    """该键挂了几个彩蛋值。"""
    return len(EASTER_EGGS.get(key, ()))


def total_eggs() -> int:
    """彩蛋值总数（用于自检：旧版 68 条定义只剩 58 条生效）。"""
    return sum(len(v) for v in EASTER_EGGS.values())
