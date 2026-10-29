# -*- coding: utf-8 -*-
"""
yasuo — 通用文件加密/压缩工具包

外部脚本快速使用：
    from yasuo import process_file, decrypt_file, AESCipher, CryptoConfig

GUI 启动：
    python -m yasuo
"""
from .config import CryptoConfig, COMPRESS_ALGOS
from .utils import format_size, create_compression_bomb
from .crypto_core import (
    AESCipher,
    generate_key, save_key_file, load_key_file,
    compute_sha256, compute_sha256_bytes,
)
from .compress_core import generic_compress, generic_decompress
from .pipeline import process_file, decrypt_file
from .compare import compare_compress_algorithms

__all__ = [
    "CryptoConfig", "COMPRESS_ALGOS",
    "format_size", "create_compression_bomb",
    "AESCipher", "generate_key", "save_key_file", "load_key_file",
    "compute_sha256", "compute_sha256_bytes",
    "generic_compress", "generic_decompress",
    "process_file", "decrypt_file",
    "compare_compress_algorithms",
]
