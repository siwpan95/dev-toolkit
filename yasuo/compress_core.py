# -*- coding: utf-8 -*-
"""
compress_core.py — 多算法流式压缩/解压
支持 zlib / lzma / bz2，文件头自带算法标识，解压时自动识别
"""
import os
import zlib
import lzma
import bz2
import struct

from .config import COMPRESS_ALGOS


# ==================== 内部工厂 ====================

def _get_compressor(algo: str, level: int):
    if algo == "zlib":
        return zlib.compressobj(level)
    elif algo == "lzma":
        filt = [{"id": lzma.FILTER_LZMA2, "preset": level}]
        return lzma.LZMACompressor(format=lzma.FORMAT_RAW, filters=filt)
    elif algo == "bz2":
        return bz2.BZ2Compressor(level)
    else:
        return zlib.compressobj(level)


def _get_decompressor(algo: str):
    if algo == "zlib":
        return zlib.decompressobj()
    elif algo == "lzma":
        return lzma.LZMADecompressor(format=lzma.FORMAT_RAW)
    elif algo == "bz2":
        return bz2.BZ2Decompressor()
    else:
        return zlib.decompressobj()


# ==================== 公开接口 ====================

def generic_compress(input_path: str, output_path: str,
                     algo: str = "zlib", level: int = 6,
                     chunk_size: int = 1024 * 1024):
    """
    通用多算法流式压缩

    文件格式：[orig_size 8B big-endian] [algo 8B ASCII padded] [compressed data]

    Returns:
        (ok: bool, info: dict)
    """
    try:
        orig_size = os.path.getsize(input_path)
        compressor = _get_compressor(algo, level)

        with open(input_path, "rb") as fin, open(output_path, "wb") as fout:
            fout.write(struct.pack(">Q", orig_size))       # 8B 原始大小
            fout.write(algo.ljust(8).encode("ascii"))      # 8B 算法标识

            while True:
                chunk = fin.read(chunk_size)
                if not chunk:
                    break
                fout.write(compressor.compress(chunk))
            fout.write(compressor.flush())

        new_size = os.path.getsize(output_path)
        return True, {
            "algo": algo,
            "input_size": orig_size,
            "output_size": new_size,
            "ratio": f"{new_size / max(1, orig_size) * 100:.2f}%",
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return False, {"error": str(e)}


def generic_decompress(input_path: str, output_path: str,
                       chunk_size: int = 1024 * 1024):
    """
    通用多算法流式解压（自动识别算法）

    Returns:
        (ok: bool, info: dict)
    """
    try:
        with open(input_path, "rb") as fin:
            header = fin.read(16)
            if len(header) < 16:
                return False, {"error": "文件头损坏"}
            orig_size = struct.unpack(">Q", header[:8])[0]
            algo = header[8:16].decode("ascii").strip()
            decompressor = _get_decompressor(algo)

        with open(output_path, "wb") as fout:
            with open(input_path, "rb") as fin:
                fin.seek(16)
                while True:
                    chunk = fin.read(chunk_size)
                    if not chunk:
                        break
                    fout.write(decompressor.decompress(chunk))
                # bz2/lzma decompress 不需要 flush，zlib decompressobj 有 flush
                if hasattr(decompressor, "flush"):
                    fout.write(decompressor.flush())

        actual_size = os.path.getsize(output_path)
        return True, {
            "algo": algo,
            "expected_size": orig_size,
            "actual_size": actual_size,
            "verified": actual_size == orig_size,
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return False, {"error": str(e)}
