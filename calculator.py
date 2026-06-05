"""
Calculator - MVC Architecture with Cryptography Features
No external dependencies. Mouse-only interaction.

MVC responsibilities:
  Model      – All state & business logic. Notifies observers on change.
  View       – Pure rendering. Reads from Model via observer callbacks.
               Never calls Model directly; never knows Controller exists.
  Controller – Wires Model ↔ View. Handles button clicks, delegates to
               Model, and manages side-effects (quit, shuffle trigger).

密码学功能:
  - 特殊数字组合触发密码学彩蛋（128=aes-128, 256=sha-256, 2048=rsa-2048等）
  - 密码学术语特殊组合（xor, key, enc, dec, sig, pki等）
  - 密码学操作模式（#caesar, #hash, #key, #xor, #rot, #b64等）
  - 内置加密算法演示（凯撒密码, ROT13, 简单哈希, XOR加密等）
  - 密钥和盐值生成

Examples:
  128 → "aes-128"       # AES密钥长度
  256 → "sha-256"        # SHA-256哈希
  2048 → "rsa-2048"      # RSA密钥长度
  xor → "⊕"              # 异或运算符
  #caesar → 进入凯撒密码模式
  #hash hello sha256 → 计算哈希
  #key 256 → 生成256位随机密钥
"""

import tkinter as tk
import random
import sys
import hashlib
from typing import Callable


# ─────────────────────────────────────────────────────────────
#  密码学工具函数
# ─────────────────────────────────────────────────────────────
class CryptoUtils:
    """简单的密码学演示工具"""

    @staticmethod
    def caesar_cipher(text: str, shift: int = 3) -> str:
        """凯撒密码加密"""
        result = []
        for char in text.lower():
            if char.isalpha():
                shifted = ord(char) - ord('a') + shift
                result.append(chr(shifted % 26 + ord('a')))
            else:
                result.append(char)
        return ''.join(result)

    @staticmethod
    def caesar_decipher(text: str, shift: int = 3) -> str:
        """凯撒密码解密"""
        result = []
        for char in text.lower():
            if char.isalpha():
                shifted = ord(char) - ord('a') - shift
                result.append(chr(shifted % 26 + ord('a')))
            else:
                result.append(char)
        return ''.join(result)

    @staticmethod
    def simple_hash(text: str, algorithm: str = "sha256") -> str:
        """简单哈希计算"""
        data = text.encode('utf-8')
        if algorithm == "md5":
            return hashlib.md5(data).hexdigest()[:16]
        elif algorithm == "sha1":
            return hashlib.sha1(data).hexdigest()[:20]
        elif algorithm == "sha256":
            return hashlib.sha256(data).hexdigest()[:32]
        elif algorithm == "sha512":
            return hashlib.sha512(data).hexdigest()[:64]
        return hashlib.sha256(data).hexdigest()[:32]

    @staticmethod
    def xor_encrypt(text: str, key: str) -> str:
        """简单的XOR加密"""
        key_bytes = key.encode()
        text_bytes = text.encode()
        result = []
        for i, byte in enumerate(text_bytes):
            result.append(chr(byte ^ key_bytes[i % len(key_bytes)]))
        return ''.join(result)

    @staticmethod
    def generate_key(bits: int = 128) -> str:
        """生成随机密钥（十六进制）"""
        num_bytes = bits // 8
        key = bytes(random.randint(0, 255) for _ in range(num_bytes))
        return key.hex()[:32]

    @staticmethod
    def generate_salt(length: int = 16) -> str:
        """生成盐值"""
        return bytes(random.randint(33, 126) for _ in range(length)).decode('latin-1')

    @staticmethod
    def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
        """带盐值哈希密码"""
        if salt is None:
            salt = CryptoUtils.generate_salt()
        salted = password + salt
        hash_val = hashlib.pbkdf2_hmac('sha256', salted.encode('utf-8'), salt.encode('utf-8'), 100000)
        return hash_val.hex()[:32], salt

    @staticmethod
    def check_password(password: str, hash_val: str, salt: str) -> bool:
        """验证密码"""
        new_hash, _ = CryptoUtils.hash_password(password, salt)
        return new_hash == hash_val

    @staticmethod
    def encode_fernet(text: str) -> str:
        """简单的Base64编码演示"""
        import base64
        return base64.b64encode(text.encode()).decode()[:32]

    @staticmethod
    def decode_fernet(encoded: str) -> str:
        """简单的Base64解码演示"""
        import base64
        padding = 4 - len(encoded) % 4
        if padding != 4:
            encoded += '=' * padding
        try:
            return base64.b64decode(encoded.encode()).decode()[:32]
        except Exception:
            return "invalid"

    @staticmethod
    def rot13(text: str) -> str:
        """ROT13加密（凯撒密码特例）"""
        return CryptoUtils.caesar_cipher(text, 13)

    @staticmethod
    def vigenere_encrypt(text: str, key: str) -> str:
        """维吉尼亚密码加密"""
        result = []
        key = key.lower()
        for i, char in enumerate(text.lower()):
            if char.isalpha():
                shift = ord(key[i % len(key)]) - ord('a')
                shifted = ord(char) - ord('a') + shift
                result.append(chr(shifted % 26 + ord('a')))
            else:
                result.append(char)
        return ''.join(result)


