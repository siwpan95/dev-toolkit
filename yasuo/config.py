# -*- coding: utf-8 -*-
"""
config.py — 配置数据类与常量
无任何 UI 依赖，可被所有其他模块安全 import
"""


class CryptoConfig:
    """加密/压缩配置"""

    def __init__(self):
        self.compress_algo = "zlib"          # 压缩算法: zlib / lzma / bz2
        self.compress_level = 6              # 压缩级别 0-9
        self.encrypt_cipher = "AES-256-GCM"  # 加密算法: AES-256-GCM / AES-256-CBC
        self.compression_bomb = False
        self.compression_bomb_layers = 3
        self.key_derivation_iterations = 100000
        self.chunk_size = 64 * 1024
        self.enable_integrity = True         # 是否嵌入 SHA256 校验

    def to_dict(self):
        return {k: v for k, v in self.__dict__.items()}

    def from_dict(self, data):
        for k, v in data.items():
            if hasattr(self, k):
                setattr(self, k, v)


COMPRESS_ALGOS = {
    "zlib": {"ext": ".zlib", "name": "zlib (Deflate)"},
    "lzma": {"ext": ".lzma", "name": "LZMA (7-zip)"},
    "bz2":  {"ext": ".bz2",  "name": "BZip2"},
}
