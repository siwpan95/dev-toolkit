# -*- coding: utf-8 -*-
"""
pipeline.py — 加密/压缩主流程
编排 compress_core + crypto_core，供 GUI / CLI 统一调用
"""
import os
import json
from pathlib import Path

from .config import CryptoConfig, COMPRESS_ALGOS
from .utils import format_size, create_compression_bomb
from .crypto_core import AESCipher, generate_key, save_key_file, load_key_file, load_cipher_mode_from_keyfile
from .compress_core import generic_compress


def process_file(input_path: str,
                 output_dir: str = None,
                 config: CryptoConfig = None,
                 password: str = None,
                 skip_compress: bool = False,
                 log_callback=None,
                 progress_callback=None):
    """
    通用文件加密/压缩流水线

    Args:
        input_path:        原始输入文件
        output_dir:        输出目录，默认与输入同目录
        config:            CryptoConfig 实例
        password:          可选密码；None 则随机生成密钥
        skip_compress:     True 时跳过压缩步骤
        log_callback:      func(msg: str) 日志回调
        progress_callback: func(val: int)  进度回调 0-100

    Returns:
        results: dict，含 'compressed' / 'encrypted' / 'key_file' / 'bomb' 等路径
    """
    def _log(msg):
        if log_callback:
            log_callback(msg)

    if config is None:
        config = CryptoConfig()
    if output_dir is None:
        output_dir = str(Path(input_path).parent)
    os.makedirs(output_dir, exist_ok=True)

    stem = Path(input_path).stem
    results = {}
    current_file = input_path

    _log("=" * 50)
    _log("🔐 通用文件加密/压缩流水线")
    _log("=" * 50)

    # Step 1: 压缩
    if not skip_compress:
        if progress_callback:
            progress_callback(10)
        algo_name = COMPRESS_ALGOS[config.compress_algo]["name"]
        _log(f"\n📦 [压缩] {algo_name} (级别 {config.compress_level})")
        ext = COMPRESS_ALGOS[config.compress_algo]["ext"]
        compressed_path = str(Path(output_dir) / f"{stem}_compressed{ext}")
        ok, info = generic_compress(current_file, compressed_path,
                                    algo=config.compress_algo,
                                    level=config.compress_level)
        if ok:
            results["compressed"] = compressed_path
            current_file = compressed_path
            _log(f"   ✅ 压缩成功: {format_size(info['input_size'])} → "
                 f"{format_size(info['output_size'])} ({info['ratio']})")
        else:
            _log(f"   ⚠️ 压缩失败: {info.get('error')}，继续使用原始文件")

    # Step 2: 加密
    if progress_callback:
        progress_callback(40)
    _log(f"\n🔒 [加密] {config.encrypt_cipher}")

    if not AESCipher.check_dependency():
        _log("❌ 缺少 cryptography 库: pip install cryptography")
    else:
        key, salt = generate_key(password, iterations=config.key_derivation_iterations)
        encrypted_path = str(Path(output_dir) / f"{stem}_encrypted.bin")
        ok, info = AESCipher.encrypt_file(
            current_file, encrypted_path, key,
            cipher_mode=config.encrypt_cipher,
            chunk_size=config.chunk_size,
            enable_integrity=config.enable_integrity,
        )
        if ok:
            results["encrypted"] = encrypted_path
            current_file = encrypted_path
            _log(f"   ✅ 加密成功: {format_size(info['output_size'])}")
            if config.enable_integrity and info.get("hash"):
                _log(f"   🔑 SHA256: {info['hash'][:32]}...")
            key_path = str(Path(output_dir) / f"{stem}_key.json")
            save_key_file(key, salt, key_path, config.encrypt_cipher)
            results["key_file"] = key_path
            _log(f"   🔑 密钥已保存: {key_path}")
        else:
            _log(f"   ❌ 加密失败: {info.get('error')}")

    # Step 3: 压缩炸弹
    if config.compression_bomb and "encrypted" in results:
        if progress_callback:
            progress_callback(70)
        _log(f"\n💣 [压缩炸弹] {config.compression_bomb_layers} 层")
        bomb_path = str(Path(output_dir) / f"{stem}_bomb.zip")
        ok, info = create_compression_bomb(results["encrypted"], bomb_path,
                                           layers=config.compression_bomb_layers)
        if ok:
            results["bomb"] = bomb_path
            _log(f"   ✅ 压缩炸弹: {format_size(info['output_size'])}")
        else:
            _log(f"   ❌ 创建失败: {info.get('error')}")

    if progress_callback:
        progress_callback(100)
    _log("\n" + "=" * 50)
    _log("✅ 处理完成！")
    _log("=" * 50)

    return results


def decrypt_file(encrypted_path: str,
                 key_file_path: str,
                 output_path: str = None,
                 log_callback=None,
                 progress_callback=None) -> bool:
    """
    解密单个文件

    Returns:
        ok: bool
    """
    def _log(msg):
        if log_callback:
            log_callback(msg)

    _log("🔓 解密文件...")
    if progress_callback:
        progress_callback(10)

    if not os.path.exists(encrypted_path):
        _log(f"❌ 加密文件不存在: {encrypted_path}")
        return False
    if not os.path.exists(key_file_path):
        _log(f"❌ 密钥文件不存在: {key_file_path}")
        return False

    if progress_callback:
        progress_callback(30)

    if output_path is None:
        output_path = encrypted_path.replace("_encrypted.bin", "_decrypted")
        if output_path == encrypted_path:
            output_path = encrypted_path + ".dec"

    key, salt = load_key_file(key_file_path)
    cipher_mode = load_cipher_mode_from_keyfile(key_file_path)

    if progress_callback:
        progress_callback(50)

    ok, info = AESCipher.decrypt_file(encrypted_path, output_path, key,
                                      cipher_mode=cipher_mode)
    if progress_callback:
        progress_callback(90)

    if ok:
        _log(f"✅ 解密完成: {output_path}")
        _log(f"   文件大小: {format_size(info['output_size'])}")
        if info.get("hash_match"):
            _log("   ✅ SHA256 完整性校验通过")
        elif "hash_match" in info:
            _log("   ⚠️ SHA256 校验不匹配！文件可能已损坏")
        if progress_callback:
            progress_callback(100)
        return True
    else:
        _log(f"❌ 解密失败: {info.get('error')}")
        return False