# ─────────────────────────────────────────────────────────────
#  Model
# ─────────────────────────────────────────────────────────────
class CalculatorModel:
    """Pure state + business logic. No GUI imports, no widget refs."""

    SPECIAL_COMBOS = {
        # ── classic ──
        "++--××÷÷()()": "cool",
        "110":  "warning",
        "119":  "warning",
        "120":  "warning",
        "911":  "fbi warning",
        "520":  "1314",
        "1314": "520",
        # ── AES加密 ──
        "128": "aes-128",    # AES-128位加密
        "192": "aes-192",    # AES-192位加密
        "256": "aes-256",    # AES-256位加密（量子安全）
        # ── 哈希函数 ──
        "128": "md5",        # MD5（已淘汰）
        "160": "sha-1",      # SHA-1（已逐步淘汰）
        "224": "sha-224",   # SHA-2家族
        "256": "sha-256",   # SHA-2最常用
        "384": "sha-384",   # SHA-2
        "512": "sha-512",   # SHA-2最高安全
        # ── RSA密钥 ──
        "1024": "rsa-1k",     # RSA-1024（已不安全）
        "2048": "rsa-2048",   # RSA-2048（需要多次）
        "3072": "rsa-3k",     # RSA-3072（需要多次）
        "4096": "rsa-4k",     # RSA-4096（需要多次）
        # ── ECC椭圆曲线 ──
        "224": "p-224",      # NIST P-224
        "256": "p-256",      # NIST P-256（secp256r1）
        "384": "p-384",      # NIST P-384
        "521": "p-521",      # NIST P-521
        # ── 密钥交换 ──
        "448": "x448",       # Curve448（需要多次）
        # ── 安全协议 ──
        "443": "https",      # HTTPS默认端口
        "22": "ssh",         # SSH远程登录
        "21": "ftp",         # FTP（明文传输，不安全）
        "443": "https",      # HTTPS默认端口
        "22": "ssh",         # SSH远程登录
        "21": "ftp",         # FTP（明文传输，不安全）
        # ── 加密模式 ──
        "ecb": "危险",        # ECB模式（泄露模式）
        "cbc": "安全",        # CBC模式（推荐）
        "gcm": "认证",        # GCM模式（AEAD）
        "ofb": "流式",        # OFB模式
        # ── 填充方案 ──
        "pkcs7": "padding",   # PKCS#7填充
        "zero": "zero",      # 零字节填充
        # ── 密钥派生 ──
        "1000": "pbkdf2",   # PBKDF2迭代次数
        "10": "bcrypt",     # bcrypt成本因子
        # ── 二进制 / 十六进制 ──
        "101": "matrix",      # 0b101 = 5
        "010": "binary",      # 前导零
        "16":  "hex",         # 十六进制基数
        "2":   "binary",      # 二进制基数
        "00":  "null",         # 空字节
        "ff":  "0xff",        # 最大字节
        "0x":  "hex",         # 十六进制前缀
        "0b":  "bin",         # 二进制前缀
        # ── 熵与随机 ──
        "256": "entropy",     # 256位熵
        "128": "nonce",       # 128位随机数
        "64":  "salt",         # 盐值
        # ── 数学常数 ──
        "314": "pi",           # π ≈ 3.14
        "271": "e",            # e ≈ 2.71
        "161": "golden",       # φ ≈ 1.61
        "618": "phi",          # φ × 1000
        # ── 安全术语 ──
        "xor": "⊕",            # 异或运算（加密基础）
        "rnd": "rand",         # 随机数
        "key": "🔐",           # 密钥
        "enc": "encrypt",      # 加密
        "dec": "decrypt",      # 解密
        "sig": "signature",    # 数字签名
        "pki": "pki",          # 公钥基础设施
        "ca":  "certificate",  # 证书颁发机构
        # ── fun ──
        "42":  "answer",       #  Hitchhiker's Guide
        "007": "bond",         #  James Bond（特工密码）
        "404": "not found",    #  HTTP错误
        "666": "beast",        #  野兽数字
        "777": "jackpot",      #  老虎机
        "000": "void",         #  空
    }

    MAX_DIGIT_PRESSES     = 4
    MAX_CHARS             = 13
    TRIPLE_SAME_RESET     = 3
    TRIPLE_BACKSPACE_QUIT = 3
    TRIPLE_EQUALS_SHUFFLE = 3

    def __init__(self):
        self._observers: list[Callable[[], None]] = []
        self._backspace_streak: int = 0
        self._equals_streak:    int = 0
        # public readable state (View reads these in observer callbacks)
        self.expression:       str  = ""
        self.display_text:     str  = "0"   # what the display should show
        self.last_eval_expr:   str  = ""    # expression before last evaluation
        self.char_limit:       bool = False
        self.digit_limit:      bool = False
        # last action type – View/Controller can inspect after notification
        self.last_action:      str  = "display"  # display|result|reset|quit|shuffle
        # 密码学模式状态
        self._crypto_mode:      str  = ""    # caesar|hash|key|xor|vigenere
        self._crypto_input:     str  = ""
        self._crypto_param:     str  = ""
        self._crypto_history:   list[str] = []
        self._reset_expr()

    # ── Observer API ─────────────────────────────────────────────
    def add_observer(self, cb: Callable[[], None]) -> None:
        self._observers.append(cb)

    def _notify(self) -> None:
        for cb in self._observers:
            cb()

    # ── Internal helpers ─────────────────────────────────────────
    def _reset_expr(self):
        self.expression        = ""
        self._last_token: str  = ""
        self._same_count: int  = 0
        self._digit_presses: int = 0
        self._update_limits()

    def _update_limits(self):
        self.char_limit  = len(self.expression) >= self.MAX_CHARS
        self.digit_limit = self._digit_presses >= self.MAX_DIGIT_PRESSES

    def _recalc_digit_presses(self):
        self._digit_presses = sum(
            1 for ch in self.expression if ch.isdigit() or ch == "."
        )
        self._update_limits()

    # ── Evaluation ───────────────────────────────────────────────
    def _evaluate(self) -> str:
        expr = self.expression.strip()
        if not expr:
            return "0"
        if expr in self.SPECIAL_COMBOS:
            return self.SPECIAL_COMBOS[expr]
        py_expr = expr.replace("×", "*").replace("÷", "/")
        try:
            allowed = set("0123456789+-*/.() ")
            if not all(c in allowed for c in py_expr):
                return "fool"
            result = eval(py_expr)   # noqa: S307 – sanitised
            if isinstance(result, float):
                if result != result:
                    return "fool"
                if result == int(result):
                    return str(int(result))
                return f"{result:.6f}".rstrip("0").rstrip(".")
            return str(result)
        except ZeroDivisionError:
            return "fool"
        except Exception:
            return "fool"

    # ── 密码学评估 ─────────────────────────────────────────────────────
    def _evaluate_crypto(self, token: str) -> str:
        """
        处理密码学相关输入并返回结果
        密码学模式前缀: #caesar #hash #key #xor #vig #rot #b64
        """
        crypto_prefixes = {
            "#caesar": ("caesar", "凯撒密码"),
            "#hash": ("hash", "哈希"),
            "#key": ("key", "密钥生成"),
            "#xor": ("xor", "异或加密"),
            "#vig": ("vigenere", "维吉尼亚"),
            "#rot": ("rot13", "ROT13"),
            "#b64": ("base64", "Base64"),
            "#salt": ("salt", "盐值生成"),
            "#pwd": ("password", "密码哈希"),
        }

        # 检查是否进入密码学模式
        if token.startswith("#"):
            for prefix, (mode, desc) in crypto_prefixes.items():
                if token.startswith(prefix):
                    self._crypto_mode = mode
                    self._crypto_input = ""
                    return f"🔐 {desc}模式"
            return "unknown crypto"

        # 在密码学模式中处理输入
        if self._crypto_mode:
            if token == "=":
                return self._finalize_crypto()
            elif token == "←":
                self._crypto_input = self._crypto_input[:-1]
                return self._crypto_input or "0"
            elif token == "C":
                self._crypto_mode = ""
                self._crypto_input = ""
                return "0"
            else:
                self._crypto_input += token
                return self._crypto_input

        return ""

    def _finalize_crypto(self) -> str:
        """完成密码学操作并返回结果"""
        text = self._crypto_input
        mode = self._crypto_mode
        result = ""

        if mode == "caesar":
            # 尝试解析位移
            parts = text.split()
            if len(parts) >= 2:
                try:
                    shift = int(parts[-1]) % 26
                    plaintext = " ".join(parts[:-1])
                    result = CryptoUtils.caesar_cipher(plaintext, shift)
                except ValueError:
                    result = CryptoUtils.caesar_cipher(text, 3)
            else:
                # 使用数字作为位移，字母作为文本
                shift = 3
                result = CryptoUtils.caesar_cipher(text, shift)

        elif mode == "rot13":
            result = CryptoUtils.rot13(text)

        elif mode == "hash":
            # 格式: text algorithm
            parts = text.split()
            if len(parts) >= 2:
                text_to_hash = parts[0]
                algo = parts[-1].lower()
            else:
                text_to_hash = text
                algo = "sha256"
            result = CryptoUtils.simple_hash(text_to_hash, algo)

        elif mode == "key":
            try:
                bits = int(text) if text else 256
                bits = min(max(bits, 64), 4096)
            except ValueError:
                bits = 256
            result = CryptoUtils.generate_key(bits)

        elif mode == "xor":
            parts = text.split(":")
            if len(parts) == 2:
                result = CryptoUtils.xor_encrypt(parts[0], parts[1])
            else:
                result = CryptoUtils.xor_encrypt(text, "secret")

        elif mode == "vigenere":
            parts = text.split()
            if len(parts) >= 2:
                result = CryptoUtils.vigenere_encrypt(parts[0], parts[-1])
            else:
                result = "需要: 文本 密钥"

        elif mode == "base64":
            try:
                result = CryptoUtils.encode_fernet(text)
            except Exception:
                result = "编码失败"

        elif mode == "salt":
            try:
                length = int(text) if text else 16
                length = min(max(length, 4), 64)
            except ValueError:
                length = 16
            result = CryptoUtils.generate_salt(length)

        elif mode == "password":
            parts = text.split()
            if len(parts) >= 1:
                pwd = parts[0]
                if len(parts) >= 2:
                    salt = parts[1]
                else:
                    salt = CryptoUtils.generate_salt(16)
                hash_val, _ = CryptoUtils.hash_password(pwd, salt)
                result = f"hash:{hash_val[:16]}... salt:{salt[:8]}"
            else:
                result = "需要: 密码 [盐值]"

        # 保存历史
        if result and len(result) < 100:
            self._crypto_history.append(f"{mode}: {text} → {result}")
            if len(self._crypto_history) > 5:
                self._crypto_history.pop(0)

        self._crypto_mode = ""
        self._crypto_input = ""
        return result

    # ── Main input entry point (called by Controller) ────────────
    def push(self, token: str) -> None:
        """
        Process one token. Updates public state fields, then notifies
        all observers. Controller inspects self.last_action afterward.
        """

        # ── 密码学模式 ─────────────────────────────────────────────
        # 处理密码学相关的输入（#前缀或已在密码学模式中）
        if token.startswith("#") or self._crypto_mode:
            crypto_result = self._evaluate_crypto(token)
            if self._crypto_mode or token.startswith("#"):
                # 在密码学模式中
                self.last_action  = "display"
                self.display_text = crypto_result
                self._notify()
                return
            else:
                # 退出密码学模式，尝试普通计算
                pass

        # ── ← backspace ──────────────────────────────────────────
        if token == "←":
            self._equals_streak = 0
            self._backspace_streak += 1
            if self._backspace_streak >= self.TRIPLE_BACKSPACE_QUIT:
                self.last_action  = "quit"
                self.display_text = ""
                self._notify()
                return
            if self.expression:
                self.expression = self.expression[:-1]
                self._recalc_digit_presses()
            self._last_token  = ""
            self._same_count  = 0
            self._update_limits()
            self.last_action  = "display"
            self.display_text = self.expression or "0"
            self._notify()
            return

        # ── = equals ─────────────────────────────────────────────
        if token == "=":
            self._backspace_streak = 0
            self._equals_streak += 1
            if self._equals_streak >= self.TRIPLE_EQUALS_SHUFFLE:
                self._equals_streak = 0
                self._reset_expr()
                self.last_action  = "shuffle"
                self.display_text = "0"
                self._notify()
                return
            self.last_eval_expr = self.expression
            value = self._evaluate()
            self._reset_expr()
            self.last_action  = "result"
            self.display_text = value or "0"
            self._notify()
            return

        # ── C 清空（密码学模式支持）────────────────────────────────
        if token == "C":
            self._crypto_mode = ""
            self._crypto_input = ""
            self._equals_streak = 0
            self._backspace_streak = 0
            self._reset_expr()
            self.last_action  = "reset"
            self.display_text = "0"
            self._notify()
            return

        # ── normal token ─────────────────────────────────────────
        self._backspace_streak = 0
        self._equals_streak    = 0

        # triple-same detection
        if token == self._last_token:
            self._same_count += 1
        else:
            self._same_count  = 1
            self._last_token  = token

        if self._same_count >= self.TRIPLE_SAME_RESET:
            self._reset_expr()
            self.last_action  = "reset"
            self.display_text = "0"
            self._notify()
            return

        # hard limits (silent ignore)
        if len(self.expression) >= self.MAX_CHARS:
            self.last_action  = "display"
            self.display_text = self.expression or "0"
            self._notify()
            return

        if token.isdigit() or token == ".":
            if self._digit_presses >= self.MAX_DIGIT_PRESSES:
                self.last_action  = "display"
                self.display_text = self.expression or "0"
                self._notify()
                return
            self._digit_presses += 1

        self.expression += token
        self._update_limits()
        self.last_action  = "display"
        self.display_text = self.expression
        self._notify()


