# -*- coding: utf-8 -*-
"""
compare.py — 压缩算法对比
"""
import os

from .compress_core import generic_compress


def compare_compress_algorithms(input_path: str, levels=(1, 6, 9)) -> dict:
    """
    对比 zlib / lzma / bz2 在不同压缩级别下的效果

    Returns:
        {
            "zlib": {1: {...}, 6: {...}, 9: {...}},
            "lzma": {...},
            "bz2":  {...},
            "original_size": int,
        }
    """
    results = {}
    orig_size = os.path.getsize(input_path)

    for algo in ["zlib", "lzma", "bz2"]:
        results[algo] = {}
        for lv in levels:
            tmp = input_path + f".__tmp_{algo}_{lv}"
            try:
                ok, info = generic_compress(input_path, tmp, algo=algo, level=lv)
                results[algo][lv] = info if ok else {"error": info.get("error", "失败")}
            finally:
                if os.path.exists(tmp):
                    os.remove(tmp)

    results["original_size"] = orig_size
    return results
