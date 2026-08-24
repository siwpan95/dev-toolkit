# -*- coding: utf-8 -*-
"""
utils.py — 通用工具函数
"""
import os
import zlib
import zipfile


def format_size(size_bytes: int) -> str:
    """将字节数格式化为人类可读字符串"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / 1024 / 1024:.2f} MB"
    else:
        return f"{size_bytes / 1024 / 1024 / 1024:.2f} GB"


def create_compression_bomb(input_path: str, output_path: str, layers: int = 3):
    """
    创建压缩炸弹（zlib 多轮压缩后包装成 ZIP）

    Returns:
        (ok: bool, info: dict)
    """
    try:
        with open(input_path, "rb") as f:
            data = f.read()
        for _ in range(layers):
            data = zlib.compress(data, level=9)
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_STORED) as zf:
            zf.writestr("encrypted_data.bin", data)
        out_size = os.path.getsize(output_path)
        return True, {
            "layers": layers,
            "input_size": os.path.getsize(input_path),
            "output_size": out_size,
        }
    except Exception as e:
        return False, {"error": str(e)}
