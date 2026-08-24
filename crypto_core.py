# -*- coding: utf-8 -*-
"""
crypto_core.py — AES 加解密 + 密钥管理 + SHA256
无 UI 依赖，可独立 import 用于脚本/命令行
"""
import os
import json
import base64
import hashlib
import secrets

from .utils import format_size


# ==================== SHA256 ====================

def compute_sha256(filepath: str, chunk_size: int = 1024 * 1024) -> str:
    """计算文件 SHA256 哈希"""
    sha = hashlib.sha256()
    with open(filepath, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            sha.update(chunk)
    return sha.hexdigest()


def compute_sha256_bytes(data: bytes) -> str:
    """计算字节数据的 SHA256"""
    return hashlib.sha256(data).hexdigest()


# ==================== 密钥管理 ====================

def generate_key(password: str = None, salt: bytes = None, iterations: int = 100000):
    """
    生成 AES-256 密钥

    Returns:
        (key: bytes, salt: bytes)
    """
    if salt is None:
        salt = secrets.token_bytes(16)
    if password:
        key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations, 32)
    else:
        key = secrets.token_bytes(32)
    return key, salt


def save_key_file(key: bytes, salt: bytes, filepath: str, cipher: str = "AES-256-GCM") -> bool:
    """保存密钥到 JSON 文件"""
    data = {
        "version": "2.0",
        "cipher": cipher,
        "key": base64.b64encode(key).decode("ascii"),
        "salt": base64.b64encode(salt).decode("ascii"),
        "note": "KEEP THIS FILE SECRET — Required for decryption.",
    }
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)
    return True


def load_key_file(filepath: str):
    """
    从文件加载密钥

    Returns:
        (key: bytes, salt: bytes)
    """
    with open(filepath, "r") as f:
        data = json.load(f)
    key = base64.b64decode(data["key"])
    salt = base64.b64decode(data["salt"])
    return key, salt


def load_cipher_mode_from_keyfile(filepath: str) -> str:
    """从密钥文件中读取 cipher 模式"""
    try:
        with open(filepath, "r") as f:
            data = json.load(f)
        return data.get("cipher", "AES-256-GCM")
    except Exception:
        return "AES-256-GCM"


# ==================== AES 加密/解密 ====================

class AESCipher:
    """AES-256-GCM / AES-256-CBC 对称加密"""

    @staticmethod
    def check_dependency() -> bool:
        try:
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes  # noqa
            return True
        except ImportError:
            return False

    @staticmethod
    def _get_cipher_module():
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.backends import default_backend
        return Cipher, algorithms, modes, default_backend

    @staticmethod
    def encrypt_file(input_path: str, output_path: str, key: bytes,
                     cipher_mode: str = "AES-256-GCM",
                     chunk_size: int = 64 * 1024,
                     enable_integrity: bool = True):
        """
        加密文件 — 支持 GCM / CBC

        文件格式：
          [nonce 12B] [pad 4B] [sha256_hash 64B(可选)] [ciphertext] [tag 16B(GCM)]

        Returns:
            (ok: bool, info: dict)
        """
        Cipher, algorithms, modes, default_backend = AESCipher._get_cipher_module()
        nonce = secrets.token_bytes(12)

        try:
            file_hash = ""
            if enable_integrity:
                file_hash = compute_sha256(input_path)

            in_size = os.path.getsize(input_path)

            if cipher_mode == "AES-256-GCM":
                cipher = Cipher(algorithms.AES(key), modes.GCM(nonce), backend=default_backend())
            else:
                cipher = Cipher(algorithms.AES(key), modes.CBC(nonce), backend=default_backend())

            encryptor = cipher.encryptor()

            with open(input_path, "rb") as fin, open(output_path, "wb") as fout:
                fout.write(nonce)                    # 12B
                fout.write(b"\x00\x00\x00\x00")     # 4B 对齐

                if enable_integrity:
                    hash_padded = file_hash.ljust(64, " ")
                    fout.write(hash_padded.encode("ascii"))

                if cipher_mode == "AES-256-CBC":
                    data = fin.read()
                    pad_len = 16 - (len(data) % 16)
                    data += bytes([pad_len] * pad_len)
                    fout.write(encryptor.update(data) + encryptor.finalize())
                else:
                    while True:
                        chunk = fin.read(chunk_size)
                        if not chunk:
                            break
                        fout.write(encryptor.update(chunk))
                    encryptor.finalize()
                    fout.write(encryptor.tag)        # 16B tag

            out_size = os.path.getsize(output_path)
            return True, {
                "input_size": in_size,
                "output_size": out_size,
                "ratio": f"{out_size / max(1, in_size) * 100:.2f}%",
                "hash": file_hash,
                "nonce": nonce.hex()[:16],
            }
        except Exception as e:
            import traceback
            traceback.print_exc()
            return False, {"error": str(e)}

    @staticmethod
    def decrypt_file(input_path: str, output_path: str, key: bytes,
                     cipher_mode: str = "AES-256-GCM",
                     chunk_size: int = 64 * 1024,
                     enable_integrity: bool = True):
        """
        解密文件

        Returns:
            (ok: bool, info: dict)
        """
        Cipher, algorithms, modes, default_backend = AESCipher._get_cipher_module()

        try:
            with open(input_path, "rb") as fin:
                nonce_and_pad = fin.read(16)
                nonce = nonce_and_pad[:12]

                stored_hash = ""
                if enable_integrity:
                    hash_bytes = fin.read(64)
                    stored_hash = hash_bytes.decode("ascii").strip()

                rest = fin.read()
                if len(rest) < 16:
                    return False, {"error": "文件格式错误（太小）"}

                if cipher_mode == "AES-256-GCM":
                    tag = rest[-16:]
                    ciphertext = rest[:-16]
                else:
                    tag = None
                    ciphertext = rest

            if cipher_mode == "AES-256-GCM":
                cipher = Cipher(algorithms.AES(key), modes.GCM(nonce, tag),
                                backend=default_backend())
            else:
                cipher = Cipher(algorithms.AES(key), modes.CBC(nonce),
                                backend=default_backend())

            decryptor = cipher.decryptor()

            if cipher_mode == "AES-256-CBC":
                decrypted = decryptor.update(ciphertext) + decryptor.finalize()
                pad_len = decrypted[-1]
                decrypted = decrypted[:-pad_len]
                with open(output_path, "wb") as fout:
                    fout.write(decrypted)
            else:
                with open(output_path, "wb") as fout:
                    fout.write(decryptor.update(ciphertext))
                    decryptor.finalize()

            hash_ok = True
            if enable_integrity and stored_hash:
                actual_hash = compute_sha256(output_path)
                hash_ok = actual_hash == stored_hash

            out_size = os.path.getsize(output_path)
            return True, {
                "output_size": out_size,
                "hash_match": hash_ok,
                "stored_hash": stored_hash,
                "actual_hash": compute_sha256(output_path) if enable_integrity else "",
            }
        except Exception as e:
            import traceback
            traceback.print_exc()
            return False, {"error": str(e)}