# ─────────────────────────────────────────────────────────────
#  View
# ─────────────────────────────────────────────────────────────
EMPTY = "□"  # invisible placeholder – occupies grid space, has no function

BUTTON_TOKENS = [
    "(", ")", "←", "÷",
    "7", "8", "9", "×",
    "4", "5", "6", "-",
    "1", "2", "3", "+",
    "0", ".", "=", EMPTY,
]

ALWAYS_ACTIVE = {"←", "=", EMPTY}

COLORS = {
    "bg":          "#1e1e2e",
    "display_bg":  "#181825",
    "display_fg":  "#cdd6f4",
    "expr_fg":     "#6c7086",
    "sep_color":   "#313244",
    "btn_num":     "#313244",
    "btn_op":      "#45475a",
    "btn_eq":      "#89b4fa",
    "btn_back":    "#f38ba8",
    "btn_fg":      "#cdd6f4",
    "btn_eq_fg":   "#1e1e2e",
    "btn_dis":     "#2a2a3a",
    "btn_dis_fg":  "#555577",
    "btn_num_hv":  "#3b3b50",
    "btn_op_hv":   "#525368",
    "btn_eq_hv":   "#9cc5fb",
    "btn_back_hv": "#f5a0b4",
}


class CalculatorView(tk.Frame):
    """
    Pure rendering layer.
    - Does NOT reference Model or Controller.
    - Exposes bind_button() so Controller can attach commands.
    - Exposes on_model_change() as the observer callback.
    """

    GRID_COLS  = 4
    BTN_FONT   = ("Consolas", 16, "bold")
    DISP_FONTS = [
        ("Consolas", 30, "bold"),   # 0-6  chars
        ("Consolas", 24, "bold"),   # 7-9  chars
        ("Consolas", 18, "bold"),   # 10+  chars
    ]
    EXPR_FONT  = ("Consolas", 13)

    def __init__(self, master: tk.Tk):
        super().__init__(master, bg=COLORS["bg"])
        self._buttons: dict[str, tk.Button] = {}
        self._order    = BUTTON_TOKENS[:]
        self._disp_var = tk.StringVar(value="0")
        self._expr_var = tk.StringVar(value="")
        self._build_display()
        self._build_buttons()

    # ── Font scaling ─────────────────────────────────────────────
    def _scale_font(self, text: str):
        n = len(text)
        if n <= 6:
            return self.DISP_FONTS[0]
        if n <= 9:
            return self.DISP_FONTS[1]
        return self.DISP_FONTS[2]

    # ── Display ──────────────────────────────────────────────────
    def _build_display(self):
        # Display frame
        disp_frame = tk.Frame(self, bg=COLORS["display_bg"])
        disp_frame.grid(row=0, column=0, columnspan=self.GRID_COLS,
                        sticky="ew", padx=10, pady=10)

        # Expression line (small, muted)
        self._expr_label = tk.Label(
            disp_frame, textvariable=self._expr_var,
            bg=COLORS["display_bg"], fg=COLORS["expr_fg"],
            font=self.EXPR_FONT, anchor="e",
            padx=16, pady=0,
        )
        self._expr_label.pack(fill="x", pady=(12, 0))

        # Result line (large, bright)
        self._disp_label = tk.Label(
            disp_frame, textvariable=self._disp_var,
            bg=COLORS["display_bg"], fg=COLORS["display_fg"],
            font=self.DISP_FONTS[0], anchor="e",
            padx=16, pady=0,
        )
        self._disp_label.pack(fill="x", pady=(2, 14))

        # Separator between display and buttons
        sep = tk.Frame(self, bg=COLORS["sep_color"], height=1)
        sep.grid(row=1, column=0, columnspan=self.GRID_COLS,
                 sticky="ew", padx=10, pady=6)

        self.columnconfigure(list(range(self.GRID_COLS)), weight=1)

    def set_display(self, text: str) -> None:
        self._disp_var.set(text or "0")
        self._disp_label.config(font=self._scale_font(text or "0"))

    def set_expression(self, text: str) -> None:
        self._expr_var.set(text)

    # ── Button color helpers ─────────────────────────────────────
    @staticmethod
    def _is_empty(token: str) -> bool:
        return token == EMPTY

    def _normal_colors(self, token: str):
        if self._is_empty(token):
            return COLORS["bg"], COLORS["bg"]
        if token == "=":
            return COLORS["btn_eq"], COLORS["btn_eq_fg"]
        if token == "←":
            return COLORS["btn_back"], COLORS["btn_fg"]
        if token in ("+", "-", "×", "÷", "(", ")"):
            return COLORS["btn_op"], COLORS["btn_fg"]
        return COLORS["btn_num"], COLORS["btn_fg"]

    def _hover_colors(self, token: str):
        if self._is_empty(token):
            return COLORS["bg"], COLORS["bg"]
        if token == "=":
            return COLORS["btn_eq_hv"], COLORS["btn_eq_fg"]
        if token == "←":
            return COLORS["btn_back_hv"], COLORS["btn_fg"]
        if token in ("+", "-", "×", "÷", "(", ")"):
            return COLORS["btn_op_hv"], COLORS["btn_fg"]
        return COLORS["btn_num_hv"], COLORS["btn_fg"]

    # ── Hover handlers ───────────────────────────────────────────
    def _on_enter(self, btn: tk.Button, token: str) -> None:
        if self._is_empty(token):
            return
        if str(btn.cget("state")) != "disabled":
            hbg, _ = self._hover_colors(token)
            btn.config(bg=hbg)

    def _on_leave(self, btn: tk.Button, token: str) -> None:
        if self._is_empty(token):
            return
        if str(btn.cget("state")) != "disabled":
            nbg, _ = self._normal_colors(token)
            btn.config(bg=nbg)

    # ── Buttons ──────────────────────────────────────────────────
    def _build_buttons(self):
        for w in self._buttons.values():
            w.destroy()
        self._buttons.clear()
        for idx, token in enumerate(self._order):
            r, c = divmod(idx, self.GRID_COLS)
            bg, fg = self._normal_colors(token)
            is_empty = self._is_empty(token)
            btn = tk.Button(
                self,
                text="" if is_empty else token,
                bg=bg, fg=fg,
                activebackground=bg if is_empty else fg,
                activeforeground=fg if is_empty else bg,
                font=self.BTN_FONT,
                width=5, height=2,
                relief="flat",
                borderwidth=0,
                cursor="arrow" if is_empty else "hand2",
                takefocus=0,
                state="disabled" if is_empty else "normal",
            )
            btn.grid(row=r + 2, column=c, padx=4, pady=4, sticky="nsew")
            if not is_empty:
                btn.bind("<Enter>", lambda e, b=btn, t=token: self._on_enter(b, t))
                btn.bind("<Leave>", lambda e, b=btn, t=token: self._on_leave(b, t))
            self._buttons[token] = btn
        total_rows = 2 + (len(self._order) + self.GRID_COLS - 1) // self.GRID_COLS
        for r in range(2, total_rows + 1):
            self.rowconfigure(r, weight=1)

    def bind_button(self, token: str, command: Callable[[], None]) -> None:
        """Controller calls this to attach a command to each button."""
        self._buttons[token].config(command=command)

    # ── Shuffle ──────────────────────────────────────────────────
    def shuffle(self) -> None:
        random.shuffle(self._order)
        self._regrid()

    def _regrid(self) -> None:
        for btn in self._buttons.values():
            btn.grid_forget()
        for idx, token in enumerate(self._order):
            r, c = divmod(idx, self.GRID_COLS)
            self._buttons[token].grid(row=r + 2, column=c,
                                       padx=4, pady=4, sticky="nsew")

    # ── Button state (enabled / disabled) ────────────────────────
    def update_button_states(self, char_limit: bool, digit_limit: bool) -> None:
        for token, btn in self._buttons.items():
            if self._is_empty(token):
                continue
            if token in ALWAYS_ACTIVE:
                self._restore(btn, token)
                continue
            if char_limit or (digit_limit and (token.isdigit() or token == ".")):
                btn.config(
                    bg=COLORS["btn_dis"],
                    fg=COLORS["btn_dis_fg"],
                    state="disabled",
                    cursor="arrow",
                )
            else:
                self._restore(btn, token)

    def _restore(self, btn: tk.Button, token: str) -> None:
        bg, fg = self._normal_colors(token)
        btn.config(bg=bg, fg=fg, state="normal", cursor="hand2")

    # ── Observer callback (registered by Controller) ─────────────
    def on_model_change(self, model: "CalculatorModel") -> None:
        """
        Called by Controller when Model notifies a change.
        Reads Model's public state and re-renders.
        Does NOT trigger any further Model mutation.
        """
        self.set_display(model.display_text)

        # Expression line: show last evaluated expression after "="
        if model.last_action == "result":
            self.set_expression(model.last_eval_expr + " =")
        elif model.last_action in ("reset", "shuffle"):
            self.set_expression("")
        else:
            self.set_expression("")

        self.update_button_states(model.char_limit, model.digit_limit)


# ─────────────────────────────────────────────────────────────
#  Controller
# ─────────────────────────────────────────────────────────────
class CalculatorController:
    """
    Wires Model ↔ View.
    - Binds each View button to a Model.push() call.
    - Registers itself as Model observer; forwards updates to View.
    - Handles side-effects that require OS-level actions (quit, shuffle).
    """

    def __init__(self, model: CalculatorModel, view: CalculatorView,
                 root: tk.Tk):
        self._model = model
        self._view  = view
        self._root  = root

        # Register view updater as model observer
        model.add_observer(self._on_model_change)

        # Bind each button in the view to push the corresponding token
        for token in BUTTON_TOKENS:
            if token == EMPTY:
                continue
            view.bind_button(token, lambda t=token: self._handle(t))

    def _handle(self, token: str) -> None:
        self._model.push(token)
        # side-effects that can't live in Model or View
        action = self._model.last_action
        if action == "quit":
            self._root.destroy()
            sys.exit(0)
        elif action == "shuffle":
            self._view.shuffle()

    def _on_model_change(self) -> None:
        """Observer callback: Model changed → tell View to re-render."""
        self._view.on_model_change(self._model)


# ─────────────────────────────────────────────────────────────
#  Bootstrap
# ─────────────────────────────────────────────────────────────
def main():
    root = tk.Tk()
    root.title("Calculator")
    root.resizable(False, False)
    root.configure(bg=COLORS["bg"])

    model = CalculatorModel()
    view  = CalculatorView(root)
    view.pack(padx=10, pady=10, fill="both", expand=True)

    controller = CalculatorController(model, view, root)  # noqa: F841

    # Center window on screen
    root.update_idletasks()
    w = root.winfo_width()
    h = root.winfo_height()
    x = (root.winfo_screenwidth()  - w) // 2
    y = (root.winfo_screenheight() - h) // 2
    root.geometry(f"+{x}+{y}")

    # Initial shuffle on open
    view.shuffle()

    root.mainloop()


if __name__ == "__main__":
    main()
